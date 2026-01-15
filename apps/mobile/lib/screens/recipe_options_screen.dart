import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../models/planning.dart';
import '../models/inventory.dart';
import '../models/profile_state.dart';
import '../config/app_config.dart';
import '../services/metrics_service.dart';
import '../services/api_client.dart';
import '../services/scanning_service.dart';
import '../services/cuisine_preference_service.dart';
import '../services/entitlements_service.dart';
import '../services/shopping_list_storage.dart';
import '../widgets/pro_paywall_sheet.dart';
import '../widgets/savo_network_image.dart';
import 'cook_now_recipe_detail_screen.dart';
import 'shopping_list_screen.dart';

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
  final Map<String, int> _carouselIndexByRecipeId = {};

  bool _recipeShownLogged = false;

  Map<String, int> _cuisineScores = const {};

  bool _suggestionsLocked = false;

  static const String _prefsAssumeStaplesKey = 'savo.assume_pantry_staples';
  bool _assumeStaplesGlobal = true;
  final Map<String, bool> _assumeStaplesOverrideByRecipeId = {};

  static const String _prefsSpiceLevelKey = 'savo.recipe.spice_level';
  String _spiceLevel = 'medium';

  bool _loadingInventoryForExpiry = false;
  Set<String> _expiringIngredientKeys = const {};

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

  static const String _supabaseShoppingTable = 'household_shopping_items';

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

  String? _householdId() {
    try {
      final profile = Provider.of<ProfileState>(context, listen: false);
      final hh = profile.household;
      final id = hh?['id'];
      final v = id?.toString().trim();
      if (v == null || v.isEmpty) return null;
      return v;
    } catch (_) {
      return null;
    }
  }

  Future<void> _addMissingToShoppingList({
    required Recipe recipe,
    required List<String> missingNames,
  }) async {
    final names = missingNames.map((s) => _prettyName(s).trim()).where((s) => s.isNotEmpty).toSet().toList()..sort();
    if (names.isEmpty) return;

    final addedCount = names.length;

    final incoming = names.map((n) => {'canonical_name': n}).toList();
    await ShoppingListStorage.mergeAndSaveIncoming(incoming);

    String message = 'Added $addedCount item${addedCount == 1 ? '' : 's'} to shopping list';

    // Best-effort sync: keep remote list from overwriting local cache.
    try {
      final session = Supabase.instance.client.auth.currentSession;
      final householdId = _householdId();
      if (session != null && householdId != null) {
        final now = DateTime.now().toUtc().toIso8601String();
        final rows = <Map<String, dynamic>>[];
        for (final item in incoming) {
          final key = ShoppingListStorage.itemKey(item);
          if (key.trim().isEmpty) continue;
          rows.add({
            'household_id': householdId,
            'item_key': key,
            'item_json': item,
            'checked': false,
            'updated_at': now,
          });
        }
        if (rows.isNotEmpty) {
          await Supabase.instance.client.from(_supabaseShoppingTable).upsert(rows);
          message = 'Added $addedCount item${addedCount == 1 ? '' : 's'} + synced';
        }
      }
    } catch (_) {
      message = 'Added $addedCount item${addedCount == 1 ? '' : 's'} (sync unavailable)';
    }

    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _copyMissingToClipboard({
    required Recipe recipe,
    required List<String> missingNames,
  }) async {
    final names = missingNames.map((s) => _prettyName(s).trim()).where((s) => s.isNotEmpty).toSet().toList()..sort();
    if (names.isEmpty) return;

    final title = _prettyName(recipe.getLocalizedName(_preferredLanguageKey()));
    final lines = <String>['Missing ingredients for $title', ''];
    for (final n in names) {
      lines.add('- $n');
    }

    await Clipboard.setData(ClipboardData(text: lines.join('\n')));
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Missing list copied')));
  }

  Future<void> _showMissingActions({
    required Recipe recipe,
    required List<String> missingNames,
  }) async {
    final names = missingNames.map((s) => _prettyName(s).trim()).where((s) => s.isNotEmpty).toSet().toList()..sort();
    if (names.isEmpty) return;

    final count = names.length;
    final primaryLabel = count == 1 ? 'Add 1 item' : 'Add $count items';

    if (!mounted) return;
    await showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (ctx) {
        final theme = Theme.of(ctx);
        final title = _prettyName(recipe.getLocalizedName(_preferredLanguageKey()));
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text('Missing ingredients', style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
                const SizedBox(height: 4),
                Text(title, style: theme.textTheme.bodyMedium),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    for (final n in names.take(12))
                      Chip(
                        visualDensity: VisualDensity.compact,
                        label: Text(n),
                        avatar: const Icon(Icons.add_shopping_cart_outlined, size: 16),
                      ),
                    if (names.length > 12)
                      Chip(
                        visualDensity: VisualDensity.compact,
                        label: Text('+${names.length - 12} more'),
                      ),
                  ],
                ),
                const SizedBox(height: 16),
                FilledButton.icon(
                  onPressed: () async {
                    Navigator.of(ctx).pop();
                    await _addMissingToShoppingList(recipe: recipe, missingNames: names);
                  },
                  icon: const Icon(Icons.add_shopping_cart_outlined),
                  label: Text(primaryLabel),
                ),
                const SizedBox(height: 10),
                OutlinedButton.icon(
                  onPressed: () async {
                    Navigator.of(ctx).pop();
                    await _copyMissingToClipboard(recipe: recipe, missingNames: names);
                  },
                  icon: const Icon(Icons.copy),
                  label: const Text('Copy list'),
                ),
                const SizedBox(height: 10),
                TextButton.icon(
                  onPressed: () {
                    Navigator.of(ctx).pop();
                    Navigator.of(context).push(MaterialPageRoute(builder: (_) => const ShoppingListScreen()));
                  },
                  icon: const Icon(Icons.receipt_long_outlined),
                  label: const Text('Open shopping list'),
                ),
              ],
            ),
          ),
        );
      },
    );
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

  String _spiceLabel(String raw) {
    final s = raw.trim().toLowerCase();
    if (s == 'none') return 'No spice';
    if (s == 'low') return 'Mild';
    if (s == 'medium') return 'Medium';
    if (s == 'high') return 'Spicy';
    if (s == 'very_high') return 'Very spicy';
    if (s.isEmpty) return 'Medium';
    return s;
  }

  Future<void> _loadExpiringIngredientsBestEffort() async {
    if (_loadingInventoryForExpiry) return;
    if (_expiringIngredientKeys.isNotEmpty) return;
    setState(() => _loadingInventoryForExpiry = true);

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final res = await apiClient.get('/inventory-db/items?include_inactive=true');

      final items = <InventoryItem>[];
      if (res is Map && res['items'] is List) {
        for (final row in (res['items'] as List)) {
          if (row is Map) {
            items.add(InventoryItem.fromJson(row.cast<String, dynamic>()));
          }
        }
      } else if (res is List) {
        for (final row in res) {
          if (row is Map) {
            items.add(InventoryItem.fromJson(row.cast<String, dynamic>()));
          }
        }
      }

      final keys = <String>{};
      for (final it in items) {
        if (!it.isCurrent) continue;
        if (!it.isExpiringSoon) continue;
        final k1 = it.canonicalName.replaceAll('_', ' ').trim().toLowerCase();
        if (k1.isNotEmpty) keys.add(k1);
        final k2 = it.displayLabel.replaceAll('_', ' ').trim().toLowerCase();
        if (k2.isNotEmpty) keys.add(k2);
      }

      if (!mounted) return;
      setState(() {
        _expiringIngredientKeys = keys;
      });
    } catch (_) {
      // Best-effort only.
    } finally {
      if (mounted) setState(() => _loadingInventoryForExpiry = false);
    }
  }

  bool _usesExpiringItems(Recipe recipe) {
    if (_expiringIngredientKeys.isEmpty) return false;
    for (final ing in recipe.ingredientsUsed) {
      final k = ing.canonicalName.replaceAll('_', ' ').trim().toLowerCase();
      if (k.isEmpty) continue;
      if (_expiringIngredientKeys.contains(k)) return true;
    }
    return false;
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
    // Best-effort signals for trust-first UI.
    fireAndForget(_loadSpicePref());
    fireAndForget(_loadExpiringIngredientsBestEffort());

    if (widget.showIngredientMatch) {
      final options = _sortedRecipesForDisplay(widget.recipes).take(5).toList();
      fireAndForget(_loadMatchCounts(options));
    }
  }

  String _preferredLanguageKey() {
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
        final missingNamesNorm = <String>[];
        for (final row in missingList) {
          final raw = _missingRowName(row);
          final norm = _normalizeIngredientName(raw);
          if (norm.isEmpty) continue;
          missingNamesNorm.add(norm);
          if (assumeStaples && _pantryStaples.contains(norm)) continue;

          final display = _prettyName(raw).trim();
          if (display.isEmpty) continue;
          missingPreviewCandidates.add(display);
        }

        // Stabilize ordering: API ordering can vary; sort for consistency.
        final missingDisplay = (missingPreviewCandidates.toSet().toList()..sort()).take(8).toList();
        final missingPreview = missingDisplay.take(2).toList();

        _matchByRecipeId[recipe.recipeId] = {
          'have': have,
          'total': total,
          'missing': missingForCount,
          'assumed_staples': assumedStaples,
          'assumed_staples_names': (assumeStaples && missingStapleNames.isNotEmpty)
              ? (missingStapleNames.toSet().toList()..sort())
              : const <String>[],
          'missing_preview': missingPreview,
          'missing_display': missingDisplay,
          'missing_names_norm': (missingNamesNorm.toSet().toList()..sort()),
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

  String? _absoluteImageUrl(String? raw) {
    final s = (raw ?? '').trim();
    if (s.isEmpty) return null;
    if (s.startsWith('/')) return '${Config.apiBaseUrl}$s';
    return s;
  }

  List<String> _galleryUrls(Recipe recipe) {
    final out = <String>[];
    for (final u in recipe.imageUrls) {
      final abs = _absoluteImageUrl(u);
      if (abs != null && abs.isNotEmpty) out.add(abs);
    }

    if (out.isNotEmpty) return out;

    final fallback = _imageUrl(recipe);
    if (fallback != null && fallback.trim().isNotEmpty) return [fallback.trim()];
    return const <String>[];
  }

  Widget _stackedThumbs(List<String> urls, int selectedIndex) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;
    if (urls.length < 2) return const SizedBox.shrink();

    final count = urls.length >= 3 ? 3 : 2;
    final thumbSize = 34.0;
    final dx = 10.0;
    final dy = 8.0;

    List<int> idxs() {
      final out = <int>[];
      for (var i = 0; i < count; i++) {
        out.add((selectedIndex + i) % urls.length);
      }
      return out;
    }

    final indices = idxs();

    return SizedBox(
      width: thumbSize + dx * (count - 1),
      height: thumbSize + dy * (count - 1),
      child: Stack(
        children: [
          for (var i = count - 1; i >= 0; i--)
            Positioned(
              right: dx * i,
              top: dy * i,
              child: Container(
                width: thumbSize,
                height: thumbSize,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(
                    color: cs.surfaceContainerHighest.withAlpha(220),
                    width: 2,
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: cs.onSurface.withAlpha(40),
                      blurRadius: 10,
                      offset: const Offset(0, 4),
                    ),
                  ],
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: SavoNetworkImage(
                    url: urls[indices[i]],
                    width: thumbSize,
                    height: thumbSize,
                    fit: BoxFit.cover,
                    shape: SavoNetworkImageShape.roundedRect,
                    borderRadius: BorderRadius.zero,
                    backgroundColor: cs.surfaceContainerHighest,
                    placeholderIcon: Icons.restaurant,
                    errorIcon: Icons.restaurant,
                    iconColor: cs.onSurfaceVariant,
                    iconSize: 16,
                  ),
                ),
              ),
            ),
          if (urls.length > count)
            Positioned(
              right: 0,
              bottom: 0,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: cs.surfaceContainerHighest.withAlpha(220),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  '+${urls.length - count}',
                  style: theme.textTheme.labelSmall?.copyWith(
                    color: cs.onSurfaceVariant,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _missingChipsSection(Recipe recipe) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;

    // Prefer match-derived display list (accounts for assume-staples and pantry truth).
    final m = _matchByRecipeId[recipe.recipeId];
    final matchMissingCount = (m == null) ? null : (m['missing'] as int?);
    final rawMatchDisplay = (m == null) ? null : m['missing_display'];

    final backendMissing = recipe.missingIngredientNames
        .map((s) => _prettyName(s))
        .where((s) => s.trim().isNotEmpty)
        .toSet()
        .toList()
      ..sort();

    final matchDisplay = <String>[];
    if (rawMatchDisplay is List) {
      for (final x in rawMatchDisplay) {
        final s = _prettyName(x.toString()).trim();
        if (s.isNotEmpty) matchDisplay.add(s);
      }
    }

    final names = matchDisplay.isNotEmpty ? matchDisplay : backendMissing;
    final missingCount = (matchMissingCount != null) ? matchMissingCount : names.length;

    if (missingCount <= 0 || names.isEmpty) return const SizedBox.shrink();

    final visible = names.take(6).toList();
    final extra = (missingCount - visible.length).clamp(0, 999);

    void openActions() {
      fireAndForget(_showMissingActions(recipe: recipe, missingNames: names));
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(Icons.remove_circle_outline, size: 18, color: cs.error),
            const SizedBox(width: 6),
            Text(
              'Missing',
              style: theme.textTheme.labelLarge?.copyWith(
                color: cs.error,
                fontWeight: FontWeight.w800,
              ),
            ),
            const Spacer(),
            TextButton.icon(
              onPressed: () {
                fireAndForget(_addMissingToShoppingList(recipe: recipe, missingNames: names));
              },
              icon: Icon(Icons.add_shopping_cart_outlined, size: 16, color: cs.error),
              label: Text(
                'Add all',
                style: theme.textTheme.labelMedium?.copyWith(
                  color: cs.error,
                  fontWeight: FontWeight.w800,
                ),
              ),
              style: TextButton.styleFrom(
                visualDensity: VisualDensity.compact,
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                minimumSize: const Size(0, 0),
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final n in visible)
              ActionChip(
                visualDensity: VisualDensity.compact,
                backgroundColor: cs.errorContainer,
                onPressed: openActions,
                label: Text(
                  n,
                  style: theme.textTheme.labelMedium?.copyWith(color: cs.onErrorContainer),
                ),
                avatar: Icon(Icons.add_shopping_cart_outlined, size: 16, color: cs.onErrorContainer),
              ),
            if (extra > 0)
              ActionChip(
                visualDensity: VisualDensity.compact,
                backgroundColor: cs.surfaceContainerHighest,
                onPressed: openActions,
                label: Text(
                  '+$extra more',
                  style: theme.textTheme.labelMedium?.copyWith(color: cs.onSurfaceVariant),
                ),
              ),
          ],
        ),
      ],
    );
  }

  Set<String> _missingNamesForRecipe(Recipe recipe) {
    final missing = <String>{};
    for (final n in recipe.missingIngredientNames) {
      final norm = _normalizeIngredientName(n);
      if (norm.isNotEmpty) missing.add(norm);
    }

    final m = _matchByRecipeId[recipe.recipeId];
    final raw = (m == null) ? null : m['missing_names_norm'];
    if (raw is List) {
      for (final x in raw) {
        final norm = _normalizeIngredientName(x.toString());
        if (norm.isNotEmpty) missing.add(norm);
      }
    }
    return missing;
  }

  Widget _ingredientChips(Recipe recipe) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;

    final ingredients = recipe.ingredientsUsed
        .map((i) => i.canonicalName.replaceAll('_', ' ').trim())
        .where((s) => s.isNotEmpty)
        .toList();

    if (ingredients.isEmpty) return const SizedBox.shrink();

    final missing = _missingNamesForRecipe(recipe);
    final m = _matchByRecipeId[recipe.recipeId];
    final hasEvidence = missing.isNotEmpty || m != null || recipe.pantryCoverage != null;
    final chips = <Widget>[];

    for (final raw in ingredients.take(6)) {
      final label = _prettyName(raw);
      final norm = _normalizeIngredientName(raw);
      final isMissing = missing.contains(norm);

        final bg = !hasEvidence
          ? cs.surfaceContainerHighest
          : isMissing
            ? cs.errorContainer
            : cs.tertiaryContainer;
        final fg = !hasEvidence
          ? cs.onSurfaceVariant
          : isMissing
            ? cs.onErrorContainer
            : cs.onTertiaryContainer;
        final icon = !hasEvidence
          ? Icons.circle_outlined
          : isMissing
            ? Icons.add_shopping_cart_outlined
            : Icons.check_circle_outline;

      chips.add(
        Chip(
          visualDensity: VisualDensity.compact,
          backgroundColor: bg,
          label: Text(label, style: theme.textTheme.labelMedium?.copyWith(color: fg)),
          avatar: Icon(icon, size: 16, color: fg),
        ),
      );
    }

    // If we have match data and there are more missing items, show a small summary chip.
    final missingCount = (m == null) ? null : (m['missing'] as int?);
    if (missingCount != null && missingCount > 0) {
      chips.add(
        Chip(
          visualDensity: VisualDensity.compact,
          backgroundColor: cs.surfaceContainerHighest,
          label: Text(
            '$missingCount missing',
            style: theme.textTheme.labelMedium?.copyWith(color: cs.onSurfaceVariant),
          ),
          avatar: Icon(Icons.remove_circle_outline, size: 16, color: cs.onSurfaceVariant),
        ),
      );
    }

    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: chips,
    );
  }

  Widget _recipeImageHeader({
    required Recipe recipe,
    required bool hasVideo,
    required List<RankedVideo> refs,
  }) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;

    final urls = _galleryUrls(recipe);
    final selected = _carouselIndexByRecipeId[recipe.recipeId] ?? 0;
    final safeSelected = (urls.isEmpty) ? 0 : (selected.clamp(0, urls.length - 1));
    if (_carouselIndexByRecipeId[recipe.recipeId] != safeSelected) {
      _carouselIndexByRecipeId[recipe.recipeId] = safeSelected;
    }

    return SizedBox(
      height: 170,
      child: Stack(
        fit: StackFit.expand,
        children: [
          if (urls.isEmpty)
            Container(
              color: cs.surfaceContainerHighest,
              alignment: Alignment.center,
              child: Icon(Icons.restaurant, size: 44, color: cs.onSurfaceVariant),
            )
          else
            PageView.builder(
              key: PageStorageKey<String>('recipe_carousel_${recipe.recipeId}'),
              itemCount: urls.length,
              onPageChanged: (idx) {
                setState(() {
                  _carouselIndexByRecipeId[recipe.recipeId] = idx;
                });
              },
              itemBuilder: (_, idx) {
                return SavoNetworkImage(
                  url: urls[idx],
                  width: double.infinity,
                  height: double.infinity,
                  fit: BoxFit.cover,
                  shape: SavoNetworkImageShape.roundedRect,
                  borderRadius: BorderRadius.zero,
                  backgroundColor: cs.surfaceContainerHighest,
                  placeholderIcon: Icons.restaurant,
                  errorIcon: Icons.restaurant,
                  iconColor: cs.onSurfaceVariant,
                  iconSize: 40,
                );
              },
            ),
          // Contrast overlay (do not block swipes/taps).
          IgnorePointer(
            child: Container(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [
                    cs.onSurface.withAlpha(10),
                    cs.onSurface.withAlpha(160),
                  ],
                ),
              ),
            ),
          ),
          if (urls.length > 1)
            Positioned(
              top: 8,
              right: 8,
              child: IgnorePointer(
                child: _stackedThumbs(urls, safeSelected),
              ),
            ),
          if (urls.length > 1)
            Positioned(
              left: 0,
              right: 0,
              bottom: 10,
              child: Center(
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: cs.surfaceContainerHighest.withAlpha(210),
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: List.generate(urls.length, (i) {
                      final isActive = i == safeSelected;
                      return Container(
                        width: isActive ? 10 : 6,
                        height: 6,
                        margin: const EdgeInsets.symmetric(horizontal: 3),
                        decoration: BoxDecoration(
                          color: isActive ? cs.primary : cs.onSurfaceVariant.withAlpha(160),
                          borderRadius: BorderRadius.circular(999),
                        ),
                      );
                    }),
                  ),
                ),
              ),
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
        ],
      ),
    );
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
    final lang = _preferredLanguageKey();

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
                final title = _prettyName(recipe.getLocalizedName(lang));
                final why = _whyItWorks(recipe);
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
                        Stack(
                          children: [
                            _recipeImageHeader(recipe: recipe, hasVideo: hasVideo, refs: refs),
                            Positioned(
                              left: 12,
                              right: 12,
                              bottom: 12,
                              child: IgnorePointer(
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
                        Builder(
                          builder: (_) {
                            final section = _missingChipsSection(recipe);
                            if (section is SizedBox) return const SizedBox.shrink();
                            return Padding(
                              padding: const EdgeInsets.fromLTRB(12, 12, 12, 0),
                              child: section,
                            );
                          },
                        ),
                        Padding(
                          padding: const EdgeInsets.all(12),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              _ingredientChips(recipe),
                              if (recipe.ingredientsUsed.isNotEmpty) const SizedBox(height: 10),
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
                                  _Badge(icon: Icons.local_fire_department_outlined, label: _spiceLabel(_spiceLevel)),
                                  if (_usesExpiringItems(recipe))
                                    const _Badge(icon: Icons.schedule, label: 'Use soon'),
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

                                    final ratioOk = total > 0 && (have / total) >= 0.7;

                                    // Prefer backend trust signals if present (from /recipes/generate).
                                    final backendCoverage = recipe.pantryCoverage;
                                    final backendMissing = recipe.missingIngredientNames;
                                    final backendTrust = recipe.trustSignals;
                                    final trust = backendTrust;
                                    final backendUsesWhatYouHave = trust != null && trust['uses_what_you_have'] == true;
                                    final backendHasData = backendCoverage != null || backendMissing.isNotEmpty || backendTrust != null;

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
                                        if (backendHasData ? backendUsesWhatYouHave : ratioOk) ...[
                                          Text(
                                            'Uses what you have',
                                            style: theme.textTheme.labelMedium?.copyWith(
                                              color: cs.tertiary,
                                              fontWeight: FontWeight.w800,
                                            ),
                                          ),
                                          const SizedBox(height: 2),
                                        ],
                                        if (backendHasData && backendCoverage != null) ...[
                                          Text(
                                            'Pantry coverage: ${(backendCoverage * 100).round()}%',
                                            style: theme.textTheme.labelMedium?.copyWith(
                                              color: cs.onSurfaceVariant,
                                              fontWeight: FontWeight.w800,
                                            ),
                                          ),
                                          const SizedBox(height: 2),
                                        ],
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
                                        if (backendHasData && backendMissing.isNotEmpty) ...[
                                          const SizedBox(height: 4),
                                          Text(
                                            'Missing: ${(backendMissing.toSet().toList()..sort()).take(3).join(', ')}'
                                            '${backendMissing.length > 3 ? '…' : ''}',
                                            style: theme.textTheme.bodySmall?.copyWith(
                                              color: cs.onSurfaceVariant,
                                            ),
                                          ),
                                        ],
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
    if (recipe.imageUrls.isNotEmpty) {
      final idx = (recipe.recipeId.hashCode).abs() % recipe.imageUrls.length;
      final raw = recipe.imageUrls[idx].trim();
      if (raw.isNotEmpty) {
        if (raw.startsWith('/')) return '${Config.apiBaseUrl}$raw';
        return raw;
      }
    }

    final raw = (recipe.imageUrl ?? '').trim();
    if (raw.isNotEmpty) {
      if (raw.startsWith('/')) return '${Config.apiBaseUrl}$raw';
      return raw;
    }

    if (kIsWeb) {
      final name = recipe.getLocalizedName(_preferredLanguageKey()).trim();
      if (name.isEmpty) return null;
      final cuisine = recipe.cuisine.trim().isEmpty ? 'general' : recipe.cuisine.trim();
      final url =
          '/recipes/image/proxy?recipe_name=${Uri.encodeComponent(name)}&cuisine=${Uri.encodeComponent(cuisine)}';
      return '${Config.apiBaseUrl}$url';
    }

    final name = recipe.getLocalizedName(_preferredLanguageKey()).trim();
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
