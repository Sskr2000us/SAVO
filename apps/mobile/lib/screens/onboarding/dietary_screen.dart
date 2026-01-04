import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../models/profile_state.dart';
import '../../services/profile_service.dart';
import '../../services/api_client.dart';
import '../../services/onboarding_storage.dart';
import '../../theme/app_theme.dart';
import '../../widgets/onboarding_app_bar.dart';
import 'onboarding_coordinator.dart';

class OnboardingDietaryScreen extends StatefulWidget {
  const OnboardingDietaryScreen({super.key});

  @override
  State<OnboardingDietaryScreen> createState() =>
      _OnboardingDietaryScreenState();
}

class _OnboardingDietaryScreenState extends State<OnboardingDietaryScreen> {
  final Set<String> _selectedRestrictions = {};
  bool _isLoading = false;
  String? _error;

  static const List<String> dietaryOptions = [
    'vegetarian',
    'vegan',
    'no_beef',
    'no_pork',
    'no_alcohol',
    'halal',
    'kosher',
    'pescatarian',
  ];

  static const Map<String, String> optionLabels = {
    'vegetarian': 'Vegetarian',
    'vegan': 'Vegan',
    'no_beef': 'No Beef',
    'no_pork': 'No Pork',
    'no_alcohol': 'No Alcohol',
    'halal': 'Halal',
    'kosher': 'Kosher',
    'pescatarian': 'Pescatarian',
  };

  @override
  void initState() {
    super.initState();
    _loadExistingDietary();
  }

  void _loadExistingDietary() {
    final profileState = Provider.of<ProfileState>(context, listen: false);
    final dietary = profileState.dietary;
    if (dietary != null) {
      setState(() {
        if (dietary['vegetarian'] == true) _selectedRestrictions.add('vegetarian');
        if (dietary['vegan'] == true) _selectedRestrictions.add('vegan');
        if (dietary['no_beef'] == true) _selectedRestrictions.add('no_beef');
        if (dietary['no_pork'] == true) _selectedRestrictions.add('no_pork');
        if (dietary['no_alcohol'] == true) _selectedRestrictions.add('no_alcohol');
      });
    }
  }

  void _toggleRestriction(String restriction) {
    setState(() {
      if (_selectedRestrictions.contains(restriction)) {
        _selectedRestrictions.remove(restriction);
      } else {
        _selectedRestrictions.add(restriction);
        // Vegan implies vegetarian
        if (restriction == 'vegan') {
          _selectedRestrictions.add('vegetarian');
        }
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
      // Update dietary restrictions only for members without existing restrictions
      // This allows each member to have their own dietary preferences
      final members = profileState.members;
      if (members.isEmpty) {
        throw Exception('No household members found');
      }

      // Apply selected restrictions only to the first/primary member
      // Other members can be configured individually in Settings
      if (members.isNotEmpty) {
        final primaryMember = members[0];
        await profileService.updateDietary(
          memberId: primaryMember['id'],
          dietaryRestrictions: _selectedRestrictions.toList(),
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
        await OnboardingStorage.saveLastStep('DIETARY', userId);
      }

      if (mounted) {
        navigateToNextOnboardingStep(context, 'DIETARY');
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

      // Save dietary restrictions if members exist and data entered
      final members = profileState.members;
      if (members.isNotEmpty && _selectedRestrictions.isNotEmpty) {
        // Only apply to primary member during onboarding
        // Other members can set their own restrictions in Settings
        final primaryMember = members[0];
        await profileService.updateDietary(
          memberId: primaryMember['id'],
          dietaryRestrictions: _selectedRestrictions.toList(),
        );

        // Save progress
        final userId = profileState.userId;
        if (userId != null) {
          await OnboardingStorage.saveLastStep('DIETARY', userId);
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
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Scaffold(
      appBar: OnboardingAppBar(
        title: 'Dietary Preferences',
        onSaveAndExit: _handleSaveAndExit,
        isLoading: _isLoading,
        showBack: Navigator.canPop(context),
      ),
      body: Column(
        children: [
          LinearProgressIndicator(
            value: getOnboardingProgress('DIETARY'),
          ),
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    'Step ${getStepNumber('DIETARY')} of 8',
                    style: theme.textTheme.bodySmall,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Any dietary restrictions?',
                    style: theme.textTheme.headlineMedium,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Select all that apply for the primary household member',
                    style: theme.textTheme.bodySmall,
                  ),
                  const SizedBox(height: 4),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppColors.card,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: AppColors.divider),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.info_outline, size: 20, color: AppColors.info),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            'Other family members can set their own dietary restrictions in Settings',
                            style: theme.textTheme.bodySmall,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),

                  Wrap(
                    spacing: 10,
                    runSpacing: 10,
                    children: [
                      FilterChip(
                        label: const Text('No dietary restrictions'),
                        selected: _selectedRestrictions.isEmpty,
                        onSelected: (value) {
                          if (value) {
                            setState(() => _selectedRestrictions.clear());
                          }
                        },
                      ),
                      ...dietaryOptions.map((option) {
                        final isSelected = _selectedRestrictions.contains(option);
                        return FilterChip(
                          label: Text(optionLabels[option] ?? option),
                          selected: isSelected,
                          onSelected: (_) => _toggleRestriction(option),
                          selectedColor: colorScheme.primary.withOpacity(0.22),
                          checkmarkColor: colorScheme.primary,
                        );
                      }),
                    ],
                  ),
                  
                  if (_error != null) ...[
                    const SizedBox(height: 16),
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: colorScheme.error.withOpacity(0.12),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        _error!,
                        style: TextStyle(color: colorScheme.error),
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
                        : const Text('Next: Spice Preference'),
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
