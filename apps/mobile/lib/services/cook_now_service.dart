import '../models/planning.dart';
import '../models/profile_state.dart';
import 'api_client.dart';
import 'metrics_service.dart';

class CookNowService {
  Future<List<Recipe>> generateRecipeOptions({
    required ApiClient apiClient,
    required ProfileState profileState,
    int maxOptions = 5,
    int avoidRecentRecipes = 3,
  }) async {
    final body = <String, dynamic>{
      'time_available_minutes': 45,
      'servings': 4,
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

    // Avoid forcing regeneration on every request.
    // On web, long-running forced generations can be cut off by upstream timeouts and surface as "Failed to fetch".
    final response = await apiClient.post('/plan/daily', body);
    final plan = MenuPlanResponse.fromJson(response);

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

    final candidates = byId.values.toList();
    if (candidates.isEmpty) return const [];

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

    fireAndForget(MetricsService.instance.recordWorkflowStep('CookNow', 'Filter'));

    final options = (filtered.isNotEmpty ? filtered : candidates).take(maxOptions).toList();
    return options;
  }
}
