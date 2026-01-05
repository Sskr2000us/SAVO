import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../ui/ui_principles.dart';
import '../services/api_client.dart';
import '../services/metrics_service.dart';

class ScanIngredientsScreen extends StatefulWidget {
  const ScanIngredientsScreen({super.key});

  @override
  State<ScanIngredientsScreen> createState() => _ScanIngredientsScreenState();
}

class _ScanIngredientsScreenState extends State<ScanIngredientsScreen> {
  final ImagePicker _picker = ImagePicker();

  bool _loading = false;
  XFile? _image;
  List<_Candidate> _candidates = [];
  String? _scanId;

  Future<void> _pickAndScan({required ImageSource source}) async {
    setState(() {
      _loading = true;
      _candidates = [];
      _image = null;
      _scanId = null;
    });

    try {
      final image = await _picker.pickImage(
        source: source,
        imageQuality: 85,
        maxWidth: 1600,
      );
      if (image == null) {
        setState(() => _loading = false);
        return;
      }

      setState(() => _image = image);

      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final response = await apiClient.postMultipart(
        '/api/scanning/analyze-image',
        file: image,
        fields: const {
          'scan_type': 'pantry',
        },
      );

      if (!mounted) return;

      final success = response['success'] == true;
      if (!success) {
        final msg = response['detail']?.toString() ?? response['error']?.toString() ?? 'Scan failed';

        final lower = msg.toLowerCase();
        if (lower.contains('too dark') || lower.contains('too blurry') || lower.contains('glare')) {
          fireAndForget(MetricsService.instance.recordEvent('pantry_scan_retake'));
        }

        _showError(msg);
        setState(() => _loading = false);
        return;
      }

      final scanId = response['scan_id']?.toString();
      final items = response['ingredients'];
      final parsed = <_Candidate>[];
      if (items is List) {
        for (final item in items) {
          if (item is Map<String, dynamic>) {
            parsed.add(_Candidate.fromDetectedJson(item));
          } else if (item is Map) {
            parsed.add(_Candidate.fromDetectedJson(item.cast<String, dynamic>()));
          }
        }
      }

      final message = response['message']?.toString();
      if (message != null && message.trim().isNotEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(message.trim())),
        );
      }

      setState(() {
        _scanId = (scanId != null && scanId.trim().isNotEmpty) ? scanId.trim() : null;
        _candidates = parsed;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      _showError(e.toString());
      setState(() => _loading = false);
    }
  }

  ({double? qty, String? unit}) _parseQtyUnit(String? input) {
    final raw = (input ?? '').trim();
    if (raw.isEmpty) return (qty: null, unit: null);

    final match = RegExp(r'^(\d+(?:\.\d+)?)\s*([a-zA-Z]+)?').firstMatch(raw);
    if (match == null) return (qty: null, unit: null);
    final qty = double.tryParse(match.group(1) ?? '');
    final unit = match.group(2);
    return (qty: qty, unit: unit);
  }

  Future<void> _confirmAndAddToInventory() async {
    if (_scanId == null || _scanId!.trim().isEmpty) {
      _showError('Missing scan id. Please rescan.');
      return;
    }
    if (_candidates.isEmpty) return;

    setState(() => _loading = true);

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);

      final confirmations = <Map<String, dynamic>>[];
      for (final c in _candidates) {
        if (c.detectedId.trim().isEmpty) {
          continue;
        }
        final name = c.ingredient.trim();
        if (!c.selected || name.isEmpty) {
          confirmations.add({'detected_id': c.detectedId, 'action': 'rejected'});
          continue;
        }

        final action = (name.toLowerCase() == c.originalIngredient.toLowerCase()) ? 'confirmed' : 'modified';
        final parsed = _parseQtyUnit(c.quantityEstimate);

        final payload = <String, dynamic>{
          'detected_id': c.detectedId,
          'action': action,
        };
        if (action == 'modified') {
          payload['confirmed_name'] = name;
        }
        if (parsed.qty != null) {
          payload['quantity'] = parsed.qty;
          if (parsed.unit != null && parsed.unit!.trim().isNotEmpty) {
            payload['unit'] = parsed.unit!.trim();
          }
        }

        confirmations.add(payload);
      }

      if (confirmations.isEmpty) {
        throw Exception('No valid detected items to confirm. Please rescan.');
      }

      final res = await apiClient.post('/api/scanning/confirm-ingredients', {
        'scan_id': _scanId,
        'confirmations': confirmations,
      });

      final msg = res['message']?.toString();
      final confirmed = res['confirmed_count']?.toString() ?? '0';
      final rejected = res['rejected_count']?.toString() ?? '0';

      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            (msg != null && msg.trim().isNotEmpty)
                ? msg.trim()
                : 'Saved pantry scan (confirmed: $confirmed, rejected: $rejected)',
          ),
        ),
      );
      Navigator.pop(context, true);
    } catch (e) {
      if (!mounted) return;
      _showError(e.toString());
      setState(() => _loading = false);
    }
  }

  void _showError(String message) {
    showDialog(
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

  Widget _buildConfidenceChip(double confidence) {
    final percentage = (confidence * 100).round();
    final Color color;
    final IconData icon;
    
    if (percentage >= 75) {
      color = Colors.green;
      icon = Icons.check_circle;
    } else if (percentage >= 50) {
      color = Colors.orange;
      icon = Icons.warning_amber_rounded;
    } else {
      color = Colors.red;
      icon = Icons.help_outline;
    }

    return Chip(
      avatar: Icon(icon, size: 18, color: color),
      label: Text(
        '$percentage%',
        style: TextStyle(
          color: color,
          fontWeight: FontWeight.bold,
          fontSize: 13,
        ),
      ),
      backgroundColor: color.withOpacity(0.1),
      side: BorderSide(color: color.withOpacity(0.3)),
      padding: const EdgeInsets.symmetric(horizontal: 4),
      visualDensity: VisualDensity.compact,
    );
  }

  @override
  Widget build(BuildContext context) {
    if (kDebugMode || kProfileMode) {
      // v1: maxChoices=3. Scan entry presents up to 2 capture choices.
      SavoUiGuards.warnIfTooManyChoices(
        screen: 'ScanIngredientsScreen',
        surface: 'Capture method',
        choices: 2,
      );

      // v1: mandatory AI confirmation. This screen always requires user review
      // (select items) before any inventory write.
      SavoUiGuards.warnIfAiConfirmationNotExplicit(
        flow: 'SnapPantry',
        surface: 'Review candidates before save',
        hasExplicitReviewStep: true,
      );
    }

    final canScan = !_loading;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Scan Ingredients'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Wrap(
              spacing: 12,
              runSpacing: 12,
              children: [
                FilledButton.icon(
                  onPressed: canScan
                      ? () => _pickAndScan(
                            source: kIsWeb ? ImageSource.gallery : ImageSource.camera,
                          )
                      : null,
                  icon: Icon(kIsWeb ? Icons.upload_file : Icons.photo_camera),
                  label: Text(kIsWeb ? 'Upload Photo' : 'Take Photo'),
                ),
                OutlinedButton.icon(
                  onPressed: canScan ? () => _pickAndScan(source: ImageSource.gallery) : null,
                  icon: const Icon(Icons.photo_library),
                  label: const Text('Pick From Gallery'),
                ),
              ],
            ),
            const SizedBox(height: 16),
            if (_loading) const LinearProgressIndicator(),
            const SizedBox(height: 16),
            Expanded(
              child: _candidates.isEmpty
                  ? Center(
                      child: Text(
                        _image == null ? 'Select a photo to scan.' : 'No ingredients detected.',
                        style: Theme.of(context).textTheme.bodyMedium,
                      ),
                    )
                  : ListView.separated(
                      itemCount: _candidates.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 12),
                      itemBuilder: (context, index) {
                        final c = _candidates[index];
                        return Card(
                          child: Padding(
                            padding: const EdgeInsets.all(12),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.stretch,
                              children: [
                                Row(
                                  children: [
                                    Checkbox(
                                      value: c.selected,
                                      onChanged: (v) {
                                        setState(() {
                                          c.selected = v ?? false;
                                        });
                                      },
                                    ),
                                    Expanded(
                                      child: TextField(
                                        controller: c.ingredientController,
                                        decoration: const InputDecoration(
                                          labelText: 'Ingredient',
                                        ),
                                        onChanged: (v) => c.ingredient = v,
                                      ),
                                    ),
                                    const SizedBox(width: 12),
                                    _buildConfidenceChip(c.confidence),
                                  ],
                                ),
                                const SizedBox(height: 8),
                                Row(
                                  children: [
                                    Expanded(
                                      child: TextField(
                                        controller: c.quantityController,
                                        decoration: const InputDecoration(
                                          labelText: 'Quantity (optional)',
                                        ),
                                        onChanged: (v) => c.quantityEstimate = v,
                                      ),
                                    ),
                                    const SizedBox(width: 8),
                                    IconButton(
                                      icon: const Icon(Icons.delete_outline),
                                      onPressed: () {
                                        setState(() {
                                          _candidates.removeAt(index);
                                        });
                                      },
                                      tooltip: 'Remove',
                                      color: Colors.red,
                                    ),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        );
                      },
                    ),
            ),
            const SizedBox(height: 12),
            FilledButton(
              onPressed: (!_loading && _candidates.isNotEmpty && _scanId != null)
                  ? _confirmAndAddToInventory
                  : null,
              child: const Text('Confirm & Add to Inventory'),
            ),
          ],
        ),
      ),
    );
  }
}

class _Candidate {
  final String detectedId;
  String ingredient;
  final String originalIngredient;
  String? quantityEstimate;
  double confidence;
  String? storageHint;
  bool selected;

  final TextEditingController ingredientController;
  final TextEditingController quantityController;

  _Candidate({
    required this.detectedId,
    required this.ingredient,
    required this.originalIngredient,
    required this.quantityEstimate,
    required this.confidence,
    required this.storageHint,
    required this.selected,
  })  : ingredientController = TextEditingController(text: ingredient),
        quantityController = TextEditingController(text: quantityEstimate ?? '');

  factory _Candidate.fromDetectedJson(Map<String, dynamic> json) {
    final detectedId = (json['id'] ?? '').toString();
    final detectedName = (json['detected_name'] ?? '').toString();

    final quantity = json['quantity'];
    final unit = json['unit']?.toString();
    final quantityEstimate = (quantity is num)
        ? '${quantity.toDouble()}${(unit != null && unit.trim().isNotEmpty) ? ' $unit' : ''}'
        : null;

    final confidenceRaw = json['confidence'];
    final confidence = (confidenceRaw is num) ? confidenceRaw.toDouble() : 0.0;
    final storageHint = null;

    return _Candidate(
      detectedId: detectedId,
      ingredient: detectedName,
      originalIngredient: detectedName,
      quantityEstimate: quantityEstimate,
      confidence: confidence.clamp(0.0, 1.0),
      storageHint: storageHint,
      selected: true,
    );
  }
}
