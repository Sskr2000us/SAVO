import 'dart:io';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Service for pantry/fridge scanning with Vision AI
class ScanningService {
  final String baseUrl = const String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8000',
  );

  Future<Map<String, dynamic>> analyzeImage({
    required File imageFile,
    required String scanType,
    String? locationHint,
  }) async {
    try {
      // Get auth token
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString('access_token');

      if (token == null) {
        return {
          'success': false,
          'error': 'Not authenticated. Please log in.',
        };
      }

      // Create multipart request
      final uri = Uri.parse('$baseUrl/api/scanning/analyze-image');
      final request = http.MultipartRequest('POST', uri);

      // Add headers
      request.headers['Authorization'] = 'Bearer $token';

      // Add image file
      final imageBytes = await imageFile.readAsBytes();
      final multipartFile = http.MultipartFile.fromBytes(
        'image',
        imageBytes,
        filename: 'scan.jpg',
        contentType: MediaType('image', 'jpeg'),
      );
      request.files.add(multipartFile);

      // Add form fields
      request.fields['scan_type'] = scanType;
      if (locationHint != null && locationHint.isNotEmpty) {
        request.fields['location_hint'] = locationHint;
      }

      // Send request
      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        return {
          'success': true,
          'scan_id': data['scan_id'],
          'ingredients': data['ingredients'],
          'metadata': data['metadata'],
          'requires_confirmation': data['requires_confirmation'],
          'message': data['message'],
        };
      } else {
        final error = json.decode(response.body);
        return {
          'success': false,
          'error': error['detail'] ?? 'Analysis failed',
        };
      }
    } catch (e) {
      return {
        'success': false,
        'error': 'Network error: $e',
      };
    }
  }

  Future<Map<String, dynamic>> confirmIngredients({
    required String scanId,
    required List<Map<String, dynamic>> confirmations,
  }) async {
    try {
      // Get auth token
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString('access_token');

      if (token == null) {
        return {
          'success': false,
          'error': 'Not authenticated. Please log in.',
        };
      }

      // Send request
      final uri = Uri.parse('$baseUrl/api/scanning/confirm-ingredients');
      final response = await http.post(
        uri,
        headers: {
          'Authorization': 'Bearer $token',
          'Content-Type': 'application/json',
        },
        body: json.encode({
          'scan_id': scanId,
          'confirmations': confirmations,
        }),
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        return {
          'success': true,
          'confirmed_count': data['confirmed_count'],
          'rejected_count': data['rejected_count'],
          'modified_count': data['modified_count'],
          'pantry_items_added': data['pantry_items_added'],
          'message': data['message'],
        };
      } else {
        final error = json.decode(response.body);
        return {
          'success': false,
          'error': error['detail'] ?? 'Confirmation failed',
        };
      }
    } catch (e) {
      return {
        'success': false,
        'error': 'Network error: $e',
      };
    }
  }

  Future<Map<String, dynamic>> getScanHistory({
    int limit = 20,
    int offset = 0,
  }) async {
    try {
      // Get auth token
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString('access_token');

      if (token == null) {
        return {
          'success': false,
          'error': 'Not authenticated. Please log in.',
        };
      }

      // Send request
      final uri = Uri.parse(
        '$baseUrl/api/scanning/history?limit=$limit&offset=$offset',
      );
      final response = await http.get(
        uri,
        headers: {
          'Authorization': 'Bearer $token',
        },
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        return {
          'success': true,
          'scans': data['scans'],
          'total_scans': data['total_scans'],
          'accuracy_stats': data['accuracy_stats'],
        };
      } else {
        final error = json.decode(response.body);
        return {
          'success': false,
          'error': error['detail'] ?? 'Failed to get history',
        };
      }
    } catch (e) {
      return {
        'success': false,
        'error': 'Network error: $e',
      };
    }
  }

  Future<Map<String, dynamic>> getPantry() async {
    try {
      // Get auth token
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString('access_token');

      if (token == null) {
        return {
          'success': false,
          'error': 'Not authenticated. Please log in.',
        };
      }

      // Send request
      final uri = Uri.parse('$baseUrl/api/scanning/pantry');
      final response = await http.get(
        uri,
        headers: {
          'Authorization': 'Bearer $token',
        },
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        return {
          'success': true,
          'pantry': data['pantry'],
          'total_items': data['total_items'],
        };
      } else {
        final error = json.decode(response.body);
        return {
          'success': false,
          'error': error['detail'] ?? 'Failed to get pantry',
        };
      }
    } catch (e) {
      return {
        'success': false,
        'error': 'Network error: $e',
      };
    }
  }

  Future<Map<String, dynamic>> removeFromPantry(String ingredientName) async {
    try {
      // Get auth token
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString('access_token');

      if (token == null) {
        return {
          'success': false,
          'error': 'Not authenticated. Please log in.',
        };
      }

      // Send request
      final uri = Uri.parse('$baseUrl/api/scanning/pantry/$ingredientName');
      final response = await http.delete(
        uri,
        headers: {
          'Authorization': 'Bearer $token',
        },
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        return {
          'success': true,
          'message': data['message'],
        };
      } else {
        final error = json.decode(response.body);
        return {
          'success': false,
          'error': error['detail'] ?? 'Failed to remove from pantry',
        };
      }
    } catch (e) {
      return {
        'success': false,
        'error': 'Network error: $e',
      };
    }
  }

  Future<Map<String, dynamic>> manualAddIngredient({
    required String ingredientName,
    required double quantity,
    required String unit,
  }) async {
    try {
      // Get auth token
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString('access_token');

      if (token == null) {
        return {
          'success': false,
          'error': 'Not authenticated. Please log in.',
        };
      }

      // Send request
      final uri = Uri.parse('$baseUrl/api/scanning/manual');
      final response = await http.post(
        uri,
        headers: {
          'Authorization': 'Bearer $token',
          'Content-Type': 'application/json',
        },
        body: json.encode({
          'ingredient_name': ingredientName,
          'quantity': quantity,
          'unit': unit,
        }),
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        return {
          'success': true,
          'action': data['action'],
          'ingredient': data['ingredient'],
          'quantity': data['quantity'],
          'unit': data['unit'],
          'message': data['message'],
        };
      } else {
        final error = json.decode(response.body);
        return {
          'success': false,
          'error': error['detail'] ?? 'Failed to add ingredient',
        };
      }
    } catch (e) {
      return {
        'success': false,
        'error': 'Network error: $e',
      };
    }
  }

  Future<Map<String, dynamic>> checkSufficiency({
    required String recipeId,
    required int servings,
  }) async {
    try {
      // Get auth token
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString('access_token');

      if (token == null) {
        return {
          'success': false,
          'error': 'Not authenticated. Please log in.',
        };
      }

      // Send request
      final uri = Uri.parse('$baseUrl/api/scanning/check-sufficiency');
      final response = await http.post(
        uri,
        headers: {
          'Authorization': 'Bearer $token',
          'Content-Type': 'application/json',
        },
        body: json.encode({
          'recipe_id': recipeId,
          'servings': servings,
        }),
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        return {
          'success': true,
          'sufficient': data['sufficient'],
          'missing': data['missing'] ?? [],
          'surplus': data['surplus'] ?? [],
          'shopping_list': data['shopping_list'] ?? [],
          'message': data['message'],
        };
      } else {
        final error = json.decode(response.body);
        return {
          'success': false,
          'error': error['detail'] ?? 'Failed to check sufficiency',
        };
      }
    } catch (e) {
      return {
        'success': false,
        'error': 'Network error: $e',
      };
    }
  }

  Future<Map<String, dynamic>> submitFeedback({
    required String scanId,
    String? detectedId,
    required String feedbackType,
    String? detectedName,
    String? correctName,
    int? overallRating,
    int? accuracyRating,
    int? speedRating,
    String? comment,
  }) async {
    try {
      // Get auth token
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString('access_token');

      if (token == null) {
        return {
          'success': false,
          'error': 'Not authenticated. Please log in.',
        };
      }

      // Build request body
      final body = {
        'scan_id': scanId,
        'feedback_type': feedbackType,
      };

      if (detectedId != null) body['detected_id'] = detectedId;
      if (detectedName != null) body['detected_name'] = detectedName;
      if (correctName != null) body['correct_name'] = correctName;
      if (overallRating != null) body['overall_rating'] = overallRating.toString();
      if (accuracyRating != null) body['accuracy_rating'] = accuracyRating.toString();
      if (speedRating != null) body['speed_rating'] = speedRating.toString();
      if (comment != null) body['comment'] = comment;

      // Send request
      final uri = Uri.parse('$baseUrl/api/scanning/feedback');
      final response = await http.post(
        uri,
        headers: {
          'Authorization': 'Bearer $token',
          'Content-Type': 'application/json',
        },
        body: json.encode(body),
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        return {
          'success': true,
          'message': data['message'],
        };
      } else {
        final error = json.decode(response.body);
        return {
          'success': false,
          'error': error['detail'] ?? 'Failed to submit feedback',
        };
      }
    } catch (e) {
      return {
        'success': false,
        'error': 'Network error: $e',
      };
    }
  }
}
