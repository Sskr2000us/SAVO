import 'dart:async';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';

class VideoCaptureResult {
  final XFile video;
  final int durationSeconds;

  const VideoCaptureResult({
    required this.video,
    required this.durationSeconds,
  });
}

class VideoCaptureScreen extends StatefulWidget {
  const VideoCaptureScreen({
    super.key,
    this.initialDurationSeconds = 30,
  });

  final int initialDurationSeconds;

  @override
  State<VideoCaptureScreen> createState() => _VideoCaptureScreenState();
}

class _VideoCaptureScreenState extends State<VideoCaptureScreen> {
  CameraController? _controller;

  bool _initializing = true;
  bool _recording = false;
  bool _stopping = false;
  String? _error;

  int _durationSeconds = 30;
  DateTime? _recordingStartedAt;
  Timer? _tick;

  int get _elapsedSeconds {
    final started = _recordingStartedAt;
    if (!_recording || started == null) return 0;
    final d = DateTime.now().difference(started);
    return d.inSeconds.clamp(0, _durationSeconds);
  }

  int get _secondsLeft => (_durationSeconds - _elapsedSeconds).clamp(0, _durationSeconds);

  @override
  void initState() {
    super.initState();
    _durationSeconds = widget.initialDurationSeconds.clamp(20, 30);
    _initCamera();
  }

  Future<void> _initCamera() async {
    try {
      final cams = await availableCameras();
      if (cams.isEmpty) {
        throw Exception('No cameras available');
      }

      final back = cams.where((c) => c.lensDirection == CameraLensDirection.back).toList();
      final selected = back.isNotEmpty ? back.first : cams.first;

      final controller = CameraController(
        selected,
        ResolutionPreset.high,
        enableAudio: false,
      );
      await controller.initialize();
      if (!mounted) return;

      setState(() {
        _controller = controller;
        _initializing = false;
        _error = null;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _initializing = false;
        _error = 'Failed to initialize camera: $e';
      });
    }
  }

  @override
  void dispose() {
    _tick?.cancel();
    _controller?.dispose();
    super.dispose();
  }

  Future<void> _startRecording() async {
    final c = _controller;
    if (c == null || !c.value.isInitialized) return;
    if (_recording || _stopping) return;

    try {
      setState(() {
        _recording = true;
        _stopping = false;
        _recordingStartedAt = DateTime.now();
      });

      await c.startVideoRecording();

      _tick?.cancel();
      _tick = Timer.periodic(const Duration(milliseconds: 250), (_) {
        if (!mounted) return;
        if (!_recording) return;
        setState(() {});
        if (_secondsLeft <= 0) {
          unawaited(_stopRecording());
        }
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _recording = false;
        _recordingStartedAt = null;
      });
      _showError('Failed to start recording: $e');
    }
  }

  Future<void> _stopRecording() async {
    final c = _controller;
    if (c == null || !c.value.isInitialized) return;
    if (!_recording || _stopping) return;

    _tick?.cancel();

    setState(() {
      _stopping = true;
    });

    try {
      final file = await c.stopVideoRecording();
      if (!mounted) return;
      Navigator.pop(
        context,
        VideoCaptureResult(video: file, durationSeconds: _durationSeconds),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _recording = false;
        _stopping = false;
        _recordingStartedAt = null;
      });
      _showError('Failed to stop recording: $e');
    }
  }

  void _showError(String message) {
    showDialog<void>(
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

  Widget _durationToggle(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    Widget chip(int seconds) {
      final selected = _durationSeconds == seconds;
      return OutlinedButton(
        onPressed: (_recording || _stopping)
            ? null
            : () => setState(() => _durationSeconds = seconds),
        style: OutlinedButton.styleFrom(
          foregroundColor: selected ? cs.onPrimary : cs.onSurface,
          backgroundColor: selected ? cs.primary : null,
        ),
        child: Text('${seconds}s'),
      );
    }

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        chip(20),
        const SizedBox(width: 8),
        chip(30),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    if (_initializing) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }

    if (_error != null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Video scan')),
        body: Center(child: Text(_error!)),
      );
    }

    final c = _controller;
    if (c == null || !c.value.isInitialized) {
      return const Scaffold(
        body: Center(child: Text('Camera not available')),
      );
    }

    final progress = _durationSeconds == 0 ? 0.0 : (_elapsedSeconds / _durationSeconds).clamp(0.0, 1.0);

    return Scaffold(
      body: SafeArea(
        child: Stack(
          fit: StackFit.expand,
          children: [
            CameraPreview(c),
            Align(
              alignment: Alignment.topCenter,
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Row(
                  children: [
                    IconButton(
                      onPressed: (_recording || _stopping) ? null : () => Navigator.pop(context),
                      icon: const Icon(Icons.close),
                      color: cs.onSurface,
                    ),
                    const Spacer(),
                    _durationToggle(context),
                  ],
                ),
              ),
            ),
            Align(
              alignment: Alignment.topCenter,
              child: Padding(
                padding: const EdgeInsets.only(top: 68, left: 16, right: 16),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                      decoration: BoxDecoration(
                        color: cs.surface.withValues(alpha: 0.85),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        _recording
                            ? 'Recording: ${_elapsedSeconds}s / ${_durationSeconds}s'
                            : 'Ready: ${_durationSeconds}s video',
                        style: Theme.of(context).textTheme.bodyMedium,
                      ),
                    ),
                    const SizedBox(height: 10),
                    if (_recording)
                      LinearProgressIndicator(
                        value: progress,
                        backgroundColor: cs.surface.withValues(alpha: 0.6),
                        valueColor: AlwaysStoppedAnimation<Color>(cs.primary),
                      ),
                    if (_recording)
                      Padding(
                        padding: const EdgeInsets.only(top: 6),
                        child: Text(
                          '${_secondsLeft}s left',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ),
                  ],
                ),
              ),
            ),
            Align(
              alignment: Alignment.bottomCenter,
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    SizedBox(
                      width: 74,
                      height: 74,
                      child: FloatingActionButton(
                        onPressed: _stopping
                            ? null
                            : () => _recording ? _stopRecording() : _startRecording(),
                        backgroundColor: cs.primary,
                        foregroundColor: cs.onPrimary,
                        child: _stopping
                            ? const SizedBox(
                                width: 26,
                                height: 26,
                                child: CircularProgressIndicator(strokeWidth: 3),
                              )
                            : Icon(_recording ? Icons.stop : Icons.videocam),
                      ),
                    ),
                    const SizedBox(height: 10),
                    Text(
                      _recording ? 'Tap to stop early' : 'Tap to start',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
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
