import 'dart:convert';
import 'package:http/http.dart' as http;

/// Regional Intelligence Service
/// Handles regional variants, cuisine recommendations, and cultural context
class RegionalIntelligenceService {
  final String baseUrl;
  final http.Client client;

  RegionalIntelligenceService({
    required this.baseUrl,
    http.Client? client,
  }) : client = client ?? http.Client();

  // ============================================================================
  // Data Models
  // ============================================================================

  /// Regional variant of an ingredient
  class RegionalVariant {
    final String variantId;
    final String ingredientName;
    final String region;
    final String countryCode;
    final String? variantNotes;
    final String? flavorDifferences;
    final String? appearanceDifferences;
    final String? typicalUses;
    final bool isNative;
    final String availabilityLevel;

    RegionalVariant({
      required this.variantId,
      required this.ingredientName,
      required this.region,
      required this.countryCode,
      this.variantNotes,
      this.flavorDifferences,
      this.appearanceDifferences,
      this.typicalUses,
      required this.isNative,
      required this.availabilityLevel,
    });

    factory RegionalVariant.fromJson(Map<String, dynamic> json) {
      return RegionalVariant(
        variantId: json['variant_id'],
        ingredientName: json['ingredient_name'],
        region: json['region'],
        countryCode: json['country_code'],
        variantNotes: json['variant_notes'],
        flavorDifferences: json['flavor_differences'],
        appearanceDifferences: json['appearance_differences'],
        typicalUses: json['typical_uses'],
        isNative: json['is_native'],
        availabilityLevel: json['availability_level'],
      );
    }

    /// Get availability emoji
    String get availabilityEmoji {
      switch (availabilityLevel) {
        case 'abundant':
          return '🌟';
        case 'common':
          return '✅';
        case 'rare':
          return '⚠️';
        default:
          return '❓';
      }
    }

    /// Get native indicator
    String get nativeIndicator {
      return isNative ? '🏠 Native' : '🌍 Imported';
    }
  }

  /// Cuisine recommendations response
  class CuisineRecommendations {
    final String cuisineType;
    final String? userRegion;
    final Map<String, List<IngredientRecommendation>> recommendationsByCategory;
    final int totalIngredients;

    CuisineRecommendations({
      required this.cuisineType,
      this.userRegion,
      required this.recommendationsByCategory,
      required this.totalIngredients,
    });

    factory CuisineRecommendations.fromJson(Map<String, dynamic> json) {
      final Map<String, List<IngredientRecommendation>> recommendations = {};

      if (json['recommendations_by_category'] != null) {
        (json['recommendations_by_category'] as Map<String, dynamic>)
            .forEach((category, ingredients) {
          recommendations[category] = (ingredients as List)
              .map((i) => IngredientRecommendation.fromJson(i))
              .toList();
        });
      }

      return CuisineRecommendations(
        cuisineType: json['cuisine_type'],
        userRegion: json['user_region'],
        recommendationsByCategory: recommendations,
        totalIngredients: json['total_ingredients'],
      );
    }

    /// Get flat list of all recommendations
    List<IngredientRecommendation> get allRecommendations {
      return recommendationsByCategory.values.expand((list) => list).toList();
    }

    /// Get categories
    List<String> get categories {
      return recommendationsByCategory.keys.toList();
    }
  }

  /// Ingredient recommendation
  class IngredientRecommendation {
    final String id;
    final String canonicalName;
    final String? subcategory;
    final Map<String, dynamic>? names;
    final List<String>? commonUses;
    final Map<String, dynamic>? tasteProfile;
    final String availability;
    final bool isNative;
    final int pairingCount;

    IngredientRecommendation({
      required this.id,
      required this.canonicalName,
      this.subcategory,
      this.names,
      this.commonUses,
      this.tasteProfile,
      required this.availability,
      required this.isNative,
      required this.pairingCount,
    });

    factory IngredientRecommendation.fromJson(Map<String, dynamic> json) {
      return IngredientRecommendation(
        id: json['id'],
        canonicalName: json['canonical_name'],
        subcategory: json['subcategory'],
        names: json['names'],
        commonUses: json['common_uses'] != null
            ? List<String>.from(json['common_uses'])
            : null,
        tasteProfile: json['taste_profile'],
        availability: json['availability'],
        isNative: json['is_native'],
        pairingCount: json['pairing_count'],
      );
    }

    /// Get popularity indicator
    String get popularityIndicator {
      if (pairingCount >= 10) return '⭐⭐⭐ Very Popular';
      if (pairingCount >= 5) return '⭐⭐ Popular';
      return '⭐ Common';
    }
  }

  /// Cultural context for an ingredient
  class CulturalContext {
    final String ingredientId;
    final String ingredientName;
    final String category;
    final Map<String, dynamic>? multiLanguageNames;
    final List<String>? commonUses;
    final Map<String, dynamic>? tasteProfile;
    final List<RegionalVariant> regionalVariants;
    final Map<String, List<CulturalPairing>> culturalPairings;
    final String? cuisineFilter;

    CulturalContext({
      required this.ingredientId,
      required this.ingredientName,
      required this.category,
      this.multiLanguageNames,
      this.commonUses,
      this.tasteProfile,
      required this.regionalVariants,
      required this.culturalPairings,
      this.cuisineFilter,
    });

    factory CulturalContext.fromJson(Map<String, dynamic> json) {
      final Map<String, List<CulturalPairing>> pairings = {};

      if (json['cultural_pairings'] != null) {
        (json['cultural_pairings'] as Map<String, dynamic>)
            .forEach((cuisine, pairingList) {
          pairings[cuisine] = (pairingList as List)
              .map((p) => CulturalPairing.fromJson(p))
              .toList();
        });
      }

      return CulturalContext(
        ingredientId: json['ingredient_id'],
        ingredientName: json['ingredient_name'],
        category: json['category'],
        multiLanguageNames: json['multi_language_names'],
        commonUses: json['common_uses'] != null
            ? List<String>.from(json['common_uses'])
            : null,
        tasteProfile: json['taste_profile'],
        regionalVariants: json['regional_variants'] != null
            ? (json['regional_variants'] as List)
                .map((v) => RegionalVariant.fromJson(v))
                .toList()
            : [],
        culturalPairings: pairings,
        cuisineFilter: json['cuisine_filter'],
      );
    }

    /// Get cuisines
    List<String> get cuisines {
      return culturalPairings.keys.toList();
    }

    /// Get total pairings count
    int get totalPairings {
      return culturalPairings.values
          .fold(0, (sum, list) => sum + list.length);
    }
  }

  /// Cultural pairing information
  class CulturalPairing {
    final String pairedIngredient;
    final List<String>? dishTypes;
    final String? pairingType;

    CulturalPairing({
      required this.pairedIngredient,
      this.dishTypes,
      this.pairingType,
    });

    factory CulturalPairing.fromJson(Map<String, dynamic> json) {
      return CulturalPairing(
        pairedIngredient: json['paired_ingredient'],
        dishTypes: json['dish_types'] != null
            ? List<String>.from(json['dish_types'])
            : null,
        pairingType: json['pairing_type'],
      );
    }

    /// Get pairing type emoji
    String get pairingTypeEmoji {
      switch (pairingType) {
        case 'complementary':
          return '🤝';
        case 'flavor_enhancer':
          return '✨';
        case 'traditional':
          return '📜';
        default:
          return '🔗';
      }
    }
  }

  /// Seasonal availability information
  class SeasonalAvailability {
    final String ingredientName;
    final String category;
    final int month;
    final String season;
    final String availabilityStatus;
    final String availabilityNotes;
    final List<RegionalAvailability> regionalAvailability;
    final String? bestSeason;
    final String? sourcingRecommendation;

    SeasonalAvailability({
      required this.ingredientName,
      required this.category,
      required this.month,
      required this.season,
      required this.availabilityStatus,
      required this.availabilityNotes,
      required this.regionalAvailability,
      this.bestSeason,
      this.sourcingRecommendation,
    });

    factory SeasonalAvailability.fromJson(Map<String, dynamic> json) {
      return SeasonalAvailability(
        ingredientName: json['ingredient_name'],
        category: json['category'],
        month: json['month'],
        season: json['season'],
        availabilityStatus: json['availability_status'],
        availabilityNotes: json['availability_notes'],
        regionalAvailability: json['regional_availability'] != null
            ? (json['regional_availability'] as List)
                .map((r) => RegionalAvailability.fromJson(r))
                .toList()
            : [],
        bestSeason: json['best_season'],
        sourcingRecommendation: json['sourcing_recommendation'],
      );
    }

    /// Get status emoji
    String get statusEmoji {
      switch (availabilityStatus) {
        case 'in_season':
          return '🌱';
        case 'year_round':
          return '🔄';
        case 'off_season':
          return '❄️';
        case 'seasonal':
          return '📅';
        default:
          return '❓';
      }
    }

    /// Is currently in peak season?
    bool get isInPeakSeason {
      return availabilityStatus == 'in_season';
    }
  }

  /// Regional availability details
  class RegionalAvailability {
    final String region;
    final String countryCode;
    final String availabilityLevel;
    final bool isNative;
    final String? notes;

    RegionalAvailability({
      required this.region,
      required this.countryCode,
      required this.availabilityLevel,
      required this.isNative,
      this.notes,
    });

    factory RegionalAvailability.fromJson(Map<String, dynamic> json) {
      return RegionalAvailability(
        region: json['region'],
        countryCode: json['country_code'],
        availabilityLevel: json['availability_level'],
        isNative: json['is_native'],
        notes: json['notes'],
      );
    }
  }

  /// Local sourcing suggestions
  class LocalSourcingSuggestions {
    final String userRegion;
    final int month;
    final List<SourcingIngredient> localAvailable;
    final List<SourcingIngredient> seasonalAvailable;
    final List<SourcingIngredient> importedAvailable;
    final SourcingSummary summary;
    final List<String> recommendations;

    LocalSourcingSuggestions({
      required this.userRegion,
      required this.month,
      required this.localAvailable,
      required this.seasonalAvailable,
      required this.importedAvailable,
      required this.summary,
      required this.recommendations,
    });

    factory LocalSourcingSuggestions.fromJson(Map<String, dynamic> json) {
      return LocalSourcingSuggestions(
        userRegion: json['user_region'],
        month: json['month'],
        localAvailable: json['local_available'] != null
            ? (json['local_available'] as List)
                .map((i) => SourcingIngredient.fromJson(i))
                .toList()
            : [],
        seasonalAvailable: json['seasonal_available'] != null
            ? (json['seasonal_available'] as List)
                .map((i) => SourcingIngredient.fromJson(i))
                .toList()
            : [],
        importedAvailable: json['imported_available'] != null
            ? (json['imported_available'] as List)
                .map((i) => SourcingIngredient.fromJson(i))
                .toList()
            : [],
        summary: SourcingSummary.fromJson(json['summary']),
        recommendations:
            json['recommendations'] != null
                ? List<String>.from(json['recommendations'])
                : [],
      );
    }

    /// Get local sourcing percentage
    double get localPercentage {
      if (summary.totalIngredients == 0) return 0.0;
      return (summary.localCount / summary.totalIngredients * 100);
    }

    /// Get sustainability rating
    String get sustainabilityRating {
      final percentage = localPercentage;
      if (percentage >= 70) return '🏆 Excellent';
      if (percentage >= 50) return '👍 Good';
      if (percentage >= 30) return '😐 Fair';
      return '⚠️ Poor';
    }
  }

  /// Sourcing ingredient details
  class SourcingIngredient {
    final String id;
    final String name;
    final String category;
    final Map<String, dynamic>? names;
    final String availability;
    final String? sourcing;
    final String? notes;
    final String? seasonNotes;

    SourcingIngredient({
      required this.id,
      required this.name,
      required this.category,
      this.names,
      required this.availability,
      this.sourcing,
      this.notes,
      this.seasonNotes,
    });

    factory SourcingIngredient.fromJson(Map<String, dynamic> json) {
      return SourcingIngredient(
        id: json['id'],
        name: json['name'],
        category: json['category'],
        names: json['names'],
        availability: json['availability'],
        sourcing: json['sourcing'],
        notes: json['notes'],
        seasonNotes: json['season_notes'],
      );
    }

    /// Get sourcing emoji
    String get sourcingEmoji {
      if (sourcing == 'imported') return '📦';
      if (availability == 'seasonal') return '🌱';
      return '🏪';
    }
  }

  /// Sourcing summary
  class SourcingSummary {
    final int localCount;
    final int seasonalCount;
    final int importedCount;
    final int totalIngredients;

    SourcingSummary({
      required this.localCount,
      required this.seasonalCount,
      required this.importedCount,
      required this.totalIngredients,
    });

    factory SourcingSummary.fromJson(Map<String, dynamic> json) {
      return SourcingSummary(
        localCount: json['local_count'],
        seasonalCount: json['seasonal_count'],
        importedCount: json['imported_count'],
        totalIngredients: json['total_ingredients'],
      );
    }
  }

  /// Cuisine comparison result
  class CuisineComparison {
    final List<String> cuisinesCompared;
    final Map<String, List<CuisineIngredient>> cuisineSpecificIngredients;
    final List<CommonIngredient> commonIngredients;
    final int totalCommon;

    CuisineComparison({
      required this.cuisinesCompared,
      required this.cuisineSpecificIngredients,
      required this.commonIngredients,
      required this.totalCommon,
    });

    factory CuisineComparison.fromJson(Map<String, dynamic> json) {
      final Map<String, List<CuisineIngredient>> specific = {};

      if (json['cuisine_specific_ingredients'] != null) {
        (json['cuisine_specific_ingredients'] as Map<String, dynamic>)
            .forEach((cuisine, ingredients) {
          specific[cuisine] = (ingredients as List)
              .map((i) => CuisineIngredient.fromJson(i))
              .toList();
        });
      }

      return CuisineComparison(
        cuisinesCompared:
            json['cuisines_compared'] != null
                ? List<String>.from(json['cuisines_compared'])
                : [],
        cuisineSpecificIngredients: specific,
        commonIngredients: json['common_ingredients'] != null
            ? (json['common_ingredients'] as List)
                .map((c) => CommonIngredient.fromJson(c))
                .toList()
            : [],
        totalCommon: json['total_common'] ?? 0,
      );
    }
  }

  /// Cuisine-specific ingredient
  class CuisineIngredient {
    final String ingredient;
    final String category;
    final int frequency;

    CuisineIngredient({
      required this.ingredient,
      required this.category,
      required this.frequency,
    });

    factory CuisineIngredient.fromJson(Map<String, dynamic> json) {
      return CuisineIngredient(
        ingredient: json['ingredient'],
        category: json['category'],
        frequency: json['frequency'],
      );
    }
  }

  /// Common ingredient across cuisines
  class CommonIngredient {
    final String ingredient;
    final List<String> cuisines;
    final int commonality;

    CommonIngredient({
      required this.ingredient,
      required this.cuisines,
      required this.commonality,
    });

    factory CommonIngredient.fromJson(Map<String, dynamic> json) {
      return CommonIngredient(
        ingredient: json['ingredient'],
        cuisines:
            json['cuisines'] != null ? List<String>.from(json['cuisines']) : [],
        commonality: json['commonality'],
      );
    }

    /// Get commonality indicator
    String get commonalityIndicator {
      if (commonality >= 4) return '🌍 Universal';
      if (commonality >= 3) return '🌏 Very Common';
      return '🔗 Common';
    }
  }

  // ============================================================================
  // API Methods
  // ============================================================================

  /// Get regional variants of an ingredient
  Future<List<RegionalVariant>> getRegionalVariants(
    String ingredientId, {
    String? userRegion,
  }) async {
    try {
      final uri = Uri.parse('$baseUrl/api/regional/variants/$ingredientId')
          .replace(
        queryParameters:
            userRegion != null ? {'user_region': userRegion} : null,
      );

      final response = await client.get(uri);

      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        return data.map((v) => RegionalVariant.fromJson(v)).toList();
      } else if (response.statusCode == 404) {
        return [];
      } else {
        throw Exception('Failed to get regional variants: ${response.body}');
      }
    } catch (e) {
      print('Error getting regional variants: $e');
      rethrow;
    }
  }

  /// Get cuisine-specific recommendations
  Future<CuisineRecommendations> getCuisineRecommendations(
    String cuisineType, {
    String? userRegion,
    int limit = 20,
  }) async {
    try {
      final response = await client.post(
        Uri.parse('$baseUrl/api/regional/cuisine-recommendations'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'cuisine_type': cuisineType,
          if (userRegion != null) 'user_region': userRegion,
          'limit': limit,
        }),
      );

      if (response.statusCode == 200) {
        return CuisineRecommendations.fromJson(json.decode(response.body));
      } else {
        throw Exception(
            'Failed to get cuisine recommendations: ${response.body}');
      }
    } catch (e) {
      print('Error getting cuisine recommendations: $e');
      rethrow;
    }
  }

  /// Get cultural context for an ingredient
  Future<CulturalContext> getCulturalContext(
    String ingredientId, {
    String? cuisineType,
  }) async {
    try {
      final uri =
          Uri.parse('$baseUrl/api/regional/cultural-context/$ingredientId')
              .replace(
        queryParameters:
            cuisineType != null ? {'cuisine_type': cuisineType} : null,
      );

      final response = await client.get(uri);

      if (response.statusCode == 200) {
        return CulturalContext.fromJson(json.decode(response.body));
      } else {
        throw Exception('Failed to get cultural context: ${response.body}');
      }
    } catch (e) {
      print('Error getting cultural context: $e');
      rethrow;
    }
  }

  /// Check seasonal availability
  Future<SeasonalAvailability> checkSeasonalAvailability(
    String ingredientId, {
    String? region,
    int? month,
  }) async {
    try {
      final response = await client.post(
        Uri.parse('$baseUrl/api/regional/seasonal-availability'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'ingredient_id': ingredientId,
          if (region != null) 'region': region,
          if (month != null) 'month': month,
        }),
      );

      if (response.statusCode == 200) {
        return SeasonalAvailability.fromJson(json.decode(response.body));
      } else {
        throw Exception(
            'Failed to check seasonal availability: ${response.body}');
      }
    } catch (e) {
      print('Error checking seasonal availability: $e');
      rethrow;
    }
  }

  /// Get local sourcing suggestions
  Future<LocalSourcingSuggestions> getLocalSourcingSuggestions(
    List<String> ingredientIds,
    String userRegion, {
    int? currentMonth,
  }) async {
    try {
      final response = await client.post(
        Uri.parse('$baseUrl/api/regional/local-sourcing'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'ingredient_ids': ingredientIds,
          'user_region': userRegion,
          if (currentMonth != null) 'current_month': currentMonth,
        }),
      );

      if (response.statusCode == 200) {
        return LocalSourcingSuggestions.fromJson(json.decode(response.body));
      } else {
        throw Exception(
            'Failed to get sourcing suggestions: ${response.body}');
      }
    } catch (e) {
      print('Error getting sourcing suggestions: $e');
      rethrow;
    }
  }

  /// Compare regional cuisines
  Future<CuisineComparison> compareCuisines(
    List<String> cuisineTypes, {
    int limit = 10,
  }) async {
    try {
      final response = await client.post(
        Uri.parse('$baseUrl/api/regional/compare-cuisines'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'cuisine_types': cuisineTypes,
          'limit': limit,
        }),
      );

      if (response.statusCode == 200) {
        return CuisineComparison.fromJson(json.decode(response.body));
      } else {
        throw Exception('Failed to compare cuisines: ${response.body}');
      }
    } catch (e) {
      print('Error comparing cuisines: $e');
      rethrow;
    }
  }

  /// Get supported cuisines
  Future<List<String>> getSupportedCuisines() async {
    try {
      final response =
          await client.get(Uri.parse('$baseUrl/api/regional/supported-cuisines'));

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        return List<String>.from(data['supported_cuisines']);
      } else {
        throw Exception('Failed to get supported cuisines: ${response.body}');
      }
    } catch (e) {
      print('Error getting supported cuisines: $e');
      rethrow;
    }
  }

  /// Get supported regions
  Future<List<Map<String, dynamic>>> getSupportedRegions() async {
    try {
      final response =
          await client.get(Uri.parse('$baseUrl/api/regional/supported-regions'));

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        return List<Map<String, dynamic>>.from(data['supported_regions']);
      } else {
        throw Exception('Failed to get supported regions: ${response.body}');
      }
    } catch (e) {
      print('Error getting supported regions: $e');
      rethrow;
    }
  }

  /// Health check
  Future<bool> checkHealth() async {
    try {
      final response =
          await client.get(Uri.parse('$baseUrl/api/regional/health'));
      return response.statusCode == 200;
    } catch (e) {
      print('Error checking health: $e');
      return false;
    }
  }

  /// Dispose resources
  void dispose() {
    client.close();
  }
}
