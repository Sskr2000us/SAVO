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
  bool _showOnboarding = true;  // Show tutorial banner
  String _currentStep = 'centering';  // centering, analyzing, confirming
  String _detectedItem = '';
  String _estimatedQuantity = '';
  
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
      _currentStep = 'analyzing';
      _detectedItem = '';
      _estimatedQuantity = '';
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

          // Update UI with detected item and quantity
          setState(() {
            _detectedItem = ingredient['detected_name'] ?? '';
            final qty = ingredient['quantity'];
            final unit = ingredient['unit'] ?? '';
            _estimatedQuantity = qty != null ? '$qty $unit' : '';
            _currentStep = 'confirming';
          });

          if (autoSaved) {
            // High confidence - just show success and continue
            _onIngredientConfirmed(ingredient);
            _showSuccessSnackbar('${ingredient['detected_name']} ($_estimatedQuantity) added!');
            
            // Dismiss onboarding after first success
            if (_showOnboarding) {
              setState(() {
                _showOnboarding = false;
              });
            }
            
            // Reset to centering state
            Future.delayed(const Duration(seconds: 1), () {
              if (mounted) {
                setState(() {
                  _currentStep = 'centering';
                  _detectedItem = '';
                  _estimatedQuantity = '';
                });
              }
            });
          } else {
            // Show confirmation modal
            _showQuickConfirmation(ingredient);
          }
        } else {
          setState(() {
            _currentStep = 'centering';
          });
          _showError(result['error'] ?? 'Analysis failed');
        }
      }
    } catch (e) {
      debugPrint('Capture error: $e');
      setState(() {
        _currentStep = 'centering';
      });
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
          
          final qty = confirmedData['quantity'];
          final unit = confirmedData['unit'] ?? '';
          final qtyStr = qty != null ? ' ($qty $unit)' : '';
          _showSuccessSnackbar('${confirmedData['name']}$qtyStr added!');
          
          // Dismiss onboarding after first success
          if (_showOnboarding) {
            setState(() {
              _showOnboarding = false;
            });
          }
          
          // Reset to centering state
          setState(() {
            _currentStep = 'centering';
            _detectedItem = '';
            _estimatedQuantity = '';
          });
          
          // Resume auto-capture
          if (_autoCapture && mounted) {
            _startFocusDetection();
          }
        },
        onReject: () {
          Navigator.pop(context);
          _showError('Item rejected');
          
          // Reset to centering state
          setState(() {
            _currentStep = 'centering';
            _detectedItem = '';
            _estimatedQuantity = '';
          });
          
          // Resume auto-capture
          if (_autoCapture && mounted) {
            _startFocusDetection();
          }
        },
      ),
    );
  }

  Future<void> _onIngredientConfirmed(Map<String, dynamic> ingredient) async {
    if (mounted) {
      setState(() {
        _scannedItems.add(ingredient);
      });
    }

    // Persist immediately so "Confirm" actually saves to pantry.
    // Best-effort: keep UX snappy and show a message only on failure.
    try {
      final name = (ingredient['canonical_name'] ?? ingredient['name'] ?? '').toString().trim();
      if (name.isEmpty) return;

      final quantityRaw = ingredient['quantity'];
      final quantity = (quantityRaw is num) ? quantityRaw.toDouble() : double.tryParse(quantityRaw?.toString() ?? '') ?? 1.0;
      final unit = (ingredient['unit'] ?? 'pieces').toString().trim();

      final res = await _scanningService.confirmSingleIngredient(
        ingredientName: name,
        quantity: quantity <= 0 ? 1.0 : quantity,
        unit: unit.isEmpty ? 'pieces' : unit,
        scanType: _scanType,
      );

      if (!mounted) return;
      if (res['success'] != true) {
        final msg = res['error']?.toString() ?? 'Could not save item to pantry.';
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(msg)),
        );
      }
    } catch (_) {
      // Best-effort only.
    }
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

  Color _getStatusColor() {
    switch (_currentStep) {
      case 'centering':
        return const Color(0xFF4CAF50);  // Green
      case 'analyzing':
        return const Color(0xFFFF9800);  // Orange
      case 'confirming':
        return const Color(0xFF2196F3);  // Blue
      default:
        return Colors.grey;
    }
  }

  IconData _getStatusIcon() {
    switch (_currentStep) {
      case 'centering':
        return Icons.center_focus_strong;
      case 'analyzing':
        return Icons.search;
      case 'confirming':
        return Icons.check_circle_outline;
      default:
        return Icons.camera_alt;
    }
  }

  String _getStatusText() {
    switch (_currentStep) {
      case 'centering':
        return _autoCapture 
            ? 'Center item in frame (auto-capture in 3s)'
            : 'Center item & tap Capture';
      case 'analyzing':
        return 'Analyzing item...';
      case 'confirming':
        return _detectedItem.isNotEmpty
            ? '$_detectedItem${_estimatedQuantity.isNotEmpty ? " • $_estimatedQuantity" : ""}'
            : 'Processing...';
      default:
        return 'Ready to scan';
    }
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
                // Onboarding banner
                if (_showOnboarding)
                  Container(
                    color: const Color(0xFF2196F3),
                    padding: const EdgeInsets.all(12),
                    child: Row(
                      children: [
                        const Icon(Icons.info_outline, color: Colors.white, size: 24),
                        const SizedBox(width: 12),
                        const Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'How to scan:',
                                style: TextStyle(
                                  color: Colors.white,
                                  fontSize: 14,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              SizedBox(height: 4),
                              Text(
                                '1. Center item in frame\n2. Wait 3 sec (auto) or tap Capture\n3. Confirm quantity & save',
                                style: TextStyle(
                                  color: Colors.white,
                                  fontSize: 12,
                                ),
                              ),
                            ],
                          ),
                        ),
                        IconButton(
                          icon: const Icon(Icons.close, color: Colors.white, size: 20),
                          onPressed: () {
                            setState(() {
                              _showOnboarding = false;
                            });
                          },
                        ),
                      ],
                    ),
                  ),
                
                // Status bar showing current step
                Container(
                  color: _getStatusColor(),
                  padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(_getStatusIcon(), color: Colors.white, size: 20),
                      const SizedBox(width: 8),
                      Text(
                        _getStatusText(),
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 14,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
                
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
                      
                      // Crosshair guide with dynamic feedback
                      Center(
                        child: Container(
                          width: 220,
                          height: 220,
                          decoration: BoxDecoration(
                            border: Border.all(
                              color: _getStatusColor(),
                              width: 3,
                            ),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(
                                _getStatusIcon(),
                                color: _getStatusColor(),
                                size: 56,
                              ),
                              const SizedBox(height: 12),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                                decoration: BoxDecoration(
                                  color: Colors.black87,
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: Text(
                                  _currentStep == 'centering' 
                                      ? 'Center item here'
                                      : _currentStep == 'analyzing'
                                          ? 'Analyzing...'
                                          : _detectedItem.isNotEmpty
                                              ? _detectedItem
                                              : 'Processing',
                                  style: const TextStyle(
                                    color: Colors.white,
                                    fontSize: 16,
                                    fontWeight: FontWeight.w500,
                                  ),
                                  textAlign: TextAlign.center,
                                ),
                              ),
                              if (_estimatedQuantity.isNotEmpty && _currentStep == 'confirming')
                                Padding(
                                  padding: const EdgeInsets.only(top: 8),
                                  child: Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                                    decoration: BoxDecoration(
                                      color: Colors.green[700],
                                      borderRadius: BorderRadius.circular(6),
                                    ),
                                    child: Text(
                                      _estimatedQuantity,
                                      style: const TextStyle(
                                        color: Colors.white,
                                        fontSize: 14,
                                        fontWeight: FontWeight.bold,
                                      ),
                                    ),
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
