import '../models/planning.dart';
import '../models/profile_state.dart';
import 'api_client.dart';
import 'metrics_service.dart';
import 'dart:math';
import 'package:shared_preferences/shared_preferences.dart';

class CookNowService {
  static const String _prefsPlanningIncludeInactiveKey = 'savo.planning.include_inactive_inventory';
  static const String _prefsInventoryShowInactiveKey = 'savo.inventory.show_inactive_items';
  static const String _prefsSpiceLevelKey = 'savo.recipe.spice_level';

  String _inferMealType() {
    final hour = DateTime.now().hour;
    if (hour < 11) return 'breakfast';
    if (hour < 16) return 'lunch';
    return 'dinner';
  }

  Future<List<Recipe>> generateRecipeOptions({
    required ApiClient apiClient,
    required ProfileState profileState,
    int maxOptions = 5,
    int avoidRecentRecipes = 3,
    bool preferCachedFirst = false,
    String? creativity,
  }) async {
    // Prefer the new constrained endpoint.
    // Keep this method signature stable; we adapt backend response to the existing `Recipe` model.
    final cuisine = (profileState.favoriteCuisines.isNotEmpty) ? profileState.favoriteCuisines.first : null;

    String? spiceLevel;
    try {
      final prefs = await SharedPreferences.getInstance();
      spiceLevel = prefs.getString(_prefsSpiceLevelKey);
    } catch (_) {
      spiceLevel = null;
    }

    // Reuse the inventory screen preference so Cook Now can consider older (inactive) pantry items.
    bool includeInactiveInventory = false;
    try {
      final prefs = await SharedPreferences.getInstance();
      final includeInactive = prefs.containsKey(_prefsPlanningIncludeInactiveKey)
          ? (prefs.getBool(_prefsPlanningIncludeInactiveKey) ?? false)
          : (prefs.getBool(_prefsInventoryShowInactiveKey) ?? false);
      includeInactiveInventory = includeInactive;
    } catch (_) {
      // Best-effort only
    }
    Future<List<Recipe>> fetchGenerated({required int attempts}) async {
      final byId = <String, Recipe>{};
      final creative = (creativity ?? '').trim().toLowerCase();
      final creativityValue = (creative == 'high' || creative == 'standard') ? creative : '';
      final req = <String, dynamic>{
        'request_text': '',
        if (cuisine != null && cuisine.trim().isNotEmpty) 'cuisine': cuisine.trim(),
        'max_time_minutes': 45,
        'serves': 4,
        'include_inactive_inventory': includeInactiveInventory,
        'use_expiring_items': true,
        // Ask backend for multiple options in a single call.
        'count': attempts.clamp(1, 8),
        if (spiceLevel != null && spiceLevel.trim().isNotEmpty) 'spice_level': spiceLevel.trim(),
        if (creativityValue.isNotEmpty) 'creativity': creativityValue,
      };

      final res = await apiClient.post('/recipes/generate-options', req);
      final rawOptions = (res['options'] is List) ? (res['options'] as List) : const [];

      for (final row in rawOptions) {
        if (row is Map) {
          final r = Recipe.fromRecipeGenerateResponse(Map<String, dynamic>.from(row));
          final id = r.recipeId.trim();
          if (id.isNotEmpty) {
            byId.putIfAbsent(id, () => r);
          }
        }
      }
      return byId.values.toList();
    }

    Future<List<Recipe>> fetchLegacyPlan() async {
      final body = <String, dynamic>{
        'meal_type': _inferMealType(),
        'time_available_minutes': 45,
        'servings': 4,
        if (includeInactiveInventory) 'include_inactive_inventory': true,
      };

      final preferred = profileState.favoriteCuisines;
      if (preferred.isNotEmpty) {
        body['cuisine_preferences'] = preferred;
      }

      final outputLang = (profileState.preferredLanguage?.trim().isNotEmpty == true)
          ? profileState.preferredLanguage!.trim()
          : (profileState.primaryLanguage?.trim().isNotEmpty == true)
              ? profileState.primaryLanguage!.trim()
              : 'en';

      body['output_language'] = outputLang;
      body['output_languages'] = outputLang == 'en' ? ['en'] : ['en', outputLang];

      final measurementSystem = profileState.measurementSystem;
      if (measurementSystem != null && measurementSystem.trim().isNotEmpty) {
        body['measurement_system'] = measurementSystem.trim();
      }

      Future<MenuPlanResponse> fetchPlan({required bool forceRegenerate}) async {
        final path = forceRegenerate ? '/plan/daily?force_regenerate=true' : '/plan/daily';
        final response = await apiClient.post(path, body);
        return MenuPlanResponse.fromJson(response);
      }

      MenuPlanResponse plan;
      if (preferCachedFirst) {
        try {
          plan = await fetchPlan(forceRegenerate: false);
        } catch (_) {
          plan = await fetchPlan(forceRegenerate: true);
        }

        if (plan.status != 'ok') {
          plan = await fetchPlan(forceRegenerate: true);
        }
      } else {
        try {
          plan = await fetchPlan(forceRegenerate: true);
        } catch (_) {
          plan = await fetchPlan(forceRegenerate: false);
        }
      }

      if (plan.status != 'ok') {
        final msg = (plan.errorMessage?.trim().isNotEmpty == true)
            ? plan.errorMessage!.trim()
            : (plan.needsClarificationQuestions.isNotEmpty)
                ? plan.needsClarificationQuestions.first.trim()
                : 'Unable to generate recipes right now.';
        throw msg;
      }

      final byId = <String, Recipe>{};
      for (final menu in plan.menus) {
        for (final course in menu.courses) {
          for (final recipe in course.recipeOptions) {
            final id = recipe.recipeId.trim();
            if (id.isEmpty) continue;
            byId.putIfAbsent(id, () => recipe);
          }
        }
      }

      var candidates = byId.values.toList();
      candidates.shuffle(Random(DateTime.now().microsecondsSinceEpoch));
      if (candidates.isEmpty) {
        plan = await fetchPlan(forceRegenerate: true);
        if (plan.status != 'ok') {
          final msg = (plan.errorMessage?.trim().isNotEmpty == true)
              ? plan.errorMessage!.trim()
              : (plan.needsClarificationQuestions.isNotEmpty)
                  ? plan.needsClarificationQuestions.first.trim()
                  : 'Unable to generate recipes right now.';
          throw msg;
        }

        final retryById = <String, Recipe>{};
        for (final menu in plan.menus) {
          for (final course in menu.courses) {
            for (final recipe in course.recipeOptions) {
              final id = recipe.recipeId.trim();
              if (id.isEmpty) continue;
              retryById.putIfAbsent(id, () => recipe);
            }
          }
        }

        candidates = retryById.values.toList();
        if (candidates.isEmpty) {
          throw 'No recipe options right now. Try again after updating your pantry.';
        }
      }
      return candidates;
    }

    List<Recipe> candidates;
    try {
      // Try to get enough distinct options by making a few generation attempts.
      final attempts = (maxOptions * 2).clamp(2, 10);
      candidates = await fetchGenerated(attempts: attempts);
      if (candidates.isEmpty) {
        candidates = await fetchLegacyPlan();
      }
    } catch (_) {
      // Fail closed to legacy plan for resilience.
      candidates = await fetchLegacyPlan();
    }

    final recentIds = <String>{};
    final recentNames = <String>{};
    if (avoidRecentRecipes > 0) {
      try {
        final res = await apiClient.get('/history/recipes?limit=$avoidRecentRecipes');
        if (res is List) {
          for (final row in res) {
            if (row is Map) {
              final m = Map<String, dynamic>.from(row);
              final id = (m['recipe_id'] ?? '').toString().trim();
              if (id.isNotEmpty) recentIds.add(id);
              final name = (m['recipe_name'] ?? '').toString().trim().toLowerCase();
              if (name.isNotEmpty) recentNames.add(name);
            }
          }
        }
      } catch (_) {
        // Best-effort only.
      }
    }

    final filtered = candidates.where((r) {
      final id = r.recipeId.trim();
      if (id.isNotEmpty && recentIds.contains(id)) return false;
      final name = r.getLocalizedName('en').trim().toLowerCase();
      if (name.isNotEmpty && recentNames.contains(name)) return false;
      return true;
    }).toList();

    filtered.shuffle(Random(DateTime.now().microsecondsSinceEpoch));

    fireAndForget(MetricsService.instance.recordWorkflowStep('CookNow', 'Filter'));

    final options = (filtered.isNotEmpty ? filtered : candidates).take(maxOptions).toList();
    return options;
  }
}
