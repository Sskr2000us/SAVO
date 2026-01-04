import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

/// Modern landing screen with hero imagery and clear CTAs
class LandingScreen extends StatelessWidget {
  const LandingScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;

    return Scaffold(
      body: SafeArea(
        child: CustomScrollView(
          slivers: [
            // Hero section
            SliverToBoxAdapter(
              child: Container(
                height: MediaQuery.of(context).size.height * 0.55,
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [
                      cs.primary.withAlpha(36),
                      cs.secondary.withAlpha(24),
                      cs.surface,
                    ],
                  ),
                ),
                child: Stack(
                  children: [
                    // Background pattern
                    Positioned.fill(
                      child: Opacity(
                        opacity: 0.18,
                        child: ColorFiltered(
                          colorFilter: ColorFilter.mode(
                            theme.scaffoldBackgroundColor.withAlpha(140),
                            BlendMode.srcATop,
                          ),
                          child: Image.network(
                            'https://images.unsplash.com/photo-1556910103-1c02745aae4d?w=1200',
                            fit: BoxFit.cover,
                            errorBuilder: (context, error, stackTrace) => const SizedBox.shrink(),
                          ),
                        ),
                      ),
                    ),
                    // Content
                    Center(
                      child: Padding(
                        padding: const EdgeInsets.all(AppSpacing.xl),
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            // Logo
                            Container(
                              width: 120,
                              height: 120,
                              decoration: BoxDecoration(
                                color: cs.surface,
                                shape: BoxShape.circle,
                                boxShadow: AppShadows.float,
                              ),
                              child: Icon(
                                Icons.restaurant_menu,
                                size: 60,
                                color: cs.primary,
                              ),
                            ),
                            const SizedBox(height: AppSpacing.xl),
                            Text(
                              'SAVO',
                              style: theme.textTheme.displayLarge?.copyWith(
                                fontWeight: FontWeight.w800,
                                letterSpacing: -0.5,
                              ),
                              textAlign: TextAlign.center,
                            ),
                            Text(
                              'Cook with what you have. Plan smarter. Waste less.',
                              style: theme.textTheme.titleMedium?.copyWith(
                                color: cs.onSurface.withAlpha(220),
                                height: 1.35,
                              ),
                              textAlign: TextAlign.center,
                            ),
                            const SizedBox(height: AppSpacing.md),
                            Text(
                              'Scan your pantry, get personalized menus, and generate a shopping list in seconds.',
                              style: theme.textTheme.bodyMedium?.copyWith(
                                color: cs.onSurface.withAlpha(190),
                                height: 1.45,
                              ),
                              textAlign: TextAlign.center,
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            
            // Features section
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.all(AppSpacing.xl),
                child: Column(
                  children: [
                    const SizedBox(height: AppSpacing.lg),
                    _FeatureCard(
                      icon: Icons.camera_alt,
                      title: 'Scan Ingredients',
                      description: 'Snap a photo to add items to your pantry fast.',
                    ),
                    const SizedBox(height: AppSpacing.md),
                    _FeatureCard(
                      icon: Icons.auto_awesome,
                      title: 'Smart meal plans',
                      description: 'Daily, weekly, or party plans tailored to you.',
                    ),
                    const SizedBox(height: AppSpacing.md),
                    _FeatureCard(
                      icon: Icons.savings,
                      title: 'Reduce waste',
                      description: 'Prioritize expiring items and plan with leftovers.',
                    ),
                    const SizedBox(height: AppSpacing.xl),
                    
                    // CTA Button
                    SizedBox(
                      width: double.infinity,
                      height: 54,
                      child: FilledButton(
                        onPressed: () {
                          Navigator.of(context).pushNamed('/login');
                        },
                        child: const Text(
                          'Get Started',
                        ),
                      ),
                    ),
                    
                    const SizedBox(height: AppSpacing.xl),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _FeatureCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final String description;

  const _FeatureCard({
    required this.icon,
    required this.title,
    required this.description,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;

    return Container(
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        color: cs.surface,
        borderRadius: BorderRadius.circular(AppRadius.lg),
        boxShadow: AppShadows.card,
      ),
      child: Row(
        children: [
          Container(
            width: 60,
            height: 60,
            decoration: BoxDecoration(
              color: cs.primary.withAlpha(22),
              borderRadius: BorderRadius.circular(AppRadius.md),
            ),
            child: Icon(
              icon,
              size: 32,
              color: cs.primary,
            ),
          ),
          const SizedBox(width: AppSpacing.lg),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: AppSpacing.xs),
                Text(
                  description,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: cs.onSurface.withAlpha(200),
                    height: 1.35,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
