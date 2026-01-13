import 'dart:async';
import 'dart:io';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import '../../services/scanning_service.dart';
import '../../services/barcode_lookup_service.dart';
import 'barcode_scan_screen.dart';
import '../../widgets/quick_confirmation_card.dart';

/// Continuous single-item scanning screen (optimized UX)
class ContinuousCameraScanScreen extends StatefulWidget {
  const ContinuousCameraScanScreen({Key? key}) : super(key: key);

  @override
  _ContinuousCameraScanScreenState createState() => _ContinuousCameraScanScreenState();
}

class _ContinuousCameraScanScreenState extends State<ContinuousCameraScanScreen> {
  static const String _prefsScanTypeKey = 'savo.scan.single_item.scan_type';
  static const String _prefsAutoCaptureKey = 'savo.scan.single_item.auto_capture';
  static const Duration _autoHoldDuration = Duration(seconds: 2);
  static const Duration _autoCooldown = Duration(seconds: 2);

  CameraController? _cameraController;
  List<CameraDescription>? _cameras;
  bool _isInitialized = false;
  bool _isProcessing = false;
  bool _autoCapture = false;
  Timer? _focusCheckTimer;
  List<Map<String, dynamic>> _scannedItems = [];
  String _scanType = 'pantry';
  bool _showOnboarding = true;  // Show tutorial banner
  String _currentStep = 'centering';  // centering, analyzing, confirming
  String _detectedItem = '';
  String _estimatedQuantity = '';

  DateTime? _steadySince;
  int? _autoCountdownSeconds;

  String? _qualityHint;
  DateTime? _qualityHintUntil;

  DateTime? _nextAutoCaptureAllowedAt;
  
  final ScanningService _scanningService = ScanningService();
  final BarcodeLookupService _barcodeLookup = BarcodeLookupService();

  @override
  void initState() {
    super.initState();
    _loadPrefs().whenComplete(_initializeCamera);
  }

  Future<void> _loadPrefs() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final savedType = prefs.getString(_prefsScanTypeKey);
      final savedAuto = prefs.getBool(_prefsAutoCaptureKey);
      if (savedType != null && savedType.trim().isNotEmpty) {
        _scanType = savedType.trim();
      }
      if (savedAuto != null) {
        _autoCapture = savedAuto;
      }
    } catch (_) {
      // Best-effort only.
    }
  }

  Future<void> _savePrefs() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_prefsScanTypeKey, _scanType);
      await prefs.setBool(_prefsAutoCaptureKey, _autoCapture);
    } catch (_) {
      // Best-effort only.
    }
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
    _stopFocusDetection();
    _steadySince = null;
    if (mounted) {
      setState(() {
        _autoCountdownSeconds = null;
      });
    }

    _focusCheckTimer = Timer.periodic(const Duration(milliseconds: 650), (timer) async {
      if (!mounted) return;
      if (!_autoCapture) {
        _steadySince = null;
        if (_autoCountdownSeconds != null) {
          setState(() {
            _autoCountdownSeconds = null;
          });
        }
        return;
      }

      final now = DateTime.now();
      final allowAt = _nextAutoCaptureAllowedAt;
      if (allowAt != null && now.isBefore(allowAt)) {
        _steadySince = null;
        if (_autoCountdownSeconds != null) {
          setState(() {
            _autoCountdownSeconds = null;
          });
        }
        return;
      }

      if (_currentStep != 'centering' || _isProcessing) {
        _steadySince = null;
        if (_autoCountdownSeconds != null) {
          setState(() {
            _autoCountdownSeconds = null;
          });
        }
        return;
      }

      if (!_isInFocus()) {
        _steadySince = null;
        if (_autoCountdownSeconds != null) {
          setState(() {
            _autoCountdownSeconds = null;
          });
        }
        return;
      }

      _steadySince ??= now;
      final elapsed = now.difference(_steadySince!);
      final remaining = _autoHoldDuration - elapsed;
      final seconds = remaining.isNegative ? 0 : (remaining.inMilliseconds / 1000).ceil();
      if (seconds != _autoCountdownSeconds) {
        setState(() {
          _autoCountdownSeconds = seconds == 0 ? null : seconds;
        });
      }

      if (elapsed < _autoHoldDuration) return;

      // Enforce a minimum delay between auto-captures (even if focus stays stable).
      _steadySince = null;
      setState(() {
        _autoCountdownSeconds = null;
      });
      _nextAutoCaptureAllowedAt = now.add(_autoCooldown);
      await _autoCaptureSingleItem();
    });
  }

  void _stopFocusDetection() {
    _focusCheckTimer?.cancel();
    _focusCheckTimer = null;
    _steadySince = null;
    if (_autoCountdownSeconds != null && mounted) {
      setState(() {
        _autoCountdownSeconds = null;
      });
    }
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

  void _setQualityHint(String message, {Duration duration = const Duration(seconds: 2)}) {
    if (!mounted) return;
    setState(() {
      _qualityHint = message;
      _qualityHintUntil = DateTime.now().add(duration);
    });
  }

  String? _extractQualityHint(Map<String, dynamic>? metadataOrDetail) {
    if (metadataOrDetail == null) return null;

    // Backend may return quality_issues or issues.
    final issues = (metadataOrDetail['quality_issues'] ?? metadataOrDetail['issues']);
    if (issues is List && issues.isNotEmpty) {
      final set = issues.map((e) => e.toString().toLowerCase()).toSet();
      if (set.any((x) => x.contains('dark') || x.contains('low_light'))) {
        return 'Too dark — turn on a light';
      }
      if (set.any((x) => x.contains('blur') || x.contains('shaky'))) {
        return 'Too blurry — hold steady';
      }
      if (set.any((x) => x.contains('far') || x.contains('small'))) {
        return 'Too far — move closer';
      }
      if (set.any((x) => x.contains('glare') || x.contains('reflect'))) {
        return 'Glare — tilt the item slightly';
      }
    }

    return null;
  }

  Future<Map<String, dynamic>> _scanOnce() async {
    // Capture image
    final XFile image = await _cameraController!.takePicture();
    final File imageFile = File(image.path);
    return _scanningService.scanSingleItem(imageFile: imageFile, scanType: _scanType);
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
      // Analyze with backend
      final result = await _scanOnce();

      if (mounted) {
        if (result['success'] == true) {
          final ingredient = result['ingredient'];
          final scanId = result['scan_id']?.toString().trim();
          final imageUrl = result['image_url']?.toString().trim();
          final autoSaved = result['auto_saved'] ?? false;
          final metadata = (result['metadata'] is Map)
              ? Map<String, dynamic>.from(result['metadata'])
              : (ingredient is Map && ingredient['metadata'] is Map)
                  ? Map<String, dynamic>.from(ingredient['metadata'])
                  : null;

          final qualityHint = _extractQualityHint(metadata);
          if (qualityHint != null) {
            setState(() {
              _currentStep = 'centering';
              _detectedItem = '';
              _estimatedQuantity = '';
            });
            _setQualityHint(qualityHint);
            _nextAutoCaptureAllowedAt = DateTime.now().add(const Duration(milliseconds: 900));
            return;
          }

          final detectedName = (ingredient is Map ? (ingredient['detected_name'] ?? '') : '').toString().trim();
          final confRaw = (ingredient is Map) ? ingredient['confidence'] : null;
          final conf = (confRaw is num) ? confRaw.toDouble() : double.tryParse(confRaw?.toString() ?? '');
          if (detectedName.isEmpty || detectedName.toLowerCase() == 'unknown' || conf == null) {
            setState(() {
              _currentStep = 'centering';
              _detectedItem = '';
              _estimatedQuantity = '';
            });
            _showError('Couldn\'t identify item. Hold steady and try again.');

            // Retry sooner for unknown items (don’t wait full 3s).
            _nextAutoCaptureAllowedAt = DateTime.now().add(const Duration(milliseconds: 900));
            if (_autoCapture && mounted) {
              Future.delayed(const Duration(milliseconds: 950), () {
                if (!mounted) return;
                if (_isProcessing) return;
                if (_currentStep != 'centering') return;
                _autoCaptureSingleItem();
              });
            }
            return;
          }

          // Multi-frame voting for borderline detections.
          var votedIngredient = (ingredient is Map) ? Map<String, dynamic>.from(ingredient) : <String, dynamic>{};
          if (scanId != null && scanId.isNotEmpty) {
            votedIngredient['scan_id'] = scanId;
          }
          if (imageUrl != null && imageUrl.isNotEmpty) {
            votedIngredient['image_url'] = imageUrl;
          }
          votedIngredient['auto_saved'] = (autoSaved == true);
          if (!autoSaved && conf >= 0.55 && conf < 0.80) {
            try {
              // Small delay to allow a steadier frame.
              await Future.delayed(const Duration(milliseconds: 550));
              final second = await _scanOnce();
              if (second['success'] == true && second['ingredient'] is Map) {
                final ing2 = Map<String, dynamic>.from(second['ingredient']);
                final n2 = (ing2['detected_name'] ?? '').toString().trim();
                final c2raw = ing2['confidence'];
                final c2 = (c2raw is num) ? c2raw.toDouble() : double.tryParse(c2raw?.toString() ?? '');
                if (n2.isNotEmpty && n2.toLowerCase() != 'unknown' && c2 != null) {
                  if (n2.toLowerCase() == detectedName.toLowerCase()) {
                    votedIngredient = votedIngredient..['confidence'] = ((conf + c2) / 2.0);
                  } else {
                    // Offer the second guess as an alternative.
                    final alts = <dynamic>[];
                    if (votedIngredient['close_alternatives'] is List) {
                      alts.addAll((votedIngredient['close_alternatives'] as List));
                    }
                    alts.insert(0, {'name': n2, 'confidence': c2});
                    votedIngredient['close_alternatives'] = alts;
                    // If second scan is much stronger, prefer it.
                    if (c2 > conf + 0.12) {
                      votedIngredient['detected_name'] = n2;
                      votedIngredient['confidence'] = c2;
                    }
                  }
                }
              }
            } catch (_) {
              // Best-effort only.
            }
          }

          // Update UI with detected item and quantity
          setState(() {
            _detectedItem = detectedName;
            final qty = votedIngredient['quantity'] ?? (ingredient is Map ? ingredient['quantity'] : null);
            final unit = votedIngredient['unit'] ?? (ingredient is Map ? (ingredient['unit'] ?? '') : '');
            _estimatedQuantity = qty != null ? '$qty $unit' : '';
            _currentStep = 'confirming';
          });

          if (autoSaved) {
            // High confidence - just show success and continue
            _onIngredientConfirmed(votedIngredient);
            _showSuccessSnackbar('${votedIngredient['detected_name']} ($_estimatedQuantity) added!');
            
            // Dismiss onboarding after first success
            if (_showOnboarding) {
              setState(() {
                _showOnboarding = false;
              });
            }
            
            // Reset to centering state
            // Give the user a moment to see what was detected/saved.
            _nextAutoCaptureAllowedAt = DateTime.now().add(const Duration(seconds: 3));
            Future.delayed(const Duration(seconds: 3), () {
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
            _showQuickConfirmation(votedIngredient);
          }
        } else {
          setState(() {
            _currentStep = 'centering';
          });
          _showError(result['error'] ?? 'Analysis failed');

          final hint = _extractQualityHint(result);
          if (hint != null) _setQualityHint(hint);

          // Back off a bit (but still retry faster than the normal 3s loop).
          _nextAutoCaptureAllowedAt = DateTime.now().add(const Duration(milliseconds: 900));
        }
      }
    } catch (e) {
      debugPrint('Capture error: $e');
      setState(() {
        _currentStep = 'centering';
      });
      _showError('Failed to scan item: $e');

      _setQualityHint('Hold steady and try again');

      _nextAutoCaptureAllowedAt = DateTime.now().add(const Duration(milliseconds: 900));
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
            // Small delay so the user isn’t rushed into the next capture.
            _nextAutoCaptureAllowedAt = DateTime.now().add(const Duration(seconds: 2));
            Future.delayed(const Duration(seconds: 2), () {
              if (!mounted) return;
              _startFocusDetection();
            });
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
      // If the backend already auto-saved this item, don't double-add.
      if (ingredient['auto_saved'] == true) return;

      final name = (ingredient['canonical_name'] ?? ingredient['name'] ?? '').toString().trim();
      if (name.isEmpty) return;

      final quantityRaw = ingredient['quantity'];
      final quantity = (quantityRaw is num) ? quantityRaw.toDouble() : double.tryParse(quantityRaw?.toString() ?? '') ?? 1.0;
      final unit = (ingredient['unit'] ?? 'pieces').toString().trim();

      final scanId = (ingredient['scan_id'] ?? '').toString().trim();

      final res = await _scanningService.confirmSingleIngredient(
        ingredientName: name,
        quantity: quantity <= 0 ? 1.0 : quantity,
        unit: unit.isEmpty ? 'pieces' : unit,
        scanType: _scanType,
        scanId: scanId.isEmpty ? null : scanId,
      );

      if (!mounted) return;

      final qtyStr = '${quantity <= 0 ? 1.0 : quantity} ${unit.isEmpty ? 'pieces' : unit}'.trim();
      final label = name;

      if (res['success'] == true) {
        final queued = res['queued'] == true;
        final message = queued
            ? (res['message']?.toString().trim().isNotEmpty == true ? res['message'].toString() : 'Saved offline. Will sync when online.')
            : 'Saved $label ($qtyStr)';
        _showSuccessSnackbar(message);
        return;
      }

      // Roll back optimistic add on failure.
      setState(() {
        _scannedItems.remove(ingredient);
      });

      final msg = res['error']?.toString() ?? 'Could not save item to pantry.';
      _showError(msg);
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _scannedItems.remove(ingredient);
      });
      _showError('Could not save item. Please try again.');
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
        return _autoCapture ? 'Center 1 item • hold 2s for auto-capture' : 'Center 1 item • tap Capture';
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
    final hintActive = _qualityHint != null && (_qualityHintUntil == null || DateTime.now().isBefore(_qualityHintUntil!));

    return Scaffold(
      appBar: AppBar(
        title: const Text('Scan Items'),
        backgroundColor: const Color(0xFF4CAF50),
        actions: [
          IconButton(
            tooltip: 'Scan barcode',
            onPressed: _isProcessing ? null : _openBarcodeScanner,
            icon: const Icon(Icons.qr_code_scanner, color: Colors.white),
          ),
          IconButton(
            tooltip: 'More',
            onPressed: _openMore,
            icon: const Icon(Icons.more_vert, color: Colors.white),
          ),
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
                                '1. Center item in frame\n2. Hold steady ~2 sec (auto) or tap Capture\n3. Confirm quantity & save',
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
                                      ? (hintActive
                                          ? (_qualityHint ?? 'Hold steady')
                                          : (_autoCapture && _autoCountdownSeconds != null)
                                              ? 'Hold steady… auto in ${_autoCountdownSeconds}s'
                                              : 'Fill box with the item/label')
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
                              if (_currentStep == 'centering' && !hintActive)
                                const Padding(
                                  padding: EdgeInsets.only(top: 8),
                                  child: Text(
                                    'One item at a time',
                                    style: TextStyle(color: Colors.white70, fontSize: 12),
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
                                  _savePrefs();
                                  if (value) {
                                    _startFocusDetection();
                                  } else {
                                    _stopFocusDetection();
                                  }
                                },
                              ),
                              const Text('Auto (hands-free)'),
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

  Future<void> _openBarcodeScanner() async {
    // Pause auto-capture while barcode scanning.
    if (_autoCapture) _stopFocusDetection();

    final code = await Navigator.push<String>(
      context,
      MaterialPageRoute(builder: (_) => const BarcodeScanScreen()),
    );

    if (!mounted) return;

    if (_autoCapture) {
      _nextAutoCaptureAllowedAt = DateTime.now().add(const Duration(seconds: 1));
      _startFocusDetection();
    }

    final barcode = (code ?? '').trim();
    if (barcode.isEmpty) return;

    setState(() {
      _isProcessing = true;
      _currentStep = 'analyzing';
    });

    try {
      final name = await _barcodeLookup.lookupName(barcode);
      if (!mounted) return;

      if (name == null || name.trim().isEmpty) {
        setState(() {
          _currentStep = 'centering';
        });
        _showError('Barcode not recognized. Try scanning the front label.');
        _setQualityHint('Try label scan');
        return;
      }

      final ingredient = <String, dynamic>{
        'detected_name': name,
        'canonical_name': name,
        'quantity': 1.0,
        'unit': 'pieces',
        'confidence': 0.99,
        'close_alternatives': const [],
      };

      setState(() {
        _detectedItem = name;
        _estimatedQuantity = '1 pieces';
        _currentStep = 'confirming';
      });

      _showQuickConfirmation(ingredient);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _currentStep = 'centering';
      });
      _showError('Barcode lookup failed: $e');
      _setQualityHint('Check connection');
    } finally {
      if (!mounted) return;
      setState(() {
        _isProcessing = false;
      });
    }
  }

  Future<void> _openMore() async {
    await showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (ctx, setLocal) {
            return Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text('More', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
                  const SizedBox(height: 12),
                  const Text('Scan location'),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    children: [
                      _buildScanTypeChip('Pantry', 'pantry', setLocal),
                      _buildScanTypeChip('Fridge', 'fridge', setLocal),
                      _buildScanTypeChip('Counter', 'counter', setLocal),
                      _buildScanTypeChip('Shopping', 'shopping', setLocal),
                    ],
                  ),
                  const SizedBox(height: 12),
                  FilledButton.icon(
                    onPressed: () {
                      Navigator.pop(ctx);
                      _openBarcodeScanner();
                    },
                    icon: const Icon(Icons.qr_code_scanner),
                    label: const Text('Scan barcode'),
                  ),
                  const SizedBox(height: 8),
                  TextButton(
                    onPressed: () => Navigator.pop(ctx),
                    child: const Text('Close'),
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }

  Widget _buildScanTypeChip(String label, String value, void Function(void Function())? setLocal) {
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
          if (mounted) {
            setState(() {
              _scanType = value;
            });
          }
          setLocal?.call(() {
            _scanType = value;
          });
          _savePrefs();
        }
      },
    );
  }
}
