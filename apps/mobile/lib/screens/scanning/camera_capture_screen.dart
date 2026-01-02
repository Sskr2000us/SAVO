import 'dart:io';
import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:image_picker/image_picker.dart';
import '../../services/scanning_service.dart';
import 'ingredient_confirmation_screen.dart';

/// Camera capture screen for scanning pantry/fridge
class CameraCaptureScreen extends StatefulWidget {
  const CameraCaptureScreen({Key? key}) : super(key: key);

  @override
  _CameraCaptureScreenState createState() => _CameraCaptureScreenState();
}

class _CameraCaptureScreenState extends State<CameraCaptureScreen> {
  CameraController? _cameraController;
  List<CameraDescription>? _cameras;
  bool _isInitialized = false;
  bool _isProcessing = false;
  File? _capturedImage;
  String _scanType = 'pantry';
  final TextEditingController _locationController = TextEditingController();
  final ScanningService _scanningService = ScanningService();

  @override
  void initState() {
    super.initState();
    _initializeCamera();
  }

  Future<void> _initializeCamera() async {
    try {
      _cameras = await availableCameras();
      if (_cameras!.isNotEmpty) {
        _cameraController = CameraController(
          _cameras![0],
          ResolutionPreset.high,
          enableAudio: false,
        );

        await _cameraController!.initialize();
        setState(() {
          _isInitialized = true;
        });
      }
    } catch (e) {
      debugPrint('Camera initialization error: $e');
      _showError('Failed to initialize camera: $e');
    }
  }

  @override
  void dispose() {
    _cameraController?.dispose();
    _locationController.dispose();
    super.dispose();
  }

  Future<void> _captureImage() async {
    if (_cameraController == null || !_cameraController!.value.isInitialized) {
      return;
    }

    try {
      final XFile image = await _cameraController!.takePicture();
      setState(() {
        _capturedImage = File(image.path);
      });
    } catch (e) {
      debugPrint('Capture error: $e');
      _showError('Failed to capture image: $e');
    }
  }

  Future<void> _pickImageFromGallery() async {
    try {
      final ImagePicker picker = ImagePicker();
      final XFile? image = await picker.pickImage(
        source: ImageSource.gallery,
        maxWidth: 1920,
        maxHeight: 1080,
        imageQuality: 85,
      );

      if (image != null) {
        setState(() {
          _capturedImage = File(image.path);
        });
      }
    } catch (e) {
      debugPrint('Gallery pick error: $e');
      _showError('Failed to pick image: $e');
    }
  }

  Future<void> _analyzeImage() async {
    if (_capturedImage == null) return;

    setState(() {
      _isProcessing = true;
    });

    try {
      final result = await _scanningService.analyzeImage(
        imageFile: _capturedImage!,
        scanType: _scanType,
        locationHint: _locationController.text.isNotEmpty
            ? _locationController.text
            : null,
      );

      if (mounted) {
        if (result['success'] == true) {
          // Navigate to confirmation screen
          Navigator.of(context).push(
            MaterialPageRoute(
              builder: (context) => IngredientConfirmationScreen(
                scanId: result['scan_id'],
                ingredients: result['ingredients'],
                metadata: result['metadata'],
              ),
            ),
          );
        } else {
          _showError(result['error'] ?? 'Analysis failed');
        }
      }
    } catch (e) {
      debugPrint('Analysis error: $e');
      _showError('Failed to analyze image: $e');
    } finally {
      if (mounted) {
        setState(() {
          _isProcessing = false;
        });
      }
    }
  }

  void _retakePhoto() {
    setState(() {
      _capturedImage = null;
    });
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: Colors.red,
        duration: const Duration(seconds: 4),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Scan Ingredients'),
        backgroundColor: const Color(0xFF4CAF50),
      ),
      body: _capturedImage != null
          ? _buildImagePreview()
          : _buildCameraView(),
    );
  }

  Widget _buildCameraView() {
    if (!_isInitialized) {
      return const Center(
        child: CircularProgressIndicator(),
      );
    }

    return Column(
      children: [
        // Scan type selector
        Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'What are you scanning?',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                children: [
                  _buildScanTypeChip('Pantry', 'pantry'),
                  _buildScanTypeChip('Fridge', 'fridge'),
                  _buildScanTypeChip('Counter', 'counter'),
                  _buildScanTypeChip('Shopping', 'shopping'),
                ],
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _locationController,
                decoration: const InputDecoration(
                  labelText: 'Location hint (optional)',
                  hintText: 'e.g., "top shelf", "vegetable drawer"',
                  border: OutlineInputBorder(),
                  prefixIcon: Icon(Icons.location_on),
                ),
              ),
            ],
          ),
        ),

        // Camera preview
        Expanded(
          child: Container(
            decoration: BoxDecoration(
              border: Border.all(color: Colors.grey),
            ),
            child: CameraPreview(_cameraController!),
          ),
        ),

        // Controls
        Container(
          padding: const EdgeInsets.all(16),
          color: Colors.black87,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              // Gallery button
              IconButton(
                icon: const Icon(Icons.photo_library, color: Colors.white, size: 32),
                onPressed: _pickImageFromGallery,
              ),

              // Capture button
              Container(
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(color: Colors.white, width: 4),
                ),
                child: IconButton(
                  icon: const Icon(Icons.camera, size: 48),
                  color: Colors.white,
                  onPressed: _captureImage,
                ),
              ),

              // Placeholder for symmetry
              const SizedBox(width: 48),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildScanTypeChip(String label, String value) {
    final isSelected = _scanType == value;
    return ChoiceChip(
      label: Text(label),
      selected: isSelected,
      onSelected: (selected) {
        if (selected) {
          setState(() {
            _scanType = value;
          });
        }
      },
      selectedColor: const Color(0xFF4CAF50),
      labelStyle: TextStyle(
        color: isSelected ? Colors.white : Colors.black87,
      ),
    );
  }

  Widget _buildImagePreview() {
    return Column(
      children: [
        // Instructions
        Container(
          padding: const EdgeInsets.all(16),
          color: const Color(0xFFF5F5F5),
          child: const Row(
            children: [
              Icon(Icons.info_outline, color: Color(0xFF4CAF50)),
              SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Review your image, then tap Analyze to detect ingredients',
                  style: TextStyle(fontSize: 14),
                ),
              ),
            ],
          ),
        ),

        // Image preview
        Expanded(
          child: Container(
            color: Colors.black,
            child: Center(
              child: Image.file(_capturedImage!),
            ),
          ),
        ),

        // Action buttons
        Container(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              // Retake button
              Expanded(
                child: OutlinedButton.icon(
                  icon: const Icon(Icons.camera_alt),
                  label: const Text('Retake'),
                  onPressed: _isProcessing ? null : _retakePhoto,
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 16),
                  ),
                ),
              ),
              const SizedBox(width: 16),

              // Analyze button
              Expanded(
                flex: 2,
                child: ElevatedButton.icon(
                  icon: _isProcessing
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                          ),
                        )
                      : const Icon(Icons.search),
                  label: Text(_isProcessing ? 'Analyzing...' : 'Analyze Image'),
                  onPressed: _isProcessing ? null : _analyzeImage,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF4CAF50),
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                  ),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
