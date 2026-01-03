import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'api_client.dart';

/// Service for session security and device tracking
/// Prevents credential sharing with 2-device limit enforcement
class SessionSecurityService {
  final ApiClient _apiClient;
  
  SessionSecurityService(this._apiClient);
  
  /// Track login after successful authentication
  /// CRITICAL: Call this immediately after Supabase sign-in
  /// Returns session info or throws exception if device limit exceeded (403)
  Future<Map<String, dynamic>> trackLogin() async {
    try {
      final session = Supabase.instance.client.auth.currentSession;
      if (session == null) {
        throw Exception('No active session');
      }
      
      final response = await _apiClient.post(
        '/security/track-login',
        data: {
          'session_token': session.accessToken,
        },
      );
      
      return response;
    } on ApiException catch (e) {
      if (e.statusCode == 403) {
        // Device limit exceeded - block login
        debugPrint('🚫 Device limit exceeded: ${e.message}');
        rethrow;
      }
      debugPrint('⚠️ Error tracking login (non-critical): $e');
      // Don't block login on tracking errors
      return {'success': false, 'error': e.message};
    } catch (e) {
      debugPrint('⚠️ Error tracking login: $e');
      return {'success': false, 'error': e.toString()};
    }
  }
  
  /// Get all active sessions (devices)
  Future<List<Map<String, dynamic>>> getActiveSessions() async {
    try {
      final response = await _apiClient.get('/security/sessions');
      
      if (response['success'] == true) {
        final sessions = response['sessions'] as List<dynamic>;
        return sessions.cast<Map<String, dynamic>>();
      }
      
      return [];
    } catch (e) {
      debugPrint('Error getting active sessions: $e');
      return [];
    }
  }
  
  /// Get active session count and limits
  Future<Map<String, int>> getSessionLimits() async {
    try {
      final response = await _apiClient.get('/security/sessions');
      
      if (response['success'] == true) {
        return {
          'active': response['total_count'] ?? 0,
          'max': response['max_devices'] ?? 2,
        };
      }
      
      return {'active': 0, 'max': 2};
    } catch (e) {
      debugPrint('Error getting session limits: $e');
      return {'active': 0, 'max': 2};
    }
  }
  
  /// Sign out a specific device (revoke session)
  Future<bool> revokeSession(String sessionId) async {
    try {
      final response = await _apiClient.post(
        '/security/sessions/revoke',
        data: {'session_id': sessionId},
      );
      
      return response['success'] == true;
    } catch (e) {
      debugPrint('Error revoking session: $e');
      return false;
    }
  }
  
  /// Sign out all other devices (keep current)
  Future<int> revokeOtherSessions() async {
    try {
      final session = Supabase.instance.client.auth.currentSession;
      if (session == null) {
        throw Exception('No active session');
      }
      
      final response = await _apiClient.post(
        '/security/sessions/revoke-others',
        data: {
          'session_token': session.accessToken,
        },
      );
      
      if (response['success'] == true) {
        // Also call Supabase's built-in sign out others
        await Supabase.instance.client.auth.signOut(scope: SignOutScope.others);
        return response['revoked_count'] ?? 0;
      }
      
      return 0;
    } catch (e) {
      debugPrint('Error revoking other sessions: $e');
      return 0;
    }
  }
  
  /// Get security events for user
  Future<List<Map<String, dynamic>>> getSecurityEvents({
    int limit = 50,
    String? severity,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'limit': limit,
      };
      
      if (severity != null) {
        queryParams['severity'] = severity;
      }
      
      final response = await _apiClient.get(
        '/security/events',
        queryParameters: queryParams,
      );
      
      if (response['success'] == true) {
        final events = response['events'] as List<dynamic>;
        return events.cast<Map<String, dynamic>>();
      }
      
      return [];
    } catch (e) {
      debugPrint('Error getting security events: $e');
      return [];
    }
  }
  
  /// Get security dashboard summary
  Future<Map<String, dynamic>?> getSecurityDashboard() async {
    try {
      final response = await _apiClient.get('/security/dashboard');
      
      if (response['success'] == true) {
        return response['dashboard'];
      }
      
      return null;
    } catch (e) {
      debugPrint('Error getting security dashboard: $e');
      return null;
    }
  }
  
  /// Get trusted devices
  Future<List<Map<String, dynamic>>> getTrustedDevices() async {
    try {
      final response = await _apiClient.get('/security/trusted-devices');
      
      if (response['success'] == true) {
        final devices = response['devices'] as List<dynamic>;
        return devices.cast<Map<String, dynamic>>();
      }
      
      return [];
    } catch (e) {
      debugPrint('Error getting trusted devices: $e');
      return [];
    }
  }
  
  /// Trust current device
  Future<bool> trustCurrentDevice({String? deviceName}) async {
    try {
      // Generate device fingerprint
      final fingerprint = await _getDeviceFingerprint();
      
      final response = await _apiClient.post(
        '/security/trusted-devices',
        data: {
          'device_fingerprint': fingerprint,
          'device_name': deviceName,
        },
      );
      
      return response['success'] == true;
    } catch (e) {
      debugPrint('Error trusting device: $e');
      return false;
    }
  }
  
  /// Remove device from trusted list
  Future<bool> untrustDevice(String deviceId) async {
    try {
      final response = await _apiClient.delete(
        '/security/trusted-devices/$deviceId',
      );
      
      return response['success'] == true;
    } catch (e) {
      debugPrint('Error untrusting device: $e');
      return false;
    }
  }
  
  // ============================================================================
  // HELPER METHODS
  // ============================================================================
  
  /// Get device fingerprint for current device
  Future<String> _getDeviceFingerprint() async {
    // This is a simple fingerprint - in production, use device_info_plus package
    final platform = _getPlatformName();
    final session = Supabase.instance.client.auth.currentSession;
    final userId = session?.user.id ?? 'unknown';
    
    // Combine platform + user for basic fingerprint
    // In production, add: device ID, OS version, model, etc.
    return '$platform-$userId'.hashCode.toString();
  }
  
  /// Get platform name
  String _getPlatformName() {
    if (kIsWeb) {
      return 'Web';
    } else if (Platform.isAndroid) {
      return 'Android';
    } else if (Platform.isIOS) {
      return 'iOS';
    } else if (Platform.isMacOS) {
      return 'macOS';
    } else if (Platform.isWindows) {
      return 'Windows';
    } else if (Platform.isLinux) {
      return 'Linux';
    }
    return 'Unknown';
  }
}

/// Exception thrown when API request fails
class ApiException implements Exception {
  final String message;
  final int? statusCode;
  
  ApiException(this.message, {this.statusCode});
  
  @override
  String toString() => 'ApiException: $message (status: $statusCode)';
}
