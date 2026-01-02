import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../models/profile_state.dart';
import '../../services/profile_service.dart';
import '../../services/api_client.dart';
import '../../services/onboarding_storage.dart';
import '../../widgets/onboarding_app_bar.dart';
import 'onboarding_coordinator.dart';

class OnboardingPantryScreen extends StatefulWidget {
  const OnboardingPantryScreen({super.key});

  @override
  State<OnboardingPantryScreen> createState() => _OnboardingPantryScreenState();
}

class _OnboardingPantryScreenState extends State<OnboardingPantryScreen> {
  bool? _hasBasicSpices;
  bool _isLoading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadExistingPreference();
  }

  void _loadExistingPreference() {
    final profileState = Provider.of<ProfileState>(context, listen: false);
    final hasSpices = profileState.basicSpicesAvailable;
    if (hasSpices != null) {
      setState(() => _hasBasicSpices = hasSpices);
    }
  }

  Future<void> _handleNext({bool skip = false}) async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    final apiClient = Provider.of<ApiClient>(context, listen: false);
    final profileService = ProfileService(apiClient);
    final profileState = Provider.of<ProfileState>(context, listen: false);

    try {
      if (!skip && _hasBasicSpices != null) {
        await profileService.updatePreferences(
          basicSpicesAvailable: _hasBasicSpices,
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
        await OnboardingStorage.saveLastStep('PANTRY', userId);
      }

      if (mounted) {
        navigateToNextOnboardingStep(context, 'PANTRY');
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

      // Save pantry preference if data entered
      if (_hasBasicSpices != null) {
        await profileService.updatePreferences(
          basicSpicesAvailable: _hasBasicSpices,
        );

        // Save progress
        final userId = profileState.userId;
        if (userId != null) {
          await OnboardingStorage.saveLastStep('PANTRY', userId);
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
        title: 'Pantry Check',
        onSaveAndExit: _handleSaveAndExit,
        isLoading: _isLoading,
        showBack: Navigator.canPop(context),
      ),
      body: Column(
        children: [
          LinearProgressIndicator(
            value: getOnboardingProgress('PANTRY'),
          ),
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        'Step ${getStepNumber('PANTRY')} of 8',
                        style: const TextStyle(fontSize: 14, color: Colors.grey),
                      ),
                      const Text(
                        'Optional',
                        style: TextStyle(
                          fontSize: 14,
                          color: Colors.blue,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Do you have basic spices?',
                    style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Like salt, pepper, garlic powder, onion powder',
                    style: TextStyle(color: Colors.grey),
                  ),
                  const SizedBox(height: 32),
                  
                  // Yes option
                  Card(
                    margin: const EdgeInsets.only(bottom: 12),
                    color: _hasBasicSpices == true
                        ? Theme.of(context).colorScheme.primaryContainer
                        : null,
                    child: InkWell(
                      onTap: () => setState(() => _hasBasicSpices = true),
                      child: Padding(
                        padding: const EdgeInsets.all(20.0),
                        child: Row(
                          children: [
                            const Icon(Icons.check_circle_outline, size: 32),
                            const SizedBox(width: 16),
                            const Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    'Yes, I have them',
                                    style: TextStyle(
                                      fontSize: 18,
                                      fontWeight: FontWeight.w500,
                                    ),
                                  ),
                                  SizedBox(height: 4),
                                  Text(
                                    'SAVO will assume you have basic spices',
                                    style: TextStyle(
                                      fontSize: 14,
                                      color: Colors.grey,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            if (_hasBasicSpices == true)
                              const Icon(Icons.check_circle, color: Colors.green),
                          ],
                        ),
                      ),
                    ),
                  ),
                  
                  // No option
                  Card(
                    color: _hasBasicSpices == false
                        ? Theme.of(context).colorScheme.primaryContainer
                        : null,
                    child: InkWell(
                      onTap: () => setState(() => _hasBasicSpices = false),
                      child: Padding(
                        padding: const EdgeInsets.all(20.0),
                        child: Row(
                          children: [
                            const Icon(Icons.cancel_outlined, size: 32),
                            const SizedBox(width: 16),
                            const Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    'No, I need to buy them',
                                    style: TextStyle(
                                      fontSize: 18,
                                      fontWeight: FontWeight.w500,
                                    ),
                                  ),
                                  SizedBox(height: 4),
                                  Text(
                                    'SAVO will include spices in shopping lists',
                                    style: TextStyle(
                                      fontSize: 14,
                                      color: Colors.grey,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            if (_hasBasicSpices == false)
                              const Icon(Icons.check_circle, color: Colors.green),
                          ],
                        ),
                      ),
                    ),
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
                    onPressed: _isLoading ? null : () => _handleNext(),
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                    ),
                    child: _isLoading
                        ? const CircularProgressIndicator()
                        : const Text('Next: Language'),
                  ),
                  
                  const SizedBox(height: 12),
                  
                  OutlinedButton(
                    onPressed: _isLoading ? null : () => _handleNext(skip: true),
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                    ),
                    child: const Text('Skip'),
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
