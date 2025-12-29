import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

/// Custom card with SAVO design tokens
class SavoCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry? padding;
  final VoidCallback? onTap;
  final bool elevated;

  const SavoCard({
    super.key,
    required this.child,
    this.padding,
    this.onTap,
    this.elevated = false,
  });

  @override
  Widget build(BuildContext context) {
    final card = Container(
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(AppRadius.md),
        boxShadow: elevated ? AppShadows.card : null,
      ),
      padding: padding ?? const EdgeInsets.all(AppSpacing.md),
      child: child,
    );

    if (onTap != null) {
      return Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(AppRadius.md),
          child: card,
        ),
      );
    }

    return card;
  }
}

/// Recipe card with image and badges
class RecipeCard extends StatelessWidget {
  final String title;
  final String? imageUrl;
  final int? timeMinutes;
  final int? caloriesKcal;
  final String? difficulty;
  final VoidCallback? onTap;

  const RecipeCard({
    super.key,
    required this.title,
    this.imageUrl,
    this.timeMinutes,
    this.caloriesKcal,
    this.difficulty,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 280,
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(AppRadius.md),
        boxShadow: AppShadows.card,
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(AppRadius.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Image
              ClipRRect(
                borderRadius: const BorderRadius.vertical(
                  top: Radius.circular(AppRadius.md),
                ),
                child: imageUrl != null
                    ? Image.network(
                        imageUrl!,
                        height: 180,
                        width: double.infinity,
                        fit: BoxFit.cover,
                        errorBuilder: (context, error, stackTrace) =>
                            _buildPlaceholder(),
                      )
                    : _buildPlaceholder(),
              ),

              // Content
              Padding(
                padding: const EdgeInsets.all(AppSpacing.md),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Title
                    Text(
                      title,
                      style: AppTypography.bodyStyle().copyWith(
                        fontWeight: AppTypography.semibold,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: AppSpacing.sm),

                    // Badges
                    Wrap(
                      spacing: AppSpacing.xs,
                      runSpacing: AppSpacing.xs,
                      children: [
                        if (timeMinutes != null)
                          AppBadge(
                            label: '${timeMinutes}min',
                            icon: Icons.timer_outlined,
                          ),
                        if (caloriesKcal != null)
                          AppBadge(
                            label: '${caloriesKcal}kcal',
                            icon: Icons.local_fire_department_outlined,
                          ),
                        if (difficulty != null)
                          AppBadge(
                            label: difficulty!,
                            icon: Icons.auto_awesome_outlined,
                          ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    ).scaleIn();
  }

  Widget _buildPlaceholder() {
    return Container(
      height: 180,
      width: double.infinity,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            AppColors.primary.withOpacity(0.3),
            AppColors.secondary.withOpacity(0.3),
          ],
        ),
      ),
      child: const Icon(
        Icons.restaurant_menu,
        size: 48,
        color: Colors.white30,
      ),
    );
  }
}

/// Ingredient chip with state colors
class IngredientChip extends StatelessWidget {
  final String name;
  final String? quantity;
  final bool isExpiring;
  final bool isLeftover;
  final VoidCallback? onTap;

  const IngredientChip({
    super.key,
    required this.name,
    this.quantity,
    this.isExpiring = false,
    this.isLeftover = false,
    this.onTap,
  });

  Color get _backgroundColor {
    if (isExpiring) return AppColors.warning.withOpacity(0.2);
    if (isLeftover) return AppColors.info.withOpacity(0.2);
    return AppColors.card;
  }

  Color get _borderColor {
    if (isExpiring) return AppColors.warning;
    if (isLeftover) return AppColors.info;
    return AppColors.divider;
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: _backgroundColor,
        borderRadius: BorderRadius.circular(AppRadius.pill),
        border: Border.all(color: _borderColor, width: 1.5),
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(AppRadius.pill),
          child: Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.md,
              vertical: AppSpacing.sm,
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  name,
                  style: AppTypography.bodyStyle(),
                ),
                if (quantity != null) ...[
                  const SizedBox(width: AppSpacing.xs),
                  Text(
                    quantity!,
                    style: AppTypography.captionStyle(),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    ).fadeIn();
  }
}

/// Section header with divider
class SectionHeader extends StatelessWidget {
  final String title;
  final String? subtitle;
  final Widget? trailing;

  const SectionHeader({
    super.key,
    required this.title,
    this.subtitle,
    this.trailing,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: AppTypography.h2Style(),
                  ),
                  if (subtitle != null) ...[
                    const SizedBox(height: AppSpacing.xs),
                    Text(
                      subtitle!,
                      style: AppTypography.captionStyle(),
                    ),
                  ],
                ],
              ),
            ),
            if (trailing != null) trailing!,
          ],
        ),
        const SizedBox(height: AppSpacing.md),
        const Divider(height: 1),
        const SizedBox(height: AppSpacing.md),
      ],
    );
  }
}

/// Loading shimmer effect
class ShimmerLoading extends StatefulWidget {
  final double width;
  final double height;
  final BorderRadius? borderRadius;

  const ShimmerLoading({
    super.key,
    required this.width,
    required this.height,
    this.borderRadius,
  });

  @override
  State<ShimmerLoading> createState() => _ShimmerLoadingState();
}

class _ShimmerLoadingState extends State<ShimmerLoading>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        return Container(
          width: widget.width,
          height: widget.height,
          decoration: BoxDecoration(
            borderRadius: widget.borderRadius ?? BorderRadius.circular(AppRadius.sm),
            gradient: LinearGradient(
              begin: Alignment(-1.0 + (_controller.value * 2), 0),
              end: Alignment(1.0 + (_controller.value * 2), 0),
              colors: [
                AppColors.card,
                AppColors.card.withOpacity(0.5),
                AppColors.card,
              ],
            ),
          ),
        );
      },
    );
  }
}
