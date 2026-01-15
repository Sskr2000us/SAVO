import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/planning.dart';
import '../models/profile_state.dart';
import '../services/api_client.dart';
import '../services/cuisine_preference_service.dart';
import '../services/metrics_service.dart';
import '../services/scanning_service.dart';
import '../services/saved_recipes_local_service.dart';
import '../services/entitlements_service.dart';
import '../services/upsell_service.dart';
import '../services/weekly_cook_streak_service.dart';
import '../widgets/pro_paywall_sheet.dart';
import '../widgets/savo_network_image.dart';
import '../config/app_config.dart';
import 'cook_mode_screen.dart';
import 'party_setup_screen.dart';
import 'planning_results_screen.dart';

class CookNowRecipeDetailScreen extends StatefulWidget {
  final Recipe recipe;
  final bool? assumeStaples;

  const CookNowRecipeDetailScreen({super.key, required this.recipe, this.assumeStaples});

  @override
  State<CookNowRecipeDetailScreen> createState() => _CookNowRecipeDetailScreenState();
}

class _CookNowRecipeDetailScreenState extends State<CookNowRecipeDetailScreen> {
  static const String _prefsAssumeStaplesKey = 'savo.assume_pantry_staples';
  static const String _prefsSpiceLevelKey = 'savo.recipe.spice_level';

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

  String? _bestEffortRecipeImageUrl(BuildContext context) {
    final raw = (widget.recipe.imageUrl ?? '').trim();
    if (raw.isNotEmpty) {
      if (raw.startsWith('/')) return '${Config.apiBaseUrl}$raw';
      return raw;
    }

    if (kIsWeb) {
      final name = widget.recipe.getLocalizedName(_preferredLanguageKey(context)).trim();
      if (name.isEmpty) return null;
      final cuisine = widget.recipe.cuisine.trim().isEmpty ? 'general' : widget.recipe.cuisine.trim();
      final url =
          '/recipes/image/proxy?recipe_name=${Uri.encodeComponent(name)}&cuisine=${Uri.encodeComponent(cuisine)}';
      return '${Config.apiBaseUrl}$url';
    }

    final name = widget.recipe.getLocalizedName(_preferredLanguageKey(context)).trim();
    if (name.isEmpty) return null;
    final encoded = Uri.encodeComponent(name);
    return 'https://source.unsplash.com/featured/?food,$encoded';
  }

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

  bool _checking = true;
  Map<String, dynamic>? _sufficiency;
  bool _assumeStaples = true;

  String _spiceLevel = 'medium';

  bool _checkingSaved = true;
  bool _savingToggle = false;
  bool _isSaved = false;

  bool _markingCooked = false;
  bool _addingToPlan = false;

  String _todayIsoDate() {
    final now = DateTime.now();
    final y = now.year.toString().padLeft(4, '0');
    final m = now.month.toString().padLeft(2, '0');
    final d = now.day.toString().padLeft(2, '0');
    return '$y-$m-$d';
  }

  Future<void> _addToDailyPlan() async {
    if (_addingToPlan) return;
    setState(() => _addingToPlan = true);

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final recipe = widget.recipe;

      final body = <String, dynamic>{
        'time_available_minutes': (recipe.estimatedTimes.totalMinutes > 0) ? recipe.estimatedTimes.totalMinutes : 60,
        'servings': 4,
        'current_date': _todayIsoDate(),
        'meal_type': 'dinner',
        'seed_recipe': recipe.toJson(),
      };

      final res = await apiClient.post('/plan/daily', body);
      final plan = MenuPlanResponse.fromJson(res);

      if (!mounted) return;
      await Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => PlanningResultsScreen(
            menuPlan: plan,
            planType: 'daily',
          ),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to add to plan: $e')),
      );
    } finally {
      if (mounted) setState(() => _addingToPlan = false);
    }
  }

  Future<void> _addToWeeklyPlan() async {
    if (_addingToPlan) return;
    setState(() => _addingToPlan = true);

    try {
      final isPro = await EntitlementsService.instance.isPro();
      if (!isPro && mounted) {
        await showProPaywallSheet(
          context,
          title: 'Upgrade to SAVO Pro',
          ctaLabel: 'Upgrade to weekly planning',
          reason: 'Weekly planning is a Pro feature.',
          trigger: 'weekly_planning_gate',
        );
        return;
      }

      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final recipe = widget.recipe;

      final body = <String, dynamic>{
        'start_date': _todayIsoDate(),
        'num_days': 3,
        'servings': 4,
        'time_available_minutes': 60,
        'seed_recipe': recipe.toJson(),
      };

      final res = await apiClient.post('/plan/weekly', body);
      final plan = MenuPlanResponse.fromJson(res);

      if (!mounted) return;
      await Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => PlanningResultsScreen(
            menuPlan: plan,
            planType: 'weekly',
          ),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to add to weekly plan: $e')),
      );
    } finally {
      if (mounted) setState(() => _addingToPlan = false);
    }
  }

  Future<void> _addToPartyPlan() async {
    if (_addingToPlan) return;

    // Party planning requires guest inputs; route to setup and carry the seed recipe.
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => PartySetupScreen(
          mode: PartyPlanningMode.dinnerParty,
          seedRecipe: widget.recipe,
        ),
      ),
    );
  }

  Future<void> _showAddToPlanChooser() async {
    if (_addingToPlan) return;

    final selection = await showModalBottomSheet<String>(
      context: context,
      showDragHandle: true,
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              title: const Text('Daily plan'),
              onTap: () => Navigator.pop(ctx, 'daily'),
            ),
            ListTile(
              title: const Text('Weekly plan'),
              onTap: () => Navigator.pop(ctx, 'weekly'),
            ),
            ListTile(
              title: const Text('Party plan'),
              onTap: () => Navigator.pop(ctx, 'party'),
            ),
          ],
        ),
      ),
    );

    if (!mounted) return;
    if (selection == 'daily') return _addToDailyPlan();
    if (selection == 'weekly') return _addToWeeklyPlan();
    if (selection == 'party') return _addToPartyPlan();
  }

  final WeeklyCookStreakService _weeklyCookStreakService = WeeklyCookStreakService();

  Future<void> _markCooked() async {
    if (_markingCooked) return;
    setState(() => _markingCooked = true);

    try {
      fireAndForget(MetricsService.instance.recordEvent('recipe_marked_cooked'));
      fireAndForget(MetricsService.instance.recordEvent('recipe_cooked'));
      fireAndForget(_weeklyCookStreakService.markCooked());
      fireAndForget(MetricsService.instance.endTimer('ttfv'));

      // Activation funnel reporting (best-effort; ignore failures).
      try {
        final apiClient = Provider.of<ApiClient>(context, listen: false);
        fireAndForget(() async {
          try {
            await apiClient.post('/analytics/events', {
              'events': [
                {
                  'name': 'recipe_cooked',
                  'ts': DateTime.now().toIso8601String(),
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

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Marked as cooked')),
      );
    } finally {
      if (mounted) setState(() => _markingCooked = false);
    }
  }

  String _stripIngredientDumpSuffix(String input) {
    var s = (input).trim();
    if (s.isEmpty) return input;

    // Strip suffix patterns like:
    //   "Pantry Comfort Meal (Barilla..., Kroger..., ...)"
    final m = RegExp(r'^(.*)\(([^()]*)\)\s*$').firstMatch(s);
    if (m == null) return input;

    final base = (m.group(1) ?? '').trim();
    final inside = (m.group(2) ?? '').trim();
    if (base.isEmpty || inside.isEmpty) return input;

    final insideLower = inside.toLowerCase();
    final hasDigits = RegExp(r'\d').hasMatch(inside);
    final looksLikeMetadata = RegExp(
      r'\b(min|mins|minute|minutes|serves|serving|servings|prep|cook|kcal|calories)\b',
      caseSensitive: false,
    ).hasMatch(insideLower);

    final parts = inside.split(',').map((p) => p.trim()).where((p) => p.isNotEmpty).toList();
    final looksLikeList = inside.contains('_') || parts.length >= 2;

    if (looksLikeList && !hasDigits && !looksLikeMetadata) {
      return base;
    }

    return input;
  }

  String _prettyName(String raw) {
    final s = raw
        .replaceAll('_', ' ')
        .replaceAll(RegExp(r'\s+'), ' ')
        .trim();
    if (s.isEmpty) return raw;
    return s
        .split(' ')
        .map((w) => w.isEmpty ? w : '${w[0].toUpperCase()}${w.substring(1)}')
        .join(' ');
  }

  String _formatAmount(double amount) {
    if (amount == 0) return '';
    if (amount % 1 == 0) return amount.toInt().toString();
    return amount.toStringAsFixed(1);
  }

  String _formatIngredientSuffix({
    required String amountText,
    required String unit,
    required String notes,
  }) {
    final hasQty = amountText.trim().isNotEmpty;
    final hasUnit = unit.trim().isNotEmpty;
    final hasNotes = notes.trim().isNotEmpty;

    final qtyPart = hasQty ? amountText.trim() : '';
    final unitPart = hasUnit ? unit.trim() : '';
    final qtyUnit = [qtyPart, unitPart].where((s) => s.isNotEmpty).join(' ');

    final suffixParts = <String>[];
    if (qtyUnit.isNotEmpty) suffixParts.add(qtyUnit);
    if (hasNotes) suffixParts.add('(${notes.trim()})');

    if (suffixParts.isEmpty) return '';
    return ' — ${suffixParts.join(' ')}';
  }

  String? _secondaryLanguageKey(
    Map<String, String> localized, {
    String? exclude,
  }) {
    final ex = exclude?.trim().toLowerCase();
    for (final e in localized.entries) {
      final key = e.key.trim().toLowerCase();
      final value = e.value.trim();
      if (key.isEmpty) continue;
      if (key == 'en') continue;
      if (ex != null && ex.isNotEmpty && key == ex) continue;
      if (value.isNotEmpty) return key;
    }
    return null;
  }

  String _preferredLanguageKey(BuildContext context) {
    try {
      final profileState = Provider.of<ProfileState>(context, listen: false);
      final raw = (profileState.preferredLanguage?.trim().isNotEmpty == true)
          ? profileState.preferredLanguage!.trim()
          : (profileState.primaryLanguage?.trim().isNotEmpty == true)
              ? profileState.primaryLanguage!.trim()
              : Localizations.localeOf(context).languageCode;

      final lowered = raw.trim().toLowerCase();
      if (lowered.isEmpty) return 'en';
      return lowered.split(RegExp('[-_]')).first;
    } catch (_) {
      return 'en';
    }
  }

  @override
  void initState() {
    super.initState();
    // Core loop tracking: recipe opened.
    fireAndForget(MetricsService.instance.recordEvent('recipe_opened'));
    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      fireAndForget(() async {
        try {
          await apiClient.post('/analytics/events', {
            'events': [
              {
                'name': 'recipe_opened',
                'ts': DateTime.now().toIso8601String(),
                'props': {
                  'recipe_id': widget.recipe.recipeId,
                  'screen': 'CookNowRecipeDetailScreen',
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

    if (widget.assumeStaples != null) {
      _assumeStaples = widget.assumeStaples!;
    } else {
      _loadAssumeStaplesPref();
    }

    fireAndForget(_loadSpicePref());
    _loadSavedStatus();
    _check();
  }

  Future<void> _loadSpicePref() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final v = (prefs.getString(_prefsSpiceLevelKey) ?? '').trim().toLowerCase();
      if (!mounted) return;
      setState(() {
        _spiceLevel = v.isNotEmpty ? v : 'medium';
      });
    } catch (_) {
      // Best-effort.
    }
  }

  Future<void> _setSpicePref(String value) async {
    final next = value.trim().toLowerCase();
    if (next.isEmpty) return;
    setState(() {
      _spiceLevel = next;
    });
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_prefsSpiceLevelKey, next);
    } catch (_) {
      // Best-effort.
    }
  }

  Future<void> _loadSavedStatus() async {
    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final rid = widget.recipe.recipeId.trim();
      if (rid.isEmpty) return;

      final response = await apiClient.get(
        '/recipes/saved/exists?recipe_id=${Uri.encodeComponent(rid)}',
      );

      if (!mounted) return;
      if (response is Map && response['saved'] == true) {
        setState(() => _isSaved = true);
      }
    } catch (_) {
      // Best-effort only.
    } finally {
      if (mounted) setState(() => _checkingSaved = false);
    }
  }

  Future<void> _toggleSaved() async {
    if (_savingToggle) return;
    final rid = widget.recipe.recipeId.trim();
    if (rid.isEmpty) return;

    setState(() => _savingToggle = true);
    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);

      if (_isSaved) {
        await apiClient.delete('/recipes/saved/${Uri.encodeComponent(rid)}');
        await SavedRecipesLocalService.instance.removeSavedRecipeById(rid);
      } else {
        await apiClient.post('/recipes/saved', {
          'recipe': widget.recipe.toJson(),
        });
        // Preference signal: user saved this cuisine.
        await CuisinePreferenceService.instance.recordSavedCuisine(widget.recipe.cuisine);
        await SavedRecipesLocalService.instance.upsertSavedRecipe(widget.recipe);
      }


        // Core loop tracking: recipe saved.
        fireAndForget(MetricsService.instance.recordEvent('recipe_saved'));
        fireAndForget(() async {
          try {
            await apiClient.post('/analytics/events', {
              'events': [
                {
                  'name': 'recipe_saved',
                  'ts': DateTime.now().toIso8601String(),
                  'props': {
                    'recipe_id': rid,
                    'screen': 'CookNowRecipeDetailScreen',
                  },
                }
              ],
            });
          } catch (_) {
            // ignore
          }
        }());
      if (!mounted) return;
      final next = !_isSaved;
      setState(() => _isSaved = next);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(next ? 'Recipe saved.' : 'Recipe removed.')),
      );

      if (next) {
        await UpsellService.instance.recordRecipeSavedAndMaybeShow(context);
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Could not update saved recipe: $e')),
      );
    } finally {
      if (mounted) setState(() => _savingToggle = false);
    }
  }

  Future<void> _loadAssumeStaplesPref() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final v = prefs.getBool(_prefsAssumeStaplesKey);
      if (!mounted) return;
      setState(() {
        _assumeStaples = v ?? true;
      });
    } catch (_) {
      // Best-effort.
    }
  }

  Future<void> _setAssumeStaplesPref(bool value) async {
    setState(() {
      _assumeStaples = value;
    });
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_prefsAssumeStaplesKey, value);
    } catch (_) {
      // Best-effort.
    }
  }

  List<Map<String, dynamic>> _recipeIngredientsPayload() {
    return widget.recipe.ingredientsUsed
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

  Future<void> _check() async {
    setState(() {
      _checking = true;
      _sufficiency = null;
    });

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final scanningService = ScanningService();

      final result = await scanningService.checkSufficiency(
        recipeId: widget.recipe.recipeId,
        servings: 4,
        apiClient: apiClient,
        recipeIngredients: _recipeIngredientsPayload(),
        recipeServings: 4,
      );

      if (!mounted) return;
      setState(() {
        _checking = false;
        _sufficiency = result;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _checking = false;
        _sufficiency = null;
      });
    }
  }

  List<String> _whyBulletsFor(
    Recipe recipe, {
    String? matchSummary,
  }) {
    final bullets = <String>[];

    final ms = matchSummary?.trim();
    if (ms != null && ms.isNotEmpty) {
      bullets.add(ms);
    }

    final used = recipe.ingredientsUsed
        .map((i) => i.canonicalName.replaceAll('_', ' ').trim())
        .where((s) => s.isNotEmpty)
        .toList();

    if (used.isNotEmpty) {
      final top = used.take(6).toList();
      final suffix = used.length > 6 ? '…' : '';
      bullets.add('Uses: ${top.join(', ')}$suffix');
    } else {
      bullets.add("Built from what's in your pantry");
    }

    final di = recipe.dietaryInformation;
    final tags = <String>[];
    if (di != null && di.isNotEmpty) {
      for (final e in di.entries) {
        final key = e.key.toString().trim();
        final value = e.value;
        if (key.isEmpty) continue;
        if (value is bool && value == true) {
          tags.add(_prettyName(key.replaceAll('_', ' ')));
        }
      }
    }

    if (tags.isNotEmpty) {
      final top = tags.take(3).toList();
      final suffix = tags.length > 3 ? '…' : '';
      bullets.add('Respects: ${top.join(' • ')}$suffix');
    } else {
      bullets.add('Respects: No restrictions');
    }

    return bullets;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;

    final recipe = widget.recipe;
    final lang = _preferredLanguageKey(context);
    final title = _prettyName(_stripIngredientDumpSuffix(recipe.getLocalizedName(lang)));

    final String? secondaryLang = (lang != 'en' && (recipe.recipeName['en'] ?? '').trim().isNotEmpty)
        ? 'en'
        : _secondaryLanguageKey(recipe.recipeName, exclude: lang);
    final secondaryTitle = secondaryLang != null ? recipe.recipeName[secondaryLang] : null;

    final missingAll = <Map<String, dynamic>>[];
    final rawMissing = _sufficiency != null ? _sufficiency!['missing'] : null;
    if (rawMissing is List) {
      for (final row in rawMissing) {
        if (row is Map) missingAll.add(Map<String, dynamic>.from(row));
      }
    }

    final missingStaples = <Map<String, dynamic>>[];
    final missingNonStaples = <Map<String, dynamic>>[];
    for (final m in missingAll) {
      final name = _normalizeIngredientName(_missingRowName(m));
      if (name.isEmpty) {
        missingNonStaples.add(m);
        continue;
      }
      if (_pantryStaples.contains(name)) {
        missingStaples.add(m);
      } else {
        missingNonStaples.add(m);
      }
    }

    final missingForDisplay = _assumeStaples ? missingNonStaples : missingAll;
    final missingSet = missingForDisplay
        .map((m) => _normalizeIngredientName(_missingRowName(m)))
        .where((s) => s.isNotEmpty)
        .toSet();

    final have = recipe.ingredientsUsed.where((i) {
      final name = _normalizeIngredientName(i.canonicalName);
      if (name.isEmpty) return true;
      return !missingSet.contains(name);
    }).toList();

    final totalForMatch = recipe.ingredientsUsed.length;
    final matchSummary = totalForMatch > 0 ? 'You already have ${have.length}/$totalForMatch ingredients' : null;

    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title),
            if (secondaryTitle != null && secondaryTitle.trim().isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 2),
                child: Text(
                  secondaryTitle.trim(),
                  style: theme.textTheme.bodySmall?.copyWith(color: cs.onSurfaceVariant),
                ),
              ),
          ],
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            clipBehavior: Clip.antiAlias,
            child: SizedBox(
              height: 170,
              child: SavoNetworkImage(
                url: _bestEffortRecipeImageUrl(context),
                width: double.infinity,
                height: double.infinity,
                fit: BoxFit.cover,
                shape: SavoNetworkImageShape.roundedRect,
                borderRadius: BorderRadius.circular(12),
                backgroundColor: cs.surfaceContainerHighest,
                placeholderIcon: Icons.restaurant,
                errorIcon: Icons.restaurant,
                iconColor: cs.onSurfaceVariant,
                iconSize: 44,
              ),
            ),
          ),
          const SizedBox(height: 16),

          if ((recipe.shortDescription ?? '').trim().isNotEmpty) ...[
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Text(
                  (recipe.shortDescription ?? '').trim(),
                  style: theme.textTheme.bodyMedium,
                ),
              ),
            ),
            const SizedBox(height: 12),
          ],

          if (recipe.servingSuggestions.isNotEmpty) ...[
            _SectionTitle(text: 'Serving Suggestions', color: cs.primary),
            const SizedBox(height: 8),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: recipe.servingSuggestions
                      .map((s) => s.trim())
                      .where((s) => s.isNotEmpty)
                      .map(
                        (s) => Padding(
                          padding: const EdgeInsets.symmetric(vertical: 4),
                          child: Text('• $s', style: theme.textTheme.bodyMedium),
                        ),
                      )
                      .toList(),
                ),
              ),
            ),
            const SizedBox(height: 16),
          ],

          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Why this recipe?',
                    style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(height: 8),
                  ..._whyBulletsFor(recipe, matchSummary: matchSummary).map(
                    (t) => Padding(
                      padding: const EdgeInsets.symmetric(vertical: 4),
                      child: Text('• $t', style: theme.textTheme.bodyMedium),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          _SectionTitle(text: 'Ingredients', color: cs.primary),
          const SizedBox(height: 8),
          if (recipe.ingredientsUsed.isNotEmpty)
            Align(
              alignment: Alignment.centerLeft,
              child: FilterChip(
                label: const Text('Assume staples'),
                selected: _assumeStaples,
                onSelected: (v) {
                  fireAndForget(_setAssumeStaplesPref(v));
                },
              ),
            ),
          if (recipe.ingredientsUsed.isNotEmpty) const SizedBox(height: 8),
          if (_checking)
            Text('Checking what you have…', style: theme.textTheme.bodyMedium)
          else if (recipe.ingredientsUsed.isEmpty)
            Text('No ingredients listed.', style: theme.textTheme.bodyMedium)
          else if (_sufficiency != null && _sufficiency!['success'] == true) ...[
            if (missingForDisplay.isNotEmpty) ...[
              Text('Missing', style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700)),
              const SizedBox(height: 6),
              ...missingForDisplay.map((m) {
                final name = (m['name'] ?? m['ingredient'] ?? 'Ingredient').toString().trim();
                final qty = m['quantity'];
                final unit = (m['unit'] ?? '').toString().trim();
                final amountDisplay = (m['amount_display'] ?? m['amountDisplay'] ?? '').toString().trim();
                final notes = (m['notes'] ?? '').toString().trim();
                final qtyText = amountDisplay.isNotEmpty
                    ? amountDisplay
                    : ((qty is num && qty != 0)
                        ? (qty % 1 == 0 ? qty.toInt().toString() : qty.toStringAsFixed(1))
                        : (qty?.toString().trim().isNotEmpty == true ? qty.toString().trim() : ''));
                final suffix = _formatIngredientSuffix(amountText: qtyText, unit: unit, notes: notes);
                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Text('• $name$suffix', style: theme.textTheme.bodyMedium?.copyWith(color: cs.error)),
                );
              }),
              const SizedBox(height: 12),
            ],
            if (_assumeStaples && missingStaples.isNotEmpty) ...[
              Text('Assumed staples', style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700)),
              const SizedBox(height: 6),
              ...missingStaples.map((m) {
                final name = (m['name'] ?? m['ingredient'] ?? 'Ingredient').toString().trim();
                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Text('• $name', style: theme.textTheme.bodyMedium?.copyWith(color: cs.onSurfaceVariant)),
                );
              }),
              const SizedBox(height: 12),
            ],
            if (have.isNotEmpty) ...[
              Text('You have', style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700)),
              const SizedBox(height: 6),
              ...have.map((i) {
                final name = i.canonicalName.trim().isNotEmpty ? _prettyName(i.canonicalName.trim()) : 'Ingredient';
                final unit = i.unit.trim();
                final amountText = (i.amountDisplay ?? '').trim().isNotEmpty
                    ? (i.amountDisplay ?? '').trim()
                    : _formatAmount(i.amount);
                final suffix = _formatIngredientSuffix(
                  amountText: amountText,
                  unit: unit,
                  notes: (i.notes ?? '').trim(),
                );
                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Text('• $name$suffix', style: theme.textTheme.bodyMedium),
                );
              }),
            ],
          ] else ...[
            ...recipe.ingredientsUsed.map((i) {
              final name = i.canonicalName.trim().isNotEmpty ? _prettyName(i.canonicalName.trim()) : 'Ingredient';
              final unit = i.unit.trim();
              final amountText = (i.amountDisplay ?? '').trim().isNotEmpty
                  ? (i.amountDisplay ?? '').trim()
                  : _formatAmount(i.amount);
              final suffix = _formatIngredientSuffix(
                amountText: amountText,
                unit: unit,
                notes: (i.notes ?? '').trim(),
              );
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 6),
                child: Text('• $name$suffix', style: theme.textTheme.bodyMedium),
              );
            }),
            const SizedBox(height: 8),
            Text(
              'Pantry check unavailable.',
              style: theme.textTheme.bodySmall?.copyWith(color: cs.onSurfaceVariant),
            ),
          ],
          const SizedBox(height: 16),

          // Steps collapsed by default
          _SectionTitle(text: 'Steps', color: cs.primary),
          const SizedBox(height: 8),
          if (recipe.steps.isEmpty)
            Text('No steps available.', style: theme.textTheme.bodyMedium)
          else
            Card(
              clipBehavior: Clip.antiAlias,
              child: ExpansionTile(
                title: const Text('Show steps'),
                childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                children: recipe.steps.map((s) {
                  final instruction = s.getLocalizedInstruction(lang).trim();
                  final secondaryInstruction = secondaryLang != null
                      ? (s.instruction[secondaryLang] ?? '').trim()
                      : '';
                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 10),
                    child: Text(
                      '${s.step}. ${instruction.isNotEmpty ? instruction : 'Step'}'
                      '${secondaryInstruction.isNotEmpty ? '\n$secondaryInstruction' : ''}',
                      style: theme.textTheme.bodyMedium,
                    ),
                  );
                }).toList(),
              ),
            ),
          const SizedBox(height: 16),

          _SectionTitle(text: 'Meta', color: cs.primary),
          const SizedBox(height: 8),
          _MetaRow(label: 'Cuisine', value: recipe.cuisine),
          _MetaRow(label: 'Difficulty', value: recipe.difficulty),
          _MetaRow(label: 'Time', value: '${recipe.estimatedTimes.totalMinutes} min'),
          _MetaRow(label: 'Method', value: recipe.cookingMethod),
          const SizedBox(height: 8),
          Card(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      'Spice level',
                      style: theme.textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600),
                    ),
                  ),
                  DropdownButton<String>(
                    value: _spiceLevel,
                    onChanged: (v) {
                      if (v == null) return;
                      fireAndForget(_setSpicePref(v));
                    },
                    items: const [
                      DropdownMenuItem(value: 'none', child: Text('No spice')),
                      DropdownMenuItem(value: 'low', child: Text('Mild')),
                      DropdownMenuItem(value: 'medium', child: Text('Medium')),
                      DropdownMenuItem(value: 'high', child: Text('Spicy')),
                      DropdownMenuItem(value: 'very_high', child: Text('Very spicy')),
                    ],
                  ),
                ],
              ),
            ),
          ),

          if (recipe.nutritionPerServing.isNotEmpty) ...[
            const SizedBox(height: 16),
            _SectionTitle(text: 'Nutrition (Per Serving)', color: cs.primary),
            const SizedBox(height: 8),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Text(
                  recipe.nutritionPerServing.entries
                      .map((e) => '${_prettyName(e.key)}: ${e.value}')
                      .join('\n'),
                  style: theme.textTheme.bodyMedium,
                ),
              ),
            ),
          ],

          if (recipe.healthBenefits != null && recipe.healthBenefits!.isNotEmpty) ...[
            const SizedBox(height: 16),
            _SectionTitle(text: 'Health Benefits', color: cs.primary),
            const SizedBox(height: 8),
            ...recipe.healthBenefits!.map((b) {
              final ing = (b['ingredient'] ?? '').toString().trim();
              final benefit = (b['benefit'] ?? '').toString().trim();
              final label = ing.isNotEmpty ? '${_prettyName(ing)}: ' : '';
              final text = (label + benefit).trim();
              if (text.isEmpty) return const SizedBox.shrink();
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 6),
                child: Text('• $text', style: theme.textTheme.bodyMedium),
              );
            }),
          ],

          if (recipe.chefTips.isNotEmpty) ...[
            const SizedBox(height: 16),
            _SectionTitle(text: "Chef's Tips", color: cs.primary),
            const SizedBox(height: 8),
            ...recipe.chefTips.map((t) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Text('• ${t.trim()}', style: theme.textTheme.bodyMedium),
                )),
          ],

          if (recipe.culturalContext != null && recipe.culturalContext!.isNotEmpty) ...[
            const SizedBox(height: 16),
            _SectionTitle(text: 'Cultural Context', color: cs.primary),
            const SizedBox(height: 8),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Text(
                  recipe.culturalContext!.entries
                      .map((e) => '${_prettyName(e.key)}: ${e.value}')
                      .join('\n'),
                  style: theme.textTheme.bodyMedium,
                ),
              ),
            ),
          ],

          if (recipe.dietaryInformation != null && recipe.dietaryInformation!.isNotEmpty) ...[
            const SizedBox(height: 16),
            _SectionTitle(text: 'Dietary Information', color: cs.primary),
            const SizedBox(height: 8),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Text(
                  recipe.dietaryInformation!.entries
                      .map((e) => '${_prettyName(e.key)}: ${e.value}')
                      .join('\n'),
                  style: theme.textTheme.bodyMedium,
                ),
              ),
            ),
          ],
          const SizedBox(height: 24),

          SizedBox(
            width: double.infinity,
            child: FilledButton(
              onPressed: () {
                fireAndForget(MetricsService.instance.recordWorkflowStep('CookNow', 'Cook'));
                Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => CookModeScreen(
                      recipe: recipe,
                      servings: 4,
                      baseServings: 4,
                      enablePostCookFeedback: true,
                      showBackToOptions: true,
                    ),
                  ),
                );
              },
              child: const Text('Start cooking'),
            ),
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: (_checkingSaved || _savingToggle) ? null : _toggleSaved,
              icon: _savingToggle
                  ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                  : Icon(_isSaved ? Icons.bookmark : Icons.bookmark_border),
              label: Text(_isSaved ? 'Saved' : 'Save'),
            ),
          ),
          const SizedBox(height: 8),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: _markingCooked ? null : _markCooked,
              icon: _markingCooked
                  ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.check_circle_outline),
              label: const Text('Mark cooked'),
            ),
          ),
          const SizedBox(height: 8),
          SizedBox(
            width: double.infinity,
            child: TextButton(
              onPressed: _addingToPlan ? null : _showAddToPlanChooser,
              child: _addingToPlan
                  ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('Add to plan'),
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  final String text;
  final Color color;

  const _SectionTitle({required this.text, required this.color});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Text(
      text,
      style: theme.textTheme.titleMedium?.copyWith(
        fontWeight: FontWeight.w700,
        color: color,
      ),
    );
  }
}

class _MetaRow extends StatelessWidget {
  final String label;
  final String value;

  const _MetaRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final v = value.trim().isEmpty ? '—' : value.trim();
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 90,
            child: Text(label, style: theme.textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600)),
          ),
          Expanded(child: Text(v, style: theme.textTheme.bodyMedium)),
        ],
      ),
    );
  }
}
