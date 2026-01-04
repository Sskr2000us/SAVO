import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import 'package:image_picker/image_picker.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

class ApiClient {
  final String baseUrl;

  ApiClient({String? baseUrl}) : baseUrl = baseUrl ?? _defaultBaseUrl();

  static String _defaultBaseUrl() {
    // Production Render backend
    return 'https://savo-ynp1.onrender.com';
    
    // Local development - uncomment to use localhost
    // if (kIsWeb) return 'http://localhost:8000';
    // return 'http://localhost:8000';
  }

  /// Get authentication headers with Bearer token
  Map<String, String> _getAuthHeaders() {
    final token = Supabase.instance.client.auth.currentSession?.accessToken;
    if (token != null) {
      return {'Authorization': 'Bearer $token'};
    }
    return {};
  }

  /// Public method to get headers with auth (for external services)
  Future<Map<String, String>> getHeaders() async {
    final token = Supabase.instance.client.auth.currentSession?.accessToken;
    final headers = <String, String>{
      'Content-Type': 'application/json',
    };
    if (token != null && token.isNotEmpty) {
      headers['Authorization'] = 'Bearer $token';
    }
    return headers;
  }

  /// Merge custom headers with auth headers
  Map<String, String> _mergeHeaders(Map<String, String>? customHeaders) {
    final headers = _getAuthHeaders();
    if (customHeaders != null) {
      headers.addAll(customHeaders);
    }
    return headers;
  }

  Future<dynamic> get(String endpoint, {Map<String, String>? headers}) async {
    final response = await http.get(
      Uri.parse('$baseUrl$endpoint'),
      headers: _mergeHeaders(headers),
    ).timeout(
      const Duration(seconds: 30),
      onTimeout: () => throw Exception('Request timed out. Please check your connection and try again.'),
    );
    if (response.statusCode == 200) {
      return json.decode(response.body);
    } else {
      String errorDetail = 'HTTP ${response.statusCode}';
      try {
        final errorBody = json.decode(response.body);
        if (errorBody is Map && errorBody['detail'] != null) {
          errorDetail = errorBody['detail'].toString();
        }
      } catch (_) {
        if (response.body.isNotEmpty) {
          errorDetail = response.body;
        }
      }
      throw Exception('Failed to load data: ${response.statusCode} ($errorDetail)');
    }
  }

  Future<Map<String, dynamic>> post(String endpoint, Map<String, dynamic> body, {Map<String, String>? headers}) async {
    final allHeaders = {'Content-Type': 'application/json'};
    allHeaders.addAll(_mergeHeaders(headers));
    
    // LLM requests (planning endpoints) need longer timeout
    final timeout = endpoint.contains('/plan/') ? 120 : 30;
    
    try {
      final response = await http.post(
        Uri.parse('$baseUrl$endpoint'),
        headers: allHeaders,
        body: json.encode(body),
      ).timeout(
        Duration(seconds: timeout),
        onTimeout: () {
          if (endpoint.contains('/plan/')) {
            throw Exception('Recipe generation is taking longer than usual. This can happen with complex requirements. Please try again.');
          }
          throw Exception('Request timed out. Please check your connection and try again.');
        },
      );
      if (response.statusCode == 200 || response.statusCode == 201) {
        return json.decode(response.body);
      } else {
        // Try to parse error message from response body
        String errorDetail = 'HTTP ${response.statusCode}';
        try {
          final errorBody = json.decode(response.body);
          if (errorBody['detail'] != null) {
            errorDetail = errorBody['detail'].toString();
          }
        } catch (_) {
          // If can't parse, use raw body
          if (response.body.isNotEmpty) {
            errorDetail = response.body;
          }
        }
        throw Exception('Failed to POST $endpoint: $errorDetail');
      }
    } catch (e) {
      // Provide more context for network errors
      if (e.toString().contains('Failed to fetch') || e.toString().contains('ClientException')) {
        throw Exception('Cannot reach server at $baseUrl$endpoint. Please check:\n'
            '1. Your internet connection\n'
            '2. The backend server is running\n'
            '3. CORS is properly configured\n'
            'Original error: $e');
      }
      if (e is Exception) rethrow;
      throw Exception('Network error: $e');
    }
  }

  Future<Map<String, dynamic>> postMultipart(
    String endpoint, {
    required XFile file,
    String fieldName = 'image',
    Map<String, String> fields = const {},
  }) async {
    final uri = Uri.parse('$baseUrl$endpoint');
    final request = http.MultipartRequest('POST', uri);

    // Add auth headers
    request.headers.addAll(_getAuthHeaders());
    
    request.fields.addAll(fields);

    // Determine MIME type from file extension
    String? mimeType = file.mimeType;
    if (mimeType == null) {
      final extension = file.name.toLowerCase().split('.').last;
      if (extension == 'jpg' || extension == 'jpeg') {
        mimeType = 'image/jpeg';
      } else if (extension == 'png') {
        mimeType = 'image/png';
      } else if (extension == 'gif') {
        mimeType = 'image/gif';
      } else if (extension == 'webp') {
        mimeType = 'image/webp';
      } else {
        mimeType = 'image/jpeg'; // Default fallback
      }
    }

    final bytes = await file.readAsBytes();
    request.files.add(
      http.MultipartFile.fromBytes(
        fieldName,
        bytes,
        filename: file.name,
        contentType: MediaType.parse(mimeType),
      ),
    );

    final streamed = await request.send();
    final response = await http.Response.fromStream(streamed);

    if (response.statusCode == 200 || response.statusCode == 201) {
      return json.decode(response.body) as Map<String, dynamic>;
    }

    throw Exception('Failed to post multipart: ${response.statusCode} ${response.body}');
  }

  Future<Map<String, dynamic>> put(String endpoint, Map<String, dynamic> body, {Map<String, String>? headers}) async {
    final allHeaders = {'Content-Type': 'application/json'};
    allHeaders.addAll(_mergeHeaders(headers));
    
    final response = await http.put(
      Uri.parse('$baseUrl$endpoint'),
      headers: allHeaders,
      body: json.encode(body),
    );
    if (response.statusCode == 200) {
      return json.decode(response.body);
    } else {
      throw Exception('Failed to update data: ${response.statusCode}');
    }
  }

  Future<Map<String, dynamic>> patch(String endpoint, Map<String, dynamic> body, {Map<String, String>? headers}) async {
    final allHeaders = {'Content-Type': 'application/json'};
    allHeaders.addAll(_mergeHeaders(headers));
    
    final response = await http.patch(
      Uri.parse('$baseUrl$endpoint'),
      headers: allHeaders,
      body: json.encode(body),
    );
    if (response.statusCode == 200) {
      return json.decode(response.body);
    } else {
      throw Exception('Failed to patch data: ${response.statusCode}');
    }
  }

  Future<void> delete(String endpoint, {Map<String, String>? headers}) async {
    final response = await http.delete(
      Uri.parse('$baseUrl$endpoint'),
      headers: _mergeHeaders(headers),
    );
    if (response.statusCode != 204 && response.statusCode != 200) {
      throw Exception('Failed to delete data: ${response.statusCode}');
    }
  }
}
