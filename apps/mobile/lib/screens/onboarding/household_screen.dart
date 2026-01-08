import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../models/profile_state.dart';
import '../../services/profile_service.dart';
import '../../services/api_client.dart';
import '../../services/onboarding_storage.dart';
import '../../widgets/onboarding_app_bar.dart';
import 'onboarding_coordinator.dart';

class OnboardingHouseholdScreen extends StatefulWidget {
  const OnboardingHouseholdScreen({super.key});

  @override
  State<OnboardingHouseholdScreen> createState() =>
      _OnboardingHouseholdScreenState();
}

class _OnboardingHouseholdScreenState extends State<OnboardingHouseholdScreen> {
  int _householdSize = 1;
  bool _isLoading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadExistingSize();
  }

  void _loadExistingSize() {
    final profileState = Provider.of<ProfileState>(context, listen: false);
    final count = profileState.members.length;
    setState(() {
      _householdSize = count > 0 ? count.clamp(1, 8) : 1;
    });
  }

  void _setHouseholdSize(int value) {
    setState(() {
      _householdSize = value.clamp(1, 8);
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
      // Create household profile if doesn't exist
      if (!profileState.hasHouseholdProfile()) {
        await profileService.createHouseholdProfile();
      }

      // Create placeholder members to match selected household size.
      // Users can customize members later in Settings.
      final existingCount = profileState.members.length;
      if (existingCount < _householdSize) {
        for (var i = existingCount; i < _householdSize; i++) {
          final name = i == 0 ? 'Me' : 'Member ${i + 1}';
          await profileService.createFamilyMember(
            name: name,
            age: 30,
            allergens: const [],
            dietaryRestrictions: const [],
          );
        }
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
        await OnboardingStorage.saveLastStep('HOUSEHOLD', userId);
      }

      if (mounted) {
        navigateToNextOnboardingStep(context, 'HOUSEHOLD');
      }
    } catch (e) {
      setState(() {
        _error = 'Failed to save: ${e.toString()}';
        _isLoading = false;
      });
    }
  }

  Future<void> _handleSaveAndExit() async {
    // Allow exit even with no data
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final profileService = ProfileService(apiClient);
      final profileState = Provider.of<ProfileState>(context, listen: false);

      if (!profileState.hasHouseholdProfile()) {
        await profileService.createHouseholdProfile();
      }

      final existingCount = profileState.members.length;
      if (existingCount < _householdSize) {
        for (var i = existingCount; i < _householdSize; i++) {
          final name = i == 0 ? 'Me' : 'Member ${i + 1}';
          await profileService.createFamilyMember(
            name: name,
            age: 30,
            allergens: const [],
            dietaryRestrictions: const [],
          );
        }
      }

      final userId = profileState.userId;
      if (userId != null) {
        await OnboardingStorage.saveLastStep('HOUSEHOLD', userId);
      }

      if (mounted) {
        // Navigate to home - user can resume onboarding later
        Navigator.of(context).pushReplacementNamed('/home');
      }
    } catch (e) {
      setState(() {
        _error = 'Failed to save: ${e.toString()}';
        _isLoading = false;
      });
      
      // Even if save fails, allow exit to home
      if (mounted) {
        Navigator.of(context).pushReplacementNamed('/home');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: OnboardingAppBar(
        title: 'Your Household',
        onSaveAndExit: _handleSaveAndExit,
        isLoading: _isLoading,
        showBack: Navigator.canPop(context),
      ),
      body: Column(
        children: [
          // Progress indicator
          LinearProgressIndicator(
            value: getOnboardingProgress('HOUSEHOLD'),
          ),
          
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    'Step ${getStepNumber('HOUSEHOLD')} of 2',
                    style: const TextStyle(
                      fontSize: 14,
                      color: Colors.grey,
                    ),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'How many people do you cook for?',
                    style: TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'This takes <10 seconds.',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.grey),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'You can customize names, ages, and diets later in Settings.',
                    style: TextStyle(color: Colors.grey),
                  ),
                  const SizedBox(height: 32),

                  Card(
                    margin: const EdgeInsets.only(bottom: 16),
                    child: Padding(
                      padding: const EdgeInsets.all(16.0),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Text('Household size', style: TextStyle(fontSize: 16)),
                          Row(
                            children: [
                              IconButton(
                                onPressed: _isLoading || _householdSize <= 1
                                    ? null
                                    : () => _setHouseholdSize(_householdSize - 1),
                                icon: const Icon(Icons.remove_circle_outline),
                              ),
                              Text(
                                '$_householdSize',
                                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                              ),
                              IconButton(
                                onPressed: _isLoading || _householdSize >= 8
                                    ? null
                                    : () => _setHouseholdSize(_householdSize + 1),
                                icon: const Icon(Icons.add_circle_outline),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ),

                  Text(
                    'You can change this later in Settings.',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.grey),
                  ),
                  const SizedBox(height: 8),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: ChoiceChip(
                      label: const Text('Just me (recommended)'),
                      selected: _householdSize == 1,
                      onSelected: _isLoading ? null : (_) => _setHouseholdSize(1),
                    ),
                  ),
                  
                  // Error message
                  if (_error != null) ...[
                    const SizedBox(height: 16),
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.red.withAlpha(26),
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
                  
                  // Next button
                  ElevatedButton(
                    onPressed: _isLoading ? null : _handleNext,
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                    ),
                    child: _isLoading
                        ? const CircularProgressIndicator()
                        : const Text('Continue'),
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
