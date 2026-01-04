import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../services/metrics_service.dart';
import '../ui/ui_principles.dart';
import 'scan_ingredients_screen.dart';

/// Web-safe fallback for the v1 SnapPantry camera step.
///
/// The v1 flow expects a camera capture experience. On web, we reuse the
/// existing photo-based scanning screen.
class PantryCameraScreen extends StatelessWidget {
  const PantryCameraScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const _PantryCameraScreenWeb();
  }
}

class _PantryCameraScreenWeb extends StatefulWidget {
  const _PantryCameraScreenWeb();

  @override
  State<_PantryCameraScreenWeb> createState() => _PantryCameraScreenWebState();
}

class _PantryCameraScreenWebState extends State<_PantryCameraScreenWeb> {
  @override
  void initState() {
    super.initState();
    fireAndForget(MetricsService.instance.recordWorkflowStep('SnapPantry', 'Capture'));
    fireAndForget(MetricsService.instance.recordEvent('pantry_scan_started'));
    fireAndForget(MetricsService.instance.startTimer('scan_to_confirm_time'));
  }

  @override
  Widget build(BuildContext context) {
    if (kDebugMode || kProfileMode) {
      SavoUiGuards.warnIfMultiplePrimaryActions(
        screen: 'PantryCameraScreen',
        surface: 'Web fallback',
        primaryActions: 1,
      );
    }

    return const ScanIngredientsScreen();
  }
}
