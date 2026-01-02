import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../screens/onboarding/login_screen.dart';

/// Reusable AppBar for onboarding screens with back button, logout, and Save & Exit
class OnboardingAppBar extends StatelessWidget implements PreferredSizeWidget {
  final String title;
  final VoidCallback? onSaveAndExit;
  final bool isLoading;
  final bool showBack;

  const OnboardingAppBar({
    super.key,
    required this.title,
    this.onSaveAndExit,
    this.isLoading = false,
    this.showBack = true,
  });

  Future<void> _handleLogout(BuildContext context) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Sign Out'),
        content: const Text('Are you sure you want to sign out? Your progress will be saved.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Sign Out', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );

    if (confirm == true && context.mounted) {
      try {
        await Supabase.instance.client.auth.signOut();
        if (context.mounted) {
          Navigator.of(context).pushAndRemoveUntil(
            MaterialPageRoute(builder: (_) => const OnboardingLoginScreen()),
            (route) => false,
          );
        }
      } catch (e) {
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Sign out failed: $e')),
          );
        }
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return AppBar(
      leading: showBack
          ? IconButton(
              icon: const Icon(Icons.arrow_back),
              onPressed: () {
                if (Navigator.canPop(context)) {
                  Navigator.pop(context);
                }
              },
              tooltip: 'Back',
            )
          : null,
      title: Text(title),
      actions: [
        // Logout button
        IconButton(
          icon: const Icon(Icons.logout),
          onPressed: () => _handleLogout(context),
          tooltip: 'Sign Out',
        ),
        // Save & Exit button (only show if callback provided)
        if (onSaveAndExit != null) ...[
          TextButton(
            onPressed: isLoading ? null : onSaveAndExit,
            child: const Text(
              'Save & Exit',
              style: TextStyle(color: Colors.white70),
            ),
          ),
          const SizedBox(width: 8),
        ],
      ],
    );
  }

  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight);
}
