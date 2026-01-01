import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../models/profile_state.dart';
import '../../services/profile_service.dart';
import '../../services/api_client.dart';
import '../../services/onboarding_storage.dart';
import 'onboarding_coordinator.dart';

class OnboardingSpiceScreen extends StatefulWidget {
  const OnboardingSpiceScreen({super.key});

  @override
  State<OnboardingSpiceScreen> createState() => _OnboardingSpiceScreenState();
}

class _OnboardingSpiceScreenState extends State<OnboardingSpiceScreen> {
  String? _selectedTolerance;
  bool _isLoading = false;
  String? _error;

  static const List<Map<String, String>> spiceOptions = [
    {'value': 'none', 'label': 'No spice', 'icon': '🚫'},
    {'value': 'mild', 'label': 'Mild', 'icon': '🌶️'},
    {'value': 'medium', 'label': 'Medium', 'icon': '🌶️🌶️'},
    {'value': 'high', 'label': 'Spicy', 'icon': '🌶️🌶️🌶️'},
    {'value': 'very_high', 'label': 'Very Spicy', 'icon': '🔥🔥🔥'},
  ];

  @override
  void initState() {
    super.initState();
    _loadExistingPreference();
  }

  void _loadExistingPreference() {
    final profileState = Provider.of<ProfileState>(context, listen: false);
    final tolerance = profileState.getSpiceTolerance();
    if (tolerance != null) {
      setState(() => _selectedTolerance = tolerance);
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
      if (!skip && _selectedTolerance != null) {
        // Update spice tolerance for first member
        final members = profileState.members;
        if (members.isNotEmpty) {
          final firstMember = members.first;
          await profileService.updateFamilyMember(
            firstMember['id'],
            {'spice_tolerance': _selectedTolerance},
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
        await OnboardingStorage.saveLastStep('SPICE', userId);
      }

      if (mounted) {
        navigateToNextOnboardingStep(context, 'SPICE');
      }
    } catch (e) {
      setState(() {
        _error = 'Failed to save: ${e.toString()}';
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Spice Preference'),
      ),
      body: Column(
        children: [
          LinearProgressIndicator(
            value: getOnboardingProgress('SPICE'),
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
                        'Step ${getStepNumber('SPICE')} of 8',
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
                    'How spicy do you like your food?',
                    style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'SAVO will adjust recipe heat levels accordingly',
                    style: TextStyle(color: Colors.grey),
                  ),
                  const SizedBox(height: 32),
                  
                  // Spice level options
                  ...spiceOptions.map((option) {
                    final isSelected = _selectedTolerance == option['value'];
                    return Card(
                      margin: const EdgeInsets.only(bottom: 12),
                      color: isSelected
                          ? Theme.of(context).colorScheme.primaryContainer
                          : null,
                      child: InkWell(
                        onTap: () => setState(() =>
                            _selectedTolerance = option['value']),
                        child: Padding(
                          padding: const EdgeInsets.all(16.0),
                          child: Row(
                            children: [
                              Text(
                                option['icon']!,
                                style: const TextStyle(fontSize: 32),
                              ),
                              const SizedBox(width: 16),
                              Expanded(
                                child: Text(
                                  option['label']!,
                                  style: const TextStyle(
                                    fontSize: 18,
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                              ),
                              if (isSelected)
                                const Icon(Icons.check_circle, color: Colors.green),
                            ],
                          ),
                        ),
                      ),
                    );
                  }),
                  
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
                        : const Text('Next: Pantry Check'),
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
