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

/// Hero card with gradient background and floating animation
class HeroCard extends StatefulWidget {
  final String title;
  final String subtitle;
  final String? imageUrl;
  final String primaryButtonText;
  final String secondaryButtonText;
  final VoidCallback? onPrimaryTap;
  final VoidCallback? onSecondaryTap;

  const HeroCard({
    super.key,
    required this.title,
    required this.subtitle,
    this.imageUrl,
    this.primaryButtonText = 'Get Started',
    this.secondaryButtonText = 'Learn More',
    this.onPrimaryTap,
    this.onSecondaryTap,
  });

  @override
  State<HeroCard> createState() => _HeroCardState();
}

class _HeroCardState extends State<HeroCard>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _floatAnimation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2000),
    )..repeat(reverse: true);

    _floatAnimation = Tween<double>(begin: 0, end: 8).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _floatAnimation,
      builder: (context, child) {
        return Transform.translate(
          offset: Offset(0, _floatAnimation.value),
          child: child,
        );
      },
      child: Container(
        height: 320,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(AppRadius.lg),
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              AppColors.primary.withOpacity(0.9),
              AppColors.primary.withOpacity(0.85),
              AppColors.secondary.withOpacity(0.8),
            ],
          ),
          boxShadow: AppShadows.float,
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(AppRadius.lg),
          child: Stack(
            children: [
              // Background image
              if (widget.imageUrl != null)
                Positioned.fill(
                  child: Opacity(
                    opacity: 0.3,
                    child: Image.network(
                      widget.imageUrl!,
                      fit: BoxFit.cover,
                      errorBuilder: (context, error, stackTrace) =>
                          const SizedBox(),
                    ),
                  ),
                ),

              // Content
              Padding(
                padding: const EdgeInsets.all(AppSpacing.lg),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Title
                    Text(
                      widget.title,
                      style: AppTypography.displayStyle().copyWith(
                        color: Colors.white,
                        fontWeight: AppTypography.bold,
                        shadows: [
                          Shadow(
                            offset: Offset(0, 1),
                            blurRadius: 3,
                            color: Colors.black.withOpacity(0.3),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: AppSpacing.sm),

                    // Subtitle
                    Text(
                      widget.subtitle,
                      style: AppTypography.h2Style().copyWith(
                        color: Colors.white,
                        fontWeight: AppTypography.regular,
                        shadows: [
                          Shadow(
                            offset: Offset(0, 1),
                            blurRadius: 3,
                            color: Colors.black.withOpacity(0.3),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: AppSpacing.lg),

                    // CTAs
                    Row(
                      children: [
                        // Primary button
                        Expanded(
                          child: ElevatedButton(
                            onPressed: widget.onPrimaryTap,
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.white,
                              foregroundColor: AppColors.primary,
                              padding: const EdgeInsets.symmetric(
                                vertical: AppSpacing.md,
                              ),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(AppRadius.md),
                              ),
                            ),
                            child: Text(
                              widget.primaryButtonText,
                              style: AppTypography.bodyStyle().copyWith(
                                fontWeight: AppTypography.semibold,
                                color: AppColors.primary,
                              ),
                            ),
                          ).withButtonPress(),
                        ),
                        const SizedBox(width: AppSpacing.md),

                        // Secondary button
                        Expanded(
                          child: OutlinedButton(
                            onPressed: widget.onSecondaryTap,
                            style: OutlinedButton.styleFrom(
                              foregroundColor: Colors.white,
                              side: const BorderSide(color: Colors.white, width: 2),
                              padding: const EdgeInsets.symmetric(
                                vertical: AppSpacing.md,
                              ),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(AppRadius.md),
                              ),
                            ),
                            child: Text(
                              widget.secondaryButtonText,
                              style: AppTypography.bodyStyle().copyWith(
                                fontWeight: AppTypography.semibold,
                                color: Colors.white,
                              ),
                            ),
                          ).withButtonPress(),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ).scaleIn(),
    );
  }
}

/// Horizontal carousel with page indicators
class SavoCarousel extends StatefulWidget {
  final List<Widget> items;
  final double itemWidth;
  final double height;

  const SavoCarousel({
    super.key,
    required this.items,
    this.itemWidth = 280,
    this.height = 300,
  });

  @override
  State<SavoCarousel> createState() => _SavoCarouselState();
}

class _SavoCarouselState extends State<SavoCarousel> {
  final PageController _pageController = PageController(viewportFraction: 0.85);
  int _currentPage = 0;

  @override
  void initState() {
    super.initState();
    _pageController.addListener(() {
      final page = _pageController.page?.round() ?? 0;
      if (page != _currentPage) {
        setState(() => _currentPage = page);
      }
    });
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // Carousel
        SizedBox(
          height: widget.height,
          child: PageView.builder(
            controller: _pageController,
            itemCount: widget.items.length,
            itemBuilder: (context, index) {
              return Padding(
                padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm),
                child: widget.items[index],
              );
            },
          ),
        ),
        const SizedBox(height: AppSpacing.md),

        // Page indicators
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: List.generate(
            widget.items.length,
            (index) => AnimatedContainer(
              duration: AppMotion.transition,
              curve: AppMotion.easing,
              margin: const EdgeInsets.symmetric(horizontal: 4),
              width: _currentPage == index ? 24 : 8,
              height: 8,
              decoration: BoxDecoration(
                color: _currentPage == index
                    ? AppColors.primary
                    : AppColors.divider,
                borderRadius: BorderRadius.circular(AppRadius.pill),
              ),
            ),
          ),
        ),
      ],
    );
  }
}

/// Selectable chip with animation
class SelectableChip extends StatefulWidget {
  final String label;
  final bool isSelected;
  final VoidCallback? onTap;

  const SelectableChip({
    super.key,
    required this.label,
    this.isSelected = false,
    this.onTap,
  });

  @override
  State<SelectableChip> createState() => _SelectableChipState();
}

class _SelectableChipState extends State<SelectableChip>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _scaleAnimation;
  late Animation<Color?> _colorAnimation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: AppMotion.transition,
    );

    _scaleAnimation = Tween<double>(begin: 1.0, end: 1.1).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeOut),
    );

    _colorAnimation = ColorTween(
      begin: AppColors.card,
      end: AppColors.primary.withOpacity(0.2),
    ).animate(_controller);
  }

  @override
  void didUpdateWidget(SelectableChip oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.isSelected != oldWidget.isSelected) {
      if (widget.isSelected) {
        _controller.forward();
      } else {
        _controller.reverse();
      }
    }
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
        return Transform.scale(
          scale: _scaleAnimation.value,
          child: Container(
            decoration: BoxDecoration(
              color: _colorAnimation.value,
              borderRadius: BorderRadius.circular(AppRadius.pill),
              border: Border.all(
                color: widget.isSelected ? AppColors.primary : AppColors.divider,
                width: 2,
              ),
            ),
            child: Material(
              color: Colors.transparent,
              child: InkWell(
                onTap: widget.onTap,
                borderRadius: BorderRadius.circular(AppRadius.pill),
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.md,
                    vertical: AppSpacing.sm,
                  ),
                  child: Text(
                    widget.label,
                    style: AppTypography.bodyStyle().copyWith(
                      color: widget.isSelected
                          ? AppColors.primary
                          : AppColors.textSecondary,
                      fontWeight: widget.isSelected
                          ? AppTypography.semibold
                          : AppTypography.regular,
                    ),
                  ),
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}
