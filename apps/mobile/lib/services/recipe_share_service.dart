import '../models/planning.dart';
import 'api_client.dart';

class RecipeShareService {
  Future<String> createShare(ApiClient apiClient, Recipe recipe, {int expiresHours = 24 * 7}) async {
    final result = await apiClient.post('/recipes/share', {
      'recipe': _recipeToJson(recipe),
      'expires_hours': expiresHours,
    });

    if (result['success'] == true && (result['share_id'] ?? '').toString().isNotEmpty) {
      return result['share_id'].toString();
    }

    throw Exception('Failed to create share link');
  }

  Future<Map<String, dynamic>> fetchShared(ApiClient apiClient, String shareId) async {
    final result = await apiClient.get(
      '/recipes/shared/$shareId',
      headers: const {'Authorization': ''},
    );

    if (result is Map<String, dynamic> && result['success'] == true) {
      return result;
    }

    throw Exception('Failed to load shared recipe');
  }

  Future<void> revokeShare(ApiClient apiClient, String shareId) async {
    await apiClient.delete('/recipes/shared/$shareId');
  }

  Map<String, dynamic> _recipeToJson(Recipe recipe) {
    return {
      'recipe_id': recipe.recipeId,
      'recipe_name': recipe.recipeName,
      'cuisine': recipe.cuisine,
      'difficulty': recipe.difficulty,
      'estimated_times': {
        'prep_minutes': recipe.estimatedTimes.prepMinutes,
        'cook_minutes': recipe.estimatedTimes.cookMinutes,
        'total_minutes': recipe.estimatedTimes.totalMinutes,
      },
      'cooking_method': recipe.cookingMethod,
      'ingredients_used': recipe.ingredientsUsed
          .map((i) => {
                'inventory_id': i.inventoryId,
                'canonical_name': i.canonicalName,
                'amount': i.amount,
                'unit': i.unit,
              })
          .toList(),
      'steps': recipe.steps
          .map((s) => {
                'step': s.step,
                'instruction': s.instruction,
                'time_minutes': s.timeMinutes,
                'tips': s.tips,
              })
          .toList(),
      'nutrition_per_serving': recipe.nutritionPerServing,
      'health_benefits': recipe.healthBenefits,
      'leftover_forecast': recipe.leftoverForecast,
      'youtube_references': recipe.youtubeReferences
          .map((v) => {
                'video_id': v.videoId,
                'title': v.title,
                'channel': v.channel,
                'trust_score': v.trustScore,
              })
          .toList(),
    };
  }
}
