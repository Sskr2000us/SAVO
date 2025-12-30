import 'package:flutter/material.dart';

/// Skill nudge toast - non-intrusive skill progression suggestion
class SkillNudgeToast extends StatefulWidget {
  final String message;
  final VoidCallback? onTryIt;
  final VoidCallback? onMaybeLater;
  final Duration autoHideDuration;

  const SkillNudgeToast({
    Key? key,
    required this.message,
    this.onTryIt,
    this.onMaybeLater,
    this.autoHideDuration = const Duration(seconds: 10),
  }) : super(key: key);

  @override
  State<SkillNudgeToast> createState() => _SkillNudgeToastState();

  /// Show skill nudge toast at bottom of screen
  static void show({
    required BuildContext context,
    required String message,
    VoidCallback? onTryIt,
    VoidCallback? onMaybeLater,
    Duration autoHideDuration = const Duration(seconds: 10),
  }) {
    final overlay = Overlay.of(context);
    late OverlayEntry overlayEntry;

    overlayEntry = OverlayEntry(
      builder: (context) => Positioned(
        bottom: 80, // Above navigation bar
        left: 16,
        right: 16,
        child: SkillNudgeToast(
          message: message,
          autoHideDuration: autoHideDuration,
          onTryIt: () {
            overlayEntry.remove();
            onTryIt?.call();
          },
          onMaybeLater: () {
            overlayEntry.remove();
            onMaybeLater?.call();
          },
        ),
      ),
    );

    overlay.insert(overlayEntry);

    // Auto-hide after duration
    Future.delayed(autoHideDuration, () {
      if (overlayEntry.mounted) {
        overlayEntry.remove();
      }
    });
  }
}

class _SkillNudgeToastState extends State<SkillNudgeToast>
    with SingleTickerProviderStateMixin {
  late AnimationController _animationController;
  late Animation<Offset> _slideAnimation;
  late Animation<double> _fadeAnimation;

  @override
  void initState() {
    super.initState();
    _animationController = AnimationController(
      duration: const Duration(milliseconds: 400),
      vsync: this,
    );

    _slideAnimation = Tween<Offset>(
      begin: const Offset(0, 1), // Start below screen
      end: Offset.zero,
    ).animate(CurvedAnimation(
      parent: _animationController,
      curve: Curves.easeOut,
    ));

    _fadeAnimation = Tween<double>(
      begin: 0.0,
      end: 1.0,
    ).animate(CurvedAnimation(
      parent: _animationController,
      curve: Curves.easeIn,
    ));

    _animationController.forward();
  }

  @override
  void dispose() {
    _animationController.dispose();
    super.dispose();
  }

  void _handleDismiss() async {
    await _animationController.reverse();
  }

  @override
  Widget build(BuildContext context) {
    return SlideTransition(
      position: _slideAnimation,
      child: FadeTransition(
        opacity: _fadeAnimation,
        child: Dismissible(
          key: const Key('skill_nudge_toast'),
          direction: DismissDirection.down,
          onDismissed: (_) => _handleDismiss(),
          child: Material(
            elevation: 8,
            borderRadius: BorderRadius.circular(12),
            child: Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.1),
                    blurRadius: 8,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Message with icon
                  Row(
                    children: [
                      const Text(
                        '🎯',
                        style: TextStyle(fontSize: 24),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          widget.message,
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w400,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  
                  // Action buttons
                  Row(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      // Maybe Later button (secondary)
                      TextButton(
                        onPressed: widget.onMaybeLater,
                        style: TextButton.styleFrom(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 24,
                            vertical: 12,
                          ),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(20),
                            side: BorderSide(
                              color: Theme.of(context).primaryColor,
                              width: 1,
                            ),
                          ),
                        ),
                        child: Text(
                          'Maybe Later',
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w500,
                            color: Theme.of(context).primaryColor,
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      
                      // Try It button (primary)
                      ElevatedButton(
                        onPressed: widget.onTryIt,
                        style: ElevatedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 24,
                            vertical: 12,
                          ),
                          backgroundColor: Theme.of(context).primaryColor,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(20),
                          ),
                        ),
                        child: const Text(
                          'Try It',
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w500,
                            color: Colors.white,
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Skill nudge manager - tracks when to show nudges
class SkillNudgeManager {
  static const int _recipesBeforeNudge = 5;
  static const Duration _minTimeBetweenNudges = Duration(days: 7);
  
  final String _prefsKey = 'skill_nudge_state';
  int _recipesCompleted = 0;
  DateTime? _lastNudgeShown;
  
  /// Check if we should show a skill nudge
  bool shouldShowNudge() {
    // Check if enough recipes completed
    if (_recipesCompleted < _recipesBeforeNudge) {
      return false;
    }
    
    // Check if enough time has passed since last nudge
    if (_lastNudgeShown != null) {
      final timeSinceLastNudge = DateTime.now().difference(_lastNudgeShown!);
      if (timeSinceLastNudge < _minTimeBetweenNudges) {
        return false;
      }
    }
    
    return true;
  }
  
  /// Mark a recipe as completed
  void markRecipeCompleted() {
    _recipesCompleted++;
  }
  
  /// Mark that a nudge was shown
  void markNudgeShown() {
    _lastNudgeShown = DateTime.now();
    _recipesCompleted = 0; // Reset counter
  }
  
  /// Reset all counters (for testing)
  void reset() {
    _recipesCompleted = 0;
    _lastNudgeShown = null;
  }
}

/// Example usage:
/// ```dart
/// if (skillNudgeManager.shouldShowNudge()) {
///   SkillNudgeToast.show(
///     context: context,
///     message: 'Want to try a slightly new technique?',
///     onTryIt: () {
///       // Navigate to slightly harder recipe
///       skillNudgeManager.markNudgeShown();
///     },
///     onMaybeLater: () {
///       // Do nothing, will ask again later
///     },
///   );
/// }
/// ```
