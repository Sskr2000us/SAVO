import 'dart:io';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';

/// Visual Intelligence Service for ingredient identification
/// Connects to FastAPI backend for GPT-4 Vision powered identification
class VisualIntelligenceService {
  final String baseUrl;
  final String? authToken;
  
  VisualIntelligenceService({
    required this.baseUrl,
    this.authToken,
  });
  
  /// Identify ingredient from camera or gallery image
  Future<IdentificationResult> identifyIngredient(
    File imageFile, {
    String? userLocation,
    String? cuisinePreference,
  }) async {
    try {
      // Create multipart request
      var request = http.MultipartRequest(
        'POST',
        Uri.parse('$baseUrl/api/intelligence/identify-ingredient'),
      );
      
      // Add auth header if available
      if (authToken != null) {
        request.headers['Authorization'] = 'Bearer $authToken';
      }
      
      // Add context parameters
      if (userLocation != null) {
        request.fields['user_location'] = userLocation;
      }
      if (cuisinePreference != null) {
        request.fields['cuisine_preference'] = cuisinePreference;
      }
      
      // Add image file
      request.files.add(
        await http.MultipartFile.fromPath('file', imageFile.path),
      );
      
      // Send request
      var streamedResponse = await request.send();
      var response = await http.Response.fromStream(streamedResponse);
      
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        return IdentificationResult.fromJson(data);
      } else {
        throw Exception('Identification failed: ${response.body}');
      }
    } catch (e) {
      throw Exception('Failed to identify ingredient: $e');
    }
  }
  
  /// Extract visual features without identification
  Future<VisualFeatures> extractVisualFeatures(File imageFile) async {
    try {
      var request = http.MultipartRequest(
        'POST',
        Uri.parse('$baseUrl/api/intelligence/extract-visual-features'),
      );
      
      if (authToken != null) {
        request.headers['Authorization'] = 'Bearer $authToken';
      }
      
      request.files.add(
        await http.MultipartFile.fromPath('file', imageFile.path),
      );
      
      var streamedResponse = await request.send();
      var response = await http.Response.fromStream(streamedResponse);
      
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        return VisualFeatures.fromJson(data);
      } else {
        throw Exception('Feature extraction failed: ${response.body}');
      }
    } catch (e) {
      throw Exception('Failed to extract features: $e');
    }
  }
  
  /// Get visually similar ingredients
  Future<List<SimilarIngredient>> getSimilarIngredients(
    String ingredientId, {
    int limit = 10,
  }) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/api/intelligence/similar-ingredients/$ingredientId?limit=$limit'),
        headers: authToken != null ? {'Authorization': 'Bearer $authToken'} : {},
      );
      
      if (response.statusCode == 200) {
        final List data = json.decode(response.body);
        return data.map((json) => SimilarIngredient.fromJson(json)).toList();
      } else {
        throw Exception('Failed to get similar ingredients: ${response.body}');
      }
    } catch (e) {
      throw Exception('Failed to get similar ingredients: $e');
    }
  }
  
  /// Confirm or correct identification result
  Future<void> confirmIdentification({
    required String scanResultId,
    required String confirmedIngredientId,
    required bool wasCorrect,
    String? correctionReason,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/intelligence/confirm-identification'),
        headers: {
          'Content-Type': 'application/json',
          if (authToken != null) 'Authorization': 'Bearer $authToken',
        },
        body: json.encode({
          'scan_result_id': scanResultId,
          'confirmed_ingredient_id': confirmedIngredientId,
          'was_correct': wasCorrect,
          if (correctionReason != null) 'correction_reason': correctionReason,
        }),
      );
      
      if (response.statusCode != 200) {
        throw Exception('Failed to confirm identification: ${response.body}');
      }
    } catch (e) {
      throw Exception('Failed to confirm identification: $e');
    }
  }
}

/// Identification result from visual intelligence
class IdentificationResult {
  final List<IngredientMatch> topMatches;
  final VisualFeatures visualFeatures;
  final String detectedState;
  final double confidenceScore;
  final int processingTimeMs;
  final String modelVersion;
  
  IdentificationResult({
    required this.topMatches,
    required this.visualFeatures,
    required this.detectedState,
    required this.confidenceScore,
    required this.processingTimeMs,
    required this.modelVersion,
  });
  
  factory IdentificationResult.fromJson(Map<String, dynamic> json) {
    return IdentificationResult(
      topMatches: (json['top_matches'] as List)
          .map((m) => IngredientMatch.fromJson(m))
          .toList(),
      visualFeatures: VisualFeatures.fromJson(json['visual_features']),
      detectedState: json['detected_state'],
      confidenceScore: json['confidence_score'].toDouble(),
      processingTimeMs: json['processing_time_ms'],
      modelVersion: json['model_version'],
    );
  }
}

/// Single ingredient match
class IngredientMatch {
  final String ingredientId;
  final String canonicalName;
  final double confidence;
  final String reasoning;
  final double visualSimilarity;
  
  IngredientMatch({
    required this.ingredientId,
    required this.canonicalName,
    required this.confidence,
    required this.reasoning,
    required this.visualSimilarity,
  });
  
  factory IngredientMatch.fromJson(Map<String, dynamic> json) {
    return IngredientMatch(
      ingredientId: json['ingredient_id'],
      canonicalName: json['canonical_name'],
      confidence: json['confidence'].toDouble(),
      reasoning: json['reasoning'],
      visualSimilarity: json['visual_similarity'].toDouble(),
    );
  }
}

/// Visual features extracted from image
class VisualFeatures {
  final List<String> dominantColors;
  final Map<String, double> colorHistogram;
  final String textureDescription;
  final double brightness;
  final double contrast;
  
  VisualFeatures({
    required this.dominantColors,
    required this.colorHistogram,
    required this.textureDescription,
    required this.brightness,
    required this.contrast,
  });
  
  factory VisualFeatures.fromJson(Map<String, dynamic> json) {
    return VisualFeatures(
      dominantColors: List<String>.from(json['dominant_colors']),
      colorHistogram: Map<String, double>.from(
        json['color_histogram'].map((k, v) => MapEntry(k, v.toDouble())),
      ),
      textureDescription: json['texture_description'],
      brightness: json['brightness'].toDouble(),
      contrast: json['contrast'].toDouble(),
    );
  }
}

/// Similar ingredient result
class SimilarIngredient {
  final String ingredientId;
  final String canonicalName;
  final double similarityScore;
  final VisualFeatures visualFeatures;
  
  SimilarIngredient({
    required this.ingredientId,
    required this.canonicalName,
    required this.similarityScore,
    required this.visualFeatures,
  });
  
  factory SimilarIngredient.fromJson(Map<String, dynamic> json) {
    return SimilarIngredient(
      ingredientId: json['ingredient_id'],
      canonicalName: json['canonical_name'],
      similarityScore: json['similarity_score'].toDouble(),
      visualFeatures: VisualFeatures.fromJson(json['visual_features']),
    );
  }
}
