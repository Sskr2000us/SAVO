import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../../models/profile_state.dart';
import '../../services/profile_service.dart';
import '../../services/api_client.dart';
import '../../services/onboarding_storage.dart';
import 'login_screen.dart';
import 'household_screen.dart';
import 'allergies_screen.dart';
import 'dietary_screen.dart';
import 'spice_screen.dart';
import 'pantry_screen.dart';
import 'language_screen.dart';
import 'complete_screen.dart';

/// Coordinates the onboarding flow based on server resume_step
class OnboardingCoordinator extends StatefulWidget {
  const OnboardingCoordinator({super.key});

  @override
  State<OnboardingCoordinator> createState() => _OnboardingCoordinatorState();
}

class _OnboardingCoordinatorState extends State<OnboardingCoordinator> {
  bool _isLoading = true;
  String? _resumeStep;

  @override
  void initState() {
    super.initState();
    _checkOnboardingStatus();
  }

  Future<void> _checkOnboardingStatus() async {
    final apiClient = Provider.of<ApiClient>(context, listen: false);
    final profileService = ProfileService(apiClient);
    final profileState = Provider.of<ProfileState>(context, listen: false);

    try {
      // Try to get current user ID for local storage lookup
      final session = Supabase.instance.client.auth.currentSession;
      final userId = session?.user.id;

      // Get onboarding status from server
      final status = await profileService.getOnboardingStatus();
      profileState.updateOnboardingStatus(status);

      // Get full profile if exists
      try {
        final profile = await profileService.getFullProfile();
        profileState.updateProfileData(profile);
      } catch (e) {
        debugPrint('No profile yet: $e');
      }

      setState(() {
        _resumeStep = status['resume_step'];
        _isLoading = false;
      });

      // If complete, navigate to home
      if (status['completed'] == true) {
        if (mounted) {
          Navigator.of(context).pushReplacementNamed('/home');
        }
      }
    } catch (e) {
      debugPrint('Error checking onboarding status from server: $e');
      
      // Fallback to local storage (offline mode)
      try {
        final session = Supabase.instance.client.auth.currentSession;
        final userId = session?.user.id;
        
        if (userId != null) {
          // Check local storage for cached step
          final cachedStep = await OnboardingStorage.getLastStep(userId);
          final isComplete = await OnboardingStorage.isOnboardingComplete(userId);
          
          if (isComplete) {
            // Local cache says complete - go to home
            if (mounted) {
              Navigator.of(context).pushReplacementNamed('/home');
            }
            return;
          }
          
          if (cachedStep != null) {
            // Resume from cached step (next step after last completed)
            final resumeStep = OnboardingStorage.getResumeStep(cachedStep);
            setState(() {
              _resumeStep = resumeStep;
              _isLoading = false;
            });
            debugPrint('Using cached onboarding step: $resumeStep (offline mode)');
            return;
          }
        }
      } catch (localError) {
        debugPrint('Error reading local storage: $localError');
      }
      
      // Ultimate fallback: start from LOGIN
      setState(() {
        _resumeStep = 'LOGIN';
        _isLoading = false;
      });
    }
  }

  Widget _getScreenForStep(String step) {
    switch (step) {
      case 'LOGIN':
        return const OnboardingLoginScreen();
      case 'HOUSEHOLD':
        return const OnboardingHouseholdScreen();
      case 'ALLERGIES':
        return const OnboardingAllergiesScreen();
      case 'DIETARY':
        return const OnboardingDietaryScreen();
      case 'SPICE':
        return const OnboardingSpiceScreen();
      case 'PANTRY':
        return const OnboardingPantryScreen();
      case 'LANGUAGE':
        return const OnboardingLanguageScreen();
      case 'COMPLETE':
        return const OnboardingCompleteScreen();
      default:
        return const OnboardingLoginScreen();
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Scaffold(
        body: Center(
          child: CircularProgressIndicator(),
        ),
      );
    }

    return _getScreenForStep(_resumeStep ?? 'LOGIN');
  }
}

/// Navigate to next onboarding step based on current step
void navigateToNextOnboardingStep(BuildContext context, String currentStep) {
  final nextSteps = {
    'LOGIN': 'HOUSEHOLD',
    'HOUSEHOLD': 'ALLERGIES',
    'ALLERGIES': 'DIETARY',
    'DIETARY': 'SPICE',
    'SPICE': 'PANTRY',
    'PANTRY': 'LANGUAGE',
    'LANGUAGE': 'COMPLETE',
    'COMPLETE': 'HOME',
  };

  final nextStep = nextSteps[currentStep];
  if (nextStep == null) return;

  if (nextStep == 'HOME') {
    Navigator.of(context).pushReplacementNamed('/home');
    return;
  }

  Widget nextScreen;
  switch (nextStep) {
    case 'HOUSEHOLD':
      nextScreen = const OnboardingHouseholdScreen();
      break;
    case 'ALLERGIES':
      nextScreen = const OnboardingAllergiesScreen();
      break;
    case 'DIETARY':
      nextScreen = const OnboardingDietaryScreen();
      break;
    case 'SPICE':
      nextScreen = const OnboardingSpiceScreen();
      break;
    case 'PANTRY':
      nextScreen = const OnboardingPantryScreen();
      break;
    case 'LANGUAGE':
      nextScreen = const OnboardingLanguageScreen();
      break;
    case 'COMPLETE':
      nextScreen = const OnboardingCompleteScreen();
      break;
    default:
      return;
  }

  Navigator.of(context).pushReplacement(
    MaterialPageRoute(builder: (context) => nextScreen),
  );
}

/// Get progress percentage based on current step
double getOnboardingProgress(String step) {
  const steps = [
    'LOGIN',
    'HOUSEHOLD',
    'ALLERGIES',
    'DIETARY',
    'SPICE',
    'PANTRY',
    'LANGUAGE',
    'COMPLETE',
  ];

  final index = steps.indexOf(step);
  if (index == -1) return 0.0;
  
  return (index + 1) / steps.length;
}

/// Get step number for display
String getStepNumber(String step) {
  const steps = {
    'LOGIN': '1',
    'HOUSEHOLD': '2',
    'ALLERGIES': '3',
    'DIETARY': '4',
    'SPICE': '5',
    'PANTRY': '6',
    'LANGUAGE': '7',
    'COMPLETE': '8',
  };
  
  return steps[step] ?? '1';
}
