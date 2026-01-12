import 'dart:io';

import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../services/camera_cache.dart';
import '../services/scanning_service.dart';
import '../services/metrics_service.dart';
import '../theme/app_theme.dart';
import '../ui/ui_principles.dart';
import 'pantry_ai_suggestions_screen.dart';

/// v1 Flow B: PantryCamera (mobile).
///
/// Requirements:
/// - Overlay: shelfGrid
/// - Status: lighting + itemDensity
/// - Primary action: CAPTURE_IMAGE
class PantryCameraScreen extends StatefulWidget {
  const PantryCameraScreen({super.key});

  @override
  State<PantryCameraScreen> createState() => _PantryCameraScreenState();
}

class _PantryCameraScreenState extends State<PantryCameraScreen> {
  CameraController? _controller;
  bool _initializing = true;
  bool _processing = false;

  bool _hintStreamActive = false;
  int _lastHintMillis = 0;
  String _lightingHint = 'Good lighting';
  String _densityHint = 'Item density looks good';

  @override
  void initState() {
    super.initState();
    fireAndForget(MetricsService.instance.recordWorkflowStep('SnapPantry', 'Capture'));
    fireAndForget(MetricsService.instance.recordEvent('pantry_scan_started'));
    fireAndForget(MetricsService.instance.startTimer('scan_to_confirm_time'));
    _init();
  }

  Future<void> _init() async {
    try {
      final cams = await CameraCache.getCameras();
      if (cams.isEmpty) {
        if (mounted) setState(() => _initializing = false);
        return;
      }

      final controller = CameraController(
        cams.first,
        ResolutionPreset.high,
        enableAudio: false,
      );

      await controller.initialize();
      if (!mounted) return;

      setState(() {
        _controller = controller;
        _initializing = false;
      });

      // Start a lightweight image stream to update status hints.
      // This is NOT auto-scanning; it's just heuristics for lighting and clutter.
      _startHintStream();
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _controller = null;
        _initializing = false;
      });
    }
  }

  void _startHintStream() {
    final controller = _controller;
    if (controller == null) return;
    if (_hintStreamActive) return;

    // Some platforms may not support image streaming; fail silently.
    try {
      _hintStreamActive = true;
      controller.startImageStream((image) {
        final now = DateTime.now().millisecondsSinceEpoch;
        if (now - _lastHintMillis < 800) return;
        _lastHintMillis = now;

        // Lighting + density heuristics from luma plane.
        // This keeps CPU low by subsampling.
        final plane = image.planes.isNotEmpty ? image.planes.first : null;
        final bytes = plane?.bytes;
        if (bytes == null || bytes.isEmpty) return;

        // Mean luminance (0..255)
        int sum = 0;
        int samples = 0;
        final step = (bytes.length ~/ 6000).clamp(8, 64);
        for (var i = 0; i < bytes.length; i += step) {
          sum += bytes[i];
          samples++;
        }
        final mean = samples == 0 ? 0.0 : (sum / samples);

        // Edge ratio (rough clutter measure)
        int edgeCount = 0;
        int edgeSamples = 0;
        const edgeThreshold = 26;
        for (var i = 0; i + step < bytes.length; i += step) {
          final a = bytes[i];
          final b = bytes[i + step];
          final diff = (a - b).abs();
          if (diff > edgeThreshold) edgeCount++;
          edgeSamples++;
        }
        final edgeRatio = edgeSamples == 0 ? 0.0 : (edgeCount / edgeSamples);

        String lighting;
        if (mean < 70) {
          lighting = 'Too dark — turn on lights';
        } else if (mean > 210) {
          lighting = 'Too bright — avoid glare';
        } else {
          lighting = 'Good lighting';
        }

        String density;
        if (edgeRatio > 0.22) {
          density = 'Too many items — move closer';
        } else {
          density = 'Item density looks good';
        }

        if (!mounted) return;
        if (lighting == _lightingHint && density == _densityHint) return;
        setState(() {
          _lightingHint = lighting;
          _densityHint = density;
        });
      });
    } catch (_) {
      _hintStreamActive = false;
    }
  }

  Future<void> _stopHintStream() async {
    final controller = _controller;
    if (controller == null) return;
    if (!_hintStreamActive) return;
    try {
      await controller.stopImageStream();
    } catch (_) {
      // Best-effort only.
    } finally {
      _hintStreamActive = false;
    }
  }

  @override
  void dispose() {
    // Stop stream first, then dispose controller.
    // ignore: discarded_futures
    _stopHintStream();
    _controller?.dispose();
    super.dispose();
  }

  Future<void> _captureAndAnalyze() async {
    if (_controller == null || !_controller!.value.isInitialized) return;

    setState(() => _processing = true);

    try {
      // camera: cannot takePicture while streaming.
      await _stopHintStream();
      final xfile = await _controller!.takePicture();
      final file = File(xfile.path);

      final svc = ScanningService();
      final res = await svc.analyzeImage(
        imageFile: file,
        scanType: 'pantry',
      );

      if (!mounted) return;

      if (res['success'] == true) {
        fireAndForget(MetricsService.instance.recordWorkflowStep('SnapPantry', 'Suggest'));
        Navigator.push(
          context,
          AppMotion.createRoute(
            PantryAiSuggestionsScreen(
              scanId: res['scan_id'],
              items: (res['ingredients'] as List?) ?? const [],
            ),
          ),
        );
      } else {
        final code = res['error_code']?.toString();
        final msg = res['error']?.toString() ?? 'Scan failed';

        if (code == 'image_quality') {
          // High-ROI capture gating: prompt retake instead of wasting user effort.
          fireAndForget(MetricsService.instance.recordEvent('pantry_scan_retake'));
        }

        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(msg)),
        );
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Scan failed: $e')),
      );
    } finally {
      if (!mounted) return;
      setState(() => _processing = false);

      // Resume hint stream so the user gets live guidance for the retake.
      _startHintStream();
    }
  }

  @override
  Widget build(BuildContext context) {
    if (kDebugMode || kProfileMode) {
      SavoUiGuards.warnIfMultiplePrimaryActions(
        screen: 'PantryCameraScreen',
        surface: 'Capture',
        primaryActions: 1,
      );
    }

    final controller = _controller;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Scan pantry shelf'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          children: [
            Expanded(
              child: ClipRRect(
                borderRadius: BorderRadius.circular(AppRadius.lg),
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    if (_initializing)
                      const Center(child: CircularProgressIndicator())
                    else if (controller == null || !controller.value.isInitialized)
                      Center(
                        child: Text(
                          'Camera unavailable',
                          style: Theme.of(context).textTheme.bodyLarge,
                        ),
                      )
                    else
                      CameraPreview(controller),

                    // Shelf grid overlay
                    const _ShelfGridOverlay(),

                    // Status hints
                    Positioned(
                      left: AppSpacing.md,
                      right: AppSpacing.md,
                      top: AppSpacing.md,
                      child: _StatusHints(
                        lighting: _lightingHint,
                        density: _densityHint,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: (_processing || _initializing || controller == null)
                    ? null
                    : _captureAndAnalyze,
                icon: const Icon(Icons.camera_alt),
                label: Text(_processing ? 'Capturing…' : 'Capture'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _StatusHints extends StatelessWidget {
  final String lighting;
  final String density;

  const _StatusHints({
    required this.lighting,
    required this.density,
  });

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Container(
      decoration: BoxDecoration(
        color: cs.surface.withOpacity(0.85),
        borderRadius: BorderRadius.circular(AppRadius.md),
      ),
      padding: const EdgeInsets.all(AppSpacing.sm),
      child: Row(
        children: [
          Expanded(
            child: Row(
              children: [
                Icon(Icons.wb_sunny_outlined, color: cs.onSurfaceVariant),
                const SizedBox(width: AppSpacing.xs),
                Text(
                  lighting,
                  style: Theme.of(context).textTheme.labelLarge,
                ),
              ],
            ),
          ),
          Expanded(
            child: Row(
              children: [
                Icon(Icons.grid_view, color: cs.onSurfaceVariant),
                const SizedBox(width: AppSpacing.xs),
                Text(
                  density,
                  style: Theme.of(context).textTheme.labelLarge,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ShelfGridOverlay extends StatelessWidget {
  const _ShelfGridOverlay();

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: CustomPaint(
        painter: _ShelfGridPainter(
          color: Theme.of(context).colorScheme.onSurface.withOpacity(0.20),
        ),
      ),
    );
  }
}

class _ShelfGridPainter extends CustomPainter {
  final Color color;

  _ShelfGridPainter({required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 1;

    // Simple shelf-like grid: 3 rows x 2 cols.
    final cols = 2;
    final rows = 3;

    for (var c = 1; c < cols; c++) {
      final x = size.width * (c / cols);
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), paint);
    }

    for (var r = 1; r < rows; r++) {
      final y = size.height * (r / rows);
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }
  }

  @override
  bool shouldRepaint(covariant _ShelfGridPainter oldDelegate) {
    return oldDelegate.color != color;
  }
}
