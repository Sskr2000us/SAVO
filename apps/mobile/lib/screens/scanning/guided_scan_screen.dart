import 'dart:async';
import 'dart:io';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../services/api_client.dart';
import '../../utils/scan_quality.dart';

class GuidedScanResult {
  final Map<String, dynamic> response;

  const GuidedScanResult(this.response);
}

/// Guided scan: capture multiple still frames over ~10–20s.
///
/// Goal: better coverage for packaged + loose goods without typing.
class GuidedScanScreen extends StatefulWidget {
  final String scanType;
  final String? locationHint;
  final String? barcode;
  final String? barcodeNameHint;
  final double? barcodeQuantityHint;
  final String? barcodeUnitHint;

  const GuidedScanScreen({
    super.key,
    this.scanType = 'pantry',
    this.locationHint,
    this.barcode,
    this.barcodeNameHint,
    this.barcodeQuantityHint,
    this.barcodeUnitHint,
  });

  @override
  State<GuidedScanScreen> createState() => _GuidedScanScreenState();
}

class _GuidedScanScreenState extends State<GuidedScanScreen> {
  CameraController? _controller;
  List<CameraDescription>? _cameras;

  bool _initializing = true;
  bool _scanning = false;
  bool _uploading = false;

  final int _secondsTotal = 20; // within 10–20s (target ~20s)
  int _secondsLeft = 20;

  int _captureCount = 0;
  final List<XFile> _captures = [];

  Timer? _tick;

  String _cue = 'Move camera left';
  String? _qualityHint;

  final List<String> _cues = const [
    'Move camera left',
    'Hold steady',
    'Move camera right',
    'Tilt down to lower shelf',
    'Tilt up to upper shelf',
  ];

  @override
  void initState() {
    super.initState();
    _initCamera();
  }

  Future<void> _initCamera() async {
    try {
      _cameras = await availableCameras();
      if (_cameras == null || _cameras!.isEmpty) {
        throw Exception('No cameras available');
      }

      _controller = CameraController(
        _cameras!.first,
        ResolutionPreset.medium,
        enableAudio: false,
      );

      await _controller!.initialize();

      if (!mounted) return;
      setState(() {
        _initializing = false;
      });
    } catch (e) {
      if (!mounted) return;
      _showError('Failed to initialize camera: $e');
      setState(() => _initializing = false);
    }
  }

  @override
  void dispose() {
    _tick?.cancel();
    _controller?.dispose();
    super.dispose();
  }

  void _showError(String message) {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Error'),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  Future<void> _startScan() async {
    if (_controller == null || !_controller!.value.isInitialized) return;
    if (_scanning || _uploading) return;

    setState(() {
      _scanning = true;
      _uploading = false;
      _secondsLeft = _secondsTotal;
      _captureCount = 0;
      _captures.clear();
      _qualityHint = null;
      _cue = _cues.first;
    });

    // Capture frames at a bounded cadence.
    // 12s total with ~1.5s spacing => 8 frames (fast enough for <=30s overall).
    final int targetFrames = 8;
    final int intervalMs = (_secondsTotal * 1000 ~/ targetFrames).clamp(900, 2000);

    int cueIdx = 0;

    Future<void> captureOnce() async {
      if (!mounted) return;
      if (!_scanning) return;

      try {
        final x = await _controller!.takePicture();
        _captures.add(x);
        _captureCount = _captures.length;

        // Quick quality hint from the most recent frame.
        try {
          final bytes = await File(x.path).readAsBytes();
          final q = ScanQuality.assessJpegOrPng(bytes);
          if (q.tooDark) {
            _qualityHint = 'Too dark — turn on lights';
          } else if (q.tooBright) {
            _qualityHint = 'Glare — adjust angle';
          } else if (q.tooBlurry) {
            _qualityHint = 'Too blurry — hold steady';
          } else {
            _qualityHint = null;
          }
        } catch (_) {
          // Ignore; guidance is best-effort.
        }

        if (mounted) setState(() {});
      } catch (_) {
        // If a capture fails, keep going.
      }
    }

    // Kick off captures on a timer.
    final captureTimer = Timer.periodic(Duration(milliseconds: intervalMs), (_) {
      captureOnce();
    });

    _tick = Timer.periodic(const Duration(seconds: 1), (t) {
      if (!_scanning) {
        t.cancel();
        return;
      }
      final next = _secondsLeft - 1;
      cueIdx = (cueIdx + 1) % _cues.length;
      setState(() {
        _secondsLeft = next;
        _cue = _cues[cueIdx];
      });
      if (next <= 0) {
        t.cancel();
      }
    });

    // Stop after allotted time.
    await Future.delayed(Duration(seconds: _secondsTotal));
    captureTimer.cancel();

    if (!mounted) return;

    setState(() {
      _scanning = false;
      _uploading = true;
    });

    await _uploadFramesAndReturn();
  }

  Future<void> _uploadFramesAndReturn() async {
    try {
      if (_captures.isEmpty) {
        throw Exception('No frames captured. Please try again.');
      }

      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final response = await apiClient.postMultipartMany(
        '/api/scanning/analyze-frames',
        files: _captures,
        fieldName: 'images',
        fields: {
          'scan_type': widget.scanType,
          if (widget.locationHint != null && widget.locationHint!.trim().isNotEmpty)
            'location_hint': widget.locationHint!.trim(),
          if (widget.barcode != null && widget.barcode!.trim().isNotEmpty)
            'barcode': widget.barcode!.trim(),
          if (widget.barcodeNameHint != null && widget.barcodeNameHint!.trim().isNotEmpty)
            'barcode_name_hint': widget.barcodeNameHint!.trim(),
          if (widget.barcodeQuantityHint != null && widget.barcodeQuantityHint! > 0)
            'barcode_quantity_hint': widget.barcodeQuantityHint!.toString(),
          if (widget.barcodeUnitHint != null && widget.barcodeUnitHint!.trim().isNotEmpty)
            'barcode_unit_hint': widget.barcodeUnitHint!.trim(),
        },
        timeoutSeconds: 30,
      );

      if (!mounted) return;
      Navigator.pop(context, GuidedScanResult(response));
    } catch (e) {
      if (!mounted) return;

      // Surface quality guidance if the backend returns structured quality errors.
      final msg = e.toString();
      if (msg.toLowerCase().contains('too dark') || msg.toLowerCase().contains('too blurry') || msg.toLowerCase().contains('glare')) {
        setState(() {
          _qualityHint = msg.replaceFirst('Exception: ', '');
        });
      } else {
        _showError(msg);
      }

      setState(() {
        _uploading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final controller = _controller;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Guided Scan'),
      ),
      body: _initializing
          ? const Center(child: CircularProgressIndicator())
          : (controller == null || !controller.value.isInitialized)
              ? Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Text('Camera not available'),
                      const SizedBox(height: 12),
                      FilledButton(
                        onPressed: () => Navigator.pop(context),
                        child: const Text('Back'),
                      ),
                    ],
                  ),
                )
              : Stack(
                  children: [
                    Positioned.fill(child: CameraPreview(controller)),
                    Positioned(
                      left: 16,
                      right: 16,
                      top: 16,
                      child: _TopOverlay(
                        secondsLeft: _scanning ? _secondsLeft : null,
                        cue: _cue,
                        qualityHint: _qualityHint,
                        captureCount: _captureCount,
                      ),
                    ),
                    Positioned(
                      left: 16,
                      right: 16,
                      bottom: 24,
                      child: _BottomControls(
                        scanning: _scanning,
                        uploading: _uploading,
                        onStart: _startScan,
                        onCancel: () => Navigator.pop(context),
                      ),
                    ),
                  ],
                ),
    );
  }
}

class _TopOverlay extends StatelessWidget {
  final int? secondsLeft;
  final String cue;
  final String? qualityHint;
  final int captureCount;

  const _TopOverlay({
    required this.secondsLeft,
    required this.cue,
    required this.qualityHint,
    required this.captureCount,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      color: Colors.black.withOpacity(0.55),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    secondsLeft != null ? 'Scanning… ${secondsLeft}s' : 'Scan for 10–20 seconds',
                    style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                  ),
                ),
                Text(
                  'Frames: $captureCount',
                  style: const TextStyle(color: Colors.white),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              cue,
              style: const TextStyle(color: Colors.white, fontSize: 14),
            ),
            if (qualityHint != null && qualityHint!.trim().isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                qualityHint!,
                style: const TextStyle(color: Colors.amber, fontSize: 13, fontWeight: FontWeight.w600),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _BottomControls extends StatelessWidget {
  final bool scanning;
  final bool uploading;
  final VoidCallback onStart;
  final VoidCallback onCancel;

  const _BottomControls({
    required this.scanning,
    required this.uploading,
    required this.onStart,
    required this.onCancel,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: OutlinedButton(
            onPressed: (scanning || uploading) ? null : onCancel,
            child: const Text('Cancel'),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: FilledButton(
            onPressed: (scanning || uploading) ? null : onStart,
            child: Text(uploading ? 'Uploading…' : (scanning ? 'Scanning…' : 'Start Scan')),
          ),
        ),
      ],
    );
  }
}
