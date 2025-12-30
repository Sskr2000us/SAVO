import 'dart:async';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:provider/provider.dart';
import '../services/api_client.dart';

/// Real-time ingredient scanning with bounding boxes
/// 
/// NOTE: This is a simplified implementation for demonstration.
/// For production, you would:
/// 1. Add TFLite object detection model (e.g., COCO-SSD or custom trained model)
/// 2. Process camera frames in isolate for performance
/// 3. Add proper object tracking to reduce flicker
/// 4. Optimize detection frequency (e.g., every 5 frames)
class RealtimeScanScreen extends StatefulWidget {
  const RealtimeScanScreen({super.key});

  @override
  State<RealtimeScanScreen> createState() => _RealtimeScanScreenState();
}

class _RealtimeScanScreenState extends State<RealtimeScanScreen> {
  CameraController? _cameraController;
  List<DetectedObject> _detectedObjects = [];
  bool _isDetecting = false;
  bool _isInitialized = false;
  Timer? _detectionTimer;
  final Set<String> _confirmedIngredients = {};

  @override
  void initState() {
    super.initState();
    if (!kIsWeb) {
      _initializeCamera();
    }
  }

  @override
  void dispose() {
    _detectionTimer?.cancel();
    _cameraController?.dispose();
    super.dispose();
  }

  Future<void> _initializeCamera() async {
    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) {
        return;
      }

      _cameraController = CameraController(
        cameras.first,
        ResolutionPreset.medium,
        enableAudio: false,
      );

      await _cameraController!.initialize();
      
      if (!mounted) return;

      setState(() {
        _isInitialized = true;
      });

      // Start periodic detection (every 2 seconds to reduce load)
      _detectionTimer = Timer.periodic(const Duration(seconds: 2), (_) {
        if (!_isDetecting) {
          _detectObjects();
        }
      });
    } catch (e) {
      debugPrint('Camera initialization error: $e');
    }
  }

  Future<void> _detectObjects() async {
    if (_cameraController == null || !_cameraController!.value.isInitialized) {
      return;
    }

    setState(() {
      _isDetecting = true;
    });

    try {
      // Take a snapshot
      final image = await _cameraController!.takePicture();
      
      // Send to backend for detection
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final response = await apiClient.postMultipart(
        '/inventory/scan',
        file: image,
        fields: const {},
      );

      if (!mounted) return;

      final status = response['status'];
      if (status == 'ok') {
        final items = response['scanned_items'] as List?;
        if (items != null) {
          setState(() {
            _detectedObjects = items.map((item) {
              return DetectedObject(
                label: item['ingredient'] ?? '',
                confidence: (item['confidence'] ?? 0.0).toDouble(),
                // Generate random bounding box for demo
                // In production, backend would return actual bounding boxes
                boundingBox: BoundingBox(
                  left: 0.1 + (item['ingredient'].hashCode % 50) / 100,
                  top: 0.2 + (item['ingredient'].hashCode % 40) / 100,
                  width: 0.3,
                  height: 0.2,
                ),
              );
            }).toList();
          });
        }
      }
    } catch (e) {
      debugPrint('Detection error: $e');
    } finally {
      setState(() {
        _isDetecting = false;
      });
    }
  }

  void _toggleIngredient(String ingredient) {
    setState(() {
      if (_confirmedIngredients.contains(ingredient)) {
        _confirmedIngredients.remove(ingredient);
      } else {
        _confirmedIngredients.add(ingredient);
      }
    });
  }

  Future<void> _finishScanning() async {
    if (_confirmedIngredients.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select at least one ingredient')),
      );
      return;
    }

    // Return confirmed ingredients to previous screen
    Navigator.pop(context, _confirmedIngredients.toList());
  }

  @override
  Widget build(BuildContext context) {
    if (kIsWeb) {
      return Scaffold(
        appBar: AppBar(title: const Text('Real-time Scan')),
        body: const Center(
          child: Padding(
            padding: EdgeInsets.all(24.0),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.camera_alt, size: 64, color: Colors.grey),
                SizedBox(height: 16),
                Text(
                  'Real-time camera scanning is not available on web.',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 16),
                ),
                SizedBox(height: 8),
                Text(
                  'Please use the regular photo upload option instead.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Colors.grey),
                ),
              ],
            ),
          ),
        ),
      );
    }

    if (!_isInitialized || _cameraController == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Real-time Scan')),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Real-time Scan'),
        actions: [
          if (_isDetecting)
            const Padding(
              padding: EdgeInsets.all(16.0),
              child: SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: Colors.white,
                ),
              ),
            ),
        ],
      ),
      body: Stack(
        children: [
          // Camera preview
          SizedBox.expand(
            child: CameraPreview(_cameraController!),
          ),

          // Bounding boxes overlay
          CustomPaint(
            size: Size.infinite,
            painter: BoundingBoxPainter(_detectedObjects),
          ),

          // Detection instructions
          Positioned(
            top: 16,
            left: 16,
            right: 16,
            child: Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.black.withOpacity(0.7),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Row(
                children: [
                  Icon(Icons.info_outline, color: Colors.white, size: 20),
                  SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Point camera at ingredients. Tap detected items to select.',
                      style: TextStyle(color: Colors.white, fontSize: 13),
                    ),
                  ),
                ],
              ),
            ),
          ),

          // Detected ingredients chips
          Positioned(
            bottom: 120,
            left: 16,
            right: 16,
            child: Wrap(
              spacing: 8,
              runSpacing: 8,
              children: _detectedObjects.map((obj) {
                final isConfirmed = _confirmedIngredients.contains(obj.label);
                final confidence = (obj.confidence * 100).round();
                
                return FilterChip(
                  selected: isConfirmed,
                  label: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(obj.label),
                      const SizedBox(width: 4),
                      Text(
                        '$confidence%',
                        style: const TextStyle(fontSize: 11),
                      ),
                    ],
                  ),
                  onSelected: (_) => _toggleIngredient(obj.label),
                  backgroundColor: Colors.black.withOpacity(0.6),
                  selectedColor: Colors.green.withOpacity(0.8),
                  labelStyle: TextStyle(
                    color: isConfirmed ? Colors.white : Colors.white70,
                  ),
                  checkmarkColor: Colors.white,
                );
              }).toList(),
            ),
          ),

          // Bottom action buttons
          Positioned(
            bottom: 16,
            left: 16,
            right: 16,
            child: Row(
              children: [
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: () => Navigator.pop(context),
                    icon: const Icon(Icons.close),
                    label: const Text('Cancel'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.red,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.all(16),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  flex: 2,
                  child: ElevatedButton.icon(
                    onPressed: _confirmedIngredients.isEmpty ? null : _finishScanning,
                    icon: const Icon(Icons.check),
                    label: Text('Add ${_confirmedIngredients.length} Items'),
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.all(16),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class DetectedObject {
  final String label;
  final double confidence;
  final BoundingBox boundingBox;

  DetectedObject({
    required this.label,
    required this.confidence,
    required this.boundingBox,
  });
}

class BoundingBox {
  final double left;
  final double top;
  final double width;
  final double height;

  BoundingBox({
    required this.left,
    required this.top,
    required this.width,
    required this.height,
  });
}

class BoundingBoxPainter extends CustomPainter {
  final List<DetectedObject> detections;

  BoundingBoxPainter(this.detections);

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3;

    final textPainter = TextPainter(
      textDirection: TextDirection.ltr,
    );

    for (final detection in detections) {
      // Determine color based on confidence
      final confidence = detection.confidence;
      Color color;
      if (confidence >= 0.75) {
        color = Colors.green;
      } else if (confidence >= 0.5) {
        color = Colors.orange;
      } else {
        color = Colors.red;
      }

      paint.color = color;

      // Draw bounding box
      final box = detection.boundingBox;
      final rect = Rect.fromLTWH(
        box.left * size.width,
        box.top * size.height,
        box.width * size.width,
        box.height * size.height,
      );
      canvas.drawRect(rect, paint);

      // Draw label background
      final labelText = '${detection.label} ${(confidence * 100).round()}%';
      textPainter.text = TextSpan(
        text: labelText,
        style: const TextStyle(
          color: Colors.white,
          fontSize: 14,
          fontWeight: FontWeight.bold,
        ),
      );
      textPainter.layout();

      final labelRect = Rect.fromLTWH(
        rect.left,
        rect.top - 24,
        textPainter.width + 8,
        20,
      );

      canvas.drawRect(labelRect, Paint()..color = color);
      textPainter.paint(canvas, Offset(rect.left + 4, rect.top - 22));
    }
  }

  @override
  bool shouldRepaint(BoundingBoxPainter oldDelegate) {
    return oldDelegate.detections != detections;
  }
}
