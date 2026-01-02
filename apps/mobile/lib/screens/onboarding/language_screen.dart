import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../models/profile_state.dart';
import '../../services/profile_service.dart';
import '../../services/api_client.dart';
import '../../services/onboarding_storage.dart';
import '../../widgets/onboarding_app_bar.dart';
import 'onboarding_coordinator.dart';

class OnboardingLanguageScreen extends StatefulWidget {
  const OnboardingLanguageScreen({super.key});

  @override
  State<OnboardingLanguageScreen> createState() => _OnboardingLanguageScreenState();
}

class _OnboardingLanguageScreenState extends State<OnboardingLanguageScreen> {
  String? _selectedLanguage;
  String? _selectedMeasurement;
  bool _isLoading = false;
  String? _error;

  static const List<Map<String, String>> languages = [
    {'code': 'en', 'label': 'English', 'flag': '🇺🇸'},
    {'code': 'es', 'label': 'Español', 'flag': '🇪🇸'},
    {'code': 'fr', 'label': 'Français', 'flag': '🇫🇷'},
    {'code': 'de', 'label': 'Deutsch', 'flag': '🇩🇪'},
    {'code': 'it', 'label': 'Italiano', 'flag': '🇮🇹'},
    {'code': 'pt', 'label': 'Português', 'flag': '🇵🇹'},
    {'code': 'zh', 'label': '中文', 'flag': '🇨🇳'},
    {'code': 'ja', 'label': '日本語', 'flag': '🇯🇵'},
    {'code': 'ko', 'label': '한국어', 'flag': '🇰🇷'},
    {'code': 'hi', 'label': 'हिन्दी', 'flag': '🇮🇳'},
  ];

  static const List<Map<String, String>> measurements = [
    {'value': 'metric', 'label': 'Metric', 'example': 'kg, L, °C'},
    {'value': 'imperial', 'label': 'Imperial', 'example': 'lb, gal, °F'},
  ];

  @override
  void initState() {
    super.initState();
    _loadExistingPreferences();
  }

  void _loadExistingPreferences() {
    final profileState = Provider.of<ProfileState>(context, listen: false);
    final lang = profileState.preferredLanguage;
    final measurement = profileState.measurementSystem;
    
    setState(() {
      _selectedLanguage = lang ?? 'en';
      _selectedMeasurement = measurement ?? 'metric';
    });
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
      if (!skip) {
        await profileService.updateLanguage(
          primaryLanguage: _selectedLanguage ?? 'en',
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
        await OnboardingStorage.saveLastStep('LANGUAGE', userId);
      }

      if (mounted) {
        navigateToNextOnboardingStep(context, 'LANGUAGE');
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

      // Save language preference if data entered
      if (_selectedLanguage != null) {
        await profileService.updateLanguage(
          primaryLanguage: _selectedLanguage!,
        );

        // Save progress
        final userId = profileState.userId;
        if (userId != null) {
          await OnboardingStorage.saveLastStep('LANGUAGE', userId);
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
        title: 'Language & Units',
        onSaveAndExit: _handleSaveAndExit,
        isLoading: _isLoading,
        showBack: Navigator.canPop(context),
      ),
      body: Column(
        children: [
          LinearProgressIndicator(
            value: getOnboardingProgress('LANGUAGE'),
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
                        'Step ${getStepNumber('LANGUAGE')} of 8',
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
                    'Choose your preferences',
                    style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Select language and measurement system',
                    style: TextStyle(color: Colors.grey),
                  ),
                  const SizedBox(height: 32),
                  
                  // Language section
                  const Text(
                    'Language',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 12),
                  
                  Container(
                    decoration: BoxDecoration(
                      border: Border.all(color: Colors.grey.shade300),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: DropdownButtonFormField<String>(
                      value: _selectedLanguage,
                      decoration: const InputDecoration(
                        contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                        border: InputBorder.none,
                      ),
                      items: languages.map((lang) {
                        return DropdownMenuItem(
                          value: lang['code'],
                          child: Row(
                            children: [
                              Text(
                                lang['flag']!,
                                style: const TextStyle(fontSize: 24),
                              ),
                              const SizedBox(width: 12),
                              Text(lang['label']!),
                            ],
                          ),
                        );
                      }).toList(),
                      onChanged: (value) => setState(() => _selectedLanguage = value),
                    ),
                  ),
                  
                  const SizedBox(height: 32),
                  
                  // Measurement system section
                  const Text(
                    'Measurement System',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 12),
                  
                  ...measurements.map((measurement) {
                    final isSelected = _selectedMeasurement == measurement['value'];
                    return Card(
                      margin: const EdgeInsets.only(bottom: 12),
                      color: isSelected
                          ? Theme.of(context).colorScheme.primaryContainer
                          : null,
                      child: InkWell(
                        onTap: () => setState(() =>
                            _selectedMeasurement = measurement['value']),
                        child: Padding(
                          padding: const EdgeInsets.all(16.0),
                          child: Row(
                            children: [
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      measurement['label']!,
                                      style: const TextStyle(
                                        fontSize: 18,
                                        fontWeight: FontWeight.w500,
                                      ),
                                    ),
                                    const SizedBox(height: 4),
                                    Text(
                                      measurement['example']!,
                                      style: const TextStyle(
                                        fontSize: 14,
                                        color: Colors.grey,
                                      ),
                                    ),
                                  ],
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
                        : const Text('Complete Setup'),
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
