import 'dart:io';
import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../config/app_config.dart';
import 'pending_scan_sync_service.dart';

/// Service for pantry/fridge scanning with Vision AI
class ScanningService {
  final String baseUrl = Config.apiBaseUrl;

  String _canonicalizeName(String raw) {
    var s = raw.trim();
    s = s.replaceAll('_', ' ');
    s = s.replaceAll(RegExp(r'\s+'), ' ').trim();

    // Remove a few common packaging/marketing suffixes.
    s = s.replaceAll(RegExp(r'\b(organic|fresh|natural|premium|classic|original)\b', caseSensitive: false), ' ');
    s = s.replaceAll(RegExp(r'\s+'), ' ').trim();

    // Small, low-risk synonym unifications.
    final lower = s.toLowerCase();
    if (lower == 'scallion' || lower == 'scallions' || lower == 'spring onion' || lower == 'spring onions') {
      return 'green onion';
    }
    if (lower == 'garbanzo' || lower == 'garbanzo beans') {
      return 'chickpeas';
    }

    return s;
  }

  String _normalizeUnit(String? unit) {
    final u = (unit ?? '').trim().toLowerCase();
    if (u.isEmpty) return 'pieces';
    if (u == 'pc' || u == 'pcs' || u == 'piece') return 'pieces';
    if (u == 'g') return 'grams';
    if (u == 'l') return 'liters';
    return u;
  }

  Map<String, dynamic> _normalizeConfirmation(Map<String, dynamic> confirmation) {
    final out = Map<String, dynamic>.from(confirmation);
    final cn = out['confirmed_name'];
    if (cn is String) {
      out['confirmed_name'] = cn.trim();
    }

    final bc = out['barcode'];
    if (bc is String) {
      final trimmed = bc.trim();
      if (trimmed.isEmpty) {
        out.remove('barcode');
      } else {
        out['barcode'] = trimmed;
      }
    }

    final bcn = out['barcode_name_hint'];
    if (bcn is String) {
      final trimmed = bcn.trim();
      if (trimmed.isEmpty) {
        out.remove('barcode_name_hint');
      } else {
        out['barcode_name_hint'] = trimmed;
      }
    }

    final bcu = out['barcode_unit_hint'];
    if (bcu is String) {
      final trimmed = bcu.trim();
      if (trimmed.isEmpty) {
        out.remove('barcode_unit_hint');
      } else {
        out['barcode_unit_hint'] = _normalizeUnit(trimmed);
      }
    }

    final bcq = out['barcode_quantity_hint'];
    if (bcq is String) {
      final parsed = double.tryParse(bcq.trim());
      if (parsed == null || parsed <= 0) {
        out.remove('barcode_quantity_hint');
      } else {
        out['barcode_quantity_hint'] = parsed;
      }
    }
    final unit = out['unit'];
    if (unit is String) {
      out['unit'] = _normalizeUnit(unit);
    }
    return out;
  }

  Future<String?> _getAccessToken() async {
    final session = Supabase.instance.client.auth.currentSession;
    final existing = session?.accessToken;
    if (existing != null && existing.isNotEmpty) return existing;

    // Best-effort: if the session hasn't been restored yet (common on web reload)
    // or the token expired, try a refresh.
    try {
      final res = await Supabase.instance.client.auth.refreshSession();
      final refreshed = res.session?.accessToken;
      if (refreshed != null && refreshed.isNotEmpty) return refreshed;
    } catch (_) {
      // Ignore; will fall back to legacy token or unauthenticated.
    }

    final after = Supabase.instance.client.auth.currentSession?.accessToken;
    if (after != null && after.isNotEmpty) return after;

    // Legacy fallback: some older flows stored tokens manually.
    final prefs = await SharedPreferences.getInstance();
    final legacy = prefs.getString('access_token');
    if (legacy != null && legacy.isNotEmpty) return legacy;

    return null;
  }

  Future<Map<String, dynamic>> analyzeImage({
    required File imageFile,
    required String scanType,
    String? locationHint,
    String? barcode,
    String? barcodeNameHint,
    double? barcodeQuantityHint,
    String? barcodeUnitHint,
    int retryCount = 0,
  }) async {
    const maxRetries = 2;
    
    try {
      // Validate image file exists and has size
      if (!await imageFile.exists()) {
        return {
          'success': false,
          'error': 'Image file not found. Please try taking the photo again.',
        };
      }
      
      final fileSize = await imageFile.length();
      if (fileSize == 0) {
        return {
          'success': false,
          'error': 'Image file is empty. Please try taking the photo again.',
        };
      }
      
      if (fileSize > 10 * 1024 * 1024) { // 10MB limit
        return {
          'success': false,
          'error': 'Image file is too large (>10MB). Please try taking a smaller photo.',
        };
      }

      // Get auth token
      final token = await _getAccessToken();

      if (token == null) {
        return {
          'success': false,
          'error': 'Not authenticated. Please log in again.',
        };
      }

      // Create multipart request
      final uri = Uri.parse('$baseUrl/api/scanning/analyze-image');
      final request = http.MultipartRequest('POST', uri);

      // Add headers
      request.headers['Authorization'] = 'Bearer $token';

      // Add image file (stream from disk; avoids loading whole file into memory)
      final multipartFile = await http.MultipartFile.fromPath(
        'image',
        imageFile.path,
        filename: 'scan.jpg',
        contentType: MediaType('image', 'jpeg'),
      );
      request.files.add(multipartFile);

      // Add form fields
      request.fields['scan_type'] = scanType;
      if (locationHint != null && locationHint.isNotEmpty) {
        request.fields['location_hint'] = locationHint;
      }

      final bc = (barcode ?? '').trim();
      if (bc.isNotEmpty) {
        request.fields['barcode'] = bc;
      }
      final bcn = (barcodeNameHint ?? '').trim();
      if (bcn.isNotEmpty) {
        request.fields['barcode_name_hint'] = bcn;
      }
      if (barcodeQuantityHint != null && barcodeQuantityHint > 0) {
        request.fields['barcode_quantity_hint'] = barcodeQuantityHint.toString();
      }
      final bcu = (barcodeUnitHint ?? '').trim();
      if (bcu.isNotEmpty) {
        request.fields['barcode_unit_hint'] = _normalizeUnit(bcu);
      }

      // Send request with timeout
      final streamedResponse = await request.send().timeout(
        const Duration(seconds: 30),
        onTimeout: () {
          throw TimeoutException('Request timed out after 30 seconds');
        },
      );
      final response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        
        // Validate response has required fields
        if (data['scan_id'] == null || data['ingredients'] == null) {
          return {
            'success': false,
            'error': 'Invalid response from server. Please try again.',
          };
        }
        
        return {
          'success': true,
          'scan_id': data['scan_id'],
          'ingredients': data['ingredients'],
          'metadata': data['metadata'] ?? {},
          'requires_confirmation': data['requires_confirmation'] ?? true,
          'message': data['message'] ?? 'Ingredients detected successfully',
        };
      } else if (response.statusCode == 401) {
        return {
          'success': false,
          'error': 'Session expired. Please log in again.',
        };
      } else if (response.statusCode >= 500 && retryCount < maxRetries) {
        // Retry on server errors
        await Future.delayed(Duration(seconds: 1 << retryCount)); // Exponential backoff
        return analyzeImage(
          imageFile: imageFile,
          scanType: scanType,
          locationHint: locationHint,
          retryCount: retryCount + 1,
        );
      } else {
        dynamic decoded;
        try {
          decoded = json.decode(response.body);
        } catch (_) {
          decoded = null;
        }

        if (decoded is Map) {
          final detail = decoded['detail'];
          if (detail is Map) {
            final code = detail['code']?.toString();
            final message = detail['message']?.toString();
            final issues = detail['issues'];
            final metrics = detail['metrics'];

            return {
              'success': false,
              'error': (message != null && message.trim().isNotEmpty)
                  ? message.trim()
                  : 'Analysis failed. Please try again.',
              if (code != null && code.trim().isNotEmpty) 'error_code': code.trim(),
              if (issues is List) 'quality_issues': issues,
              if (metrics is Map) 'quality_metrics': Map<String, dynamic>.from(metrics),
            };
          }

          final msg = (detail ?? decoded['message'] ?? '').toString().trim();
          return {
            'success': false,
            'error': msg.isNotEmpty ? msg : 'Analysis failed. Please try again.',
          };
        }

        return {
          'success': false,
          'error': 'Analysis failed. Please try again.',
        };
      }
    } on TimeoutException catch (_) {
      if (retryCount < maxRetries) {
        return analyzeImage(
          imageFile: imageFile,
          scanType: scanType,
          locationHint: locationHint,
          barcode: barcode,
          barcodeNameHint: barcodeNameHint,
          barcodeQuantityHint: barcodeQuantityHint,
          barcodeUnitHint: barcodeUnitHint,
          retryCount: retryCount + 1,
        );
      }
      return {
        'success': false,
        'error': 'Request timed out. Please check your internet connection and try again.',
      };
    } on SocketException catch (_) {
      return {
        'success': false,
        'error': 'No internet connection. Please check your network and try again.',
      };
    } catch (e) {
      if (retryCount < maxRetries) {
        return analyzeImage(
          imageFile: imageFile,
          scanType: scanType,
          locationHint: locationHint,
          barcode: barcode,
          barcodeNameHint: barcodeNameHint,
          barcodeQuantityHint: barcodeQuantityHint,
          barcodeUnitHint: barcodeUnitHint,
          retryCount: retryCount + 1,
        );
      }
      return {
        'success': false,
        'error': 'Unexpected error: ${e.toString()}. Please try again.',
      };
    }
  }

  Future<Map<String, dynamic>> confirmIngredients({
    required String scanId,
    required List<Map<String, dynamic>> confirmations,
    bool queueOnFailure = true,
  }) async {
    try {
      // Get auth token
      final token = await _getAccessToken();

      if (token == null) {
        return {
          'success': false,
          'error': 'Not authenticated. Please log in.',
        };
      }

      // Send request
      final uri = Uri.parse('$baseUrl/api/scanning/confirm-ingredients');
      final response = await http
          .post(
            uri,
            headers: {
              'Authorization': 'Bearer $token',
              'Content-Type': 'application/json',
            },
            body: json.encode({
              'scan_id': scanId,
              'confirmations': confirmations.map(_normalizeConfirmation).toList(),
            }),
          )
          .timeout(const Duration(seconds: 12));

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
    } on SocketException {
      if (queueOnFailure) {
        await PendingScanSyncService.instance.enqueueConfirmIngredients(
          scanId: scanId,
          confirmations: confirmations.map(_normalizeConfirmation).toList(),
        );
        return {
          'success': true,
          'queued': true,
          'message': 'Saved offline. Will sync when online.',
        };
      }
      return {
        'success': false,
        'error': 'No internet connection. Please check your network and try again.',
      };
    } on TimeoutException {
      if (queueOnFailure) {
        await PendingScanSyncService.instance.enqueueConfirmIngredients(
          scanId: scanId,
          confirmations: confirmations.map(_normalizeConfirmation).toList(),
        );
        return {
          'success': true,
          'queued': true,
          'message': 'Saved offline. Will sync when online.',
        };
      }
      return {
        'success': false,
        'error': 'Request timed out. Please try again.',
      };
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
      final token = await _getAccessToken();

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
      final token = await _getAccessToken();

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
      final token = await _getAccessToken();

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
      final token = await _getAccessToken();

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

  // Add apiClient parameter for proper auth handling
  Future<Map<String, dynamic>> checkSufficiency({
    required String recipeId,
    required int servings,
    required dynamic apiClient,
    List<Map<String, dynamic>>? recipeIngredients,
    int recipeServings = 4,
  }) async {
    try {
      // Use ApiClient which handles auth automatically
      final uri = Uri.parse('$baseUrl/api/scanning/check-sufficiency');
      final response = await http.post(
        uri,
        headers: await apiClient.getHeaders(),
        body: json.encode({
          'recipe_id': recipeId,
          'servings': servings,
          'recipe_servings': recipeServings,
          if (recipeIngredients != null) 'recipe_ingredients': recipeIngredients,
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
      final token = await _getAccessToken();

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

  /// Scan single item (optimized for continuous scanning)
  Future<Map<String, dynamic>> scanSingleItem({
    required File imageFile,
    required String scanType,
  }) async {
    try {
      // Validate image
      if (!await imageFile.exists()) {
        return {
          'success': false,
          'error': 'Image file not found.',
        };
      }

      final fileSize = await imageFile.length();
      if (fileSize == 0 || fileSize > 10 * 1024 * 1024) {
        return {
          'success': false,
          'error': 'Invalid image size.',
        };
      }

      // Get auth token
      final token = await _getAccessToken();
      if (token == null) {
        return {
          'success': false,
          'error': 'Not authenticated.',
        };
      }

      // Create multipart request
      final uri = Uri.parse('$baseUrl/api/scanning/single-item');
      final request = http.MultipartRequest('POST', uri);
      request.headers['Authorization'] = 'Bearer $token';

      // Add image
      final imageBytes = await imageFile.readAsBytes();
      request.files.add(
        http.MultipartFile.fromBytes(
          'image',
          imageBytes,
          filename: 'item.jpg',
          contentType: MediaType('image', 'jpeg'),
        ),
      );

      // Add scan type
      request.fields['scan_type'] = scanType;

      // Send request
      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        return {
          'success': true,
          'ingredient': data['ingredient'],
          'metadata': data['metadata'],
          'auto_saved': data['auto_saved'] ?? false,
          'requires_confirmation': data['requires_confirmation'] ?? false,
          'message': data['message'],
        };
      } else {
        final error = json.decode(response.body);
        return {
          'success': false,
          'error': error['detail'] ?? 'Scan failed',
        };
      }
    } on SocketException {
      return {
        'success': false,
        'error': 'No internet connection. Check network and try again.',
      };
    } on TimeoutException {
      return {
        'success': false,
        'error': 'Request timed out. Please try again.',
      };
    } catch (e) {
      return {
        'success': false,
        'error': 'Scan error: $e',
      };
    }
  }

  /// Confirm single ingredient (fire-and-forget)
  Future<Map<String, dynamic>> confirmSingleIngredient({
    required String ingredientName,
    required double quantity,
    required String unit,
    String scanType = 'pantry',
    bool queueOnFailure = true,
  }) async {
    try {
      final token = await _getAccessToken();
      if (token == null) {
        return {
          'success': false,
          'error': 'Not authenticated.',
        };
      }

      final uri = Uri.parse('$baseUrl/api/scanning/confirm-single');
      final request = http.MultipartRequest('POST', uri);
      request.headers['Authorization'] = 'Bearer $token';

      final name = _canonicalizeName(ingredientName);
      if (name.isEmpty) {
        return {
          'success': false,
          'error': 'Missing ingredient name.',
        };
      }

      request.fields['ingredient_name'] = name;
      request.fields['quantity'] = (quantity <= 0 ? 1.0 : quantity).toString();
      request.fields['unit'] = _normalizeUnit(unit);
      request.fields['scan_type'] = scanType;

      final streamedResponse = await request.send().timeout(
        const Duration(seconds: 12),
        onTimeout: () => throw TimeoutException('confirm-single timeout'),
          );
      final response = await http.Response.fromStream(streamedResponse);

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
          'error': error['detail'] ?? 'Confirmation failed',
        };
      }
    } on SocketException {
      if (queueOnFailure) {
        await PendingScanSyncService.instance.enqueueConfirmSingle(
          ingredientName: ingredientName,
          quantity: quantity <= 0 ? 1.0 : quantity,
          unit: _normalizeUnit(unit),
          scanType: scanType,
        );
        return {
          'success': true,
          'queued': true,
          'message': 'Saved offline. Will sync when online.',
        };
      }
      return {
        'success': false,
        'error': 'No internet connection. Check network and try again.',
      };
    } on TimeoutException {
      if (queueOnFailure) {
        await PendingScanSyncService.instance.enqueueConfirmSingle(
          ingredientName: ingredientName,
          quantity: quantity <= 0 ? 1.0 : quantity,
          unit: _normalizeUnit(unit),
          scanType: scanType,
        );
        return {
          'success': true,
          'queued': true,
          'message': 'Saved offline. Will sync when online.',
        };
      }
      return {
        'success': false,
        'error': 'Request timed out. Please try again.',
      };
    } catch (e) {
      return {
        'success': false,
        'error': 'Error: $e',
      };
    }
  }
}
