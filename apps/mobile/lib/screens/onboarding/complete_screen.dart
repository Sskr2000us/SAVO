import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../models/profile_state.dart';
import '../../services/profile_service.dart';
import '../../services/api_client.dart';
import '../../services/onboarding_storage.dart';

class OnboardingCompleteScreen extends StatefulWidget {
  const OnboardingCompleteScreen({super.key});

  @override
  State<OnboardingCompleteScreen> createState() => _OnboardingCompleteScreenState();
}

class _OnboardingCompleteScreenState extends State<OnboardingCompleteScreen> {
  bool _isLoading = false;
  String? _error;

  Future<void> _handleComplete() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    final apiClient = Provider.of<ApiClient>(context, listen: false);
    final profileService = ProfileService(apiClient);
    final profileState = Provider.of<ProfileState>(context, listen: false);

    try {
      // Mark onboarding as complete
      await profileService.completeOnboarding();

      // Refetch full profile
      final profile = await profileService.getFullProfile();
      profileState.updateProfileData(profile);

      // Update onboarding status
      final status = await profileService.getOnboardingStatus();
      profileState.updateOnboardingStatus(status);

      // Save completion locally
      final userId = profileState.userId;
      if (userId != null) {
        await OnboardingStorage.saveLastStep('COMPLETE', userId);
      }

      if (mounted) {
        // Navigate to home screen (replace entire navigation stack)
        Navigator.of(context).pushReplacementNamed('/home');
      }
    } catch (e) {
      setState(() {
        _error = 'Failed to complete onboarding: ${e.toString()}';
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Success animation/icon
              Container(
                width: 120,
                height: 120,
                decoration: BoxDecoration(
                  color: Colors.green.withOpacity(0.1),
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.check_circle,
                  size: 80,
                  color: Colors.green,
                ),
              ),
              
              const SizedBox(height: 32),
              
              const Text(
                'You\'re all set!',
                style: TextStyle(
                  fontSize: 32,
                  fontWeight: FontWeight.bold,
                ),
                textAlign: TextAlign.center,
              ),
              
              const SizedBox(height: 16),
              
              Consumer<ProfileState>(
                builder: (context, profileState, _) {
                  final householdName = profileState.householdName ?? 'your household';
                  return Text(
                    'SAVO is ready to help $householdName discover delicious, healthy meals.',
                    style: const TextStyle(
                      fontSize: 16,
                      color: Colors.grey,
                    ),
                    textAlign: TextAlign.center,
                  );
                },
              ),
              
              const SizedBox(height: 48),
              
              // Summary cards
              Consumer<ProfileState>(
                builder: (context, profileState, _) {
                  final members = profileState.members;
                  final allergens = profileState.allergens;
                  
                  return Column(
                    children: [
                      _SummaryCard(
                        icon: Icons.people,
                        title: 'Family Members',
                        value: '${members.length}',
                      ),
                      const SizedBox(height: 12),
                      _SummaryCard(
                        icon: Icons.warning_amber_rounded,
                        title: 'Allergens Tracked',
                        value: '${allergens?.length ?? 0}',
                      ),
                    ],
                  );
                },
              ),
              
              const SizedBox(height: 48),
              
              if (_error != null) ...[
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
                const SizedBox(height: 16),
              ],
              
              ElevatedButton(
                onPressed: _isLoading ? null : _handleComplete,
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 18),
                  backgroundColor: Theme.of(context).colorScheme.primary,
                  foregroundColor: Colors.white,
                ),
                child: _isLoading
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                        ),
                      )
                    : const Text(
                        'Start Cooking',
                        style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
                      ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SummaryCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final String value;

  const _SummaryCard({
    required this.icon,
    required this.title,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.grey.shade100,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.primaryContainer,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(icon, size: 28),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Text(
              title,
              style: const TextStyle(fontSize: 16),
            ),
          ),
          Text(
            value,
            style: const TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }
}
