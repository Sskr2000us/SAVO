import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../services/api_client.dart';
import '../models/planning.dart';
import '../theme/app_theme.dart';
import '../widgets/savo_widgets.dart';
import 'planning_results_screen.dart';
import 'weekly_planner_screen.dart';
import 'party_planner_screen.dart';
import 'scan_ingredients_screen.dart';
import 'settings_screen.dart';
import 'onboarding/login_screen.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
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
    final apiClient = Provider.of<ApiClient>(context, listen: false);
    
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => const Center(child: CircularProgressIndicator()),
    );

    try {
      print('DEBUG: Sending daily plan request with time=60, servings=4');
      final response = await apiClient.post('/plan/daily', {
        'time_available_minutes': 60,
        'servings': 4,
      });
      print('DEBUG: Received response: ${response.toString().substring(0, 100)}');
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
        _showError(context, response['error_message'] ?? 'Planning failed');
      }
    } catch (e) {
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
