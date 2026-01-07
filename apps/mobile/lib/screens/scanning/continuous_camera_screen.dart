import 'dart:async';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import '../../services/scanning_service.dart';
import '../../widgets/quick_confirmation_card.dart';

/// Continuous single-item scanning screen (optimized UX)
class ContinuousCameraScanScreen extends StatefulWidget {
  const ContinuousCameraScanScreen({Key? key}) : super(key: key);

  @override
  _ContinuousCameraScanScreenState createState() => _ContinuousCameraScanScreenState();
}

class _ContinuousCameraScanScreenState extends State<ContinuousCameraScanScreen> {
  CameraController? _cameraController;
  List<CameraDescription>? _cameras;
  bool _isInitialized = false;
  bool _isProcessing = false;
  bool _autoCapture = true;
  Timer? _focusCheckTimer;
  List<Map<String, dynamic>> _scannedItems = [];
  String _scanType = 'pantry';
  
  final ScanningService _scanningService = ScanningService();

  @override
  void initState() {
    super.initState();
    _initializeCamera();
  }

  @override
  void dispose() {
    _focusCheckTimer?.cancel();
    _cameraController?.dispose();
    super.dispose();
  }

  Future<void> _initializeCamera() async {
    try {
      _cameras = await availableCameras();
      if (_cameras!.isNotEmpty) {
        _cameraController = CameraController(
          _cameras![0],
          ResolutionPreset.medium,  // Medium for speed
          enableAudio: false,
        );

        await _cameraController!.initialize();
        
        setState(() {
          _isInitialized = true;
        });

        // Start auto-capture if enabled
        if (_autoCapture) {
          _startFocusDetection();
        }
      }
    } catch (e) {
      debugPrint('Camera initialization error: $e');
      _showError('Failed to initialize camera: $e');
    }
  }

  void _startFocusDetection() {
    _focusCheckTimer = Timer.periodic(const Duration(seconds: 3), (timer) async {
      if (_isInFocus() && !_isProcessing && mounted) {
        await _autoCaptureSingleItem();
      }
    });
  }

  void _stopFocusDetection() {
    _focusCheckTimer?.cancel();
    _focusCheckTimer = null;
  }

  bool _isInFocus() {
    if (_cameraController == null || !_cameraController!.value.isInitialized) {
      return false;
    }
    
    // Check if camera is focused (not moving)
    // This is a simplified check - in production you'd check actual focus lock
    return !_isProcessing;
  }

  Future<void> _autoCaptureSingleItem() async {
    await _captureSingleItem();
  }

  Future<void> _captureSingleItem() async {
    if (_cameraController == null || !_cameraController!.value.isInitialized || _isProcessing) {
      return;
    }

    setState(() {
      _isProcessing = true;
    });

    try {
      // Capture image
      final XFile image = await _cameraController!.takePicture();
      final File imageFile = File(image.path);

      // Analyze with backend
      final result = await _scanningService.scanSingleItem(
        imageFile: imageFile,
        scanType: _scanType,
      );

      if (mounted) {
        if (result['success'] == true) {
          final ingredient = result['ingredient'];
          final autoSaved = result['auto_saved'] ?? false;

          if (autoSaved) {
            // High confidence - just show success and continue
            _onIngredientConfirmed(ingredient);
            _showSuccessSnackbar('${ingredient['detected_name']} added!');
          } else {
            // Show confirmation modal
            _showQuickConfirmation(ingredient);
          }
        } else {
          _showError(result['error'] ?? 'Analysis failed');
        }
      }
    } catch (e) {
      debugPrint('Capture error: $e');
      _showError('Failed to scan item: $e');
    } finally {
      if (mounted) {
        setState(() {
          _isProcessing = false;
        });
      }
    }
  }

  void _showQuickConfirmation(Map<String, dynamic> ingredient) {
    // Pause auto-capture while confirming
    if (_autoCapture) {
      _stopFocusDetection();
    }

    showModalBottomSheet(
      context: context,
      isDismissible: false,
      enableDrag: false,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => QuickConfirmationCard(
        ingredient: ingredient,
        onConfirm: (confirmedData) {
          Navigator.pop(context);
          _onIngredientConfirmed(confirmedData);
          _showSuccessSnackbar('${confirmedData['name']} added!');
          
          // Resume auto-capture
          if (_autoCapture && mounted) {
            _startFocusDetection();
          }
        },
        onReject: () {
          Navigator.pop(context);
          _showError('Item rejected');
          
          // Resume auto-capture
          if (_autoCapture && mounted) {
            _startFocusDetection();
          }
        },
      ),
    );
  }

  Future<void> _onIngredientConfirmed(Map<String, dynamic> ingredient) async {
    setState(() {
      _scannedItems.add(ingredient);
    });
  }

  void _finishScanning() {
    Navigator.pop(context, _scannedItems);
  }

  void _showSuccessSnackbar(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: Colors.green,
        duration: const Duration(seconds: 2),
      ),
    );
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: Colors.red,
        duration: const Duration(seconds: 3),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Scan Items'),
        backgroundColor: const Color(0xFF4CAF50),
        actions: [
          TextButton(
            onPressed: _finishScanning,
            child: const Text(
              'Done',
              style: TextStyle(color: Colors.white, fontSize: 16),
            ),
          ),
        ],
      ),
      body: !_isInitialized
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                // Camera preview
                Expanded(
                  child: Stack(
                    children: [
                      // Camera
                      Container(
                        decoration: BoxDecoration(
                          border: Border.all(color: Colors.grey),
                        ),
                        child: CameraPreview(_cameraController!),
                      ),
                      
                      // Crosshair guide
                      Center(
                        child: Container(
                          width: 200,
                          height: 200,
                          decoration: BoxDecoration(
                            border: Border.all(
                              color: _isProcessing ? Colors.orange : Colors.white,
                              width: 2,
                            ),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(
                                _isProcessing ? Icons.hourglass_empty : Icons.center_focus_strong,
                                color: Colors.white,
                                size: 48,
                              ),
                              const SizedBox(height: 8),
                              Text(
                                _isProcessing ? 'Analyzing...' : 'Center item here',
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 14,
                                  backgroundColor: Colors.black54,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                      
                      // Processing overlay
                      if (_isProcessing)
                        Container(
                          color: Colors.black26,
                          child: const Center(
                            child: CircularProgressIndicator(),
                          ),
                        ),
                    ],
                  ),
                ),

                // Controls
                Container(
                  padding: const EdgeInsets.all(16),
                  color: Colors.white,
                  child: Column(
                    children: [
                      // Scan type selector
                      Wrap(
                        spacing: 8,
                        children: [
                          _buildScanTypeChip('Pantry', 'pantry'),
                          _buildScanTypeChip('Fridge', 'fridge'),
                          _buildScanTypeChip('Counter', 'counter'),
                        ],
                      ),
                      
                      const SizedBox(height: 12),
                      
                      // Auto-capture toggle & item count
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Row(
                            children: [
                              Switch(
                                value: _autoCapture,
                                activeColor: const Color(0xFF4CAF50),
                                onChanged: (value) {
                                  setState(() {
                                    _autoCapture = value;
                                  });
                                  if (value) {
                                    _startFocusDetection();
                                  } else {
                                    _stopFocusDetection();
                                  }
                                },
                              ),
                              const Text('Auto-capture'),
                            ],
                          ),
                          Text(
                            'Items: ${_scannedItems.length}',
                            style: const TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
                      
                      const SizedBox(height: 12),
                      
                      // Manual capture button
                      SizedBox(
                        width: double.infinity,
                        height: 50,
                        child: ElevatedButton.icon(
                          onPressed: _isProcessing ? null : _captureSingleItem,
                          icon: const Icon(Icons.camera_alt),
                          label: const Text('Capture Now'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFF4CAF50),
                            foregroundColor: Colors.white,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(8),
                            ),
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

  Widget _buildScanTypeChip(String label, String value) {
    final isSelected = _scanType == value;
    return ChoiceChip(
      label: Text(label),
      selected: isSelected,
      selectedColor: const Color(0xFF4CAF50),
      labelStyle: TextStyle(
        color: isSelected ? Colors.white : Colors.black,
      ),
      onSelected: (selected) {
        if (selected) {
          setState(() {
            _scanType = value;
          });
        }
      },
    );
  }
}
