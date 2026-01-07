import 'package:flutter/material.dart';

/// Quick confirmation card for continuous scanning
class QuickConfirmationCard extends StatefulWidget {
  final Map<String, dynamic> ingredient;
  final Function(Map<String, dynamic>) onConfirm;
  final VoidCallback onReject;

  const QuickConfirmationCard({
    Key? key,
    required this.ingredient,
    required this.onConfirm,
    required this.onReject,
  }) : super(key: key);

  @override
  _QuickConfirmationCardState createState() => _QuickConfirmationCardState();
}

class _QuickConfirmationCardState extends State<QuickConfirmationCard> {
  late TextEditingController _quantityController;
  late String _selectedUnit;
  bool _isConfirming = false;

  @override
  void initState() {
    super.initState();
    _quantityController = TextEditingController(
      text: (widget.ingredient['quantity'] ?? 1.0).toString(),
    );
    _selectedUnit = widget.ingredient['unit'] ?? 'pieces';
  }

  @override
  void dispose() {
    _quantityController.dispose();
    super.dispose();
  }

  Color _getConfidenceColor() {
    final confidence = widget.ingredient['confidence'] ?? 0.0;
    if (confidence >= 0.8) return Colors.green;
    if (confidence >= 0.5) return Colors.orange;
    return Colors.red;
  }

  String _getConfidenceLabel() {
    final confidence = widget.ingredient['confidence'] ?? 0.0;
    final percent = (confidence * 100).toInt();
    if (confidence >= 0.8) return '$percent% confident ✓';
    if (confidence >= 0.5) return '$percent% somewhat sure';
    return '$percent% uncertain';
  }

  void _handleConfirm() async {
    if (_isConfirming) return;

    setState(() {
      _isConfirming = true;
    });

    try {
      final confirmedData = {
        'name': widget.ingredient['detected_name'],
        'canonical_name': widget.ingredient['canonical_name'],
        'quantity': double.tryParse(_quantityController.text) ?? 1.0,
        'unit': _selectedUnit,
        'confidence': widget.ingredient['confidence'],
      };

      widget.onConfirm(confirmedData);
    } catch (e) {
      debugPrint('Confirmation error: $e');
      setState(() {
        _isConfirming = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final confidence = widget.ingredient['confidence'] ?? 0.0;
    final closeAlternatives = widget.ingredient['close_alternatives'] as List? ?? [];

    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.only(
          topLeft: Radius.circular(20),
          topRight: Radius.circular(20),
        ),
      ),
      child: Padding(
        padding: EdgeInsets.only(
          bottom: MediaQuery.of(context).viewInsets.bottom,
        ),
        child: SingleChildScrollView(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Header
                Row(
                  children: [
                    const Text(
                      'Quick Confirm',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const Spacer(),
                    IconButton(
                      icon: const Icon(Icons.close),
                      onPressed: widget.onReject,
                    ),
                  ],
                ),
                
                const SizedBox(height: 16),
                
                // Ingredient name
                Text(
                  widget.ingredient['detected_name'] ?? 'Unknown',
                  style: const TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                
                const SizedBox(height: 8),
                
                // Confidence badge
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: _getConfidenceColor().withOpacity(0.2),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(
                      color: _getConfidenceColor(),
                      width: 1,
                    ),
                  ),
                  child: Text(
                    _getConfidenceLabel(),
                    style: TextStyle(
                      color: _getConfidenceColor(),
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                
                const SizedBox(height: 20),
                
                // Quantity input
                Row(
                  children: [
                    Expanded(
                      flex: 2,
                      child: TextField(
                        controller: _quantityController,
                        keyboardType: const TextInputType.numberWithOptions(decimal: true),
                        decoration: InputDecoration(
                          labelText: 'Quantity',
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                          contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      flex: 1,
                      child: DropdownButtonFormField<String>(
                        value: _selectedUnit,
                        decoration: InputDecoration(
                          labelText: 'Unit',
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                          contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                        ),
                        items: const [
                          DropdownMenuItem(value: 'pieces', child: Text('pieces')),
                          DropdownMenuItem(value: 'grams', child: Text('g')),
                          DropdownMenuItem(value: 'kg', child: Text('kg')),
                          DropdownMenuItem(value: 'ml', child: Text('ml')),
                          DropdownMenuItem(value: 'liters', child: Text('L')),
                          DropdownMenuItem(value: 'oz', child: Text('oz')),
                          DropdownMenuItem(value: 'lbs', child: Text('lbs')),
                          DropdownMenuItem(value: 'cups', child: Text('cups')),
                        ],
                        onChanged: (value) {
                          if (value != null) {
                            setState(() {
                              _selectedUnit = value;
                            });
                          }
                        },
                      ),
                    ),
                  ],
                ),
                
                // Close alternatives (if medium/low confidence)
                if (confidence < 0.8 && closeAlternatives.isNotEmpty) ...[
                  const SizedBox(height: 20),
                  const Text(
                    'Or did you mean:',
                    style: TextStyle(
                      fontSize: 14,
                      color: Colors.grey,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    children: closeAlternatives.take(4).map((alt) {
                      final altName = alt['name'] ?? alt;
                      return ActionChip(
                        label: Text(altName.toString()),
                        onPressed: () {
                          widget.ingredient['detected_name'] = altName.toString();
                          setState(() {});
                        },
                      );
                    }).toList(),
                  ),
                ],
                
                const SizedBox(height: 24),
                
                // Action buttons
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton(
                        onPressed: _isConfirming ? null : widget.onReject,
                        style: OutlinedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(vertical: 16),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                        ),
                        child: const Text('Reject'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      flex: 2,
                      child: ElevatedButton(
                        onPressed: _isConfirming ? null : _handleConfirm,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFF4CAF50),
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(vertical: 16),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                        ),
                        child: _isConfirming
                            ? const SizedBox(
                                height: 20,
                                width: 20,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                                ),
                              )
                            : const Text('✓ Confirm & Continue'),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
