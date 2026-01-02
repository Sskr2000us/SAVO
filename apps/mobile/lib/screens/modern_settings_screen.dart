import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

/// Modern settings screen with card-based design
class ModernSettingsScreen extends StatelessWidget {
  const ModernSettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: CustomScrollView(
        slivers: [
          // Modern App Bar with gradient
          SliverAppBar(
            expandedHeight: 200,
            pinned: true,
            flexibleSpace: FlexibleSpaceBar(
              title: const Text(
                'Settings',
                style: TextStyle(
                  fontWeight: FontWeight.bold,
                  letterSpacing: 0.5,
                ),
              ),
              background: Container(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [
                      Theme.of(context).colorScheme.primary,
                      Theme.of(context).colorScheme.secondary,
                    ],
                  ),
                ),
                child: Stack(
                  children: [
                    Positioned(
                      right: -50,
                      top: -50,
                      child: Icon(
                        Icons.settings,
                        size: 200,
                        color: Colors.white.withOpacity(0.1),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          
          // Content
          SliverPadding(
            padding: const EdgeInsets.all(16),
            sliver: SliverList(
              delegate: SliverChildListDelegate([
                // Profile Section
                _buildSectionTitle('Profile & Family'),
                const SizedBox(height: 12),
                _ModernSettingCard(
                  icon: Icons.person,
                  iconColor: Colors.blue,
                  title: 'Household Profile',
                  subtitle: 'Edit family details and preferences',
                  onTap: () {
                    // Navigate to profile editor
                  },
                ),
                const SizedBox(height: 12),
                _ModernSettingCard(
                  icon: Icons.people,
                  iconColor: Colors.green,
                  title: 'Family Members',
                  subtitle: '3 members',
                  onTap: () {
                    // Navigate to family members
                  },
                ),
                
                const SizedBox(height: 32),
                
                // Preferences Section
                _buildSectionTitle('Cooking Preferences'),
                const SizedBox(height: 12),
                _ModernSettingCard(
                  icon: Icons.restaurant,
                  iconColor: Colors.orange,
                  title: 'Cuisine Style',
                  subtitle: 'Indian, Mediterranean',
                  onTap: () {
                    // Navigate to cuisine preferences
                  },
                ),
                const SizedBox(height: 12),
                _ModernSettingCard(
                  icon: Icons.whatshot,
                  iconColor: Colors.red,
                  title: 'Skill Level',
                  subtitle: 'Intermediate cook',
                  onTap: () {
                    // Navigate to skill level
                  },
                ),
                const SizedBox(height: 12),
                _ModernSettingCard(
                  icon: Icons.dinner_dining,
                  iconColor: Colors.purple,
                  title: 'Dinner Courses',
                  subtitle: '2 courses (main + side)',
                  onTap: () {
                    // Navigate to dinner courses
                  },
                ),
                
                const SizedBox(height: 32),
                
                // Pantry & Inventory
                _buildSectionTitle('Pantry & Inventory'),
                const SizedBox(height: 12),
                _ModernSettingCard(
                  icon: Icons.inventory_2,
                  iconColor: Colors.teal,
                  title: 'Manage Inventory',
                  subtitle: 'View and edit your pantry items',
                  onTap: () {
                    // Navigate to inventory
                  },
                ),
                const SizedBox(height: 12),
                _ModernSettingCard(
                  icon: Icons.local_grocery_store,
                  iconColor: Colors.indigo,
                  title: 'Shopping List',
                  subtitle: '5 items to buy',
                  onTap: () {
                    // Navigate to shopping list
                  },
                ),
                
                const SizedBox(height: 32),
                
                // Account Section
                _buildSectionTitle('Account'),
                const SizedBox(height: 12),
                _ModernSettingCard(
                  icon: Icons.notifications,
                  iconColor: Colors.amber,
                  title: 'Notifications',
                  subtitle: 'Manage notification preferences',
                  onTap: () {
                    // Navigate to notifications
                  },
                ),
                const SizedBox(height: 12),
                _ModernSettingCard(
                  icon: Icons.devices,
                  iconColor: Colors.cyan,
                  title: 'Active Sessions',
                  subtitle: '2 devices logged in',
                  onTap: () {
                    // Navigate to sessions
                  },
                ),
                const SizedBox(height: 12),
                _ModernSettingCard(
                  icon: Icons.logout,
                  iconColor: Colors.red,
                  title: 'Sign Out',
                  subtitle: 'Log out from this device',
                  onTap: () {
                    // Handle sign out
                  },
                ),
                
                const SizedBox(height: 48),
              ]),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSectionTitle(String title) {
    return Padding(
      padding: const EdgeInsets.only(left: 4, bottom: 4),
      child: Text(
        title,
        style: const TextStyle(
          fontSize: 22,
          fontWeight: FontWeight.bold,
          letterSpacing: 0.5,
        ),
      ),
    );
  }
}

class _ModernSettingCard extends StatelessWidget {
  final IconData icon;
  final Color iconColor;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  const _ModernSettingCard({
    required this.icon,
    required this.iconColor,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: Theme.of(context).cardColor,
            borderRadius: BorderRadius.circular(16),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.05),
                blurRadius: 10,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: Row(
            children: [
              // Icon
              Container(
                width: 56,
                height: 56,
                decoration: BoxDecoration(
                  color: iconColor.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(
                  icon,
                  size: 28,
                  color: iconColor,
                ),
              ),
              const SizedBox(width: 16),
              // Text
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        fontSize: 17,
                        fontWeight: FontWeight.w600,
                        letterSpacing: 0.3,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      subtitle,
                      style: TextStyle(
                        fontSize: 14,
                        color: Colors.grey.shade600,
                        height: 1.3,
                      ),
                    ),
                  ],
                ),
              ),
              // Arrow
              Icon(
                Icons.chevron_right,
                color: Colors.grey.shade400,
                size: 24,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
