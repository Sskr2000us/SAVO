import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../models/planning.dart';

class SavedRecipesLocalService {
  SavedRecipesLocalService._();

  static final SavedRecipesLocalService instance = SavedRecipesLocalService._();

  static const String _prefsKey = 'savo.saved_recipes.local_cache.v1';

  Future<List<Map<String, dynamic>>> _loadRaw() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_prefsKey);
      if (raw == null || raw.trim().isEmpty) return const [];
      final decoded = jsonDecode(raw);
      if (decoded is! List) return const [];
      return decoded.whereType<Map>().map((m) => m.cast<String, dynamic>()).toList();
    } catch (_) {
      return const [];
    }
  }

  Future<void> _saveRaw(List<Map<String, dynamic>> items) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_prefsKey, jsonEncode(items));
    } catch (_) {
      // Best-effort.
    }
  }

  Future<int> count() async {
    final raw = await _loadRaw();
    return raw.length;
  }

  Future<List<Recipe>> loadRecipesMostRecentFirst({int maxItems = 50}) async {
    final raw = await _loadRaw();
    raw.sort((a, b) {
      final ams = (a['saved_at_ms'] is int) ? a['saved_at_ms'] as int : int.tryParse(a['saved_at_ms']?.toString() ?? '') ?? 0;
      final bms = (b['saved_at_ms'] is int) ? b['saved_at_ms'] as int : int.tryParse(b['saved_at_ms']?.toString() ?? '') ?? 0;
      return bms.compareTo(ams);
    });

    final out = <Recipe>[];
    for (final entry in raw.take(maxItems)) {
      final recipeJson = entry['recipe'];
      if (recipeJson is Map) {
        try {
          out.add(Recipe.fromJson(Map<String, dynamic>.from(recipeJson)));
        } catch (_) {
          // Skip invalid.
        }
      }
    }
    return out;
  }

  Future<void> upsertSavedRecipe(Recipe recipe) async {
    final rid = recipe.recipeId.trim();
    if (rid.isEmpty) return;

    final raw = await _loadRaw();
    raw.removeWhere((e) {
      final r = e['recipe'];
      if (r is Map) {
        final id = (r['recipe_id'] ?? r['id'] ?? '').toString().trim();
        return id == rid;
      }
      return false;
    });

    raw.insert(0, {
      'saved_at_ms': DateTime.now().millisecondsSinceEpoch,
      'recipe': recipe.toJson(),
    });

    if (raw.length > 100) {
      raw.removeRange(100, raw.length);
    }

    await _saveRaw(raw);
  }

  Future<void> removeSavedRecipeById(String recipeId) async {
    final rid = recipeId.trim();
    if (rid.isEmpty) return;

    final raw = await _loadRaw();
    raw.removeWhere((e) {
      final r = e['recipe'];
      if (r is Map) {
        final id = (r['recipe_id'] ?? r['id'] ?? '').toString().trim();
        return id == rid;
      }
      return false;
    });
    await _saveRaw(raw);
  }

  List<Map<String, dynamic>> buildShoppingListFromRecipes(List<Recipe> recipes) {
    final merged = <String, Map<String, dynamic>>{};

    for (final recipe in recipes) {
      for (final ing in recipe.ingredientsUsed) {
        final name = ing.canonicalName.trim();
        if (name.isEmpty) continue;
        final unit = ing.unit.trim();
        final key = '${name.toLowerCase()}|${unit.toLowerCase()}';

        final qty = ing.amount;
        if (!merged.containsKey(key)) {
          merged[key] = {
            'canonical_name': name,
            'amount': qty,
            'unit': unit,
          };
        } else {
          final existing = merged[key]!;
          final a = existing['amount'];
          if (a is num) {
            existing['amount'] = a + qty;
          } else {
            // If existing isn't numeric, keep existing.
          }
        }
      }
    }

    final out = merged.values.toList();
    out.sort((a, b) => (a['canonical_name'] ?? '').toString().compareTo((b['canonical_name'] ?? '').toString()));
    return out;
  }

  /// Builds a lightweight weekly plan object from saved recipes (client-side fallback).
  MenuPlanResponse buildWeeklyPlanFromSaved({required List<Recipe> recipes, int numDays = 3}) {
    final picked = recipes.take(numDays).toList();

    final menus = <Menu>[];
    final today = DateTime.now();
    for (var i = 0; i < picked.length; i++) {
      final date = today.add(Duration(days: i));
      final iso = '${date.year.toString().padLeft(4, '0')}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';

      menus.add(
        Menu(
          menuType: 'weekly_day',
          dayIndex: i,
          date: iso,
          servings: const {'total': 4},
          courses: [
            Course(
              courseHeader: 'Dinner',
              recipeOptions: [picked[i]],
            ),
          ],
        ),
      );
    }

    return MenuPlanResponse(
      status: 'ok',
      selectedCuisine: 'auto',
      planningWindow: {
        'num_days': picked.length,
      },
      menuHeaders: const ['Dinner'],
      menus: menus,
    );
  }
}
