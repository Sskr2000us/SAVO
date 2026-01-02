import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../models/profile_state.dart';
import '../../services/profile_service.dart';
import '../../services/api_client.dart';
import '../../services/onboarding_storage.dart';
import '../../widgets/onboarding_app_bar.dart';
import 'onboarding_coordinator.dart';

class OnboardingAllergiesScreen extends StatefulWidget {
  const OnboardingAllergiesScreen({super.key});

  @override
  State<OnboardingAllergiesScreen> createState() =>
      _OnboardingAllergiesScreenState();
}

class _OnboardingAllergiesScreenState extends State<OnboardingAllergiesScreen> {
  final Set<String> _selectedAllergens = {};
  bool _isLoading = false;
  String? _error;

  static const List<String> commonAllergens = [
    'Peanuts',
    'Tree Nuts',
    'Milk',
    'Eggs',
    'Wheat',
    'Soy',
    'Fish',
    'Shellfish',
    'Sesame',
    'Mustard',
    'Celery',
    'Lupin',
    'Molluscs',
    'Sulfites',
  ];

  @override
  void initState() {
    super.initState();
    _loadExistingAllergens();
  }

  void _loadExistingAllergens() {
    final profileState = Provider.of<ProfileState>(context, listen: false);
    if (profileState.declaredAllergens.isNotEmpty) {
      setState(() {
        _selectedAllergens.addAll(profileState.declaredAllergens);
      });
    }
  }

  void _toggleAllergen(String allergen) {
    setState(() {
      if (_selectedAllergens.contains(allergen)) {
        _selectedAllergens.remove(allergen);
      } else {
        _selectedAllergens.add(allergen);
      }
    });
  }

  Future<void> _handleNext() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    final apiClient = Provider.of<ApiClient>(context, listen: false);
    final profileService = ProfileService(apiClient);
    final profileState = Provider.of<ProfileState>(context, listen: false);

    try {
      // Update allergens for all members
      final members = profileState.members;
      if (members.isEmpty) {
        throw Exception('No household members found');
      }

      // Apply to all members (simplest approach as per spec)
      for (var member in members) {
        await profileService.updateAllergens(
          memberId: member['id'],
          allergens: _selectedAllergens.toList(),
          reason: 'Initial onboarding',
        );
      }

      // Refetch full profile
      final profile = await profileService.getFullProfile();
      profileState.updateProfileData(profile);

      // Update onboarding status
      final status = await profileService.getOnboardingStatus();
      profileState.updateOnboardingStatus(status);

      // Save progress locally for offline resume
      final userId = profileState.userId;
      if (userId != null) {
        await OnboardingStorage.saveLastStep('ALLERGIES', userId);
      }

      if (mounted) {
        navigateToNextOnboardingStep(context, 'ALLERGIES');
      }
    } catch (e) {
      setState(() {
        _error = 'Failed to save: ${e.toString()}';
        _isLoading = false;
      });
    }
  }

  Future<void> _handleSaveAndExit() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final profileService = ProfileService(apiClient);
      final profileState = Provider.of<ProfileState>(context, listen: false);

      // Save allergens if members exist
      final members = profileState.members;
      if (members.isNotEmpty) {
        for (var member in members) {
          await profileService.updateAllergens(
            memberId: member['id'],
            allergens: _selectedAllergens.toList(),
            reason: 'Partial onboarding save',
          );
        }

        // Save progress
        final userId = profileState.userId;
        if (userId != null) {
          await OnboardingStorage.saveLastStep('ALLERGIES', userId);
        }
      }

      if (mounted) {
        Navigator.of(context).pushReplacementNamed('/home');
      }
    } catch (e) {
      // Even if save fails, allow exit
      if (mounted) {
        Navigator.of(context).pushReplacementNamed('/home');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: OnboardingAppBar(
        title: 'Allergies',
        onSaveAndExit: _handleSaveAndExit,
        isLoading: _isLoading,
        showBack: Navigator.canPop(context),
      ),
      body: Column(
        children: [
          LinearProgressIndicator(
            value: getOnboardingProgress('ALLERGIES'),
          ),
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    'Step ${getStepNumber('ALLERGIES')} of 8',
                    style: const TextStyle(fontSize: 14, color: Colors.grey),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Any food allergies?',
                    style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Select all that apply. SAVO will never suggest recipes with these ingredients.',
                    style: TextStyle(color: Colors.grey),
                  ),
                  const SizedBox(height: 32),
                  
                  // Allergen chips
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: commonAllergens.map((allergen) {
                      final isSelected = _selectedAllergens.contains(allergen);
                      return FilterChip(
                        label: Text(allergen),
                        selected: isSelected,
                        onSelected: (_) => _toggleAllergen(allergen),
                        selectedColor: Colors.red.withOpacity(0.3),
                        checkmarkColor: Colors.red,
                      );
                    }).toList(),
                  ),
                  
                  const SizedBox(height: 16),
                  
                  // None option
                  CheckboxListTile(
                    title: const Text('No allergies'),
                    value: _selectedAllergens.isEmpty,
                    onChanged: (value) {
                      if (value == true) {
                        setState(() => _selectedAllergens.clear());
                      }
                    },
                    contentPadding: EdgeInsets.zero,
                  ),
                  
                  if (_error != null) ...[
                    const SizedBox(height: 16),
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.red.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        _error!,
                        style: const TextStyle(color: Colors.red),
                        textAlign: TextAlign.center,
                      ),
                    ),
                  ],
                  
                  const SizedBox(height: 24),
                  
                  ElevatedButton(
                    onPressed: _isLoading ? null : _handleNext,
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                    ),
                    child: _isLoading
                        ? const CircularProgressIndicator()
                        : const Text('Next: Dietary Preferences'),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
