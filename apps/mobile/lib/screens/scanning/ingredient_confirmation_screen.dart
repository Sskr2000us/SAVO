import 'package:flutter/material.dart';
import '../../services/scanning_service.dart';
import '../../widgets/quantity_picker.dart';

/// Confirmation screen for detected ingredients with chip-based UI
class IngredientConfirmationScreen extends StatefulWidget {
  final String scanId;
  final List<dynamic> ingredients;
  final Map<String, dynamic> metadata;

  const IngredientConfirmationScreen({
    Key? key,
    required this.scanId,
    required this.ingredients,
    required this.metadata,
  }) : super(key: key);

  @override
  _IngredientConfirmationScreenState createState() =>
      _IngredientConfirmationScreenState();
}

class _IngredientConfirmationScreenState
    extends State<IngredientConfirmationScreen> {
  final ScanningService _scanningService = ScanningService();
  final Map<String, Map<String, dynamic>> _userChoices = {};
  final Map<String, double> _quantities = {};
  final Map<String, String> _units = {};
  bool _isSubmitting = false;

  @override
  void initState() {
    super.initState();
    // Initialize default choices (auto-confirm high confidence)
    for (var ingredient in widget.ingredients) {
      final confidenceCategory = ingredient['confidence_category'];
      if (confidenceCategory == 'high') {
        _userChoices[ingredient['id']] = {
          'action': 'confirmed',
          'confirmed_name': ingredient['canonical_name'] ?? ingredient['detected_name'],
        };
      }
      
      // Initialize quantities from OCR detection or defaults
      final detectedQuantity = ingredient['quantity'];
      final detectedUnit = ingredient['unit'];
      
      if (detectedQuantity != null && detectedQuantity > 0) {
        _quantities[ingredient['id']] = (detectedQuantity as num).toDouble();
        _units[ingredient['id']] = detectedUnit ?? 'pieces';
      } else {
        // Default values
        _quantities[ingredient['id']] = 1.0;
        final smartUnits = getSmartUnitSuggestions(
          ingredient['category'],
          ingredient['detected_name'],
        );
        _units[ingredient['id']] = smartUnits.first;
      }
    }
  }

  void _handleConfirm(String detectedId, String name) {
    setState(() {
      _userChoices[detectedId] = {
        'action': 'confirmed',
        'confirmed_name': name,
      };
    });
  }

  void _handleModify(String detectedId, String newName) {
    setState(() {
      _userChoices[detectedId] = {
        'action': 'modified',
        'confirmed_name': newName,
      };
    });
  }

  void _handleReject(String detectedId) {
    setState(() {
      _userChoices[detectedId] = {
        'action': 'rejected',
      };
    });
  }

  Future<void> _submitConfirmations() async {
    setState(() {
      _isSubmitting = true;
    });

    try {
      // Build confirmations list
      final confirmations = _userChoices.entries.map((entry) {
        return {
          'detected_id': entry.key,
          'action': entry.value['action'],
          if (entry.value['confirmed_name'] != null)
            'confirmed_name': entry.value['confirmed_name'],
          // Add quantity and unit
          if (_quantities.containsKey(entry.key))
            'quantity': _quantities[entry.key],
          if (_units.containsKey(entry.key))
            'unit': _units[entry.key],
        };
      }).toList();

      final result = await _scanningService.confirmIngredients(
        scanId: widget.scanId,
        confirmations: confirmations,
      );

      if (mounted) {
        if (result['success'] == true) {
          // Show success message
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(result['message'] ?? 'Ingredients confirmed!'),
              backgroundColor: Colors.green,
              duration: const Duration(seconds: 3),
            ),
          );

          // Navigate back to home (pop twice: confirmation + camera)
          Navigator.of(context).pop();
          Navigator.of(context).pop();
        } else {
          _showError(result['error'] ?? 'Confirmation failed');
        }
      }
    } catch (e) {
      _showError('Failed to confirm ingredients: $e');
    } finally {
      if (mounted) {
        setState(() {
          _isSubmitting = false;
        });
      }
    }
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

  int _getConfirmedCount() {
    return _userChoices.values
        .where((choice) => choice['action'] == 'confirmed' || choice['action'] == 'modified')
        .length;
  }

  @override
  Widget build(BuildContext context) {
    final highConfidence = widget.ingredients
        .where((i) => i['confidence_category'] == 'high')
        .toList();
    final mediumConfidence = widget.ingredients
        .where((i) => i['confidence_category'] == 'medium')
        .toList();
    final lowConfidence = widget.ingredients
        .where((i) => i['confidence_category'] == 'low')
        .toList();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Confirm Ingredients'),
        backgroundColor: const Color(0xFF4CAF50),
      ),
      body: Column(
        children: [
          // Summary header
          Container(
            padding: const EdgeInsets.all(16),
            color: const Color(0xFFF5F5F5),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Detected ${widget.ingredients.length} ingredients',
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    _buildConfidenceBadge(
                      'High',
                      highConfidence.length,
                      Colors.green,
                    ),
                    const SizedBox(width: 8),
                    _buildConfidenceBadge(
                      'Medium',
                      mediumConfidence.length,
                      Colors.orange,
                    ),
                    const SizedBox(width: 8),
                    _buildConfidenceBadge(
                      'Low',
                      lowConfidence.length,
                      Colors.red,
                    ),
                  ],
                ),
              ],
            ),
          ),

          // Ingredients list
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                if (highConfidence.isNotEmpty) ...[
                  _buildSectionHeader('High Confidence', Colors.green, 
                      'Auto-confirmed (tap to modify)'),
                  ...highConfidence.map((ing) => _buildIngredientCard(ing)),
                  const SizedBox(height: 16),
                ],
                if (mediumConfidence.isNotEmpty) ...[
                  _buildSectionHeader('Please Review', Colors.orange,
                      'Select the correct ingredient'),
                  ...mediumConfidence.map((ing) => _buildIngredientCard(ing)),
                  const SizedBox(height: 16),
                ],
                if (lowConfidence.isNotEmpty) ...[
                  _buildSectionHeader('Uncertain', Colors.red,
                      'Help us identify these'),
                  ...lowConfidence.map((ing) => _buildIngredientCard(ing)),
                ],
              ],
            ),
          ),

          // Submit button
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white,
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.1),
                  blurRadius: 4,
                  offset: const Offset(0, -2),
                ),
              ],
            ),
            child: SafeArea(
              child: ElevatedButton(
                onPressed: _isSubmitting ? null : _submitConfirmations,
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF4CAF50),
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  minimumSize: const Size(double.infinity, 50),
                ),
                child: _isSubmitting
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                        ),
                      )
                    : Text(
                        'Confirm ${_getConfirmedCount()} Ingredients',
                        style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                      ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildConfidenceBadge(String label, int count, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            label,
            style: TextStyle(
              color: color,
              fontWeight: FontWeight.bold,
              fontSize: 12,
            ),
          ),
          const SizedBox(width: 4),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(
              color: color,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Text(
              count.toString(),
              style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.bold,
                fontSize: 11,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(String title, Color color, String subtitle) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 4,
                height: 20,
                decoration: BoxDecoration(
                  color: color,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(width: 8),
              Text(
                title,
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Padding(
            padding: const EdgeInsets.only(left: 12),
            child: Text(
              subtitle,
              style: TextStyle(
                fontSize: 13,
                color: Colors.grey[600],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildIngredientCard(Map<String, dynamic> ingredient) {
    final detectedId = ingredient['id'];
    final detectedName = ingredient['detected_name'];
    final canonicalName = ingredient['canonical_name'] ?? detectedName;
    final confidence = (ingredient['confidence'] as num).toDouble();
    final confidenceCategory = ingredient['confidence_category'];
    final closeAlternatives = ingredient['close_alternatives'] as List? ?? [];
    final allergenWarnings = ingredient['allergen_warnings'] as List? ?? [];
    
    final userChoice = _userChoices[detectedId];
    final isConfirmed = userChoice?['action'] == 'confirmed';
    final isModified = userChoice?['action'] == 'modified';
    final isRejected = userChoice?['action'] == 'rejected';

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      elevation: 2,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: isRejected
              ? Colors.red.withOpacity(0.5)
              : (isConfirmed || isModified)
                  ? Colors.green.withOpacity(0.5)
                  : Colors.transparent,
          width: 2,
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header: Name + Confidence
            Row(
              children: [
                Expanded(
                  child: Text(
                    canonicalName.replaceAll('_', ' ').toUpperCase(),
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                _buildConfidenceIndicator(confidence, confidenceCategory),
              ],
            ),

            // Allergen warnings
            if (allergenWarnings.isNotEmpty) ...[
              const SizedBox(height: 12),
              ...allergenWarnings.map((warning) => Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: Colors.red[50],
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.red),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.warning, color: Colors.red, size: 20),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            warning['message'],
                            style: const TextStyle(
                              color: Colors.red,
                              fontWeight: FontWeight.bold,
                              fontSize: 13,
                            ),
                          ),
                        ),
                      ],
                    ),
                  )),
            ],

            // Quantity picker
            if (!isRejected) ...[
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.grey[50],
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.grey.shade300),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.scale, size: 18, color: Colors.grey),
                        const SizedBox(width: 8),
                        const Text(
                          'Quantity:',
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        if (ingredient['quantity'] != null) ...[
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 2,
                            ),
                            decoration: BoxDecoration(
                              color: Colors.blue.shade50,
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: const Text(
                              'Auto-detected',
                              style: TextStyle(
                                fontSize: 11,
                                color: Colors.blue,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                    const SizedBox(height: 8),
                    QuantityPicker(
                      initialQuantity: _quantities[detectedId] ?? 1.0,
                      initialUnit: _units[detectedId] ?? 'pieces',
                      availableUnits: getSmartUnitSuggestions(
                        ingredient['category'],
                        ingredient['detected_name'],
                      ),
                      onChanged: (qty, unit) {
                        setState(() {
                          _quantities[detectedId] = qty;
                          _units[detectedId] = unit;
                        });
                      },
                      enabled: true,
                    ),
                  ],
                ),
              ),
            ],

            // Close alternatives (for medium/low confidence)
            if (closeAlternatives.isNotEmpty && confidenceCategory != 'high') ...[
              const SizedBox(height: 12),
              const Text(
                'Or select one of these:',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w500,
                ),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: closeAlternatives.map((alt) {
                  final altName = alt['name'];
                  final isSelected = userChoice?['confirmed_name'] == altName;
                  return _buildAlternativeChip(
                    detectedId,
                    altName,
                    alt['display_name'],
                    alt['likelihood'],
                    isSelected,
                  );
                }).toList(),
              ),
            ],

            // Action buttons
            const SizedBox(height: 12),
            Row(
              children: [
                // Confirm button
                if (!isRejected)
                  Expanded(
                    child: OutlinedButton.icon(
                      icon: Icon(
                        isConfirmed || isModified ? Icons.check_circle : Icons.check,
                        size: 18,
                      ),
                      label: Text(isConfirmed || isModified ? 'Confirmed' : 'Confirm'),
                      onPressed: () => _handleConfirm(detectedId, canonicalName),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: isConfirmed || isModified ? Colors.green : Colors.black87,
                        side: BorderSide(
                          color: isConfirmed || isModified ? Colors.green : Colors.grey,
                        ),
                      ),
                    ),
                  ),

                const SizedBox(width: 8),

                // Reject button
                Expanded(
                  child: OutlinedButton.icon(
                    icon: Icon(
                      isRejected ? Icons.cancel : Icons.close,
                      size: 18,
                    ),
                    label: Text(isRejected ? 'Rejected' : 'Reject'),
                    onPressed: () => _handleReject(detectedId),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: isRejected ? Colors.red : Colors.black87,
                      side: BorderSide(
                        color: isRejected ? Colors.red : Colors.grey,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildConfidenceIndicator(double confidence, String category) {
    Color color;
    String label;

    switch (category) {
      case 'high':
        color = Colors.green;
        label = 'High';
        break;
      case 'medium':
        color = Colors.orange;
        label = 'Medium';
        break;
      default:
        color = Colors.red;
        label = 'Low';
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            '${(confidence * 100).toInt()}%',
            style: TextStyle(
              color: color,
              fontWeight: FontWeight.bold,
              fontSize: 12,
            ),
          ),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(
              color: color,
              fontSize: 11,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAlternativeChip(
    String detectedId,
    String name,
    String displayName,
    String likelihood,
    bool isSelected,
  ) {
    return ChoiceChip(
      label: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(displayName),
          if (likelihood == 'high') ...[
            const SizedBox(width: 4),
            const Icon(Icons.star, size: 14, color: Colors.orange),
          ],
        ],
      ),
      selected: isSelected,
      onSelected: (selected) {
        if (selected) {
          _handleModify(detectedId, name);
        }
      },
      selectedColor: const Color(0xFF4CAF50),
      labelStyle: TextStyle(
        color: isSelected ? Colors.white : Colors.black87,
        fontSize: 13,
      ),
    );
  }
}
