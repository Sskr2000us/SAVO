import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:shared_preferences/shared_preferences.dart';

import '../models/planning.dart';
import '../config/app_config.dart';
import '../services/metrics_service.dart';
import '../services/api_client.dart';
import '../services/scanning_service.dart';
import '../services/cuisine_preference_service.dart';
import '../services/entitlements_service.dart';
import '../widgets/pro_paywall_sheet.dart';
import 'cook_now_recipe_detail_screen.dart';

class RecipeOptionsScreen extends StatefulWidget {
  final List<Recipe> recipes;
  final bool showIngredientMatch;
  final String? titleOverride;
  final bool skipSuggestionSessionGate;

  const RecipeOptionsScreen({
    super.key,
    required this.recipes,
    this.showIngredientMatch = false,
    this.titleOverride,
    this.skipSuggestionSessionGate = false,
  });

  @override
  State<RecipeOptionsScreen> createState() => _RecipeOptionsScreenState();
}

class _RecipeOptionsScreenState extends State<RecipeOptionsScreen> {
  bool _timerStarted = false;
  final Map<String, Map<String, dynamic>> _matchByRecipeId = {};

  bool _recipeShownLogged = false;

  Map<String, int> _cuisineScores = const {};

  bool _suggestionsLocked = false;

  static const String _prefsAssumeStaplesKey = 'savo.assume_pantry_staples';
  bool _assumeStaplesGlobal = true;
  final Map<String, bool> _assumeStaplesOverrideByRecipeId = {};

  static const Set<String> _pantryStaples = {
    'salt',
    'pepper',
    'black pepper',
    'olive oil',
    'oil',
    'vegetable oil',
    'butter',
    'flour',
    'sugar',
    'garlic',
    'garlic powder',
    'onion',
    'onion powder',
    'vinegar',
    'soy sauce',
    'baking powder',
    'baking soda',
  };

  static String _normalizeIngredientName(String input) {
    return input
        .replaceAll('_', ' ')
        .replaceAll(RegExp(r'[^a-zA-Z0-9\s]'), ' ')
        .replaceAll(RegExp(r'\s+'), ' ')
        .trim()
        .toLowerCase();
  }

  static String _missingRowName(dynamic row) {
    if (row is Map) {
      return (row['name'] ?? row['ingredient'] ?? row['canonical_name'] ?? '').toString();
    }
    return row?.toString() ?? '';
  }

  bool _assumeStaplesForRecipe(String recipeId) {
    return _assumeStaplesOverrideByRecipeId[recipeId] ?? _assumeStaplesGlobal;
  }

  Future<void> _loadAssumeStaplesPref() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final v = prefs.getBool(_prefsAssumeStaplesKey);
      if (!mounted) return;
      setState(() {
        _assumeStaplesGlobal = v ?? true;
      });
    } catch (_) {
      // Best-effort.
    }
  }

  Future<void> _setAssumeStaplesPref(bool value) async {
    setState(() {
      _assumeStaplesGlobal = value;
    });
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_prefsAssumeStaplesKey, value);
    } catch (_) {
      // Best-effort.
    }

    _matchByRecipeId.clear();
    if (widget.showIngredientMatch) {
      final options = _sortedRecipesForDisplay(widget.recipes).take(5).toList();
      fireAndForget(_loadMatchCounts(options));
    }
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (widget.showIngredientMatch) {
      final options = _sortedRecipesForDisplay(widget.recipes).take(5).toList();
      fireAndForget(_loadMatchCounts(options));
    }
  }

  static String _normalizeCuisine(String input) {
    final s = input.trim().toLowerCase();
    if (s.isEmpty) return '';
    return s.replaceAll(RegExp(r'\s+'), ' ');
  }

  int _scoreForCuisine(String cuisine) {
    if (_cuisineScores.isEmpty) return 0;
    final k = _normalizeCuisine(cuisine);
    if (k.isEmpty) return 0;
    return _cuisineScores[k] ?? 0;
  }

  List<Recipe> _sortedRecipesForDisplay(List<Recipe> input) {
    if (input.length <= 1 || _cuisineScores.isEmpty) return input;

    final indexed = input.asMap().entries.toList();
    indexed.sort((a, b) {
      final sa = _scoreForCuisine(a.value.cuisine);
      final sb = _scoreForCuisine(b.value.cuisine);
      if (sa != sb) return sb.compareTo(sa);
      return a.key.compareTo(b.key);
    });

    return indexed.map((e) => e.value).toList();
  }

  Future<void> _loadCuisineScores() async {
    try {
      final scores = await CuisinePreferenceService.instance.getCombinedScores();
      if (!mounted) return;
      setState(() {
        _cuisineScores = scores;
      });

      // If the ranking changed, re-fetch match counts for the new top options.
      if (widget.showIngredientMatch) {
        _matchByRecipeId.clear();
        final options = _sortedRecipesForDisplay(widget.recipes).take(5).toList();
        fireAndForget(_loadMatchCounts(options));
      }
    } catch (_) {
      // Best-effort only.
    }
  }

  List<Map<String, dynamic>> _recipeIngredientsPayload(Recipe recipe) {
    return recipe.ingredientsUsed
        .where((i) => i.canonicalName.trim().isNotEmpty)
        .map(
          (i) => {
            'name': i.canonicalName.trim(),
            'quantity': i.amount,
            'unit': i.unit,
            'amount_display': i.amountDisplay,
            'notes': i.notes,
          },
        )
        .toList();
  }

  Future<void> _loadMatchCounts(List<Recipe> options) async {
    // Avoid refetching if already loaded.
    final missing = options.where((r) => !_matchByRecipeId.containsKey(r.recipeId)).toList();
    if (missing.isEmpty) return;

    final apiClient = Provider.of<ApiClient>(context, listen: false);
    final scanningService = ScanningService();

    for (final recipe in missing) {
      try {
        final total = recipe.ingredientsUsed.length;
        if (total == 0) {
          _matchByRecipeId[recipe.recipeId] = {
            'have': 0,
            'total': 0,
            'missing': 0,
            'assumed_staples': 0,
            'assumed_staples_names': const <String>[],
          };
          if (mounted) setState(() {});
          continue;
        }

        final res = await scanningService.checkSufficiency(
          recipeId: recipe.recipeId,
          servings: 4,
          apiClient: apiClient,
          recipeIngredients: _recipeIngredientsPayload(recipe),
          recipeServings: 4,
        );

        final rawMissing = res['missing'];
        final missingList = (rawMissing is List) ? rawMissing : const <dynamic>[];

        final assumeStaples = _assumeStaplesForRecipe(recipe.recipeId);

        final missingStapleNames = <String>[];
        for (final row in missingList) {
          final raw = _missingRowName(row);
          final norm = _normalizeIngredientName(raw);
          if (norm.isEmpty) continue;
          if (_pantryStaples.contains(norm)) {
            missingStapleNames.add(norm);
          }
        }

        final missingCount = missingList.length;
        final missingStaples = missingStapleNames.length;
        final missingNonStaples = (missingCount - missingStaples).clamp(0, missingCount);
        final assumedStaples = assumeStaples ? missingStaples : 0;
        final missingForCount = assumeStaples ? missingNonStaples : missingCount;
        final have = (total - missingForCount).clamp(0, total);

        final missingPreviewCandidates = <String>[];
        for (final row in missingList) {
          final raw = _missingRowName(row);
          final norm = _normalizeIngredientName(raw);
          if (norm.isEmpty) continue;
          if (assumeStaples && _pantryStaples.contains(norm)) continue;

          final display = _prettyName(raw).trim();
          if (display.isEmpty) continue;
          missingPreviewCandidates.add(display);
        }

        // Stabilize ordering: API ordering can vary; sort for consistency.
        final missingPreview = (missingPreviewCandidates.toSet().toList()..sort()).take(2).toList();

        _matchByRecipeId[recipe.recipeId] = {
          'have': have,
          'total': total,
          'missing': missingForCount,
          'assumed_staples': assumedStaples,
          'assumed_staples_names': (assumeStaples && missingStapleNames.isNotEmpty)
              ? (missingStapleNames.toSet().toList()..sort())
              : const <String>[],
          'missing_preview': missingPreview,
        };

        if (!mounted) return;
        setState(() {});
      } catch (_) {
        // Best-effort only.
      }
    }
  }

  String _prettyName(String raw) {
    final s = raw
        .replaceAll('_', ' ')
        .replaceAll(RegExp(r'\s+'), ' ')
        .trim();
    if (s.isEmpty) return raw;

    // If the title has a long ingredient list in parentheses, drop it.
    final m = RegExp(r'^(.*)\(([^)]*)\)\s*$').firstMatch(s);
    if (m != null) {
      final head = (m.group(1) ?? '').trim();
      final inside = (m.group(2) ?? '').trim();
      final looksLikeIngredientList = inside.contains(',') && (inside.contains('_') || inside.length > 24);
      if (head.isNotEmpty && looksLikeIngredientList) {
        return head;
      }
    }

    return s;
  }

  @override
  void initState() {
    super.initState();
    _timerStarted = true;
    fireAndForget(MetricsService.instance.startTimer('open_to_recipe_decision'));
    fireAndForget(MetricsService.instance.recordEvent('cook_now_opened'));
    fireAndForget(_loadAssumeStaplesPref());
    fireAndForget(_loadCuisineScores());

    // Free tier: limit daily suggestion sessions.
    if (!widget.skipSuggestionSessionGate) {
      () async {
        try {
          final gate = await EntitlementsService.instance.tryConsumeSuggestionSession();
          if (!mounted) return;
          if (!gate.allowed) {
            setState(() => _suggestionsLocked = true);
            return;
          }

          // Gate passed: this is the moment options are actually shown.
          _logRecipeShownOnce();
        } catch (_) {
          // Best-effort only.
        }
      }();
    } else {
      // No gate: options are shown immediately.
      _logRecipeShownOnce();
    }
  }

  void _logRecipeShownOnce() {
    if (_recipeShownLogged) return;
    _recipeShownLogged = true;

    fireAndForget(MetricsService.instance.recordEvent('recipe_shown'));
    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      fireAndForget(() async {
        try {
          await apiClient.post('/analytics/events', {
            'events': [
              {
                'name': 'recipe_shown',
                'ts': DateTime.now().toIso8601String(),
                'props': {
                  'count': widget.recipes.length,
                  'screen': 'RecipeOptionsScreen',
                },
              }
            ],
          });
        } catch (_) {
          // ignore
        }
      }());
    } catch (_) {
      // ignore
    }
  }

  @override
  void dispose() {
    if (_timerStarted) {
      fireAndForget(MetricsService.instance.endTimer('open_to_recipe_decision'));
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;

    if (_suggestionsLocked) {
      return Scaffold(
        appBar: AppBar(
          title: Text(widget.titleOverride ?? 'Recipe options'),
        ),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  'You\'ve used today\'s free recipe suggestions.',
                  style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                Text(
                  'Upgrade to Pro for unlimited daily suggestions plus weekly planning and shopping lists.',
                  style: theme.textTheme.bodyMedium?.copyWith(color: cs.onSurfaceVariant),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: () async {
                    final upgraded = await showProPaywallSheet(
                      context,
                      title: 'Upgrade to SAVO Pro',
                      ctaLabel: 'Upgrade for unlimited suggestions',
                      reason: 'Free tier includes scanning + a limited number of daily suggestion sessions. Pro unlocks unlimited suggestions and planning.',
                      trigger: 'suggestions_limit',
                    );
                    if (upgraded && mounted) {
                      setState(() => _suggestionsLocked = false);
                    }
                  },
                  child: const Text('Upgrade to Pro'),
                ),
                const SizedBox(height: 8),
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Back'),
                ),
              ],
            ),
          ),
        ),
      );
    }

    final ranked = _sortedRecipesForDisplay(widget.recipes);
    final options = ranked.take(5).toList();
    final showStaplesUi = widget.showIngredientMatch;

    String? bestMatchRecipeId;
    if (showStaplesUi) {
      var bestScore = -1.0;
      for (final r in options) {
        final m = _matchByRecipeId[r.recipeId];
        if (m == null) continue;
        final have = (m['have'] as int?) ?? 0;
        final total = (m['total'] as int?) ?? 0;
        if (total <= 0) continue;
        final score = have / total;
        if (score > bestScore) {
          bestScore = score;
          bestMatchRecipeId = r.recipeId;
        }
      }
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.titleOverride ?? 'Recipe options'),
      ),
      body: options.isEmpty
          ? Center(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Text(
                  'No recipe options right now. Try again after updating your pantry.',
                  style: theme.textTheme.bodyMedium,
                  textAlign: TextAlign.center,
                ),
              ),
            )
          : ListView.separated(
              padding: const EdgeInsets.all(16),
              itemCount: options.length + (showStaplesUi ? 1 : 0),
              separatorBuilder: (_, __) => const SizedBox(height: 12),
              itemBuilder: (context, index) {
                if (showStaplesUi && index == 0) {
                  return Card(
                    child: SwitchListTile(
                      title: const Text('Assume pantry staples'),
                      subtitle: const Text('Counts common staples (salt, oil, etc.) as available.'),
                      value: _assumeStaplesGlobal,
                      onChanged: (v) => fireAndForget(_setAssumeStaplesPref(v)),
                    ),
                  );
                }

                final recipeIndex = showStaplesUi ? index - 1 : index;
                final recipe = options[recipeIndex];
                final title = _prettyName(recipe.getLocalizedName('en'));
                final why = _whyItWorks(recipe);
                final imageUrl = _imageUrl(recipe);
                final refs = recipe.youtubeReferences;
                final hasVideo = refs.isNotEmpty;

                return Card(
                  clipBehavior: Clip.antiAlias,
                  child: InkWell(
                    onTap: () {
                      if (_timerStarted) {
                        _timerStarted = false;
                        fireAndForget(MetricsService.instance.endTimer('open_to_recipe_decision'));
                      }
                      fireAndForget(MetricsService.instance.recordEvent('recipe_decision_made'));
                      Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => CookNowRecipeDetailScreen(
                            recipe: recipe,
                            assumeStaples: _assumeStaplesForRecipe(recipe.recipeId),
                          ),
                        ),
                      );
                    },
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        SizedBox(
                          height: 150,
                          child: Stack(
                            fit: StackFit.expand,
                            children: [
                              if (imageUrl != null)
                                Image.network(
                                  imageUrl,
                                  fit: BoxFit.cover,
                                  errorBuilder: (_, __, ___) => Container(
                                    color: cs.surfaceContainerHighest,
                                    child: Icon(Icons.restaurant, color: cs.onSurfaceVariant, size: 40),
                                  ),
                                )
                              else
                                Container(
                                  color: cs.surfaceContainerHighest,
                                  child: Icon(Icons.restaurant, color: cs.onSurfaceVariant, size: 40),
                                ),
                              if (hasVideo)
                                Positioned(
                                  top: 8,
                                  left: 8,
                                  child: Material(
                                    color: cs.surfaceContainerHighest.withAlpha(230),
                                    shape: const CircleBorder(),
                                    child: IconButton(
                                      tooltip: 'Watch video'
                                          '${refs.first.title.trim().isNotEmpty ? ": ${refs.first.title.trim()}" : ""}',
                                      onPressed: () async {
                                        final vid = refs.first.videoId.trim();
                                        if (vid.isEmpty) return;
                                        final uri = Uri.parse('https://www.youtube.com/watch?v=$vid');
                                        if (await canLaunchUrl(uri)) {
                                          await launchUrl(uri, mode: LaunchMode.externalApplication);
                                        }
                                      },
                                      icon: Icon(Icons.play_circle_fill, color: cs.onSurfaceVariant),
                                    ),
                                  ),
                                ),
                              Container(
                                decoration: BoxDecoration(
                                  gradient: LinearGradient(
                                    begin: Alignment.topCenter,
                                    end: Alignment.bottomCenter,
                                    colors: [
                                      cs.onSurface.withAlpha(13),
                                      cs.onSurface.withAlpha(140),
                                    ],
                                  ),
                                ),
                              ),
                              Positioned(
                                left: 12,
                                right: 12,
                                bottom: 12,
                                child: Text(
                                  title,
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                  style: theme.textTheme.titleMedium?.copyWith(
                                    color: cs.surface,
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                              ),
                              if (showStaplesUi && bestMatchRecipeId != null && recipe.recipeId == bestMatchRecipeId)
                                Positioned(
                                  top: 10,
                                  right: 10,
                                  child: Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                                    decoration: BoxDecoration(
                                      color: cs.surfaceContainerHighest.withAlpha(230),
                                      borderRadius: BorderRadius.circular(999),
                                    ),
                                    child: Text(
                                      'Best match',
                                      style: theme.textTheme.labelSmall?.copyWith(
                                        color: cs.onSurfaceVariant,
                                        fontWeight: FontWeight.w800,
                                      ),
                                    ),
                                  ),
                                ),
                            ],
                          ),
                        ),
                        Padding(
                          padding: const EdgeInsets.all(12),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                why,
                                style: theme.textTheme.bodyMedium,
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                              ),
                              const SizedBox(height: 10),
                              Wrap(
                                spacing: 8,
                                runSpacing: 8,
                                children: [
                                  _Badge(icon: Icons.signal_cellular_alt, label: recipe.difficulty),
                                  _Badge(icon: Icons.timer, label: '${recipe.estimatedTimes.totalMinutes} min'),
                                ],
                              ),
                              if (widget.showIngredientMatch) ...[
                                const SizedBox(height: 10),
                                Align(
                                  alignment: Alignment.centerLeft,
                                  child: FilterChip(
                                    label: const Text('Assume staples'),
                                    selected: _assumeStaplesForRecipe(recipe.recipeId),
                                    onSelected: (v) {
                                      setState(() {
                                        _assumeStaplesOverrideByRecipeId[recipe.recipeId] = v;
                                        _matchByRecipeId.remove(recipe.recipeId);
                                      });
                                      fireAndForget(_loadMatchCounts([recipe]));
                                    },
                                  ),
                                ),
                                const SizedBox(height: 8),
                                Builder(
                                  builder: (_) {
                                    final m = _matchByRecipeId[recipe.recipeId];
                                    if (m == null) {
                                      return Text(
                                        'Checking ingredient match…',
                                        style: theme.textTheme.bodySmall?.copyWith(
                                          color: cs.onSurfaceVariant,
                                        ),
                                      );
                                    }

                                    final have = (m['have'] as int?) ?? 0;
                                    final total = (m['total'] as int?) ?? 0;
                                    final missing = (m['missing'] as int?) ?? 0;
                                    final assumed = (m['assumed_staples'] as int?) ?? 0;
                                    final assumedNames = (m['assumed_staples_names'] as List?)
                                            ?.map((x) => x.toString())
                                            .toList() ??
                                        const <String>[];
                                    final missingPreview = (m['missing_preview'] as List?)
                                        ?.map((x) => x.toString())
                                        .toList() ??
                                      const <String>[];

                                    String matchLabel() {
                                      if (total <= 0) return '';
                                      final ratio = have / total;
                                      if (ratio >= 0.8) return 'Great match';
                                      if (ratio >= 0.6) return 'Good match';
                                      return 'Needs a few items';
                                    }

                                    final label = matchLabel();
                                    final matchText = 'You have $have/$total ingredients';
                                    final assumedSuffix = assumed > 0 ? ' • Assumes $assumed staples' : '';

                                    final headline = missing > 0
                                        ? '$matchText$assumedSuffix • Missing $missing'
                                        : '$matchText$assumedSuffix';

                                    final headlineStyle = theme.textTheme.bodySmall?.copyWith(
                                      color: missing > 0 ? cs.error : cs.tertiary,
                                      fontWeight: FontWeight.w700,
                                    );

                                    final assumedLabel = assumedNames.isNotEmpty
                                        ? 'Assumed staples: ${assumedNames.take(3).join(', ')}'
                                            '${assumedNames.length > 3 ? '…' : ''}'
                                        : null;

                                    final isLowMatch = total > 0 && (have / total) < 0.6;
                                    final showMissingPreview = missing > 0 && isLowMatch && missingPreview.isNotEmpty;
                                    final missingLabel = showMissingPreview
                                        ? 'Missing: ${missingPreview.take(3).join(', ')}'
                                            '${missingPreview.length > 3 ? '…' : ''}'
                                        : null;

                                    return Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        if (label.isNotEmpty) ...[
                                          Text(
                                            label,
                                            style: theme.textTheme.labelMedium?.copyWith(
                                              color: missing > 0 ? cs.onSurfaceVariant : cs.tertiary,
                                              fontWeight: FontWeight.w800,
                                            ),
                                          ),
                                          const SizedBox(height: 2),
                                        ],
                                        Text(headline, style: headlineStyle),
                                        if (missingLabel != null) ...[
                                          const SizedBox(height: 4),
                                          Text(
                                            missingLabel,
                                            style: theme.textTheme.bodySmall?.copyWith(
                                              color: cs.onSurfaceVariant,
                                            ),
                                          ),
                                        ],
                                        if (assumedLabel != null) ...[
                                          const SizedBox(height: 4),
                                          Text(
                                            assumedLabel,
                                            style: theme.textTheme.bodySmall?.copyWith(
                                              color: cs.onSurfaceVariant,
                                            ),
                                          ),
                                        ],
                                      ],
                                    );
                                  },
                                ),
                              ],
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
    );
  }

  String _whyItWorks(Recipe recipe) {
    final ingredients = recipe.ingredientsUsed
        .map((i) => i.canonicalName.replaceAll('_', ' ').trim())
        .where((s) => s.isNotEmpty)
        .toList();

    if (ingredients.isEmpty) {
      return 'Based on what\'s in your pantry';
    }

    final top = ingredients.take(3).toList();
    final suffix = ingredients.length > 3 ? '…' : '';
    return 'Uses: ${top.join(', ')}$suffix';
  }

  String? _imageUrl(Recipe recipe) {
    final raw = (recipe.imageUrl ?? '').trim();
    if (raw.isNotEmpty) {
      if (raw.startsWith('/')) return '${Config.apiBaseUrl}$raw';
      return raw;
    }

    if (kIsWeb) {
      final name = recipe.getLocalizedName('en').trim();
      if (name.isEmpty) return null;
      final cuisine = recipe.cuisine.trim().isEmpty ? 'general' : recipe.cuisine.trim();
      final url =
          '/recipes/image/proxy?recipe_name=${Uri.encodeComponent(name)}&cuisine=${Uri.encodeComponent(cuisine)}';
      return '${Config.apiBaseUrl}$url';
    }

    final name = recipe.getLocalizedName('en').trim();
    if (name.isEmpty) return null;
    final encoded = Uri.encodeComponent(name);
    return 'https://source.unsplash.com/featured/?food,$encoded';
  }
}

class _Badge extends StatelessWidget {
  final IconData icon;
  final String label;

  const _Badge({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: cs.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: cs.onSurfaceVariant),
          const SizedBox(width: 6),
          Text(label, style: theme.textTheme.labelMedium),
        ],
      ),
    );
  }
}
