import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../services/auth_service.dart';
import '../theme/app_theme.dart';
import '../widgets/savo_widgets.dart';
import 'settings_screen.dart';
import 'inventory_screen.dart';
import 'recipe_import_screen.dart';
import 'shopping_list_screen.dart';
import 'settings/device_security_screen.dart';
import '../models/market_config_state.dart';

/// User profile hub (v1: UserProfile).
///
/// Hosts profile preferences and related account controls.
class UserProfileScreen extends StatelessWidget {
  const UserProfileScreen({super.key});

  Future<void> _handleSignOut(BuildContext context) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Sign Out'),
        content: const Text('Are you sure you want to sign out?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Sign Out'),
          ),
        ],
      ),
    );

    if (confirmed != true || !context.mounted) return;

    try {
      final authService = Provider.of<AuthService>(context, listen: false);
      await authService.signOut();

      if (context.mounted) {
        Navigator.of(context).pushNamedAndRemoveUntil(
          '/login',
          (route) => false,
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to sign out: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final market = Provider.of<MarketConfigState>(context);
    final showShoppingList = market.isEnabled('shopping_list', defaultValue: true);
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('User profile'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(AppSpacing.md),
        children: [
          // Profile Section
          _buildSectionHeader(context, 'Profile'),
          const SizedBox(height: AppSpacing.sm),
          _settingTile(
            context: context,
            icon: Icons.family_restroom,
            iconColor: theme.colorScheme.primary,
            title: 'Family Profile',
            subtitle: 'Household, cuisines, skill, dietary needs',
            onTap: () {
              Navigator.push(context, AppMotion.createRoute(const SettingsScreen()));
            },
          ),
          
          const SizedBox(height: AppSpacing.lg),
          
          // Pantry Section
          _buildSectionHeader(context, 'Pantry'),
          const SizedBox(height: AppSpacing.sm),
          _settingTile(
            context: context,
            icon: Icons.inventory_2,
            iconColor: theme.colorScheme.secondary,
            title: 'Manage Inventory',
            subtitle: 'View and edit pantry items',
            onTap: () {
              Navigator.push(context, AppMotion.createRoute(const InventoryScreen()));
            },
          ),

          const SizedBox(height: AppSpacing.sm),
          if (showShoppingList)
            _settingTile(
              context: context,
              icon: Icons.local_grocery_store,
              iconColor: theme.colorScheme.secondary,
              title: 'Shopping List',
              subtitle: 'Items to buy (from recipes)',
              onTap: () {
                Navigator.push(context, AppMotion.createRoute(const ShoppingListScreen()));
              },
            ),

          const SizedBox(height: AppSpacing.lg),

          // Recipes Section
          _buildSectionHeader(context, 'Recipes'),
          const SizedBox(height: AppSpacing.sm),
          _settingTile(
            context: context,
            icon: Icons.download,
            iconColor: theme.colorScheme.tertiary,
            title: 'Import Recipe',
            subtitle: 'From URL, text, or photo',
            onTap: () {
              Navigator.push(context, AppMotion.createRoute(const RecipeImportScreen()));
            },
          ),
          
          const SizedBox(height: AppSpacing.lg),
          
          // Security Section
          _buildSectionHeader(context, 'Security'),
          const SizedBox(height: AppSpacing.sm),
          _settingTile(
            context: context,
            icon: Icons.devices,
            iconColor: theme.colorScheme.error,
            title: 'Device Security (Max 2)',
            subtitle: 'Manage devices and sessions',
            onTap: () {
              Navigator.push(context, AppMotion.createRoute(const DeviceSecurityScreen()));
            },
          ),
          const SizedBox(height: AppSpacing.sm),
          _settingTile(
            context: context,
            icon: Icons.logout,
            iconColor: theme.colorScheme.error,
            title: 'Sign Out',
            subtitle: 'Log out from this device',
            onTap: () => _handleSignOut(context),
          ),
          
          const SizedBox(height: AppSpacing.xl),
          
          // App Info
          Center(
            child: Column(
              children: [
                Text(
                  'SAVO',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  'Version 1.0.0',
                  style: TextStyle(
                    fontSize: 12,
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(BuildContext context, String title) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(left: 4),
      child: Text(
        title,
        style: theme.textTheme.labelLarge?.copyWith(
          color: theme.colorScheme.onSurfaceVariant,
          letterSpacing: 0.5,
        ),
      ),
    );
  }

  Widget _settingTile({
    required BuildContext context,
    required IconData icon,
    required Color iconColor,
    required String title,
    required String subtitle,
    required VoidCallback onTap,
  }) {
    final theme = Theme.of(context);
    return SavoCard(
      elevated: true,
      onTap: onTap,
      child: Row(
        children: [
          Icon(icon, color: iconColor),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: theme.textTheme.titleMedium),
                const SizedBox(height: AppSpacing.xs),
                Text(
                  subtitle,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
          Icon(Icons.chevron_right, color: theme.colorScheme.onSurfaceVariant),
        ],
      ),
    );
  }
}
