import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../services/scanning_service.dart';
import '../../services/api_client.dart';
import '../../services/cook_now_service.dart';
import '../../services/entitlements_service.dart';
import '../../models/profile_state.dart';
import '../../widgets/quantity_picker.dart';
import '../recipe_options_screen.dart';

/// Confirmation screen for detected ingredients with chip-based UI
class IngredientConfirmationScreen extends StatefulWidget {
  final String scanId;
  final List<dynamic> ingredients;
  final Map<String, dynamic> metadata;
  final String? barcode;
  final String? barcodeNameHint;
  final double? barcodeQuantityHint;
  final String? barcodeUnitHint;

  const IngredientConfirmationScreen({
    Key? key,
    required this.scanId,
    required this.ingredients,
    required this.metadata,
    this.barcode,
    this.barcodeNameHint,
    this.barcodeQuantityHint,
    this.barcodeUnitHint,
  }) : super(key: key);

  @override
  _IngredientConfirmationScreenState createState() =>
      _IngredientConfirmationScreenState();
}

class _IngredientThumb extends StatelessWidget {
  const _IngredientThumb({
    required this.thumbnailUrl,
    required this.fullImageUrl,
  });

  final String? thumbnailUrl;
  final String? fullImageUrl;

  @override
  Widget build(BuildContext context) {
    final url = (thumbnailUrl ?? '').trim().isNotEmpty
        ? thumbnailUrl!.trim()
        : ((fullImageUrl ?? '').trim().isNotEmpty ? fullImageUrl!.trim() : null);

    if (url == null) {
      return Container(
        width: 44,
        height: 44,
        decoration: BoxDecoration(
          color: Colors.grey.shade100,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: Colors.grey.shade300),
        ),
        alignment: Alignment.center,
        child: const Icon(Icons.photo_outlined, size: 18, color: Colors.grey),
      );
    }

    return ClipRRect(
      borderRadius: BorderRadius.circular(10),
      child: Image.network(
        url,
        width: 44,
        height: 44,
        fit: BoxFit.cover,
        errorBuilder: (_, __, ___) {
          return Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: Colors.grey.shade100,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: Colors.grey.shade300),
            ),
            alignment: Alignment.center,
            child: const Icon(Icons.broken_image_outlined, size: 18, color: Colors.grey),
          );
        },
      ),
    );
  }
}

class _IngredientConfirmationScreenState
    extends State<IngredientConfirmationScreen> {
  final ScanningService _scanningService = ScanningService();
  final Map<String, Map<String, dynamic>> _userChoices = {};
  final Map<String, double> _quantities = {};
  final Map<String, String> _units = {};
  final Map<String, bool> _quantityConfirmed = {};
  final Map<String, double?> _suggestedQuantities = {};
  final Map<String, String?> _suggestedUnits = {};
  bool _isSubmitting = false;

  static const double _lowQuantityConfidenceThreshold = 0.70;

  Map<String, dynamic>? get _delta {
    final d = widget.metadata['delta'];
    if (d is Map<String, dynamic>) return d;
    if (d is Map) return d.cast<String, dynamic>();
    return null;
  }

  Widget _buildDeltaSummary() {
    final delta = _delta;
    if (delta == null) return const SizedBox.shrink();

    final newCount = (delta['new_count'] is num) ? (delta['new_count'] as num).toInt() : 0;
    final removedCount = (delta['removed_count'] is num) ? (delta['removed_count'] as num).toInt() : 0;
    final changedCount = (delta['changed_count'] is num) ? (delta['changed_count'] as num).toInt() : 0;

    if (newCount == 0 && removedCount == 0 && changedCount == 0) {
      return const SizedBox.shrink();
    }

    return Container(
      margin: const EdgeInsets.only(top: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.grey.shade300),
      ),
      child: Row(
        children: [
          Expanded(child: Text('New: $newCount', style: const TextStyle(fontWeight: FontWeight.w600))),
          Expanded(child: Text('Removed: $removedCount', style: const TextStyle(fontWeight: FontWeight.w600))),
          Expanded(child: Text('Changed: $changedCount', style: const TextStyle(fontWeight: FontWeight.w600))),
        ],
      ),
    );
  }

  @override
  void initState() {
    super.initState();
    // Initialize default choices (auto-confirm high confidence)
    for (var ingredient in widget.ingredients) {
      final detectedId = ingredient['id']?.toString() ?? '';
      if (detectedId.trim().isEmpty) {
        continue;
      }

      final confidenceCategory = ingredient['confidence_category'];
      if (confidenceCategory == 'high') {
        _userChoices[detectedId] = {
          'action': 'confirmed',
          'confirmed_name': ingredient['canonical_name'] ?? ingredient['detected_name'],
        };
      }
      
      // Initialize quantities from OCR detection or defaults
      final detectedQuantity = ingredient['quantity'];
      final detectedUnit = ingredient['unit'];
      final qcRaw = ingredient['quantity_confidence'];
      final double? quantityConfidence = (qcRaw is num)
          ? qcRaw.toDouble().clamp(0.0, 1.0)
          : double.tryParse(qcRaw?.toString() ?? '');
      
      if (detectedQuantity != null && detectedQuantity > 0) {
        final q = (detectedQuantity as num).toDouble();
        final u = (detectedUnit ?? 'pieces').toString();
        _quantities[detectedId] = q;
        _units[detectedId] = u;
        _suggestedQuantities[detectedId] = q;
        _suggestedUnits[detectedId] = u;

        // Low-confidence quantities must be explicitly confirmed/edited.
        final needsConfirm = (quantityConfidence == null) || (quantityConfidence < _lowQuantityConfidenceThreshold);
        _quantityConfirmed[detectedId] = !needsConfirm;
      } else {
        // Default values
        _quantities[detectedId] = 1.0;
        final smartUnits = getSmartUnitSuggestions(
          ingredient['category'],
          ingredient['detected_name'],
        );
        _units[detectedId] = smartUnits.first;

        // No auto-detected quantity => no gating.
        _suggestedQuantities[detectedId] = null;
        _suggestedUnits[detectedId] = null;
        _quantityConfirmed[detectedId] = true;
      }
    }
  }

  bool _quantityNeedsConfirmation(Map<String, dynamic> ingredient) {
    final detectedId = ingredient['id']?.toString() ?? '';
    if (detectedId.trim().isEmpty) return false;
    if ((_userChoices[detectedId]?['action'] ?? '') == 'rejected') return false;

    // Only gate when we had an auto-detected quantity.
    final suggestedQty = _suggestedQuantities[detectedId];
    return suggestedQty != null;
  }

  bool _hasUnconfirmedLowConfidenceQuantities() {
    for (final ing in widget.ingredients) {
      if (ing is! Map) continue;
      final ingredient = ing.cast<String, dynamic>();
      final detectedId = ingredient['id']?.toString() ?? '';
      if (detectedId.trim().isEmpty) continue;
      if ((_userChoices[detectedId]?['action'] ?? '') == 'rejected') continue;
      if (!_quantityNeedsConfirmation(ingredient)) continue;
      if (_quantityConfirmed[detectedId] != true) return true;
    }
    return false;
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
    if (_hasUnconfirmedLowConfidenceQuantities()) {
      _showError('Please confirm or edit low-confidence quantities first.');
      return;
    }

    setState(() {
      _isSubmitting = true;
    });

    try {
      // Build confirmations list
      final confirmations = _userChoices.entries.map((entry) {
        final action = entry.value['action'];
        final out = {
          'detected_id': entry.key,
          'action': action,
          if (entry.value['confirmed_name'] != null)
            'confirmed_name': entry.value['confirmed_name'],
          // Add quantity and unit
          if (_quantities.containsKey(entry.key))
            'quantity': _quantities[entry.key],
          if (_units.containsKey(entry.key))
            'unit': _units[entry.key],
        };

        // Attach barcode metadata only for user identity corrections.
        if (action == 'modified') {
          final bc = (widget.barcode ?? '').trim();
          if (bc.isNotEmpty) out['barcode'] = bc;
          final bcn = (widget.barcodeNameHint ?? '').trim();
          if (bcn.isNotEmpty) out['barcode_name_hint'] = bcn;
          if (widget.barcodeQuantityHint != null && widget.barcodeQuantityHint! > 0) {
            out['barcode_quantity_hint'] = widget.barcodeQuantityHint;
          }
          final bcu = (widget.barcodeUnitHint ?? '').trim();
          if (bcu.isNotEmpty) out['barcode_unit_hint'] = bcu;
        }

        return out;
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

          // Give a moment for the user to see confirmation before navigating away.
          await Future.delayed(const Duration(milliseconds: 900));

          // Immediately present recipe options (best-effort) so the user doesn't
          // need to press a separate "Generate recipes" button.
          try {
            final gate = await EntitlementsService.instance.tryConsumeSuggestionSession();
            if (!mounted) return;
            if (gate.allowed) {
              final apiClient = Provider.of<ApiClient>(context, listen: false);
              final profileState = Provider.of<ProfileState>(context, listen: false);
              final service = CookNowService();
              final options = await service.generateRecipeOptions(
                apiClient: apiClient,
                profileState: profileState,
                maxOptions: 5,
                avoidRecentRecipes: 3,
              );

              if (!mounted) return;
              if (options.isNotEmpty) {
                await Navigator.of(context).pushAndRemoveUntil(
                  MaterialPageRoute(
                    settings: const RouteSettings(name: '/recipe_options'),
                    builder: (_) => RecipeOptionsScreen(
                      recipes: options,
                      showIngredientMatch: true,
                      titleOverride: 'Meals you can cook tonight',
                      skipSuggestionSessionGate: true,
                    ),
                  ),
                  (route) => route.isFirst,
                );
                return;
              }
            }
          } catch (_) {
            // Best-effort only.
          }

          // Fallback: Navigate back to home (pop twice: confirmation + camera)
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

                _buildDeltaSummary(),
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
                onPressed: (_isSubmitting || _hasUnconfirmedLowConfidenceQuantities()) ? null : _submitConfirmations,
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

    final changeStatus = (ingredient['change_status'] ?? '').toString().toLowerCase();
    final prevQtyRaw = ingredient['previous_quantity'];
    final double? previousQuantity = (prevQtyRaw is num)
      ? prevQtyRaw.toDouble()
      : double.tryParse(prevQtyRaw?.toString() ?? '');
    final previousUnit = ingredient['previous_unit']?.toString();

    final needsQuantityConfirm = _quantityNeedsConfirmation(ingredient);
    final quantityConfirmed = _quantityConfirmed[detectedId] == true;
    final currentQty = _quantities[detectedId] ?? 1.0;
    final currentUnit = _units[detectedId] ?? 'pieces';

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
                if (changeStatus == 'new') ...[
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: Colors.blue.shade50,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: Colors.blue.shade200),
                    ),
                    child: const Text('NEW', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
                  ),
                ] else if (changeStatus == 'changed') ...[
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: Colors.orange.shade50,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: Colors.orange.shade200),
                    ),
                    child: const Text('CHANGED', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
                  ),
                ],
                _buildConfidenceIndicator(confidence, confidenceCategory),
              ],
            ),

            if (changeStatus == 'changed' && previousQuantity != null) ...[
              const SizedBox(height: 6),
              Text(
                'Was ${previousQuantity.toStringAsFixed(previousQuantity == previousQuantity.roundToDouble() ? 0 : 1)}${(previousUnit != null && previousUnit.trim().isNotEmpty) ? ' $previousUnit' : ''}',
                style: TextStyle(fontSize: 12, color: Colors.grey[700]),
              ),
            ],

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

                    if (needsQuantityConfirm && !quantityConfirmed) ...[
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              'Looks like ${currentQty.toStringAsFixed(currentQty == currentQty.roundToDouble() ? 0 : 1)} $currentUnit — correct?',
                              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                            ),
                          ),
                          TextButton(
                            onPressed: () {
                              setState(() {
                                _quantityConfirmed[detectedId] = true;
                              });
                            },
                            child: const Text('Correct'),
                          ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'If not, adjust the quantity below.',
                        style: TextStyle(fontSize: 12, color: Colors.grey[700]),
                      ),
                    ],

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

                          // Any edit counts as confirmation for low-confidence quantities.
                          if (needsQuantityConfirm) {
                            _quantityConfirmed[detectedId] = true;
                          }
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
                      onPressed: (needsQuantityConfirm && !quantityConfirmed)
                          ? null
                          : () => _handleConfirm(detectedId, canonicalName),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: isConfirmed || isModified ? Colors.green : Colors.black87,
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
          Text(
            displayName,
            overflow: TextOverflow.ellipsis,
          ),
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
      labelStyle: const TextStyle(fontSize: 13),
    );
  }
}
