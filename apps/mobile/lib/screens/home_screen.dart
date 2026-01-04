import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../ui/ui_principles.dart';
import '../services/api_client.dart';
import '../services/profile_service.dart';
import '../models/profile_state.dart';
import '../theme/app_theme.dart';
import '../widgets/savo_widgets.dart';
import 'plan_screen.dart';
import 'cook_now_entry_screen.dart';
import 'pantry_update_entry_screen.dart';
import 'settings_screen.dart';
import 'onboarding/onboarding_coordinator.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  bool _loadingOnboarding = true;
  Map<String, dynamic>? _onboardingStatus;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _refreshOnboardingStatus();
    });
  }

  Future<void> _refreshOnboardingStatus() async {
    if (mounted) {
      setState(() {
        _loadingOnboarding = true;
      });
    }
    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final profileState = Provider.of<ProfileState>(context, listen: false);
      final profileService = ProfileService(apiClient);
      final status = await profileService.getOnboardingStatus();
      profileState.updateOnboardingStatus(status);

      if (!mounted) return;
      setState(() {
        _onboardingStatus = status;
        _loadingOnboarding = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loadingOnboarding = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (kDebugMode || kProfileMode) {
      // v1: TodayHome should present 1 primary + 2 secondary actions.
      SavoUiGuards.warnIfTooManyChoices(
        screen: 'HomeScreen',
        surface: 'Today actions',
        choices: 3,
      );
      SavoUiGuards.warnIfMultiplePrimaryActions(
        screen: 'HomeScreen',
        surface: 'Today hero',
        primaryActions: 1,
      );
    }

    // Check authentication on every build
    final session = Supabase.instance.client.auth.currentSession;
    if (session == null) {
      // Redirect to login if no session
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (context.mounted) {
          Navigator.of(context).pushReplacementNamed('/login');
        }
      });
      // Return loading screen while redirecting
      return const Scaffold(
        body: Center(
          child: CircularProgressIndicator(),
        ),
      );
    }
    
    return Scaffold(
      appBar: AppBar(
        title: const Text('SAVO'),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: () {
              Navigator.push(
                context,
                AppMotion.createRoute(const SettingsScreen()),
              );
            },
            tooltip: 'Family Profile Settings',
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              _greetingWithName(context),
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: AppSpacing.sm),
            SavoCard(
              elevated: true,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'You can cook something right now',
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  Text(
                    'Based on what’s in your pantry',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                  const SizedBox(height: AppSpacing.md),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      onPressed: () {
                          Navigator.push(
                          context,
                            AppMotion.createRoute(const CookNowEntryScreen()),
                        );
                      },
                      child: const Text('See options'),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () {
                      Navigator.push(
                        context,
                        AppMotion.createRoute(const PlanScreen()),
                      );
                    },
                    child: const Text('Plan a meal / party'),
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: OutlinedButton(
                    onPressed: () {
                      Navigator.push(
                        context,
                        AppMotion.createRoute(const PantryUpdateEntryScreen()),
                      );
                    },
                    child: const Text('Update pantry'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.lg),

            if (!_loadingOnboarding) ...[
              _SetupBanner(
                onboardingStatus: _onboardingStatus,
                onResume: () {
                  Navigator.push(
                    context,
                    AppMotion.createRoute(const OnboardingCoordinator()),
                  );
                },
                onRefresh: _refreshOnboardingStatus,
              ),
              const SizedBox(height: AppSpacing.lg),
            ],
          ],
        ),
      ),
    );
  }

  String _greeting() {
    final h = DateTime.now().hour;
    if (h < 12) return 'Good morning';
    if (h < 17) return 'Good afternoon';
    return 'Good evening';
  }

  String _greetingWithName(BuildContext context) {
    final base = _greeting();
    final name = _resolveUserName(context);
    if (name == null || name.trim().isEmpty) return base;
    return '$base, $name';
  }

  String? _resolveUserName(BuildContext context) {
    try {
      final profileState = Provider.of<ProfileState>(context, listen: false);
      final profile = profileState.profile;
      final household = profileState.household;

      final candidates = <Object?>[
        profile?['display_name'],
        profile?['full_name'],
        profile?['name'],
        profile?['first_name'],
        household?['name'],
      ];

      for (final c in candidates) {
        final s = c?.toString().trim();
        if (s != null && s.isNotEmpty) return s;
      }
    } catch (_) {
      // Best-effort only.
    }

    final session = Supabase.instance.client.auth.currentSession;
    final meta = session?.user.userMetadata;
    if (meta != null) {
      for (final key in const ['full_name', 'name', 'display_name', 'first_name']) {
        final v = meta[key];
        final s = v?.toString().trim();
        if (s != null && s.isNotEmpty) return s;
      }
    }

    final email = session?.user.email;
    if (email != null && email.contains('@')) {
      final prefix = email.split('@').first.trim();
      if (prefix.isNotEmpty) return prefix;
    }

    return null;
  }
}

class _SetupBanner extends StatelessWidget {
  final Map<String, dynamic>? onboardingStatus;
  final VoidCallback onResume;
  final VoidCallback onRefresh;

  const _SetupBanner({
    required this.onboardingStatus,
    required this.onResume,
    required this.onRefresh,
  });

  bool get _completed => onboardingStatus?['completed'] == true;

  List<String> get _missingLabels {
    final raw = onboardingStatus?['missing_fields'];
    if (raw is! List) return const [];

    final labels = <String>[];
    for (final v in raw) {
      final s = v.toString().trim().toLowerCase();
      if (s.isEmpty) continue;

      if (s.contains('household')) {
        labels.add('Household');
      } else if (s.contains('allerg') || s.contains('safety')) {
        labels.add('Allergens');
      } else if (s.contains('diet')) {
        labels.add('Dietary');
      } else if (s.contains('spice')) {
        labels.add('Spice');
      } else if (s.contains('pantry')) {
        labels.add('Pantry');
      } else if (s.contains('language')) {
        labels.add('Language');
      }
    }
    return labels.toSet().toList()..sort();
  }

  @override
  Widget build(BuildContext context) {
    if (_completed) return const SizedBox.shrink();

    final theme = Theme.of(context);
    final cs = theme.colorScheme;

    return Card(
      color: cs.primaryContainer,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.auto_fix_high, color: cs.onPrimaryContainer),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Finish setup to personalize your menus',
                    style: theme.textTheme.titleMedium?.copyWith(
                      color: cs.onPrimaryContainer,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                IconButton(
                  tooltip: 'Refresh',
                  onPressed: onRefresh,
                  icon: Icon(Icons.refresh, color: cs.onPrimaryContainer),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              'Set your household, allergens, and dietary preferences so SAVO can plan safely and accurately.',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: cs.onPrimaryContainer,
              ),
            ),
            if (_missingLabels.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                'Missing: ${_missingLabels.join(', ')}',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: cs.onPrimaryContainer,
                ),
              ),
            ],
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: onResume,
                icon: const Icon(Icons.play_arrow),
                label: const Text('Complete setup'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
