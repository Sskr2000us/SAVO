import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_client.dart';
import '../services/auth_service.dart';
import '../theme/app_theme.dart';
import '../widgets/savo_widgets.dart';
import 'inventory_screen.dart';
import 'settings/active_sessions_screen.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _formKey = GlobalKey<FormState>();
  
  // Family members list
  List<Map<String, dynamic>> _familyMembers = [];
  
  // Regional settings
  String _region = 'US';
  String _culture = 'western';
  
  // Meal times
  String _breakfastTime = '07:00-09:00';
  String _lunchTime = '12:00-14:00';
  String _dinnerTime = '18:00-21:00';
  
  // Meal preferences
  String _breakfastStyle = 'continental';
  String _lunchStyle = 'balanced';
  String _dinnerStyle = 'family_meal';
  int _dinnerCourses = 2;

  // Cuisine preferences (min 1, max 5)
  List<String> _favoriteCuisines = const ['Italian', 'American'];
  List<String> _availableCuisines = const [
    'Italian',
    'Indian',
    'Mexican',
    'Chinese',
    'Japanese',
    'French',
    'Mediterranean',
    'Thai',
    'American',
    'Middle Eastern',
  ];
  
  // Cooking skill level
  int _skillLevel = 2; // 1=Beginner, 2=Basic, 3=Intermediate, 4=Multi-step, 5=Advanced
  
  bool _isLoading = false;
  bool _isSaving = false;

  @override
  void initState() {
    super.initState();
    _loadConfiguration();
  }

  Future<void> _handleSignOut() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Sign Out?'),
        content: const Text(
          'Are you sure you want to sign out? You will need to sign in again to access your account.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.red,
            ),
            child: const Text('Sign Out'),
          ),
        ],
      ),
    );

    if (confirmed != true || !mounted) return;

    try {
      final authService = Provider.of<AuthService>(context, listen: false);
      await authService.signOut();

      if (mounted) {
        // Navigate to login screen and remove all previous routes
        Navigator.of(context).pushNamedAndRemoveUntil(
          '/login',
          (route) => false,
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to sign out: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  Future<void> _loadConfiguration() async {
    setState(() => _isLoading = true);
    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      
      // Load household profile from database
      final householdResponse = await apiClient.get('/profile/household');
      
      // Load family members from database
      final membersResponse = await apiClient.get('/profile/family-members');

      // Load cuisine options (best-effort)
      try {
        final cuisinesResponse = await apiClient.get('/cuisines');
        final List<dynamic>? cuisineList = cuisinesResponse is Map && cuisinesResponse['cuisines'] is List
            ? cuisinesResponse['cuisines'] as List
            : (cuisinesResponse is List ? cuisinesResponse : null);

        if (cuisineList != null) {
          final names = cuisineList
              .whereType<Map>()
              .map((c) => c['name'])
              .whereType<String>()
              .where((s) => s.trim().isNotEmpty)
              .toSet()
              .toList();
          if (names.isNotEmpty) {
            names.sort();
            _availableCuisines = names;
          }
        }
      } catch (_) {
        // Ignore cuisine list load errors; fallback list is fine.
      }
      
      setState(() {
        // Load household profile
        if (householdResponse != null && householdResponse['exists'] == true) {
          final profile = householdResponse['profile'] as Map<String, dynamic>;
          _region = profile['region'] ?? 'US';
          _culture = profile['culture'] ?? 'western';

          final fav = profile['favorite_cuisines'] as List?;
          if (fav != null) {
            final parsed = fav.whereType<String>().where((s) => s.trim().isNotEmpty).toList();
            if (parsed.isNotEmpty) {
              // Enforce max 5.
              _favoriteCuisines = parsed.take(5).toList();
            }
          }
          
          final mealTimes = profile['meal_times'] as Map<String, dynamic>?;
          if (mealTimes != null) {
            _breakfastTime = mealTimes['breakfast'] ?? '07:00-09:00';
            _lunchTime = mealTimes['lunch'] ?? '12:00-14:00';
            _dinnerTime = mealTimes['dinner'] ?? '18:00-21:00';
          }
          
          final breakfastPrefs = profile['breakfast_preferences'] as List?;
          if (breakfastPrefs != null && breakfastPrefs.isNotEmpty) {
            _breakfastStyle = breakfastPrefs[0] ?? 'continental';
          }
          
          final lunchPrefs = profile['lunch_preferences'] as List?;
          if (lunchPrefs != null && lunchPrefs.isNotEmpty) {
            _lunchStyle = lunchPrefs[0] ?? 'balanced';
          }
          
          final dinnerPrefs = profile['dinner_preferences'] as List?;
          if (dinnerPrefs != null && dinnerPrefs.isNotEmpty) {
            _dinnerStyle = dinnerPrefs[0] ?? 'family_meal';
          }
          
          // Load skill level and dinner courses
          _skillLevel = profile['skill_level'] ?? 2;
          _dinnerCourses = profile['dinner_courses'] ?? 2;
        }
        
        // Load family members
        if (membersResponse != null && membersResponse['members'] is List) {
          _familyMembers = (membersResponse['members'] as List)
              .cast<Map<String, dynamic>>();
        }
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to load configuration: $e')),
        );
      }
    } finally {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _saveHouseholdProfile() async {
    setState(() => _isSaving = true);
    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);

      if (_favoriteCuisines.isEmpty) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Please select at least 1 cuisine (max 5).'),
              backgroundColor: AppColors.danger,
            ),
          );
        }
        return;
      }
      
      // Check if household exists
      final existsResponse = await apiClient.get('/profile/household');
      final householdExists = existsResponse?['exists'] == true;
      
      // Prepare household data
      final householdData = {
        'region': _region,
        'culture': _culture,
        'meal_times': {
          'breakfast': _breakfastTime,
          'lunch': _lunchTime,
          'dinner': _dinnerTime,
        },
        'breakfast_preferences': [_breakfastStyle],
        'lunch_preferences': [_lunchStyle],
        'dinner_preferences': [_dinnerStyle],
        'favorite_cuisines': _favoriteCuisines,
        'skill_level': _skillLevel,
        'dinner_courses': _dinnerCourses,
      };
      
      // Create or update household profile in database
      if (householdExists) {
        await apiClient.patch('/profile/household', householdData);
      } else {
        await apiClient.post('/profile/household', householdData);
      }
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Household settings saved to database!'),
            backgroundColor: AppColors.success,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to save household settings: $e'),
            backgroundColor: AppColors.danger,
          ),
        );
      }
    } finally {
      setState(() => _isSaving = false);
    }
  }

  Future<void> _saveFamilyMembers() async {
    setState(() => _isSaving = true);
    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      
      // Ensure household profile exists first
      final householdResponse = await apiClient.get('/profile/household');
      if (householdResponse?['exists'] != true) {
        // Create household profile first if it doesn't exist
        await _saveHouseholdProfile();
      }
      
      // Delete existing members first
      try {
        final existingMembers = await apiClient.get('/profile/family-members');
        
        if (existingMembers?['members'] is List) {
          for (var member in existingMembers['members']) {
            await apiClient.delete('/profile/family-members/${member['id']}');
          }
        }
      } catch (e) {
        // Ignore errors when deleting (members might not exist yet)
        debugPrint('No existing members to delete: $e');
      }
      
      // Add new family members
      for (var i = 0; i < _familyMembers.length; i++) {
        final member = _familyMembers[i];
        
        // Convert medical_dietary_needs to array if it's a Map
        List<String> medicalNeeds = [];
        if (member['medical_dietary_needs'] is List) {
          medicalNeeds = List<String>.from(member['medical_dietary_needs']);
        }
        
        final memberData = {
          'name': member['name'] ?? 'Family Member',
          'age': member['age'] ?? 30,
          'age_category': member['age_category'] ?? 'adult',
          'dietary_restrictions': member['dietary_restrictions'] ?? [],
          'allergens': member['allergens'] ?? [],
          'health_conditions': member['health_conditions'] ?? [],
          'medical_dietary_needs': medicalNeeds,
          'spice_tolerance': member['spice_tolerance'] ?? 'medium',
          'food_preferences': member['food_preferences'] ?? [],
          'food_dislikes': member['food_dislikes'] ?? [],
          'display_order': i,
        };
        
        await apiClient.post('/profile/family-members', memberData);
      }
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Family members saved to database!'),
            backgroundColor: AppColors.success,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        // Show detailed error message
        final errorMessage = e.toString().contains('Exception: ')
            ? e.toString().replaceFirst('Exception: ', '')
            : e.toString();
        
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to save family members: $errorMessage'),
            backgroundColor: AppColors.danger,
            duration: const Duration(seconds: 5),
          ),
        );
        
        debugPrint('Full error saving family members: $e');
      }
    } finally {
      setState(() => _isSaving = false);
    }
  }

  Future<void> _saveConfiguration() async {
    // Save both household and family members
    await _saveHouseholdProfile();
    if (mounted && !_isSaving) {
      await _saveFamilyMembers();
    }
  }

  void _addFamilyMember() {
    setState(() {
      _familyMembers.add({
        'member_id': 'member_${DateTime.now().millisecondsSinceEpoch}',
        'name': '',
        'age': 30,
        'age_category': 'adult',
        'dietary_restrictions': <String>[],
        'allergens': <String>[],
        'health_conditions': <String>[],
        'medical_dietary_needs': <String>[],
        'spice_tolerance': 'medium',
        'food_preferences': <String>[],
        'food_dislikes': <String>[],
      });
    });
  }

  void _removeFamilyMember(int index) {
    setState(() {
      _familyMembers.removeAt(index);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Family Profile Settings'),
        actions: [
          if (_isSaving)
            const Center(
              child: Padding(
                padding: EdgeInsets.symmetric(horizontal: 16.0),
                child: SizedBox(
                  width: 24,
                  height: 24,
                  child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                ),
              ),
            )
          else
            IconButton(
              icon: const Icon(Icons.save, color: Colors.white),
              onPressed: _saveConfiguration,
              tooltip: 'Save Settings',
              iconSize: 28,
            ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : Form(
              key: _formKey,
              child: ListView(
                padding: const EdgeInsets.all(AppSpacing.md),
                children: [
                  // Regional Settings Section
                  _buildSectionHeader('Regional & Cultural Settings'),
                  SavoCard(
                    child: Column(
                      children: [
                        _buildDropdown(
                          label: 'Region',
                          value: _region,
                          items: const ['US', 'IN', 'UK', 'CA', 'AU'],
                          onChanged: (value) => setState(() => _region = value!),
                        ),
                        const SizedBox(height: AppSpacing.md),
                        _buildDropdown(
                          label: 'Culture',
                          value: _culture,
                          items: const ['western', 'indian', 'asian', 'middle_eastern', 'mediterranean'],
                          onChanged: (value) => setState(() => _culture = value!),
                        ),
                        const SizedBox(height: AppSpacing.md),
                        SizedBox(
                          width: double.infinity,
                          child: ElevatedButton.icon(
                            onPressed: _saveHouseholdProfile,
                            icon: const Icon(Icons.save),
                            label: const Text('Save Regional Settings'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: AppColors.primary,
                              padding: const EdgeInsets.symmetric(vertical: 12),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: AppSpacing.lg),

                  // Cuisine Preferences Section
                  _buildSectionHeader('Cuisine Preferences'),
                  SavoCard(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Select 1–5 cuisines you prefer. These will be sent to planning requests.',
                          style: AppTypography.captionStyle(color: AppColors.textSecondary),
                        ),
                        const SizedBox(height: AppSpacing.md),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: _availableCuisines.map((cuisine) {
                            final selected = _favoriteCuisines.contains(cuisine);
                            return FilterChip(
                              label: Text(cuisine),
                              selected: selected,
                              onSelected: (value) {
                                setState(() {
                                  if (value) {
                                    if (_favoriteCuisines.length >= 5) {
                                      ScaffoldMessenger.of(context).showSnackBar(
                                        const SnackBar(
                                          content: Text('You can select up to 5 cuisines.'),
                                          backgroundColor: AppColors.danger,
                                        ),
                                      );
                                      return;
                                    }
                                    _favoriteCuisines = [..._favoriteCuisines, cuisine];
                                  } else {
                                    if (_favoriteCuisines.length <= 1) {
                                      ScaffoldMessenger.of(context).showSnackBar(
                                        const SnackBar(
                                          content: Text('Please keep at least 1 cuisine selected.'),
                                          backgroundColor: AppColors.danger,
                                        ),
                                      );
                                      return;
                                    }
                                    _favoriteCuisines = _favoriteCuisines.where((c) => c != cuisine).toList();
                                  }
                                });
                              },
                            );
                          }).toList(),
                        ),
                        const SizedBox(height: AppSpacing.md),
                        SizedBox(
                          width: double.infinity,
                          child: ElevatedButton.icon(
                            onPressed: _saveHouseholdProfile,
                            icon: const Icon(Icons.save),
                            label: const Text('Save Cuisine Preferences'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: AppColors.primary,
                              padding: const EdgeInsets.symmetric(vertical: 12),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: AppSpacing.lg),

                  // Meal Times Section
                  _buildSectionHeader('Meal Times'),
                  SavoCard(
                    child: Column(
                      children: [
                        _buildTextField(
                          label: 'Breakfast Time',
                          value: _breakfastTime,
                          hint: '07:00-09:00',
                          onChanged: (value) => _breakfastTime = value,
                        ),
                        const SizedBox(height: AppSpacing.md),
                        _buildTextField(
                          label: 'Lunch Time',
                          value: _lunchTime,
                          hint: '12:00-14:00',
                          onChanged: (value) => _lunchTime = value,
                        ),
                        const SizedBox(height: AppSpacing.md),
                        _buildTextField(
                          label: 'Dinner Time',
                          value: _dinnerTime,
                          hint: '18:00-21:00',
                          onChanged: (value) => _dinnerTime = value,
                        ),
                        const SizedBox(height: AppSpacing.md),
                        SizedBox(
                          width: double.infinity,
                          child: ElevatedButton.icon(
                            onPressed: _saveHouseholdProfile,
                            icon: const Icon(Icons.save),
                            label: const Text('Save Meal Times'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: AppColors.primary,
                              padding: const EdgeInsets.symmetric(vertical: 12),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: AppSpacing.lg),

                  // Meal Preferences Section
                  _buildSectionHeader('Meal Preferences'),
                  SavoCard(
                    child: Column(
                      children: [
                        _buildDropdown(
                          label: 'Breakfast Style',
                          value: _breakfastStyle,
                          items: const ['continental', 'indian', 'american', 'healthy'],
                          onChanged: (value) => setState(() => _breakfastStyle = value!),
                        ),
                        const SizedBox(height: AppSpacing.md),
                        _buildDropdown(
                          label: 'Lunch Style',
                          value: _lunchStyle,
                          items: const ['balanced', 'light', 'hearty', 'quick'],
                          onChanged: (value) => setState(() => _lunchStyle = value!),
                        ),
                        const SizedBox(height: AppSpacing.md),
                        _buildDropdown(
                          label: 'Dinner Style',
                          value: _dinnerStyle,
                          items: const ['family_meal', 'romantic', 'quick', 'elaborate'],
                          onChanged: (value) => setState(() => _dinnerStyle = value!),
                        ),
                        const SizedBox(height: AppSpacing.md),
                        _buildNumberField(
                          label: 'Dinner Courses',
                          value: _dinnerCourses,
                          min: 1,
                          max: 5,
                          onChanged: (value) => setState(() => _dinnerCourses = value),
                        ),
                        const SizedBox(height: AppSpacing.md),
                        SizedBox(
                          width: double.infinity,
                          child: ElevatedButton.icon(
                            onPressed: _saveHouseholdProfile,
                            icon: const Icon(Icons.save),
                            label: const Text('Save Meal Preferences'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: AppColors.primary,
                              padding: const EdgeInsets.symmetric(vertical: 12),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: AppSpacing.lg),

                  // Cooking Skill Level Section
                  _buildSectionHeader('Cooking Skill Level'),
                  SavoCard(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Your cooking experience helps us recommend appropriate recipes',
                          style: AppTypography.captionStyle(color: AppColors.textSecondary),
                        ),
                        const SizedBox(height: AppSpacing.md),
                        _buildSkillLevelSelector(),
                        const SizedBox(height: AppSpacing.md),
                        SizedBox(
                          width: double.infinity,
                          child: ElevatedButton.icon(
                            onPressed: _saveHouseholdProfile,
                            icon: const Icon(Icons.save),
                            label: const Text('Save Skill Level'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: AppColors.primary,
                              padding: const EdgeInsets.symmetric(vertical: 12),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: AppSpacing.lg),

                  // Family Members Section
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      _buildSectionHeader('Family Members (${_familyMembers.length})'),
                      ElevatedButton.icon(
                        onPressed: _addFamilyMember,
                        icon: const Icon(Icons.add),
                        label: const Text('Add Member'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppColors.secondary,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  
                  // Info card about individual preferences
                  Container(
                    padding: const EdgeInsets.all(12),
                    margin: const EdgeInsets.only(bottom: AppSpacing.md),
                    decoration: BoxDecoration(
                      color: Colors.blue.shade50,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.blue.shade200),
                    ),
                    child: Row(
                      children: const [
                        Icon(Icons.info_outline, size: 20, color: Colors.blue),
                        SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            'Each family member can have their own dietary restrictions and allergens',
                            style: TextStyle(fontSize: 13, color: Colors.black87),
                          ),
                        ),
                      ],
                    ),
                  ),

                  // Family members list
                  if (_familyMembers.isEmpty)
                    SavoCard(
                      child: Center(
                        child: Padding(
                          padding: const EdgeInsets.all(AppSpacing.lg),
                          child: Column(
                            children: [
                              Icon(Icons.people_outline, size: 48, color: AppColors.textSecondary),
                              const SizedBox(height: AppSpacing.sm),
                              Text(
                                'No family members added yet',
                                style: AppTypography.bodyStyle(color: AppColors.textSecondary),
                              ),
                              const SizedBox(height: AppSpacing.xs),
                              Text(
                                'Add members to personalize meal planning',
                                style: AppTypography.captionStyle(color: AppColors.textSecondary),
                              ),
                            ],
                          ),
                        ),
                      ),
                    )
                  else
                    ..._familyMembers.asMap().entries.map((entry) {
                      final index = entry.key;
                      final member = entry.value;
                      return _buildFamilyMemberCard(index, member);
                    }),

                  // Save Family Members button
                  if (_familyMembers.isNotEmpty) ...[
                    const SizedBox(height: AppSpacing.md),
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton.icon(
                        onPressed: _saveFamilyMembers,
                        icon: const Icon(Icons.save),
                        label: const Text('Save Family Members'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppColors.secondary,
                          padding: const EdgeInsets.symmetric(vertical: 12),
                        ),
                      ),
                    ),
                  ],

                  const SizedBox(height: AppSpacing.xl),
                ],
              ),
            ),
      floatingActionButton: _isSaving
          ? null
          : FloatingActionButton.extended(
              onPressed: _saveConfiguration,
              icon: const Icon(Icons.save),
              label: const Text('Save Profile'),
              backgroundColor: AppColors.primary,
              tooltip: 'Save all changes to database',
            ),
    );
  }

  Widget _buildQuickAction({
    required IconData icon,
    required String title,
    required VoidCallback onTap,
  }) {
    return SavoCard(
      child: ListTile(
        leading: Icon(icon, color: AppColors.primary),
        title: Text(title, style: AppTypography.bodyStyle()),
        trailing: const Icon(Icons.arrow_forward_ios, size: 16),
        onTap: onTap,
      ),
    );
  }

  Widget _buildSectionHeader(String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: Text(
        title,
        style: AppTypography.h2Style(),
      ),
    );
  }

  Widget _buildFamilyMemberCard(int index, Map<String, dynamic> member) {
    // Get member's dietary restrictions for summary
    final dietaryRestrictions = List<String>.from(member['dietary_restrictions'] ?? []);
    final allergens = List<String>.from(member['allergens'] ?? []);
    
    // Build summary text
    String summaryText = '${member['age'] ?? 30} years old • ${member['age_category'] ?? 'adult'}';
    if (dietaryRestrictions.isNotEmpty) {
      summaryText += '\nDietary: ${dietaryRestrictions.join(", ")}';
    }
    if (allergens.isNotEmpty) {
      summaryText += '\nAllergens: ${allergens.join(", ")}';
    }
    
    return Card(
      margin: const EdgeInsets.only(bottom: AppSpacing.md),
      child: ExpansionTile(
        title: Text(
          member['name']?.isEmpty ?? true
              ? 'New Family Member'
              : member['name'],
          style: AppTypography.h2Style(),
        ),
        subtitle: Text(
          summaryText,
          style: AppTypography.captionStyle(),
          maxLines: 3,
          overflow: TextOverflow.ellipsis,
        ),
        trailing: IconButton(
          icon: const Icon(Icons.delete, color: AppColors.danger),
          onPressed: () => _removeFamilyMember(index),
        ),
        children: [
          Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Basic Info
                _buildTextField(
                  label: 'Name',
                  value: member['name'] ?? '',
                  onChanged: (value) {
                    setState(() {
                      _familyMembers[index]['name'] = value;
                    });
                  },
                ),
                const SizedBox(height: AppSpacing.md),

                Row(
                  children: [
                    Expanded(
                      child: _buildNumberField(
                        label: 'Age',
                        value: member['age'] ?? 30,
                        min: 0,
                        max: 120,
                        onChanged: (value) {
                          setState(() {
                            _familyMembers[index]['age'] = value;
                            // Auto-set age category
                            if (value < 13) {
                              _familyMembers[index]['age_category'] = 'child';
                            } else if (value < 18) {
                              _familyMembers[index]['age_category'] = 'teen';
                            } else if (value < 65) {
                              _familyMembers[index]['age_category'] = 'adult';
                            } else {
                              _familyMembers[index]['age_category'] = 'senior';
                            }
                          });
                        },
                      ),
                    ),
                    const SizedBox(width: AppSpacing.md),
                    Expanded(
                      child: _buildDropdown(
                        label: 'Category',
                        value: member['age_category'] ?? 'adult',
                        items: const ['child', 'teen', 'adult', 'senior'],
                        onChanged: (value) {
                          setState(() {
                            _familyMembers[index]['age_category'] = value;
                          });
                        },
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: AppSpacing.md),

                // Dietary Restrictions
                _buildMultiSelectChips(
                  label: 'Dietary Restrictions',
                  options: const [
                    'vegetarian',
                    'vegan',
                    'halal',
                    'kosher',
                    'gluten-free',
                    'dairy-free',
                    'pescatarian',
                  ],
                  selected: List<String>.from(member['dietary_restrictions'] ?? []),
                  onChanged: (selected) {
                    setState(() {
                      _familyMembers[index]['dietary_restrictions'] = selected;
                    });
                  },
                ),
                const SizedBox(height: AppSpacing.md),

                // Allergens (with safety confirmation for removal)
                _buildAllergenChips(
                  label: 'Allergens',
                  options: const [
                    'peanuts',
                    'tree nuts',
                    'shellfish',
                    'fish',
                    'eggs',
                    'milk',
                    'soy',
                    'wheat',
                  ],
                  selected: List<String>.from(member['allergens'] ?? []),
                  memberName: member['name'] ?? 'member',
                  onChanged: (selected) {
                    setState(() {
                      _familyMembers[index]['allergens'] = selected;
                    });
                  },
                ),
                const SizedBox(height: AppSpacing.md),

                // Health Conditions
                _buildMultiSelectChips(
                  label: 'Health Conditions',
                  options: const [
                    'diabetes',
                    'hypertension',
                    'high_cholesterol',
                    'kidney_disease',
                    'heart_disease',
                  ],
                  selected: List<String>.from(member['health_conditions'] ?? []),
                  onChanged: (selected) {
                    setState(() {
                      _familyMembers[index]['health_conditions'] = selected;
                    });
                  },
                ),
                const SizedBox(height: AppSpacing.md),

                // Medical Dietary Needs
                Text('Medical Dietary Needs', style: AppTypography.bodyStyle()),
                const SizedBox(height: AppSpacing.sm),
                Wrap(
                  spacing: AppSpacing.sm,
                  runSpacing: AppSpacing.sm,
                  children: [
                    _buildCheckbox(
                      label: 'Low Sodium',
                      value: (member['medical_dietary_needs'] as List?)?.contains('low_sodium') ?? false,
                      onChanged: (value) {
                        setState(() {
                          _familyMembers[index]['medical_dietary_needs'] ??= [];
                          final list = _familyMembers[index]['medical_dietary_needs'] as List;
                          if (value) {
                            if (!list.contains('low_sodium')) list.add('low_sodium');
                          } else {
                            list.remove('low_sodium');
                          }
                        });
                      },
                    ),
                    _buildCheckbox(
                      label: 'Low Sugar',
                      value: (member['medical_dietary_needs'] as List?)?.contains('low_sugar') ?? false,
                      onChanged: (value) {
                        setState(() {
                          _familyMembers[index]['medical_dietary_needs'] ??= [];
                          final list = _familyMembers[index]['medical_dietary_needs'] as List;
                          if (value) {
                            if (!list.contains('low_sugar')) list.add('low_sugar');
                          } else {
                            list.remove('low_sugar');
                          }
                        });
                      },
                    ),
                    _buildCheckbox(
                      label: 'Low Fat',
                      value: (member['medical_dietary_needs'] as List?)?.contains('low_fat') ?? false,
                      onChanged: (value) {
                        setState(() {
                          _familyMembers[index]['medical_dietary_needs'] ??= [];
                          final list = _familyMembers[index]['medical_dietary_needs'] as List;
                          if (value) {
                            if (!list.contains('low_fat')) list.add('low_fat');
                          } else {
                            list.remove('low_fat');
                          }
                        });
                      },
                    ),
                  ],
                ),
                const SizedBox(height: AppSpacing.md),

                // Spice Tolerance
                _buildDropdown(
                  label: 'Spice Tolerance',
                  value: member['spice_tolerance'] ?? 'medium',
                  items: const ['none', 'mild', 'medium', 'high', 'very_high'],
                  onChanged: (value) {
                    setState(() {
                      _familyMembers[index]['spice_tolerance'] = value;
                    });
                  },
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTextField({
    required String label,
    required String value,
    String? hint,
    required Function(String) onChanged,
  }) {
    return TextFormField(
      initialValue: value,
      decoration: InputDecoration(
        labelText: label,
        hintText: hint,
        border: const OutlineInputBorder(),
      ),
      onChanged: onChanged,
    );
  }

  Widget _buildNumberField({
    required String label,
    required int value,
    required int min,
    required int max,
    required Function(int) onChanged,
  }) {
    return TextFormField(
      initialValue: value.toString(),
      decoration: InputDecoration(
        labelText: label,
        border: const OutlineInputBorder(),
      ),
      keyboardType: TextInputType.number,
      onChanged: (text) {
        final number = int.tryParse(text);
        if (number != null && number >= min && number <= max) {
          onChanged(number);
        }
      },
    );
  }

  Widget _buildDropdown({
    required String label,
    required String value,
    required List<String> items,
    required Function(String?) onChanged,
  }) {
    return DropdownButtonFormField<String>(
      value: value,
      decoration: InputDecoration(
        labelText: label,
        border: const OutlineInputBorder(),
      ),
      items: items.map((item) {
        return DropdownMenuItem(
          value: item,
          child: Text(item.replaceAll('_', ' ').toUpperCase()),
        );
      }).toList(),
      onChanged: onChanged,
    );
  }

  Widget _buildMultiSelectChips({
    required String label,
    required List<String> options,
    required List<String> selected,
    required Function(List<String>) onChanged,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: AppTypography.bodyStyle()),
        const SizedBox(height: AppSpacing.sm),
        Wrap(
          spacing: AppSpacing.sm,
          runSpacing: AppSpacing.sm,
          children: options.map((option) {
            final isSelected = selected.contains(option);
            return FilterChip(
              label: Text(option.replaceAll('_', ' ')),
              selected: isSelected,
              onSelected: (isNowSelected) {
                final newSelected = List<String>.from(selected);
                if (isNowSelected) {
                  newSelected.add(option);
                } else {
                  newSelected.remove(option);
                }
                onChanged(newSelected);
              },
              selectedColor: AppColors.secondary.withOpacity(0.3),
              checkmarkColor: AppColors.secondary,
            );
          }).toList(),
        ),
      ],
    );
  }

  /// Special allergen chips with removal confirmation dialog
  Widget _buildAllergenChips({
    required String label,
    required List<String> options,
    required List<String> selected,
    required String memberName,
    required Function(List<String>) onChanged,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(label, style: AppTypography.bodyStyle()),
            const SizedBox(width: 8),
            const Icon(Icons.warning_amber, size: 16, color: Colors.orange),
          ],
        ),
        const SizedBox(height: AppSpacing.sm),
        Wrap(
          spacing: AppSpacing.sm,
          runSpacing: AppSpacing.sm,
          children: options.map((option) {
            final isSelected = selected.contains(option);
            return FilterChip(
              label: Text(option.replaceAll('_', ' ')),
              selected: isSelected,
              onSelected: (isNowSelected) async {
                // Adding allergen - no confirmation needed
                if (isNowSelected) {
                  final newSelected = List<String>.from(selected);
                  newSelected.add(option);
                  onChanged(newSelected);
                  return;
                }
                
                // Removing allergen - show confirmation dialog
                final confirmed = await _showAllergenRemovalConfirmation(
                  context,
                  option,
                  memberName,
                );
                
                if (confirmed == true) {
                  final newSelected = List<String>.from(selected);
                  newSelected.remove(option);
                  onChanged(newSelected);
                }
              },
              selectedColor: Colors.red.withOpacity(0.2),
              checkmarkColor: Colors.red,
            );
          }).toList(),
        ),
        const SizedBox(height: 4),
        const Text(
          'Safety note: Removing allergens will allow SAVO to suggest recipes containing them.',
          style: TextStyle(fontSize: 12, color: Colors.orange, fontStyle: FontStyle.italic),
        ),
      ],
    );
  }

  /// Show confirmation dialog when removing an allergen
  Future<bool?> _showAllergenRemovalConfirmation(
    BuildContext context,
    String allergen,
    String memberName,
  ) {
    return showDialog<bool>(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: const Row(
            children: [
              Icon(Icons.warning_amber, color: Colors.orange, size: 32),
              SizedBox(width: 12),
              Text('Remove Allergen?'),
            ],
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Are you sure you want to remove "$allergen" from ${memberName}\'s allergen list?',
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.orange.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.orange.withOpacity(0.3)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Row(
                      children: [
                        Icon(Icons.info_outline, size: 20, color: Colors.orange),
                        SizedBox(width: 8),
                        Text(
                          'Important:',
                          style: TextStyle(fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'SAVO will start including "$allergen" in recipe suggestions for $memberName.',
                      style: const TextStyle(fontSize: 14),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'This change will be logged for your safety.',
                      style: TextStyle(fontSize: 12, fontStyle: FontStyle.italic),
                    ),
                  ],
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(false),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              onPressed: () => Navigator.of(context).pop(true),
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.orange,
                foregroundColor: Colors.white,
              ),
              child: const Text('Yes, Remove'),
            ),
          ],
        );
      },
    );
  }

  Widget _buildCheckbox({
    required String label,
    required bool value,
    required Function(bool) onChanged,
  }) {
    return IntrinsicWidth(
      child: Row(
        children: [
          Checkbox(
            value: value,
            onChanged: (newValue) => onChanged(newValue ?? false),
            activeColor: AppColors.secondary,
          ),
          Text(label, style: AppTypography.captionStyle()),
        ],
      ),
    );
  }

  Widget _buildSkillLevelSelector() {
    const skillLevels = {
      1: {'name': 'Beginner', 'description': 'Assembly / No-Skill', 'icon': Icons.looks_one},
      2: {'name': 'Basic', 'description': 'Simple cooking', 'icon': Icons.looks_two},
      3: {'name': 'Intermediate', 'description': 'Technique-based', 'icon': Icons.looks_3},
      4: {'name': 'Multi-Step', 'description': 'Complex recipes', 'icon': Icons.looks_4},
      5: {'name': 'Advanced', 'description': 'Professional techniques', 'icon': Icons.looks_5},
    };

    return Column(
      children: skillLevels.entries.map((entry) {
        final level = entry.key;
        final data = entry.value;
        final isSelected = _skillLevel == level;

        return GestureDetector(
          onTap: () => setState(() => _skillLevel = level),
          child: Container(
            margin: const EdgeInsets.only(bottom: 8),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: isSelected ? AppColors.primary.withOpacity(0.1) : Colors.transparent,
              border: Border.all(
                color: isSelected ? AppColors.primary : Colors.grey.shade300,
                width: isSelected ? 2 : 1,
              ),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Row(
              children: [
                Icon(
                  data['icon'] as IconData,
                  color: isSelected ? AppColors.primary : Colors.grey.shade600,
                  size: 32,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        data['name'] as String,
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                          color: isSelected ? AppColors.primary : Colors.black87,
                        ),
                      ),
                      Text(
                        data['description'] as String,
                        style: AppTypography.captionStyle(
                          color: isSelected ? AppColors.primary : AppColors.textSecondary,
                        ),
                      ),
                    ],
                  ),
                ),
                if (isSelected)
                  Icon(Icons.check_circle, color: AppColors.primary, size: 24),
              ],
            ),
          ),
        );
      }).toList(),
    );
  }
}
