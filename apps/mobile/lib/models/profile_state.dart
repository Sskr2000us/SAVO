import 'package:flutter/foundation.dart';

/// Model representing the complete user profile state
class ProfileState extends ChangeNotifier {
  Map<String, dynamic>? _profileData;
  Map<String, dynamic>? _onboardingStatus;
  bool _isLoading = false;
  String? _error;

  // Getters
  Map<String, dynamic>? get profileData => _profileData;
  Map<String, dynamic>? get onboardingStatus => _onboardingStatus;
  bool get isLoading => _isLoading;
  String? get error => _error;
  
  bool get isOnboardingComplete => 
      _onboardingStatus?['completed'] == true;
  
  String? get resumeStep => 
      _onboardingStatus?['resume_step'];
  
  List<String> get missingFields => 
      List<String>.from(_onboardingStatus?['missing_fields'] ?? []);

  // User data accessors
  Map<String, dynamic>? get user => _profileData?['user'];
  Map<String, dynamic>? get household => _profileData?['household'];
  Map<String, dynamic>? get profile => _profileData?['profile'];
  List<dynamic> get members => _profileData?['members'] ?? [];
  Map<String, dynamic>? get allergens => _profileData?['allergens'];
  Map<String, dynamic>? get dietary => _profileData?['dietary'];

  String? get userId => user?['id'];
  String? get userEmail => user?['email'];
  String? get householdName => household?['name'];
  String? get primaryLanguage => household?['primary_language'];
  String? get preferredLanguage => household?['preferred_language'];
  String? get measurementSystem => household?['measurement_system'];
  bool? get basicSpicesAvailable => household?['basic_spices_available'];

  List<String> get favoriteCuisines =>
      List<String>.from(household?['favorite_cuisines'] ?? const <String>[]);
  
  List<String> get declaredAllergens => 
      List<String>.from(allergens?['declared_allergens'] ?? []);
  
  bool get isVegetarian => dietary?['vegetarian'] == true;
  bool get isVegan => dietary?['vegan'] == true;
  bool get noBeef => dietary?['no_beef'] == true;
  bool get noPork => dietary?['no_pork'] == true;
  bool get noAlcohol => dietary?['no_alcohol'] == true;

  // Update methods
  void setLoading(bool loading) {
    _isLoading = loading;
    notifyListeners();
  }

  void setError(String? error) {
    _error = error;
    notifyListeners();
  }

  void updateProfileData(Map<String, dynamic> data) {
    _profileData = data;
    _error = null;
    notifyListeners();
  }

  void updateOnboardingStatus(Map<String, dynamic> status) {
    _onboardingStatus = status;
    _error = null;
    notifyListeners();
  }

  void clearError() {
    _error = null;
    notifyListeners();
  }

  void clear() {
    _profileData = null;
    _onboardingStatus = null;
    _isLoading = false;
    _error = null;
    notifyListeners();
  }

  // Convenience methods for onboarding screens
  bool hasHouseholdProfile() {
    return household != null && household!.isNotEmpty;
  }

  bool hasMembers() {
    return members.isNotEmpty;
  }

  bool hasAllergensDeclared() {
    return allergens != null && allergens!.containsKey('declared_allergens');
  }

  bool hasDietaryDeclared() {
    return dietary != null && dietary!.isNotEmpty;
  }

  String? getSpiceTolerance() {
    // Get from first member or household default
    if (members.isNotEmpty) {
      final firstMember = members.first;
      return firstMember['spice_tolerance'];
    }
    return null;
  }

  // Get member by ID
  Map<String, dynamic>? getMemberById(String memberId) {
    try {
      return members.firstWhere(
        (m) => m['id'] == memberId,
        orElse: () => null,
      );
    } catch (e) {
      return null;
    }
  }

  // Check if specific step is complete
  bool isStepComplete(String step) {
    if (_onboardingStatus == null) return false;
    
    switch (step) {
      case 'HOUSEHOLD':
        return hasMembers();
      case 'ALLERGIES':
        return hasAllergensDeclared();
      case 'DIETARY':
        return hasDietaryDeclared();
      case 'SPICE':
        return getSpiceTolerance() != null;
      case 'PANTRY':
        return basicSpicesAvailable != null;
      case 'LANGUAGE':
        return primaryLanguage != null && primaryLanguage!.isNotEmpty;
      case 'COMPLETE':
        return isOnboardingComplete;
      default:
        return false;
    }
  }
}
