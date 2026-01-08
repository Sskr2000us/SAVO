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

  int _currentIndex = 0;
  int _savedCount = 0;
  int _skippedCount = 0;

  int? _nextPendingIndex({int startAt = 0}) {
    if (_candidates.isEmpty) return null;
    for (int i = startAt; i < _candidates.length; i++) {
      if (!_candidates[i].processed) return i;
    }
    for (int i = 0; i < startAt && i < _candidates.length; i++) {
      if (!_candidates[i].processed) return i;
    }
    return null;
  }

  void _jumpToNextPending() {
    final next = _nextPendingIndex(startAt: _currentIndex);
    if (next == null) return;
    setState(() => _currentIndex = next);
  }

  Future<void> _pickAndScan({required ImageSource source}) async {
    setState(() {
      _loading = true;
      _candidates = [];
      _image = null;
      _scanId = null;

      _currentIndex = 0;
      _savedCount = 0;
      _skippedCount = 0;
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
        String msg = 'Scan failed';
        final detail = response['detail'];
        if (detail is Map) {
          final m = detail['message']?.toString();
          if (m != null && m.trim().isNotEmpty) {
            msg = m.trim();
          } else {
            msg = detail.toString();
          }
        } else {
          msg = response['detail']?.toString() ?? response['error']?.toString() ?? 'Scan failed';
        }

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

        _currentIndex = 0;
        _savedCount = 0;
        _skippedCount = 0;
      });

      _jumpToNextPending();
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

  Future<void> _confirmCurrentAndAdvance({required bool save}) async {
    if (_scanId == null || _scanId!.trim().isEmpty) {
      _showError('Missing scan id. Please rescan.');
      return;
    }
    if (_candidates.isEmpty) return;

    final pendingIndex = _nextPendingIndex(startAt: _currentIndex);
    if (pendingIndex == null) {
      if (mounted) Navigator.pop(context, _savedCount > 0);
      return;
    }

    final c = _candidates[pendingIndex];
    if (c.detectedId.trim().isEmpty) {
      setState(() {
        c.processed = true;
        _skippedCount += 1;
      });
      _jumpToNextPending();
      return;
    }

    setState(() {
      _loading = true;
      _currentIndex = pendingIndex;
    });

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);

      final name = c.ingredientController.text.trim();
      final parsed = _parseQtyUnit(c.quantityController.text);

      final Map<String, dynamic> confirmation = {
        'detected_id': c.detectedId,
        'action': 'rejected',
      };

      if (save && name.isNotEmpty) {
        final original = c.originalIngredient.trim().toLowerCase();
        final edited = name.toLowerCase();
        if (edited != original) {
          confirmation['action'] = 'modified';
          confirmation['confirmed_name'] = name;
        } else {
          confirmation['action'] = 'confirmed';
        }

        if (parsed.qty != null) {
          confirmation['quantity'] = parsed.qty;
          if (parsed.unit != null && parsed.unit!.trim().isNotEmpty) {
            confirmation['unit'] = parsed.unit!.trim();
          }
        }
      }

      final res = await apiClient.post('/api/scanning/confirm-ingredients', {
        'scan_id': _scanId,
        'confirmations': [confirmation],
      });

      if (!mounted) return;

      final msg = res['message']?.toString();

      setState(() {
        c.processed = true;
        if (save && name.isNotEmpty) {
          _savedCount += 1;
        } else {
          _skippedCount += 1;
        }
      });

      // If the user chose Save, jump back to Inventory immediately.
      // InventoryScreen already reloads when this screen returns `true`.
      if (save && name.isNotEmpty) {
        Navigator.pop(context, true);
        return;
      }

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            (msg != null && msg.trim().isNotEmpty)
                ? msg.trim()
                : (save ? 'Saved to inventory' : 'Skipped item'),
          ),
        ),
      );

      final next = _nextPendingIndex(startAt: _currentIndex + 1);
      if (next == null) {
        Navigator.pop(context, _savedCount > 0);
        return;
      }

      setState(() {
        _loading = false;
        _currentIndex = next;
      });
    } catch (e) {
      if (!mounted) return;
      _showError(e.toString());
      setState(() => _loading = false);
    }
  }

  void _finish() {
    Navigator.pop(context, _savedCount > 0);
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

    final hasResults = _scanId != null && _candidates.isNotEmpty;
    final int? pendingIndex = hasResults ? _nextPendingIndex(startAt: _currentIndex) : null;
    final _Candidate? current = (pendingIndex != null) ? _candidates[pendingIndex] : null;

    final Widget scanContent;
    if (!hasResults) {
      scanContent = Center(
        child: Text(
          _image == null ? 'Select a photo to scan.' : 'No ingredients detected.',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
      );
    } else if (pendingIndex == null || current == null) {
      scanContent = Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'All items reviewed.',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            FilledButton(
              onPressed: _loading ? null : _finish,
              child: const Text('Back to inventory'),
            ),
          ],
        ),
      );
    } else {
      scanContent = Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      'Item ${pendingIndex + 1} of ${_candidates.length}',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                  ),
                  _buildConfidenceChip(current.confidence),
                ],
              ),
              const SizedBox(height: 12),
              TextField(
                controller: current.ingredientController,
                enabled: !_loading,
                decoration: const InputDecoration(
                  labelText: 'Ingredient',
                  border: OutlineInputBorder(),
                ),
                onChanged: (v) => current.ingredient = v,
              ),
              const SizedBox(height: 10),
              TextField(
                controller: current.quantityController,
                enabled: !_loading,
                decoration: const InputDecoration(
                  labelText: 'Quantity (optional, e.g., 2 kg)',
                  border: OutlineInputBorder(),
                ),
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                onChanged: (v) => current.quantityEstimate = v,
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: _loading ? null : () => _confirmCurrentAndAdvance(save: false),
                      child: const Text('Skip'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: FilledButton(
                      onPressed: _loading ? null : () => _confirmCurrentAndAdvance(save: true),
                      child: const Text('Save to inventory'),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                'Saved: $_savedCount  Skipped: $_skippedCount',
                style: Theme.of(context).textTheme.bodySmall,
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Scan Ingredients'),
        actions: [
          if (hasResults)
            TextButton(
              onPressed: _loading ? null : _finish,
              child: const Text('Done'),
            ),
        ],
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
              child: scanContent,
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

  bool processed;

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
    required this.processed,
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
      processed: false,
    );
  }
}
