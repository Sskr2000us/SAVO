import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../services/api_client.dart';
import '../services/profile_service.dart';
import '../models/planning.dart';
import '../models/profile_state.dart';
import '../theme/app_theme.dart';
import '../widgets/savo_widgets.dart';
import 'planning_results_screen.dart';
import 'weekly_planner_screen.dart';
import 'party_planner_screen.dart';
import 'scan_ingredients_screen.dart';
import 'settings_screen.dart';
import 'onboarding/login_screen.dart';
import 'onboarding/household_screen.dart';
import 'onboarding/allergies_screen.dart';
import 'onboarding/dietary_screen.dart';
import 'onboarding/onboarding_coordinator.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  bool _loadingOnboarding = true;
  Map<String, dynamic>? _onboardingStatus;

  static const Map<String, String> _planningGoalLabels = {
    'balanced': 'Balanced',
    'fastest': 'Fastest',
    'healthiest': 'Healthiest',
    'kid_friendly': 'Kid-friendly',
    'budget': 'Budget',
    'use_what_i_have': 'Use what I have',
  };

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
          // Direct logout button (more visible for testing)
          TextButton.icon(
            onPressed: () async {
              final confirmed = await showDialog<bool>(
                context: context,
                builder: (context) => AlertDialog(
                  title: const Text('Sign Out'),
                  content: const Text('Are you sure you want to sign out?'),
                  actions: [
                    TextButton(
                      onPressed: () => Navigator.pop(context, false),
                      child: const Text('Cancel'),
                    ),
                    ElevatedButton(
                      onPressed: () => Navigator.pop(context, true),
                      child: const Text('Sign Out'),
                    ),
                  ],
                ),
              );
              
              if (confirmed == true && context.mounted) {
                await Supabase.instance.client.auth.signOut();
                if (context.mounted) {
                  Navigator.of(context).pushAndRemoveUntil(
                    MaterialPageRoute(builder: (_) => const OnboardingLoginScreen()),
                    (route) => false,
                  );
                }
              }
            },
            icon: const Icon(Icons.logout),
            label: const Text('Sign Out'),
            style: TextButton.styleFrom(
              foregroundColor: Colors.white70,
            ),
          ),
          const SizedBox(width: 8),
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
            // Hero Card
            HeroCard(
              title: 'Cook Today',
              subtitle: 'Transform your ingredients into delicious meals',
              primaryButtonText: 'Plan Daily Menu',
              secondaryButtonText: 'View Recipes',
              onPrimaryTap: () => _planDaily(context),
              onSecondaryTap: () {
                // Navigate to recipes (future feature)
              },
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
                onHousehold: () {
                  Navigator.push(
                    context,
                    AppMotion.createRoute(const OnboardingHouseholdScreen()),
                  );
                },
                onAllergies: () {
                  Navigator.push(
                    context,
                    AppMotion.createRoute(const OnboardingAllergiesScreen()),
                  );
                },
                onDietary: () {
                  Navigator.push(
                    context,
                    AppMotion.createRoute(const OnboardingDietaryScreen()),
                  );
                },
                onRefresh: _refreshOnboardingStatus,
              ),
              const SizedBox(height: AppSpacing.lg),
            ],

            // Section header
            Text(
              'What would you like to plan?',
              style: AppTypography.h2Style(),
            ),
            const SizedBox(height: AppSpacing.md),

            // Scan Ingredients Card (NEW!)
            _PlanningOptionCard(
              title: 'Scan Ingredients',
              description: 'Add items from photo',
              icon: Icons.camera_alt,
              color: AppColors.accent,
              onTap: () {
                Navigator.push(
                  context,
                  AppMotion.createRoute(const ScanIngredientsScreen()),
                );
              },
            ),
            const SizedBox(height: AppSpacing.md),

            // Planning options
            _PlanningOptionCard(
              title: 'Daily Menu',
              description: 'Plan today\'s meals',
              icon: Icons.today,
              color: AppColors.primary,
              onTap: () => _planDaily(context),
            ),
            const SizedBox(height: AppSpacing.md),
            _PlanningOptionCard(
              title: 'Weekly Planner',
              description: 'Plan 1-4 days ahead',
              icon: Icons.calendar_today,
              color: AppColors.secondary,
              onTap: () {
                Navigator.push(
                  context,
                  AppMotion.createRoute(const WeeklyPlannerScreen()),
                );
              },
            ),
            const SizedBox(height: AppSpacing.md),
            _PlanningOptionCard(
              title: 'Party Menu',
              description: 'Plan for guests',
              icon: Icons.celebration,
              color: AppColors.accent,
              onTap: () {
                Navigator.push(
                  context,
                  AppMotion.createRoute(const PartyPlannerScreen()),
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _planDaily(BuildContext context) async {
    // Check authentication first
    final session = Supabase.instance.client.auth.currentSession;
    if (session == null) {
      _showError(context, 'Please log in to access this feature');
      Navigator.of(context).pushReplacementNamed('/login');
      return;
    }

    final advanced = await _showDailyPlanningOptions(context);
    if (!context.mounted) return;
    if (advanced == null) return;
    
    final apiClient = Provider.of<ApiClient>(context, listen: false);
    final profileState = Provider.of<ProfileState>(context, listen: false);
    
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => WillPopScope(
        onWillPop: () async => false,
        child: Center(
          child: Card(
            margin: const EdgeInsets.all(24),
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: const [
                  CircularProgressIndicator(),
                  SizedBox(height: 16),
                  Text(
                    'Creating your personalized menu...',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w500),
                  ),
                  SizedBox(height: 8),
                  Text(
                    'This may take 30-60 seconds',
                    style: TextStyle(fontSize: 12, color: Colors.grey),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );

    try {
      // Best-effort warm-up to reduce Render cold-start fetch failures on web.
      try {
        await apiClient.get('/health');
      } catch (_) {
        // Ignore warm-up failures; the main request may still succeed.
      }

      final body = <String, dynamic>{
        'time_available_minutes': 60,
        'servings': 4,
      };

      if (advanced.planningGoal != null && advanced.planningGoal != 'balanced') {
        body['planning_goal'] = advanced.planningGoal;
      }
      if (advanced.avoidWaste == true) {
        body['avoid_waste'] = true;
      }
      if (advanced.useLeftovers == false) {
        body['use_leftovers'] = false;
      }

      // Pass preferred cuisines (min 1, max 5 configured in Settings).
      final preferred = profileState.favoriteCuisines;
      if (preferred.isNotEmpty) {
        body['cuisine_preferences'] = preferred;
      }

      final response = await apiClient.post('/plan/daily', body);
      if (!context.mounted) return;
      Navigator.pop(context); // Close loading

      if (response['status'] == 'ok') {
        final menuPlan = MenuPlanResponse.fromJson(response);
        Navigator.push(
          context,
          AppMotion.createRoute(
            PlanningResultsScreen(
              menuPlan: menuPlan,
              planType: 'daily',
            ),
          ),
        );
      } else {
        String message = 'Planning failed';

        final err = response['error_message'];
        if (err is String && err.trim().isNotEmpty) {
          message = err;
        } else {
          final q = response['needs_clarification_questions'];
          if (q is List && q.isNotEmpty && q.first is String && (q.first as String).trim().isNotEmpty) {
            message = (q.first as String).trim();
          } else if (response['detail'] is String && (response['detail'] as String).trim().isNotEmpty) {
            message = (response['detail'] as String).trim();
          } else {
            // Last resort: show status so it's debuggable.
            final s = response['status'];
            if (s is String && s.trim().isNotEmpty) {
              message = 'Planning failed (status=$s)';
            }
          }
        }

        _showError(context, message);
      }
    } catch (e) {
      if (!context.mounted) return;
      Navigator.pop(context);
      _showError(context, e.toString());
    }
  }

  void _showError(BuildContext context, String message) {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Error'),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  Future<_AdvancedPlanningOptions?> _showDailyPlanningOptions(BuildContext context) async {
    String selectedGoal = 'balanced';
    bool avoidWaste = false;
    bool useLeftovers = true;

    return showDialog<_AdvancedPlanningOptions>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, setLocalState) => AlertDialog(
          title: const Text('Daily Menu'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text('Advanced options (optional)'),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                value: selectedGoal,
                decoration: const InputDecoration(
                  labelText: 'Planning goal',
                  border: OutlineInputBorder(),
                ),
                items: _planningGoalLabels.entries
                    .map(
                      (e) => DropdownMenuItem<String>(
                        value: e.key,
                        child: Text(e.value),
                      ),
                    )
                    .toList(),
                onChanged: (v) {
                  if (v == null) return;
                  setLocalState(() => selectedGoal = v);
                },
              ),
              const SizedBox(height: 8),
              SwitchListTile.adaptive(
                value: avoidWaste,
                contentPadding: EdgeInsets.zero,
                title: const Text('Avoid waste'),
                subtitle: const Text('Prioritize expiring items and leftover reuse'),
                onChanged: (v) => setLocalState(() => avoidWaste = v),
              ),
              SwitchListTile.adaptive(
                value: useLeftovers,
                contentPadding: EdgeInsets.zero,
                title: const Text('Use leftovers (when available)'),
                subtitle: const Text('Schedule leftovers sooner when safe'),
                onChanged: (v) => setLocalState(() => useLeftovers = v),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(
                dialogContext,
                _AdvancedPlanningOptions(
                  planningGoal: selectedGoal,
                  avoidWaste: avoidWaste,
                  useLeftovers: useLeftovers,
                ),
              ),
              child: const Text('Plan'),
            ),
          ],
        ),
      ),
    );
  }
}

class _AdvancedPlanningOptions {
  final String? planningGoal;
  final bool avoidWaste;
  final bool useLeftovers;

  const _AdvancedPlanningOptions({
    required this.planningGoal,
    required this.avoidWaste,
    required this.useLeftovers,
  });
}

class _SetupBanner extends StatelessWidget {
  final Map<String, dynamic>? onboardingStatus;
  final VoidCallback onResume;
  final VoidCallback onHousehold;
  final VoidCallback onAllergies;
  final VoidCallback onDietary;
  final VoidCallback onRefresh;

  const _SetupBanner({
    required this.onboardingStatus,
    required this.onResume,
    required this.onHousehold,
    required this.onAllergies,
    required this.onDietary,
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
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                FilledButton.icon(
                  onPressed: onResume,
                  icon: const Icon(Icons.play_arrow),
                  label: const Text('Resume setup'),
                ),
                FilledButton.tonalIcon(
                  onPressed: onHousehold,
                  icon: const Icon(Icons.people_outline),
                  label: const Text('Household'),
                ),
                FilledButton.tonalIcon(
                  onPressed: onAllergies,
                  icon: const Icon(Icons.health_and_safety_outlined),
                  label: const Text('Allergens'),
                ),
                FilledButton.tonalIcon(
                  onPressed: onDietary,
                  icon: const Icon(Icons.restaurant_menu),
                  label: const Text('Dietary'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _PlanningOptionCard extends StatelessWidget {
  final String title;
  final String description;
  final IconData icon;
  final Color color;
  final VoidCallback onTap;

  const _PlanningOptionCard({
    required this.title,
    required this.description,
    required this.icon,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return SavoCard(
      elevated: true,
      onTap: onTap,
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(AppSpacing.sm),
            decoration: BoxDecoration(
              color: color.withOpacity(0.2),
              borderRadius: BorderRadius.circular(AppRadius.md),
            ),
            child: Icon(icon, color: color, size: 32),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: AppTypography.bodyStyle().copyWith(
                    fontWeight: AppTypography.semibold,
                  ),
                ),
                const SizedBox(height: AppSpacing.xs),
                Text(
                  description,
                  style: AppTypography.captionStyle(),
                ),
              ],
            ),
          ),
          Icon(
            Icons.arrow_forward_ios,
            size: 16,
            color: AppColors.textSecondary,
          ),
        ],
      ),
    );
  }
}
