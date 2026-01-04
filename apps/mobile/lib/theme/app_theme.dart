import 'package:flutter/material.dart';

/// SAVO Custom Theme - v1 design tokens
/// Source of truth: `SAVO_COMPREHENSIVE_UI_JSON_USER_STORIES_V1.md`

class AppColors {
  // v1 colors
  static const Color primary = Color(0xFF2F6F62);
  static const Color primarySoft = Color(0xFFE6F1EE);
  static const Color accent = Color(0xFFE07A3F);
  static const Color background = Color(0xFFFAFAF7);
  static const Color surface = Color(0xFFFFFFFF);
  static const Color textPrimary = Color(0xFF1F2933);
  static const Color textSecondary = Color(0xFF6B7280);

  // Back-compat aliases (used throughout the existing UI)
  static const Color secondary = accent;
  static const Color bg = background;
  static const Color info = primary;

  // Derived neutrals (keep in sync with v1 tokens; avoid introducing new hexes)
  static const Color divider = Color(0x336B7280); // textSecondary @ 20%

  // Surfaces
  static const Color card = surface;

  // State colors
  static const Color success = Color(0xFF2E7D32);
  static const Color warning = Color(0xFFED6C02);
  static const Color danger = Color(0xFFC62828);
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
  static const double xs = 4;
  static const double sm = 8;
  static const double md = 16;
  static const double lg = 24;
  static const double xl = 32;
}

class AppRadius {
  static const double sm = 8;
  static const double md = 12;
  static const double lg = 20;
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
  static const Duration fast = Duration(milliseconds: 150);
  static const Duration transition = Duration(milliseconds: 250);
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
  static ThemeData get lightTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      visualDensity: VisualDensity.standard,

      // Color Scheme
      colorScheme: const ColorScheme.light(
        primary: AppColors.primary,
        secondary: AppColors.accent,
        tertiary: AppColors.primarySoft,
        primaryContainer: AppColors.primarySoft,
        secondaryContainer: AppColors.primarySoft,
        tertiaryContainer: AppColors.primarySoft,
        surface: AppColors.surface,
        surfaceVariant: AppColors.primarySoft,
        outline: AppColors.divider,
        outlineVariant: AppColors.divider,
        error: AppColors.danger,
        onPrimary: Colors.white,
        onSecondary: Colors.white,
        onTertiary: AppColors.textPrimary,
        onPrimaryContainer: AppColors.textPrimary,
        onSecondaryContainer: AppColors.textPrimary,
        onTertiaryContainer: AppColors.textPrimary,
        onSurface: AppColors.textPrimary,
        onSurfaceVariant: AppColors.textSecondary,
        onError: Colors.white,
      ),

      // Scaffold
      scaffoldBackgroundColor: AppColors.background,

      // AppBar
      appBarTheme: AppBarTheme(
        backgroundColor: AppColors.background,
        elevation: 0,
        scrolledUnderElevation: 0,
        surfaceTintColor: Colors.transparent,
        centerTitle: false,
        titleTextStyle: AppTypography.h2Style(),
        iconTheme: const IconThemeData(color: AppColors.textPrimary),
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

      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: AppColors.textPrimary,
          textStyle: AppTypography.bodyStyle().copyWith(
            fontWeight: AppTypography.semibold,
          ),
        ),
      ),

      // Input Decoration
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.primarySoft,
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

      // List Tiles
      listTileTheme: ListTileThemeData(
        iconColor: AppColors.textSecondary,
        textColor: AppColors.textPrimary,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: AppSpacing.xs,
        ),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppRadius.md),
        ),
      ),

      // Switch / Checkbox
      switchTheme: SwitchThemeData(
        thumbColor: MaterialStateProperty.resolveWith((states) {
          if (states.contains(MaterialState.selected)) {
            return Colors.white;
          }
          return AppColors.textSecondary;
        }),
        trackColor: MaterialStateProperty.resolveWith((states) {
          if (states.contains(MaterialState.selected)) {
            return AppColors.primary;
          }
          return AppColors.divider;
        }),
      ),

      checkboxTheme: CheckboxThemeData(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(6),
        ),
        side: const BorderSide(color: AppColors.divider, width: 1.5),
        fillColor: MaterialStateProperty.resolveWith((states) {
          if (states.contains(MaterialState.selected)) {
            return AppColors.primary;
          }
          return Colors.transparent;
        }),
        checkColor: MaterialStateProperty.all(Colors.white),
      ),

      // Chip Theme
      chipTheme: ChipThemeData(
        backgroundColor: AppColors.primarySoft,
        selectedColor: AppColors.primary.withOpacity(0.22),
        disabledColor: AppColors.primarySoft.withOpacity(0.5),
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

  /// Legacy dark theme (kept to avoid churn; not currently used by default).
  static ThemeData get darkTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      visualDensity: VisualDensity.standard,
      colorScheme: ColorScheme.dark(
        primary: AppColors.primary,
        secondary: AppColors.accent,
        tertiary: AppColors.primarySoft,
        primaryContainer: AppColors.primary.withOpacity(0.18),
        secondaryContainer: AppColors.accent.withOpacity(0.18),
        tertiaryContainer: AppColors.primarySoft.withOpacity(0.35),
        surface: const Color(0xFF121826),
        surfaceVariant: const Color(0xFF161F2E),
        outline: const Color(0xFF243049),
        outlineVariant: const Color(0xFF243049),
        background: const Color(0xFF0B0F14),
        error: AppColors.danger,
        onPrimary: Colors.white,
        onSecondary: Colors.white,
        onTertiary: Colors.black,
        onPrimaryContainer: const Color(0xFFF4F7FF),
        onSecondaryContainer: const Color(0xFFF4F7FF),
        onTertiaryContainer: const Color(0xFFF4F7FF),
        onSurface: const Color(0xFFF4F7FF),
        onSurfaceVariant: const Color(0xFFA9B1C3),
        onBackground: const Color(0xFFF4F7FF),
        onError: Colors.white,
      ),
      scaffoldBackgroundColor: const Color(0xFF0B0F14),
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
