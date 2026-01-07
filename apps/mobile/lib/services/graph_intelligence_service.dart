"""
Graph Intelligence Service for Flutter Mobile App
Handles substitutions, confusions, pairings, and recipe compatibility
"""

import 'dart:convert';
import 'package:http/http.dart' as http;

class GraphIntelligenceService {
  final String baseUrl;
  
  GraphIntelligenceService({required this.baseUrl});
  
  /// Get substitution recommendations for an ingredient
  Future<SubstitutionResponse> getSubstitutions({
    required String ingredientId,
    SubstitutionContext? context,
    int limit = 10,
  }) async {
    final uri = Uri.parse('$baseUrl/api/graph/substitutions');
    
    final response = await http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: json.encode({
        'ingredient_id': ingredientId,
        if (context != null) 'context': context.toJson(),
        'limit': limit,
      }),
    );
    
    if (response.statusCode == 200) {
      return SubstitutionResponse.fromJson(json.decode(response.body));
    } else {
      throw Exception('Failed to get substitutions: ${response.statusCode}');
    }
  }
  
  /// Get substitutions (simple GET method)
  Future<SubstitutionResponse> getSubstitutionsSimple({
    required String ingredientId,
    int limit = 10,
    String? form,
    String? dishType,
  }) async {
    final queryParams = {
      'limit': limit.toString(),
      if (form != null) 'form': form,
      if (dishType != null) 'dish_type': dishType,
    };
    
    final uri = Uri.parse('$baseUrl/api/graph/substitutions/$ingredientId')
        .replace(queryParameters: queryParams);
    
    final response = await http.get(uri);
    
    if (response.statusCode == 200) {
      return SubstitutionResponse.fromJson(json.decode(response.body));
    } else {
      throw Exception('Failed to get substitutions: ${response.statusCode}');
    }
  }
  
  /// Disambiguate between commonly confused ingredients
  Future<ConfusionResult> resolveConfusion({
    required List<String> detectedIngredients,
    Map<String, dynamic>? visualFeatures,
    Map<String, dynamic>? userContext,
  }) async {
    final uri = Uri.parse('$baseUrl/api/graph/resolve-confusion');
    
    final response = await http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: json.encode({
        'detected_ingredients': detectedIngredients,
        if (visualFeatures != null) 'visual_features': visualFeatures,
        if (userContext != null) 'user_context': userContext,
      }),
    );
    
    if (response.statusCode == 200) {
      return ConfusionResult.fromJson(json.decode(response.body));
    } else {
      throw Exception('Failed to resolve confusion: ${response.statusCode}');
    }
  }
  
  /// Get complementary ingredient pairing suggestions
  Future<PairingsResponse> getPairings({
    required List<String> ingredientIds,
    String? cuisineType,
    String? dishType,
    int limit = 20,
  }) async {
    final uri = Uri.parse('$baseUrl/api/graph/pairings');
    
    final response = await http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: json.encode({
        'ingredient_ids': ingredientIds,
        if (cuisineType != null) 'cuisine_type': cuisineType,
        if (dishType != null) 'dish_type': dishType,
        'limit': limit,
      }),
    );
    
    if (response.statusCode == 200) {
      return PairingsResponse.fromJson(json.decode(response.body));
    } else {
      throw Exception('Failed to get pairings: ${response.statusCode}');
    }
  }
  
  /// Calculate recipe compatibility score
  Future<RecipeCompatibility> calculateRecipeCompatibility({
    required List<String> ingredientIds,
    String? cuisineType,
  }) async {
    final uri = Uri.parse('$baseUrl/api/graph/recipe-compatibility');
    
    final response = await http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: json.encode({
        'ingredient_ids': ingredientIds,
        if (cuisineType != null) 'cuisine_type': cuisineType,
      }),
    );
    
    if (response.statusCode == 200) {
      return RecipeCompatibility.fromJson(json.decode(response.body));
    } else {
      throw Exception('Failed to calculate compatibility: ${response.statusCode}');
    }
  }
  
  /// Optimize grocery shopping list
  Future<GroceryOptimization> optimizeGroceryList({
    required List<String> ingredientIds,
    List<String>? userInventory,
    double? budgetConstraint,
  }) async {
    final uri = Uri.parse('$baseUrl/api/graph/optimize-grocery-list');
    
    final response = await http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: json.encode({
        'ingredient_ids': ingredientIds,
        if (userInventory != null) 'user_inventory': userInventory,
        if (budgetConstraint != null) 'budget_constraint': budgetConstraint,
      }),
    );
    
    if (response.statusCode == 200) {
      return GroceryOptimization.fromJson(json.decode(response.body));
    } else {
      throw Exception('Failed to optimize grocery list: ${response.statusCode}');
    }
  }
  
  /// Record user feedback on substitution
  Future<void> recordSubstitutionFeedback({
    required String substitutionId,
    required bool wasAccepted,
    String? feedbackNote,
  }) async {
    final uri = Uri.parse('$baseUrl/api/graph/substitution-feedback');
    
    final response = await http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: json.encode({
        'substitution_id': substitutionId,
        'was_accepted': wasAccepted,
        if (feedbackNote != null) 'feedback_note': feedbackNote,
      }),
    );
    
    if (response.statusCode != 200) {
      throw Exception('Failed to record feedback: ${response.statusCode}');
    }
  }
  
  /// Health check
  Future<bool> checkHealth() async {
    try {
      final uri = Uri.parse('$baseUrl/api/graph/health');
      final response = await http.get(uri);
      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }
}

// ============================================================================
// DATA MODELS
// ============================================================================

class SubstitutionContext {
  final String? form;
  final String? dishType;
  final String? cuisine;
  final List<String>? dietaryRestrictions;
  
  SubstitutionContext({
    this.form,
    this.dishType,
    this.cuisine,
    this.dietaryRestrictions,
  });
  
  Map<String, dynamic> toJson() {
    return {
      if (form != null) 'form': form,
      if (dishType != null) 'dish_type': dishType,
      if (cuisine != null) 'cuisine': cuisine,
      if (dietaryRestrictions != null) 'dietary_restrictions': dietaryRestrictions,
    };
  }
}

class SubstitutionResponse {
  final String ingredientId;
  final Map<String, dynamic>? context;
  final List<Substitution> substitutions;
  final int count;
  
  SubstitutionResponse({
    required this.ingredientId,
    this.context,
    required this.substitutions,
    required this.count,
  });
  
  factory SubstitutionResponse.fromJson(Map<String, dynamic> json) {
    return SubstitutionResponse(
      ingredientId: json['ingredient_id'],
      context: json['context'],
      substitutions: (json['substitutions'] as List)
          .map((s) => Substitution.fromJson(s))
          .toList(),
      count: json['count'],
    );
  }
}

class Substitution {
  final String substitutionId;
  final String ingredientId;
  final String canonicalName;
  final String category;
  final Map<String, dynamic> names;
  final List<String>? tasteProfile;
  final List<String>? commonUses;
  final String substitutionType;
  final double similarityScore;
  final List<String>? applicableForms;
  final List<String>? applicableDishes;
  final String? notes;
  final double? userAcceptanceRate;
  final Map<String, dynamic>? usageStats;
  
  Substitution({
    required this.substitutionId,
    required this.ingredientId,
    required this.canonicalName,
    required this.category,
    required this.names,
    this.tasteProfile,
    this.commonUses,
    required this.substitutionType,
    required this.similarityScore,
    this.applicableForms,
    this.applicableDishes,
    this.notes,
    this.userAcceptanceRate,
    this.usageStats,
  });
  
  factory Substitution.fromJson(Map<String, dynamic> json) {
    return Substitution(
      substitutionId: json['substitution_id'],
      ingredientId: json['ingredient_id'],
      canonicalName: json['canonical_name'],
      category: json['category'],
      names: Map<String, dynamic>.from(json['names']),
      tasteProfile: json['taste_profile'] != null
          ? List<String>.from(json['taste_profile'])
          : null,
      commonUses: json['common_uses'] != null
          ? List<String>.from(json['common_uses'])
          : null,
      substitutionType: json['substitution_type'],
      similarityScore: json['similarity_score'].toDouble(),
      applicableForms: json['applicable_forms'] != null
          ? List<String>.from(json['applicable_forms'])
          : null,
      applicableDishes: json['applicable_dishes'] != null
          ? List<String>.from(json['applicable_dishes'])
          : null,
      notes: json['notes'],
      userAcceptanceRate: json['user_acceptance_rate']?.toDouble(),
      usageStats: json['usage_stats'],
    );
  }
  
  /// Get quality indicator for substitution
  String getQualityLevel() {
    if (similarityScore >= 0.9) return 'Excellent';
    if (similarityScore >= 0.75) return 'Good';
    if (similarityScore >= 0.6) return 'Fair';
    return 'Emergency Only';
  }
}

class ConfusionResult {
  final bool needsDisambiguation;
  final int detectedCount;
  final int? confusionPatterns;
  final List<ConfusionRecommendation>? recommendations;
  final String? message;
  
  ConfusionResult({
    required this.needsDisambiguation,
    required this.detectedCount,
    this.confusionPatterns,
    this.recommendations,
    this.message,
  });
  
  factory ConfusionResult.fromJson(Map<String, dynamic> json) {
    return ConfusionResult(
      needsDisambiguation: json['needs_disambiguation'],
      detectedCount: json['detected_count'],
      confusionPatterns: json['confusion_patterns'],
      recommendations: json['recommendations'] != null
          ? (json['recommendations'] as List)
              .map((r) => ConfusionRecommendation.fromJson(r))
              .toList()
          : null,
      message: json['message'],
    );
  }
}

class ConfusionRecommendation {
  final List<String> confusedPair;
  final String reason;
  final List<String> disambiguationTips;
  final List<String> visualDifferences;
  final String confidence;
  final String? matchedVisualClue;
  
  ConfusionRecommendation({
    required this.confusedPair,
    required this.reason,
    required this.disambiguationTips,
    required this.visualDifferences,
    required this.confidence,
    this.matchedVisualClue,
  });
  
  factory ConfusionRecommendation.fromJson(Map<String, dynamic> json) {
    return ConfusionRecommendation(
      confusedPair: List<String>.from(json['confused_pair']),
      reason: json['reason'],
      disambiguationTips: List<String>.from(json['disambiguation_tips']),
      visualDifferences: List<String>.from(json['visual_differences']),
      confidence: json['confidence'],
      matchedVisualClue: json['matched_visual_clue'],
    );
  }
}

class PairingsResponse {
  final List<String> inputIngredients;
  final String? cuisineType;
  final String? dishType;
  final List<IngredientPairing> pairings;
  final int count;
  
  PairingsResponse({
    required this.inputIngredients,
    this.cuisineType,
    this.dishType,
    required this.pairings,
    required this.count,
  });
  
  factory PairingsResponse.fromJson(Map<String, dynamic> json) {
    return PairingsResponse(
      inputIngredients: List<String>.from(json['input_ingredients']),
      cuisineType: json['cuisine_type'],
      dishType: json['dish_type'],
      pairings: (json['pairings'] as List)
          .map((p) => IngredientPairing.fromJson(p))
          .toList(),
      count: json['count'],
    );
  }
}

class IngredientPairing {
  final String pairingId;
  final String ingredientId;
  final String canonicalName;
  final String category;
  final Map<String, dynamic> names;
  final List<String>? tasteProfile;
  final double pairingScore;
  final String pairingType;
  final List<String> cuisineTypes;
  final List<String> dishTypes;
  final String source;
  final int timesUsedTogether;
  
  IngredientPairing({
    required this.pairingId,
    required this.ingredientId,
    required this.canonicalName,
    required this.category,
    required this.names,
    this.tasteProfile,
    required this.pairingScore,
    required this.pairingType,
    required this.cuisineTypes,
    required this.dishTypes,
    required this.source,
    required this.timesUsedTogether,
  });
  
  factory IngredientPairing.fromJson(Map<String, dynamic> json) {
    return IngredientPairing(
      pairingId: json['pairing_id'],
      ingredientId: json['ingredient_id'],
      canonicalName: json['canonical_name'],
      category: json['category'],
      names: Map<String, dynamic>.from(json['names']),
      tasteProfile: json['taste_profile'] != null
          ? List<String>.from(json['taste_profile'])
          : null,
      pairingScore: json['pairing_score'].toDouble(),
      pairingType: json['pairing_type'],
      cuisineTypes: List<String>.from(json['cuisine_types']),
      dishTypes: List<String>.from(json['dish_types']),
      source: json['source'],
      timesUsedTogether: json['times_used_together'],
    );
  }
  
  /// Get pairing strength indicator
  String getPairingStrength() {
    if (pairingScore >= 0.9) return 'Perfect Match';
    if (pairingScore >= 0.8) return 'Excellent';
    if (pairingScore >= 0.7) return 'Very Good';
    if (pairingScore >= 0.6) return 'Good';
    return 'Fair';
  }
}

class RecipeCompatibility {
  final double compatibilityScore;
  final String compatibilityLevel;
  final String confidence;
  final int ingredientCount;
  final int knownPairings;
  final List<PairingDetail> pairingDetails;
  
  RecipeCompatibility({
    required this.compatibilityScore,
    required this.compatibilityLevel,
    required this.confidence,
    required this.ingredientCount,
    required this.knownPairings,
    required this.pairingDetails,
  });
  
  factory RecipeCompatibility.fromJson(Map<String, dynamic> json) {
    return RecipeCompatibility(
      compatibilityScore: json['compatibility_score'].toDouble(),
      compatibilityLevel: json['compatibility_level'],
      confidence: json['confidence'],
      ingredientCount: json['ingredient_count'],
      knownPairings: json['known_pairings'],
      pairingDetails: (json['pairing_details'] as List)
          .map((p) => PairingDetail.fromJson(p))
          .toList(),
    );
  }
}

class PairingDetail {
  final List<String> ingredients;
  final double score;
  final String type;
  final List<String>? cuisines;
  
  PairingDetail({
    required this.ingredients,
    required this.score,
    required this.type,
    this.cuisines,
  });
  
  factory PairingDetail.fromJson(Map<String, dynamic> json) {
    return PairingDetail(
      ingredients: List<String>.from(json['ingredients']),
      score: json['score'].toDouble(),
      type: json['type'],
      cuisines: json['cuisines'] != null
          ? List<String>.from(json['cuisines'])
          : null,
    );
  }
}

class GroceryOptimization {
  final int totalIngredients;
  final int alreadyHave;
  final int needToBuy;
  final List<dynamic> itemsToBuy;
  final Map<String, dynamic> optimizations;
  final int? estimatedSavings;
  
  GroceryOptimization({
    required this.totalIngredients,
    required this.alreadyHave,
    required this.needToBuy,
    required this.itemsToBuy,
    required this.optimizations,
    this.estimatedSavings,
  });
  
  factory GroceryOptimization.fromJson(Map<String, dynamic> json) {
    return GroceryOptimization(
      totalIngredients: json['total_ingredients'],
      alreadyHave: json['already_have'],
      needToBuy: json['need_to_buy'],
      itemsToBuy: json['items_to_buy'],
      optimizations: json['optimizations'],
      estimatedSavings: json['estimated_savings'],
    );
  }
}
