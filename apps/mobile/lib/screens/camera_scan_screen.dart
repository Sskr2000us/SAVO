import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import '../services/visual_intelligence_service.dart';

/// Camera Scan Screen for Ingredient Identification
/// Allows users to scan ingredients using camera or select from gallery
class CameraScanScreen extends StatefulWidget {
  final VisualIntelligenceService intelligenceService;
  
  const CameraScanScreen({
    Key? key,
    required this.intelligenceService,
  }) : super(key: key);
  
  @override
  State<CameraScanScreen> createState() => _CameraScanScreenState();
}

class _CameraScanScreenState extends State<CameraScanScreen> {
  final ImagePicker _picker = ImagePicker();
  File? _selectedImage;
  IdentificationResult? _identificationResult;
  bool _isProcessing = false;
  String? _errorMessage;
  
  /// Capture image from camera
  Future<void> _captureFromCamera() async {
    try {
      final XFile? photo = await _picker.pickImage(
        source: ImageSource.camera,
        maxWidth: 1920,
        maxHeight: 1080,
        imageQuality: 85,
      );
      
      if (photo != null) {
        setState(() {
          _selectedImage = File(photo.path);
          _identificationResult = null;
          _errorMessage = null;
        });
        
        await _identifyIngredient();
      }
    } catch (e) {
      setState(() {
        _errorMessage = 'Failed to capture image: $e';
      });
    }
  }
  
  /// Select image from gallery
  Future<void> _selectFromGallery() async {
    try {
      final XFile? image = await _picker.pickImage(
        source: ImageSource.gallery,
        maxWidth: 1920,
        maxHeight: 1080,
        imageQuality: 85,
      );
      
      if (image != null) {
        setState(() {
          _selectedImage = File(image.path);
          _identificationResult = null;
          _errorMessage = null;
        });
        
        await _identifyIngredient();
      }
    } catch (e) {
      setState(() {
        _errorMessage = 'Failed to select image: $e';
      });
    }
  }
  
  /// Identify ingredient using visual intelligence
  Future<void> _identifyIngredient() async {
    if (_selectedImage == null) return;
    
    setState(() {
      _isProcessing = true;
      _errorMessage = null;
    });
    
    try {
      final result = await widget.intelligenceService.identifyIngredient(
        _selectedImage!,
      );
      
      setState(() {
        _identificationResult = result;
        _isProcessing = false;
      });
      
      // Show result bottom sheet
      _showResultBottomSheet();
      
    } catch (e) {
      setState(() {
        _errorMessage = 'Failed to identify ingredient: $e';
        _isProcessing = false;
      });
    }
  }
  
  /// Show identification results in bottom sheet
  void _showResultBottomSheet() {
    if (_identificationResult == null) return;
    
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.7,
        minChildSize: 0.5,
        maxChildSize: 0.95,
        builder: (context, scrollController) => Container(
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
          ),
          child: _buildResultContent(scrollController),
        ),
      ),
    );
  }
  
  /// Build result content
  Widget _buildResultContent(ScrollController scrollController) {
    final result = _identificationResult!;
    final topMatch = result.topMatches.isNotEmpty ? result.topMatches.first : null;
    
    return ListView(
      controller: scrollController,
      padding: EdgeInsets.all(20),
      children: [
        // Handle bar
        Center(
          child: Container(
            width: 40,
            height: 4,
            margin: EdgeInsets.only(bottom: 20),
            decoration: BoxDecoration(
              color: Colors.grey[300],
              borderRadius: BorderRadius.circular(2),
            ),
          ),
        ),
        
        // Title
        Text(
          'Ingredient Identified!',
          style: TextStyle(
            fontSize: 24,
            fontWeight: FontWeight.bold,
          ),
        ),
        SizedBox(height: 20),
        
        // Top match
        if (topMatch != null) ...[
          _buildMatchCard(topMatch, isTopMatch: true),
          SizedBox(height: 20),
        ],
        
        // Visual features
        Text(
          'Visual Features',
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w600,
          ),
        ),
        SizedBox(height: 10),
        _buildVisualFeaturesCard(result.visualFeatures),
        SizedBox(height: 20),
        
        // Other matches
        if (result.topMatches.length > 1) ...[
          Text(
            'Alternative Matches',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w600,
            ),
          ),
          SizedBox(height: 10),
          ...result.topMatches.skip(1).map(
            (match) => Padding(
              padding: EdgeInsets.only(bottom: 10),
              child: _buildMatchCard(match, isTopMatch: false),
            ),
          ),
        ],
        
        // Action buttons
        SizedBox(height: 20),
        Row(
          children: [
            Expanded(
              child: ElevatedButton(
                onPressed: () {
                  // Add to inventory
                  Navigator.pop(context);
                  // TODO: Navigate to add inventory screen with pre-filled data
                },
                child: Text('Add to Inventory'),
              ),
            ),
            SizedBox(width: 10),
            Expanded(
              child: OutlinedButton(
                onPressed: () {
                  Navigator.pop(context);
                },
                child: Text('Cancel'),
              ),
            ),
          ],
        ),
      ],
    );
  }
  
  /// Build match card
  Widget _buildMatchCard(IngredientMatch match, {required bool isTopMatch}) {
    return Card(
      elevation: isTopMatch ? 4 : 2,
      color: isTopMatch ? Colors.green.shade50 : Colors.white,
      child: Padding(
        padding: EdgeInsets.all(16),
        child: Column(
          children: [
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        match.canonicalName,
                        style: TextStyle(
                          fontSize: isTopMatch ? 20 : 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      SizedBox(height: 4),
                      Text(
                        match.reasoning,
                        style: TextStyle(
                          fontSize: 14,
                          color: Colors.grey[700],
                        ),
                      ),
                    ],
                  ),
                ),
                Column(
                  children: [
                    CircularProgressIndicator(
                      value: match.confidence,
                      backgroundColor: Colors.grey[300],
                      valueColor: AlwaysStoppedAnimation<Color>(
                        match.confidence > 0.8
                            ? Colors.green
                            : match.confidence > 0.6
                                ? Colors.orange
                                : Colors.red,
                      ),
                    ),
                    SizedBox(height: 4),
                    Text(
                      '${(match.confidence * 100).toStringAsFixed(0)}%',
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
  
  /// Build visual features card
  Widget _buildVisualFeaturesCard(VisualFeatures features) {
    return Card(
      child: Padding(
        padding: EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildFeatureRow('Colors', features.dominantColors.join(', ')),
            Divider(),
            _buildFeatureRow('Texture', features.textureDescription),
            Divider(),
            _buildFeatureRow('Brightness', '${(features.brightness * 100).toStringAsFixed(0)}%'),
          ],
        ),
      ),
    );
  }
  
  /// Build feature row
  Widget _buildFeatureRow(String label, String value) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          label,
          style: TextStyle(
            fontWeight: FontWeight.w600,
            color: Colors.grey[700],
          ),
        ),
        Text(value),
      ],
    );
  }
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Scan Ingredient'),
      ),
      body: Column(
        children: [
          // Image preview
          Expanded(
            child: Center(
              child: _selectedImage != null
                  ? Stack(
                      alignment: Alignment.center,
                      children: [
                        Image.file(
                          _selectedImage!,
                          fit: BoxFit.contain,
                        ),
                        if (_isProcessing)
                          Container(
                            color: Colors.black54,
                            child: Center(
                              child: Column(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  CircularProgressIndicator(
                                    valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                                  ),
                                  SizedBox(height: 16),
                                  Text(
                                    'Analyzing ingredient...',
                                    style: TextStyle(
                                      color: Colors.white,
                                      fontSize: 16,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                      ],
                    )
                  : Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          Icons.camera_alt_outlined,
                          size: 100,
                          color: Colors.grey[400],
                        ),
                        SizedBox(height: 20),
                        Text(
                          'Take a photo or select from gallery',
                          style: TextStyle(
                            fontSize: 16,
                            color: Colors.grey[600],
                          ),
                        ),
                      ],
                    ),
            ),
          ),
          
          // Error message
          if (_errorMessage != null)
            Container(
              padding: EdgeInsets.all(16),
              color: Colors.red.shade100,
              child: Row(
                children: [
                  Icon(Icons.error, color: Colors.red),
                  SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      _errorMessage!,
                      style: TextStyle(color: Colors.red.shade900),
                    ),
                  ),
                ],
              ),
            ),
          
          // Action buttons
          SafeArea(
            child: Padding(
              padding: EdgeInsets.all(16),
              child: Row(
                children: [
                  Expanded(
                    child: ElevatedButton.icon(
                      onPressed: _isProcessing ? null : _captureFromCamera,
                      icon: Icon(Icons.camera_alt),
                      label: Text('Camera'),
                      style: ElevatedButton.styleFrom(
                        padding: EdgeInsets.all(16),
                      ),
                    ),
                  ),
                  SizedBox(width: 16),
                  Expanded(
                    child: ElevatedButton.icon(
                      onPressed: _isProcessing ? null : _selectFromGallery,
                      icon: Icon(Icons.photo_library),
                      label: Text('Gallery'),
                      style: ElevatedButton.styleFrom(
                        padding: EdgeInsets.all(16),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
