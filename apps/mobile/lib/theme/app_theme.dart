import 'package:flutter/material.dart';

/// SAVO Custom Theme - Figma-ready design tokens
/// Based on docs/spec/ui-spec.ant.figma-ready.json

class AppColors {
  // Brand Colors
  static const Color primary = Color(0xFFFF5A3C);
  static const Color secondary = Color(0xFF2CCB7F);
  static const Color accent = Color(0xFFFFC043);

  // Food Palette
  static const Color tomato = Color(0xFFFF4D4D);
  static const Color basil = Color(0xFF2ECC71);
  static const Color saffron = Color(0xFFFFB000);
  static const Color blueberry = Color(0xFF5B6CFF);
  static const Color cocoa = Color(0xFF7A4E2D);

  // Neutrals (Dark Mode)
  static const Color bg = Color(0xFF0B0F14);
  static const Color surface = Color(0xFF121826);
  static const Color card = Color(0xFF161F2E);
  static const Color textPrimary = Color(0xFFF4F7FF);
  static const Color textSecondary = Color(0xFFA9B1C3);
  static const Color divider = Color(0xFF243049);

  // State Colors
  static const Color success = Color(0xFF2CCB7F);
  static const Color warning = Color(0xFFFFC043);
  static const Color danger = Color(0xFFFF4D4D);
  static const Color info = Color(0xFF5B6CFF);
}

class AppTypography {
  // Font sizes from spec
  static const double display = 34;
  static const double h1 = 28;
  static const double h2 = 22;
  static const double body = 16;
  static const double caption = 13;
  static const double micro = 11;

  // Font weights
  static const FontWeight regular = FontWeight.w400;
  static const FontWeight medium = FontWeight.w500;
  static const FontWeight semibold = FontWeight.w600;
  static const FontWeight bold = FontWeight.w700;

  // Text styles
  static TextStyle displayStyle({Color? color}) => TextStyle(
        fontSize: display,
        fontWeight: bold,
        color: color ?? AppColors.textPrimary,
        height: 1.2,
      );

  static TextStyle h1Style({Color? color}) => TextStyle(
        fontSize: h1,
        fontWeight: semibold,
        color: color ?? AppColors.textPrimary,
        height: 1.3,
      );

  static TextStyle h2Style({Color? color}) => TextStyle(
        fontSize: h2,
        fontWeight: semibold,
        color: color ?? AppColors.textPrimary,
        height: 1.3,
      );

  static TextStyle bodyStyle({Color? color}) => TextStyle(
        fontSize: body,
        fontWeight: regular,
        color: color ?? AppColors.textPrimary,
        height: 1.5,
      );

  static TextStyle captionStyle({Color? color}) => TextStyle(
        fontSize: caption,
        fontWeight: regular,
        color: color ?? AppColors.textSecondary,
        height: 1.4,
      );

  static TextStyle microStyle({Color? color}) => TextStyle(
        fontSize: micro,
        fontWeight: medium,
        color: color ?? AppColors.textSecondary,
        height: 1.3,
      );
}

class AppSpacing {
  static const double xs = 6;
  static const double sm = 10;
  static const double md = 16;
  static const double lg = 24;
  static const double xl = 32;
}

class AppRadius {
  static const double sm = 10;
  static const double md = 16;
  static const double lg = 24;
  static const double pill = 999;
}

class AppShadows {
  static List<BoxShadow> get card => [
        BoxShadow(
          color: Colors.black.withOpacity(0.35),
          blurRadius: 30,
          offset: const Offset(0, 10),
        ),
      ];

  static List<BoxShadow> get float => [
        BoxShadow(
          color: Colors.black.withOpacity(0.45),
          blurRadius: 40,
          offset: const Offset(0, 16),
        ),
      ];
}

class AppMotion {
  static const Duration transition = Duration(milliseconds: 220);
  static const Curve easing = Curves.easeInOutCubic; // Approximates cubic-bezier(0.2, 0.8, 0.2, 1)

  /// Create a custom page route with slide and fade animation
  static PageRoute<T> createRoute<T>(Widget page) {
    return PageRouteBuilder<T>(
      pageBuilder: (context, animation, secondaryAnimation) => page,
      transitionsBuilder: (context, animation, secondaryAnimation, child) {
        const begin = Offset(1.0, 0.0);
        const end = Offset.zero;
        const curve = Curves.easeInOutCubic;

        var slideTween = Tween(begin: begin, end: end)
            .chain(CurveTween(curve: curve));
        var fadeTween = Tween<double>(begin: 0.0, end: 1.0);

        return SlideTransition(
          position: animation.drive(slideTween),
          child: FadeTransition(
            opacity: animation.drive(fadeTween),
            child: child,
          ),
        );
      },
      transitionDuration: transition,
    );
  }
}

/// Main Theme Data
class AppTheme {
  static ThemeData get darkTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      
      // Color Scheme
      colorScheme: ColorScheme.dark(
        primary: AppColors.primary,
        secondary: AppColors.secondary,
        tertiary: AppColors.accent,
        surface: AppColors.surface,
        background: AppColors.bg,
        error: AppColors.danger,
        onPrimary: Colors.white,
        onSecondary: Colors.white,
        onSurface: AppColors.textPrimary,
        onBackground: AppColors.textPrimary,
      ),

      // Scaffold
      scaffoldBackgroundColor: AppColors.bg,

      // AppBar
      appBarTheme: AppBarTheme(
        backgroundColor: AppColors.surface,
        elevation: 0,
        centerTitle: false,
        titleTextStyle: AppTypography.h2Style(),
        iconTheme: const IconThemeData(color: AppColors.textPrimary),
      ),

      // Card
      cardTheme: const CardThemeData(
        color: AppColors.card,
        elevation: 0,
        shadowColor: Colors.black,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(AppRadius.md)),
        ),
      ),

      // Text Theme
      textTheme: TextTheme(
        displayLarge: AppTypography.displayStyle(),
        headlineLarge: AppTypography.h1Style(),
        headlineMedium: AppTypography.h2Style(),
        bodyLarge: AppTypography.bodyStyle(),
        bodyMedium: AppTypography.bodyStyle(),
        bodySmall: AppTypography.captionStyle(),
        labelSmall: AppTypography.microStyle(),
      ),

      // Button Theme
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.primary,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.lg,
            vertical: AppSpacing.md,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppRadius.md),
          ),
          elevation: 0,
          textStyle: AppTypography.bodyStyle(color: Colors.white).copyWith(
            fontWeight: AppTypography.semibold,
          ),
        ),
      ),

      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: AppColors.primary,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.lg,
            vertical: AppSpacing.md,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppRadius.md),
          ),
          elevation: 0,
          textStyle: AppTypography.bodyStyle(color: Colors.white).copyWith(
            fontWeight: AppTypography.semibold,
          ),
        ),
      ),

      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: AppColors.primary,
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.lg,
            vertical: AppSpacing.md,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppRadius.md),
          ),
          side: const BorderSide(color: AppColors.primary, width: 1.5),
        ),
      ),

      // Input Decoration
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.card,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppRadius.md),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppRadius.md),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppRadius.md),
          borderSide: const BorderSide(color: AppColors.primary, width: 2),
        ),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: AppSpacing.md,
        ),
        hintStyle: AppTypography.bodyStyle(color: AppColors.textSecondary),
      ),

      // Chip Theme
      chipTheme: ChipThemeData(
        backgroundColor: AppColors.card,
        selectedColor: AppColors.primary.withOpacity(0.2),
        disabledColor: AppColors.card.withOpacity(0.5),
        labelStyle: AppTypography.captionStyle(),
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.sm,
          vertical: AppSpacing.xs,
        ),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppRadius.pill),
        ),
      ),

      // Divider
      dividerTheme: const DividerThemeData(
        color: AppColors.divider,
        thickness: 1,
        space: AppSpacing.md,
      ),

      // Bottom Navigation Bar
      bottomNavigationBarTheme: BottomNavigationBarThemeData(
        backgroundColor: AppColors.surface,
        selectedItemColor: AppColors.primary,
        unselectedItemColor: AppColors.textSecondary,
        type: BottomNavigationBarType.fixed,
        elevation: 0,
        selectedLabelStyle: AppTypography.microStyle(),
        unselectedLabelStyle: AppTypography.microStyle(),
      ),

      // Icon Theme
      iconTheme: const IconThemeData(
        color: AppColors.textPrimary,
        size: 24,
      ),

      // Page Transitions
      pageTransitionsTheme: const PageTransitionsTheme(
        builders: {
          TargetPlatform.android: CupertinoPageTransitionsBuilder(),
          TargetPlatform.iOS: CupertinoPageTransitionsBuilder(),
          TargetPlatform.windows: FadeUpwardsPageTransitionsBuilder(),
        },
      ),
    );
  }
}

/// Extension for animated transitions
extension AnimatedWidgetExtensions on Widget {
  Widget fadeIn({Duration? duration}) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0.0, end: 1.0),
      duration: duration ?? AppMotion.transition,
      curve: AppMotion.easing,
      builder: (context, value, child) {
        return Opacity(
          opacity: value,
          child: child,
        );
      },
      child: this,
    );
  }

  Widget scaleIn({Duration? duration}) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0.9, end: 1.0),
      duration: duration ?? AppMotion.transition,
      curve: AppMotion.easing,
      builder: (context, value, child) {
        return Transform.scale(
          scale: value,
          child: Opacity(
            opacity: value,
            child: child,
          ),
        );
      },
      child: this,
    );
  }

  /// Button press feedback animation
  Widget withButtonPress() {
    return _ButtonPressWrapper(child: this);
  }
}

class _ButtonPressWrapper extends StatefulWidget {
  final Widget child;

  const _ButtonPressWrapper({required this.child});

  @override
  State<_ButtonPressWrapper> createState() => _ButtonPressWrapperState();
}

class _ButtonPressWrapperState extends State<_ButtonPressWrapper>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _scaleAnimation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 100),
    );
    _scaleAnimation = Tween<double>(begin: 1.0, end: 0.95).animate(
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
    return GestureDetector(
      onTapDown: (_) => _controller.forward(),
      onTapUp: (_) => _controller.reverse(),
      onTapCancel: () => _controller.reverse(),
      child: AnimatedBuilder(
        animation: _scaleAnimation,
        builder: (context, child) {
          return Transform.scale(
            scale: _scaleAnimation.value,
            child: child,
          );
        },
        child: widget.child,
      ),
    );
  }
}

/// Badge widget helper
class AppBadge extends StatelessWidget {
  final String label;
  final Color? backgroundColor;
  final Color? textColor;
  final IconData? icon;

  const AppBadge({
    super.key,
    required this.label,
    this.backgroundColor,
    this.textColor,
    this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.sm,
        vertical: AppSpacing.xs,
      ),
      decoration: BoxDecoration(
        color: backgroundColor ?? AppColors.card,
        borderRadius: BorderRadius.circular(AppRadius.sm),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 14, color: textColor ?? AppColors.textSecondary),
            const SizedBox(width: 4),
          ],
          Text(
            label,
            style: AppTypography.microStyle(color: textColor),
          ),
        ],
      ),
    );
  }
}
