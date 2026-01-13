import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../theme/app_theme.dart';
import '../services/entitlements_service.dart';
import '../widgets/pro_paywall_sheet.dart';
import 'onboarding/login_screen.dart';
import 'pantry_update_entry_screen.dart';

/// Modern landing screen with hero imagery and clear CTAs
class LandingScreen extends StatefulWidget {
  const LandingScreen({super.key});

  @override
  State<LandingScreen> createState() => _LandingScreenState();
}

class _LandingScreenState extends State<LandingScreen> {
  final GlobalKey _howItWorksKey = GlobalKey();
  bool _showHowItWorksExplainer = false;

  void _seeHowItWorks() {
    if (!_showHowItWorksExplainer) {
      setState(() {
        _showHowItWorksExplainer = true;
      });
    }
    final ctx = _howItWorksKey.currentContext;
    if (ctx == null) return;
    Scrollable.ensureVisible(
      ctx,
      duration: const Duration(milliseconds: 350),
      curve: Curves.easeInOut,
      alignment: 0.1,
    );
  }

  Future<void> _startScanning() async {
    final session = Supabase.instance.client.auth.currentSession;
    if (session == null) {
      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => const OnboardingLoginScreen(postLoginRoute: '/scan'),
        ),
      );
      return;
    }

    final gate = await EntitlementsService.instance.tryConsumeScan();
    if (!gate.allowed && mounted) {
      await showProPaywallSheet(
        context,
        title: 'Upgrade to SAVO Pro',
        ctaLabel: 'Upgrade for unlimited scans',
        reason: 'You\'ve hit today\'s free scan limit. Upgrade to keep scanning and get unlimited suggestions.',
        trigger: 'scan_limit',
      );
      return;
    }

    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => const PantryUpdateEntryScreen(),
      ),
    );
  }

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
                              'Scan groceries → get meals you can cook tonight',
                              style: theme.textTheme.titleMedium?.copyWith(
                                color: cs.onSurface.withAlpha(220),
                                height: 1.35,
                              ),
                              textAlign: TextAlign.center,
                            ),
                            const SizedBox(height: AppSpacing.sm),
                            Text(
                              'Takes ~30 seconds.',
                              style: theme.textTheme.bodyMedium?.copyWith(
                                color: cs.onSurface.withAlpha(200),
                                fontWeight: FontWeight.w700,
                              ),
                              textAlign: TextAlign.center,
                            ),
                            const SizedBox(height: AppSpacing.md),
                            Text(
                              'Confirm what you have, then pick a meal in minutes.',
                              style: theme.textTheme.bodyMedium?.copyWith(
                                color: cs.onSurface.withAlpha(190),
                                height: 1.45,
                              ),
                              textAlign: TextAlign.center,
                            ),
                            const SizedBox(height: AppSpacing.lg),
                            SizedBox(
                              width: double.infinity,
                              height: 54,
                              child: FilledButton(
                                onPressed: () => _startScanning(),
                                child: const Text('Start scanning'),
                              ),
                            ),
                            const SizedBox(height: AppSpacing.sm),
                            Text(
                              'Works best with pantry staples enabled.',
                              style: theme.textTheme.bodySmall?.copyWith(
                                color: cs.onSurfaceVariant,
                              ),
                              textAlign: TextAlign.center,
                            ),
                            const SizedBox(height: AppSpacing.md),
                            Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                _FlowStep(icon: Icons.camera_alt, label: 'Scan pantry', color: cs.primary),
                                Padding(
                                  padding: const EdgeInsets.symmetric(horizontal: 10),
                                  child: Icon(Icons.chevron_right, color: cs.onSurfaceVariant),
                                ),
                                _FlowStep(icon: Icons.auto_awesome, label: 'Pick recipe', color: cs.primary),
                                Padding(
                                  padding: const EdgeInsets.symmetric(horizontal: 10),
                                  child: Icon(Icons.chevron_right, color: cs.onSurfaceVariant),
                                ),
                                _FlowStep(icon: Icons.local_dining, label: 'Cook', color: cs.primary),
                              ],
                            ),
                            const SizedBox(height: AppSpacing.sm),
                            TextButton(
                              onPressed: _seeHowItWorks,
                              child: const Text('See how it works'),
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
              key: _howItWorksKey,
              child: Padding(
                padding: const EdgeInsets.all(AppSpacing.xl),
                child: Column(
                  children: [
                    const SizedBox(height: AppSpacing.lg),
                    if (_showHowItWorksExplainer) ...[
                      Container(
                        padding: const EdgeInsets.all(AppSpacing.lg),
                        decoration: BoxDecoration(
                          color: cs.surface,
                          borderRadius: BorderRadius.circular(AppRadius.lg),
                          boxShadow: AppShadows.card,
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'How it works',
                              style: theme.textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                            const SizedBox(height: AppSpacing.sm),
                            Text(
                              '• Scan your groceries (photo or barcode).',
                              style: theme.textTheme.bodyMedium,
                            ),
                            const SizedBox(height: AppSpacing.xs),
                            Text(
                              '• Quickly confirm anything uncertain.',
                              style: theme.textTheme.bodyMedium,
                            ),
                            const SizedBox(height: AppSpacing.xs),
                            Text(
                              '• Get 3–5 meals you can cook tonight.',
                              style: theme.textTheme.bodyMedium,
                            ),
                            const SizedBox(height: AppSpacing.md),
                            Text(
                              'Privacy: no extra signup required to learn how it works.',
                              style: theme.textTheme.bodySmall?.copyWith(
                                color: cs.onSurfaceVariant,
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: AppSpacing.md),
                    ],
                    _FeatureCard(
                      icon: Icons.camera_alt,
                      title: 'Scan Ingredients',
                      description: 'Snap a photo to add items to your pantry fast.',
                      imageUrl: 'https://images.unsplash.com/photo-1542838132-92c53300491e?w=600',
                    ),
                    const SizedBox(height: AppSpacing.md),
                    _FeatureCard(
                      icon: Icons.auto_awesome,
                      title: 'Smart meal plans',
                      description: 'Daily, weekly, or party plans tailored to you.',
                      imageUrl: 'https://images.unsplash.com/photo-1540189549336-e6e99c3679fe?w=600',
                    ),
                    const SizedBox(height: AppSpacing.md),
                    _FeatureCard(
                      icon: Icons.savings,
                      title: 'Reduce waste',
                      description: 'Prioritize expiring items and plan with leftovers.',
                      imageUrl: 'https://images.unsplash.com/photo-1606914501449-5a96b6ce24ca?w=600',
                    ),
                    const SizedBox(height: AppSpacing.xl),
                    
                    // CTA Button
                    // CTA already shown in hero for fast value.
                    
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
  final String? imageUrl;

  const _FeatureCard({
    required this.icon,
    required this.title,
    required this.description,
    this.imageUrl,
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
          if (imageUrl != null && imageUrl!.trim().isNotEmpty) ...[
            const SizedBox(width: AppSpacing.lg),
            ClipRRect(
              borderRadius: BorderRadius.circular(AppRadius.md),
              child: Image.network(
                imageUrl!,
                width: 72,
                height: 72,
                fit: BoxFit.cover,
                errorBuilder: (context, error, stackTrace) => const SizedBox.shrink(),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _FlowStep extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;

  const _FlowStep({
    required this.icon,
    required this.label,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 18, color: color),
        const SizedBox(height: 4),
        Text(
          label,
          style: theme.textTheme.labelSmall?.copyWith(
            color: cs.onSurfaceVariant,
            fontWeight: FontWeight.w700,
          ),
        ),
      ],
    );
  }
}
