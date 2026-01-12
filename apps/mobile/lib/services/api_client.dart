import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import 'package:image_picker/image_picker.dart';
import 'package:image/image.dart' as img;
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
      // Ignore; caller will proceed unauthenticated.
    }

    final after = Supabase.instance.client.auth.currentSession?.accessToken;
    if (after != null && after.isNotEmpty) return after;
    return null;
  }

  /// Get authentication headers with Bearer token
  Future<Map<String, String>> _getAuthHeaders() async {
    final token = await _getAccessToken();
    if (token != null && token.isNotEmpty) {
      return {'Authorization': 'Bearer $token'};
    }
    return {};
  }

  /// Public method to get headers with auth (for external services)
  Future<Map<String, String>> getHeaders() async {
    final headers = <String, String>{'Content-Type': 'application/json'};
    final auth = await _getAuthHeaders();
    headers.addAll(auth);
    return headers;
  }

  /// Merge custom headers with auth headers
  Future<Map<String, String>> _mergeHeaders(Map<String, String>? customHeaders) async {
    final headers = await _getAuthHeaders();
    if (customHeaders != null) {
      headers.addAll(customHeaders);
    }
    return headers;
  }

  Future<dynamic> get(String endpoint, {Map<String, String>? headers}) async {
    final merged = await _mergeHeaders(headers);
    final response = await http.get(
      Uri.parse('$baseUrl$endpoint'),
      headers: merged,
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
    allHeaders.addAll(await _mergeHeaders(headers));
    
    // LLM requests (planning endpoints) need longer timeout
    // Party planning is the heaviest (multi-course) and can exceed the default.
    final timeout = endpoint.contains('/plan/party')
      ? 240
      : endpoint.contains('/plan/')
        ? 180
        : (endpoint.contains('/recipes/generate') || endpoint.contains('/recipes/generate-options'))
          ? 120
          : 30;
    
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
    int timeoutSeconds = 30,
  }) async {
    final uri = Uri.parse('$baseUrl$endpoint');
    final request = http.MultipartRequest('POST', uri);

    // Add auth headers
    request.headers.addAll(await _getAuthHeaders());
    
    request.fields.addAll(fields);

    // Determine MIME type from file extension
    String mimeType = file.mimeType ?? (() {
      final extension = file.name.toLowerCase().split('.').last;
      if (extension == 'jpg' || extension == 'jpeg') {
        return 'image/jpeg';
      } else if (extension == 'png') {
        return 'image/png';
      } else if (extension == 'gif') {
        return 'image/gif';
      } else if (extension == 'webp') {
        return 'image/webp';
      } else if (extension == 'mp4') {
        return 'video/mp4';
      } else if (extension == 'mov') {
        return 'video/quicktime';
      } else if (extension == 'avi') {
        return 'video/x-msvideo';
      }
      return 'image/jpeg'; // Default fallback
    })();

    var bytes = await file.readAsBytes();

    // Large images can slow recognition and cause iOS upload flakiness.
    // Best-effort: resize and re-encode to a sane JPEG.
    try {
      final isImage = mimeType.startsWith('image/');
      if (isImage && bytes.lengthInBytes > 900 * 1024) {
        final decoded = img.decodeImage(bytes);
        if (decoded != null) {
          final maxDim = max(decoded.width, decoded.height);
          img.Image out = decoded;
          if (maxDim > 1280) {
            final scale = 1280 / maxDim;
            final newW = max(1, (decoded.width * scale).round());
            final newH = max(1, (decoded.height * scale).round());
            out = img.copyResize(decoded, width: newW, height: newH);
          }
          bytes = img.encodeJpg(out, quality: 80);
          mimeType = 'image/jpeg';
        }
      }
    } catch (_) {
      // Best-effort only; fall back to original bytes.
    }

    final filename = (mimeType == 'image/jpeg' && !file.name.toLowerCase().endsWith('.jpg') && !file.name.toLowerCase().endsWith('.jpeg'))
        ? '${file.name}.jpg'
        : file.name;
    request.files.add(
      http.MultipartFile.fromBytes(
        fieldName,
        bytes,
        filename: filename,
        contentType: MediaType.parse(mimeType),
      ),
    );

    http.StreamedResponse streamed;
    try {
      streamed = await request.send().timeout(
        Duration(seconds: timeoutSeconds),
        onTimeout: () => throw TimeoutException('multipart timeout'),
      );
    } on TimeoutException {
      throw Exception('Upload is taking too long. Please try again on a faster connection.');
    } on http.ClientException catch (e) {
      final msg = e.toString().toLowerCase();
      if (msg.contains('bad file descriptor')) {
        throw Exception('Upload failed. Please try again.');
      }
      rethrow;
    }

    final response = await http.Response.fromStream(streamed);

    if (response.statusCode == 200 || response.statusCode == 201) {
      return json.decode(response.body) as Map<String, dynamic>;
    }

    throw Exception('Failed to post multipart: ${response.statusCode} ${response.body}');
  }

  Future<Map<String, dynamic>> postMultipartMany(
    String endpoint, {
    required List<XFile> files,
    String fieldName = 'images',
    Map<String, String> fields = const {},
    int timeoutSeconds = 30,
  }) async {
    final uri = Uri.parse('$baseUrl$endpoint');
    final request = http.MultipartRequest('POST', uri);

    request.headers.addAll(await _getAuthHeaders());
    request.fields.addAll(fields);

    // Cap is enforced server-side too, but avoid huge uploads.
    final capped = files.length > 20 ? files.sublist(0, 20) : files;
    for (final file in capped) {
      String mimeType = file.mimeType ?? (() {
        final extension = file.name.toLowerCase().split('.').last;
        if (extension == 'jpg' || extension == 'jpeg') {
          return 'image/jpeg';
        } else if (extension == 'png') {
          return 'image/png';
        }
        return 'image/jpeg';
      })();

      var bytes = await file.readAsBytes();

      // Guided scans can capture very large frames; shrink to keep uploads reliable.
      // This reduces server/proxy drops that can surface on iOS as: ClientException: Bad file descriptor.
      try {
        // Only attempt to decode/resize if the payload is large enough to matter.
        if (bytes.lengthInBytes > 900 * 1024) {
          final decoded = img.decodeImage(bytes);
          if (decoded != null) {
            final maxDim = max(decoded.width, decoded.height);
            // Resize if very large, otherwise still re-encode at a sane JPEG quality.
            img.Image out = decoded;
            if (maxDim > 1280) {
              final scale = 1280 / maxDim;
              final newW = max(1, (decoded.width * scale).round());
              final newH = max(1, (decoded.height * scale).round());
              out = img.copyResize(decoded, width: newW, height: newH);
            }
            bytes = img.encodeJpg(out, quality: 80);
            mimeType = 'image/jpeg';
          }
        }
      } catch (_) {
        // Best-effort only; fall back to original bytes.
      }

      final filename = (mimeType == 'image/jpeg' && !file.name.toLowerCase().endsWith('.jpg') && !file.name.toLowerCase().endsWith('.jpeg'))
          ? '${file.name}.jpg'
          : file.name;
      request.files.add(
        http.MultipartFile.fromBytes(
          fieldName,
          bytes,
          filename: filename,
          contentType: MediaType.parse(mimeType),
        ),
      );
    }

    http.StreamedResponse streamed;
    try {
      streamed = await request.send().timeout(
        Duration(seconds: timeoutSeconds),
        onTimeout: () => throw Exception('Request timed out. Please try again.'),
      );
    } on http.ClientException catch (e) {
      final msg = e.toString().toLowerCase();
      if (msg.contains('bad file descriptor')) {
        throw Exception('Upload failed. Please try again (move closer to Wi‑Fi / reduce movement).');
      }
      rethrow;
    }
    final response = await http.Response.fromStream(streamed);

    if (response.statusCode == 200 || response.statusCode == 201) {
      return json.decode(response.body) as Map<String, dynamic>;
    }

    throw Exception('Failed to post multipart: ${response.statusCode} ${response.body}');
  }

  Future<Map<String, dynamic>> put(String endpoint, Map<String, dynamic> body, {Map<String, String>? headers}) async {
    final allHeaders = {'Content-Type': 'application/json'};
    allHeaders.addAll(await _mergeHeaders(headers));
    
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
    allHeaders.addAll(await _mergeHeaders(headers));
    
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
    final merged = await _mergeHeaders(headers);
    final response = await http.delete(
      Uri.parse('$baseUrl$endpoint'),
      headers: merged,
    );
    if (response.statusCode != 204 && response.statusCode != 200) {
      throw Exception('Failed to delete data: ${response.statusCode}');
    }
  }
}
