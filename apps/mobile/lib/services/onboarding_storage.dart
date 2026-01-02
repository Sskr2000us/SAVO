import 'package:shared_preferences/shared_preferences.dart';

/// Service for persisting onboarding state locally
/// Provides offline fallback when server is unreachable
class OnboardingStorage {
  static const String _keyLastStep = 'onboarding_last_step';
  static const String _keyCompleted = 'onboarding_completed';
  static const String _keyLastUserId = 'onboarding_last_user_id';

  /// Step order mapping (1-indexed for SharedPreferences int storage)
  static const Map<String, int> stepToIndex = {
    'LOGIN': 1,
    'HOUSEHOLD': 2,
    'ALLERGIES': 3,
    'DIETARY': 4,
    'SPICE': 5,
    'PANTRY': 6,
    'LANGUAGE': 7,
    'COMPLETE': 8,
  };

  static const Map<int, String> indexToStep = {
    1: 'LOGIN',
    2: 'HOUSEHOLD',
    3: 'ALLERGIES',
    4: 'DIETARY',
    5: 'SPICE',
    6: 'PANTRY',
    7: 'LANGUAGE',
    8: 'COMPLETE',
  };

  /// Save the last completed step for offline resume
  /// Call this after successful API submission
  static Future<void> saveLastStep(String step, String userId) async {
    final prefs = await SharedPreferences.getInstance();
    final stepIndex = stepToIndex[step];
    
    if (stepIndex != null) {
      await prefs.setInt(_keyLastStep, stepIndex);
      await prefs.setString(_keyLastUserId, userId);
      
      // Mark as completed if reached COMPLETE step
      if (step == 'COMPLETE') {
        await prefs.setBool(_keyCompleted, true);
      }
    }
  }

  /// Get the last saved step for resume
  /// Returns null if no cached step or user mismatch
  static Future<String?> getLastStep(String currentUserId) async {
    final prefs = await SharedPreferences.getInstance();
    
    // Check if cached data is for current user
    final cachedUserId = prefs.getString(_keyLastUserId);
    if (cachedUserId == null || cachedUserId != currentUserId) {
      // Different user or no cache - clear and return null
      await clearOnboardingData();
      return null;
    }
    
    final stepIndex = prefs.getInt(_keyLastStep);
    return stepIndex != null ? indexToStep[stepIndex] : null;
  }

  /// Get onboarding completion status from local cache
  static Future<bool> isOnboardingComplete(String currentUserId) async {
    final prefs = await SharedPreferences.getInstance();
    
    // Check if cached data is for current user
    final cachedUserId = prefs.getString(_keyLastUserId);
    if (cachedUserId == null || cachedUserId != currentUserId) {
      return false;
    }
    
    return prefs.getBool(_keyCompleted) ?? false;
  }

  /// Clear all onboarding data (e.g., on logout or user change)
  static Future<void> clearOnboardingData() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_keyLastStep);
    await prefs.remove(_keyCompleted);
    await prefs.remove(_keyLastUserId);
  }

  /// Get the next step in the onboarding flow
  static String? getNextStep(String currentStep) {
    final nextSteps = {
      'LOGIN': 'HOUSEHOLD',
      'HOUSEHOLD': 'ALLERGIES',
      'ALLERGIES': 'DIETARY',
      'DIETARY': 'SPICE',
      'SPICE': 'PANTRY',
      'PANTRY': 'LANGUAGE',
      'LANGUAGE': 'COMPLETE',
      'COMPLETE': null, // Onboarding complete
    };
    
    return nextSteps[currentStep];
  }

  /// Calculate resume step based on last completed step
  /// Returns the next step that should be shown
  static String getResumeStep(String lastCompletedStep) {
    final nextStep = getNextStep(lastCompletedStep);
    return nextStep ?? 'COMPLETE';
  }
}
