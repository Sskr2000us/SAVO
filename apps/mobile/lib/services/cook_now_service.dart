import '../models/planning.dart';
import '../models/profile_state.dart';
import 'api_client.dart';
import 'metrics_service.dart';
import 'dart:math';
import 'package:shared_preferences/shared_preferences.dart';

class CookNowService {
  static const String _prefsPlanningIncludeInactiveKey = 'savo.planning.include_inactive_inventory';
  static const String _prefsInventoryShowInactiveKey = 'savo.inventory.show_inactive_items';

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
  }) async {
    final body = <String, dynamic>{
      // Without meal_type, the backend may generate a full-day plan (slower).
      // Cook Now should be a single meal to keep latency low.
      'meal_type': _inferMealType(),
      'time_available_minutes': 45,
      'servings': 4,
    };

    // Reuse the inventory screen preference so Cook Now can consider older (inactive) pantry items.
    try {
      final prefs = await SharedPreferences.getInstance();
      final includeInactive = prefs.containsKey(_prefsPlanningIncludeInactiveKey)
          ? (prefs.getBool(_prefsPlanningIncludeInactiveKey) ?? false)
          : (prefs.getBool(_prefsInventoryShowInactiveKey) ?? false);
      if (includeInactive) {
        body['include_inactive_inventory'] = true;
      }
    } catch (_) {
      // Best-effort only
    }

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

    // Avoid forcing regeneration on every request.
    // On web, long-running forced generations can be cut off by upstream timeouts and surface as "Failed to fetch".
    Future<MenuPlanResponse> fetchPlan({required bool forceRegenerate}) async {
      final path = forceRegenerate ? '/plan/daily?force_regenerate=true' : '/plan/daily';
      final response = await apiClient.post(path, body);
      return MenuPlanResponse.fromJson(response);
    }

    var plan = await fetchPlan(forceRegenerate: false);

    // If the backend is asking for safety/profile clarification, surface that directly.
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

    // Provide variety without forcing a slow regeneration.
    // The backend returns multiple recipe options; shuffle before filtering/selection.
    candidates.shuffle(Random(DateTime.now().microsecondsSinceEpoch));

    // If we got an OK response but no recipes, the saved plan may be stale/missing fields.
    // Retry once with force_regenerate=true to rebuild a complete payload.
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
