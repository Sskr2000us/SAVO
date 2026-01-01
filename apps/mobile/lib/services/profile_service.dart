import 'package:flutter/foundation.dart';
import 'api_client.dart';

/// Service for managing user profile data
/// Interfaces with all Phase C profile endpoints
class ProfileService {
  final ApiClient _apiClient;

  ProfileService(this._apiClient);

  // ============================================================================
  // FULL PROFILE (C1)
  // ============================================================================

  /// Get complete user profile with all related data
  /// Returns: user, profile, household, members, allergens, dietary
  Future<Map<String, dynamic>> getFullProfile() async {
    try {
      final response = await _apiClient.get('/profile/full');
      if (response['success'] == true) {
        return response['data'];
      }
      throw Exception('Failed to get full profile');
    } catch (e) {
      debugPrint('Error getting full profile: $e');
      rethrow;
    }
  }

  // ============================================================================
  // HOUSEHOLD ENDPOINTS (Existing - refactored to Bearer)
  // ============================================================================

  /// Get household profile
  Future<Map<String, dynamic>> getHouseholdProfile() async {
    try {
      final response = await _apiClient.get('/profile/household');
      return response;
    } catch (e) {
      debugPrint('Error getting household profile: $e');
      rethrow;
    }
  }

  /// Create household profile
  Future<Map<String, dynamic>> createHouseholdProfile({
    String region = 'US',
    String culture = 'western',
    String primaryLanguage = 'en-US',
    String measurementSystem = 'imperial',
    List<String> favoriteCuisines = const ['Italian', 'American'],
    int skillLevel = 2,
  }) async {
    try {
      final response = await _apiClient.post('/profile/household', {
        'region': region,
        'culture': culture,
        'primary_language': primaryLanguage,
        'measurement_system': measurementSystem,
        'favorite_cuisines': favoriteCuisines,
        'skill_level': skillLevel,
      });
      return response;
    } catch (e) {
      debugPrint('Error creating household profile: $e');
      rethrow;
    }
  }

  /// Update household profile
  Future<Map<String, dynamic>> updateHouseholdProfile(
    Map<String, dynamic> updates,
  ) async {
    try {
      final response = await _apiClient.patch('/profile/household', updates);
      return response;
    } catch (e) {
      debugPrint('Error updating household profile: $e');
      rethrow;
    }
  }

  // ============================================================================
  // FAMILY MEMBER ENDPOINTS (Existing - refactored to Bearer)
  // ============================================================================

  /// Get all family members
  Future<List<dynamic>> getFamilyMembers() async {
    try {
      final response = await _apiClient.get('/profile/family-members');
      return response['members'] ?? [];
    } catch (e) {
      debugPrint('Error getting family members: $e');
      rethrow;
    }
  }

  /// Create family member
  Future<Map<String, dynamic>> createFamilyMember({
    required String name,
    required int age,
    List<String> allergens = const [],
    List<String> dietaryRestrictions = const [],
    String spiceTolerance = 'medium',
  }) async {
    try {
      final response = await _apiClient.post('/profile/family-members', {
        'name': name,
        'age': age,
        'allergens': allergens,
        'dietary_restrictions': dietaryRestrictions,
        'spice_tolerance': spiceTolerance,
      });
      return response;
    } catch (e) {
      debugPrint('Error creating family member: $e');
      rethrow;
    }
  }

  /// Update family member
  Future<Map<String, dynamic>> updateFamilyMember(
    String memberId,
    Map<String, dynamic> updates,
  ) async {
    try {
      final response = await _apiClient.patch(
        '/profile/family-members/$memberId',
        updates,
      );
      return response;
    } catch (e) {
      debugPrint('Error updating family member: $e');
      rethrow;
    }
  }

  /// Delete family member
  Future<void> deleteFamilyMember(String memberId) async {
    try {
      await _apiClient.delete('/profile/family-members/$memberId');
    } catch (e) {
      debugPrint('Error deleting family member: $e');
      rethrow;
    }
  }

  // ============================================================================
  // SPECIALIZED UPDATE ENDPOINTS (C2)
  // ============================================================================

  /// Update allergens for a family member (with audit logging)
  Future<Map<String, dynamic>> updateAllergens({
    required String memberId,
    required List<String> allergens,
    String? reason,
  }) async {
    try {
      final response = await _apiClient.patch('/profile/allergens', {
        'member_id': memberId,
        'allergens': allergens,
        if (reason != null) 'reason': reason,
      });
      return response;
    } catch (e) {
      debugPrint('Error updating allergens: $e');
      rethrow;
    }
  }

  /// Update dietary restrictions for a family member
  Future<Map<String, dynamic>> updateDietary({
    required String memberId,
    required List<String> dietaryRestrictions,
  }) async {
    try {
      final response = await _apiClient.patch('/profile/dietary', {
        'member_id': memberId,
        'dietary_restrictions': dietaryRestrictions,
      });
      return response;
    } catch (e) {
      debugPrint('Error updating dietary restrictions: $e');
      rethrow;
    }
  }

  /// Update household preferences (cuisines, spices, pantry)
  Future<Map<String, dynamic>> updatePreferences({
    List<String>? favoriteCuisines,
    List<String>? avoidedCuisines,
    String? spiceTolerance,
    bool? basicSpicesAvailable,
  }) async {
    try {
      final body = <String, dynamic>{};
      if (favoriteCuisines != null) body['favorite_cuisines'] = favoriteCuisines;
      if (avoidedCuisines != null) body['avoided_cuisines'] = avoidedCuisines;
      if (spiceTolerance != null) body['spice_tolerance'] = spiceTolerance;
      if (basicSpicesAvailable != null) {
        body['basic_spices_available'] = basicSpicesAvailable;
      }

      final response = await _apiClient.patch('/profile/preferences', body);
      return response;
    } catch (e) {
      debugPrint('Error updating preferences: $e');
      rethrow;
    }
  }

  /// Update primary language
  Future<Map<String, dynamic>> updateLanguage({
    required String primaryLanguage,
  }) async {
    try {
      final response = await _apiClient.patch('/profile/language', {
        'primary_language': primaryLanguage,
      });
      return response;
    } catch (e) {
      debugPrint('Error updating language: $e');
      rethrow;
    }
  }

  // ============================================================================
  // ONBOARDING STATUS ENDPOINTS (C3)
  // ============================================================================

  /// Get onboarding completion status
  /// Returns: {completed, resume_step, missing_fields}
  /// Resume steps: HOUSEHOLD → ALLERGIES → DIETARY → SPICE → PANTRY → LANGUAGE → COMPLETE
  Future<Map<String, dynamic>> getOnboardingStatus() async {
    try {
      final response = await _apiClient.get('/profile/onboarding-status');
      if (response['success'] == true) {
        return response['data'];
      }
      throw Exception('Failed to get onboarding status');
    } catch (e) {
      debugPrint('Error getting onboarding status: $e');
      rethrow;
    }
  }

  /// Mark onboarding as completed
  Future<Map<String, dynamic>> completeOnboarding() async {
    try {
      final response = await _apiClient.patch('/profile/complete', {});
      return response;
    } catch (e) {
      debugPrint('Error completing onboarding: $e');
      rethrow;
    }
  }

  // ============================================================================
  // HELPER METHODS
  // ============================================================================

  /// Perform a write operation and then refetch full profile
  /// This ensures UI state is always in sync with backend
  Future<Map<String, dynamic>> writeAndRefetch(
    Future<Map<String, dynamic>> Function() writeOperation,
  ) async {
    try {
      // Perform the write
      await writeOperation();
      
      // Refetch full profile
      return await getFullProfile();
    } catch (e) {
      debugPrint('Error in write and refetch: $e');
      rethrow;
    }
  }

  /// Check if onboarding is complete
  Future<bool> isOnboardingComplete() async {
    try {
      final status = await getOnboardingStatus();
      return status['completed'] == true;
    } catch (e) {
      debugPrint('Error checking onboarding completion: $e');
      return false;
    }
  }

  /// Get resume step for incomplete onboarding
  Future<String?> getResumeStep() async {
    try {
      final status = await getOnboardingStatus();
      if (status['completed'] == true) {
        return 'COMPLETE';
      }
      return status['resume_step'];
    } catch (e) {
      debugPrint('Error getting resume step: $e');
      return null;
    }
  }
}
