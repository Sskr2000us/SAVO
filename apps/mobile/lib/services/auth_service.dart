import 'package:flutter/foundation.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

/// Service for handling authentication with Supabase
class AuthService {
  final SupabaseClient _client = Supabase.instance.client;

  /// Get the current authenticated user
  User? get currentUser => _client.auth.currentUser;

  /// Get the current session
  Session? get currentSession => _client.auth.currentSession;

  /// Get the JWT access token for API calls
  String? get accessToken => _client.auth.currentSession?.accessToken;

  /// Check if user is authenticated
  bool get isAuthenticated => currentSession != null;

  /// Get the current user ID
  String? get userId => currentUser?.id;

  /// Sign in with email and password
  Future<AuthResponse> signInWithPassword({
    required String email,
    required String password,
  }) async {
    try {
      final response = await _client.auth.signInWithPassword(
        email: email,
        password: password,
      );
      return response;
    } catch (e) {
      debugPrint('Sign in error: $e');
      rethrow;
    }
  }

  /// Sign in with email OTP (magic link)
  Future<void> signInWithOtp({required String email}) async {
    try {
      await _client.auth.signInWithOtp(
        email: email,
        emailRedirectTo: null, // Will be handled by deep link in mobile app
      );
    } catch (e) {
      debugPrint('OTP sign in error: $e');
      rethrow;
    }
  }

  /// Verify OTP code
  Future<AuthResponse> verifyOtp({
    required String email,
    required String token,
  }) async {
    try {
      final response = await _client.auth.verifyOTP(
        email: email,
        token: token,
        type: OtpType.email,
      );
      return response;
    } catch (e) {
      debugPrint('OTP verification error: $e');
      rethrow;
    }
  }

  /// Sign up with email and password
  Future<AuthResponse> signUp({
    required String email,
    required String password,
  }) async {
    try {
      final response = await _client.auth.signUp(
        email: email,
        password: password,
      );
      return response;
    } catch (e) {
      debugPrint('Sign up error: $e');
      rethrow;
    }
  }

  /// Sign out
  Future<void> signOut() async {
    try {
      await _client.auth.signOut();
    } catch (e) {
      debugPrint('Sign out error: $e');
      rethrow;
    }
  }

  /// Sign out from all devices except current
  Future<void> signOutOtherDevices() async {
    try {
      await _client.auth.signOut(scope: SignOutScope.others);
    } catch (e) {
      debugPrint('Sign out others error: $e');
      rethrow;
    }
  }

  /// Refresh the current session
  Future<AuthResponse> refreshSession() async {
    try {
      final response = await _client.auth.refreshSession();
      return response;
    } catch (e) {
      debugPrint('Session refresh error: $e');
      rethrow;
    }
  }

  /// Listen to auth state changes
  Stream<AuthState> get authStateChanges => _client.auth.onAuthStateChange;

  /// Update user metadata (e.g., last login device)
  Future<UserResponse> updateUser({
    required Map<String, dynamic> data,
  }) async {
    try {
      final response = await _client.auth.updateUser(
        UserAttributes(data: data),
      );
      return response;
    } catch (e) {
      debugPrint('Update user error: $e');
      rethrow;
    }
  }

  /// Get device info for audit logging
  Map<String, dynamic> getDeviceInfo() {
    // In production, use device_info_plus package for detailed info
    return {
      'platform': defaultTargetPlatform.name,
      'timestamp': DateTime.now().toIso8601String(),
    };
  }
}
