import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../ui/ui_principles.dart';
import '../services/api_client.dart';
import '../services/metrics_service.dart';
import 'scanning/guided_scan_screen.dart';

class ScanIngredientsScreen extends StatefulWidget {
  const ScanIngredientsScreen({super.key});

  @override
  State<ScanIngredientsScreen> createState() => _ScanIngredientsScreenState();
}

class _ScanIngredientsScreenState extends State<ScanIngredientsScreen> {
  final ImagePicker _picker = ImagePicker();
  final FocusNode _quantityFocus = FocusNode();

  static const double _lowQuantityConfidenceThreshold = 0.70;

  bool _loading = false;
  XFile? _image;
  List<_Candidate> _candidates = [];
  String? _scanId;
  Map<String, dynamic>? _deltaSummary;

  int _currentIndex = 0;
  int _savedCount = 0;
  int _skippedCount = 0;

  bool _quantityNeedsConfirmation(_Candidate c) {
    final hasSuggestion = (c.quantityController.text.trim().isNotEmpty);
    if (!hasSuggestion) return false;

    // If quantity confidence is missing, treat as low confidence to be safe.
    final qc = c.quantityConfidence;
    return qc == null || qc < _lowQuantityConfidenceThreshold;
  }

  Future<void> _editQuantityDialog(_Candidate c) async {
    final initial = c.quantityController.text.trim();
    final controller = TextEditingController(text: initial);

    final res = await showDialog<String>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Edit quantity'),
        content: TextField(
          controller: controller,
          autofocus: true,
          decoration: const InputDecoration(
            labelText: 'e.g., 500 g, 2 kg, 3 pieces',
            border: OutlineInputBorder(),
          ),
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, controller.text.trim()),
            child: const Text('Save'),
          ),
        ],
      ),
    );

    if (!mounted) return;
    if (res == null) return;

    setState(() {
      c.quantityController.text = res;
      c.quantityEstimate = res;
      c.quantityConfirmed = true;
    });
  }

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
      _deltaSummary = null;

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
      final meta = response['metadata'];
      Map<String, dynamic>? delta;
      if (meta is Map) {
        final d = meta['delta'];
        if (d is Map<String, dynamic>) {
          delta = d;
        } else if (d is Map) {
          delta = d.cast<String, dynamic>();
        }
      }
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
        _deltaSummary = delta;
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

  Future<void> _guidedScan() async {
    setState(() {
      _loading = true;
      _candidates = [];
      _image = null;
      _scanId = null;
      _deltaSummary = null;

      _currentIndex = 0;
      _savedCount = 0;
      _skippedCount = 0;
    });

    try {
      final res = await Navigator.of(context).push<GuidedScanResult>(
        MaterialPageRoute(
          builder: (_) => const GuidedScanScreen(scanType: 'pantry'),
        ),
      );

      if (!mounted) return;
      if (res == null) {
        setState(() => _loading = false);
        return;
      }

      final response = res.response;

      final success = response['success'] == true;
      if (!success) {
        final detail = response['detail'];
        final msg = (detail is Map)
            ? (detail['message']?.toString() ?? detail.toString())
            : (response['detail']?.toString() ?? response['error']?.toString() ?? 'Scan failed');
        _showError(msg);
        setState(() => _loading = false);
        return;
      }

      final scanId = response['scan_id']?.toString();
      final meta = response['metadata'];
      Map<String, dynamic>? delta;
      if (meta is Map) {
        final d = meta['delta'];
        if (d is Map<String, dynamic>) {
          delta = d;
        } else if (d is Map) {
          delta = d.cast<String, dynamic>();
        }
      }
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
        _deltaSummary = delta;
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
      if (save && _quantityNeedsConfirmation(c) && !c.quantityConfirmed) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Confirm or edit the quantity first.')),
          );
        }
        setState(() => _loading = false);
        return;
      }

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

  @override
  void dispose() {
    _quantityFocus.dispose();
    super.dispose();
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

  Widget _buildFormChip(String? itemForm) {
    final raw = (itemForm ?? '').trim().toLowerCase();
    if (raw.isEmpty || raw == 'unknown') return const SizedBox.shrink();

    final label = raw == 'packaged' ? 'Packaged' : (raw == 'loose' ? 'Loose' : raw);
    return Chip(
      label: Text(label, style: const TextStyle(fontSize: 13)),
      visualDensity: VisualDensity.compact,
    );
  }

  Widget _buildDeltaSummary() {
    final delta = _deltaSummary;
    if (delta == null) return const SizedBox.shrink();

    final newCount = (delta['new_count'] is num) ? (delta['new_count'] as num).toInt() : 0;
    final removedCount = (delta['removed_count'] is num) ? (delta['removed_count'] as num).toInt() : 0;
    final changedCount = (delta['changed_count'] is num) ? (delta['changed_count'] as num).toInt() : 0;

    if (newCount == 0 && removedCount == 0 && changedCount == 0) {
      return const SizedBox.shrink();
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            Expanded(child: Text('New: $newCount')),
            Expanded(child: Text('Removed: $removedCount')),
            Expanded(child: Text('Changed: $changedCount')),
          ],
        ),
      ),
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
                  if ((current.changeStatus ?? '').toLowerCase() == 'new') ...[
                    const Chip(label: Text('NEW'), visualDensity: VisualDensity.compact),
                    const SizedBox(width: 8),
                  ] else if ((current.changeStatus ?? '').toLowerCase() == 'changed') ...[
                    const Chip(label: Text('CHANGED'), visualDensity: VisualDensity.compact),
                    const SizedBox(width: 8),
                  ],
                  _buildFormChip(current.itemForm),
                  const SizedBox(width: 8),
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
              if (current.quantityController.text.trim().isNotEmpty) ...[
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        _quantityNeedsConfirmation(current) && !current.quantityConfirmed
                            ? 'Looks like ${current.quantityController.text.trim()} — correct?'
                            : 'Looks like ${current.quantityController.text.trim()}',
                        style: Theme.of(context).textTheme.bodyMedium,
                      ),
                    ),
                    if (_quantityNeedsConfirmation(current) && !current.quantityConfirmed) ...[
                      TextButton(
                        onPressed: _loading
                            ? null
                            : () => setState(() {
                                  current.quantityConfirmed = true;
                                }),
                        child: const Text('Correct'),
                      ),
                      TextButton(
                        onPressed: _loading ? null : () => _editQuantityDialog(current),
                        child: const Text('Edit'),
                      ),
                    ] else ...[
                      TextButton(
                        onPressed: _loading ? null : () => _editQuantityDialog(current),
                        child: const Text('Edit'),
                      ),
                    ],
                  ],
                ),
                if ((current.changeStatus ?? '').toLowerCase() == 'changed' && current.previousQuantity != null) ...[
                  const SizedBox(height: 6),
                  Text(
                    'Was ${current.previousQuantity}${(current.previousUnit != null && current.previousUnit!.trim().isNotEmpty) ? ' ${current.previousUnit}' : ''}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
                const SizedBox(height: 10),
              ],
              TextField(
                controller: current.quantityController,
                focusNode: _quantityFocus,
                enabled: !_loading,
                decoration: InputDecoration(
                  labelText: _quantityNeedsConfirmation(current)
                      ? 'Quantity (required review)'
                      : 'Quantity (optional, e.g., 2 kg)',
                  border: const OutlineInputBorder(),
                ),
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                onChanged: (v) {
                  current.quantityEstimate = v;
                  // Any edit counts as confirmation for low-confidence quantities.
                  if (_quantityNeedsConfirmation(current)) {
                    current.quantityConfirmed = true;
                  }
                },
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
                      onPressed: (_loading || (_quantityNeedsConfirmation(current) && !current.quantityConfirmed))
                          ? null
                          : () => _confirmCurrentAndAdvance(save: true),
                      child: const Text('Save to inventory'),
                    ),
                  ),
                ],
              ),
              if (_quantityNeedsConfirmation(current) && !current.quantityConfirmed) ...[
                const SizedBox(height: 8),
                Text(
                  'Please confirm or edit the quantity before saving.',
                  style: Theme.of(context).textTheme.bodySmall,
                  textAlign: TextAlign.center,
                ),
              ],
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
            if (hasResults) ...[
              _buildDeltaSummary(),
              const SizedBox(height: 12),
            ],
            Wrap(
              spacing: 12,
              runSpacing: 12,
              children: [
                FilledButton.icon(
                  onPressed: canScan
                      ? () => (kIsWeb ? _pickAndScan(source: ImageSource.gallery) : _guidedScan())
                      : null,
                  icon: Icon(kIsWeb ? Icons.upload_file : Icons.photo_camera),
                  label: Text(kIsWeb ? 'Upload Photo' : 'Guided Scan'),
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
  final String? originalQuantityEstimate;
  double confidence;
  double? quantityConfidence;
  String? quantitySource;
  String? itemForm;
  String? changeStatus;
  double? previousQuantity;
  String? previousUnit;
  String? storageHint;
  bool selected;

  bool processed;
  bool quantityConfirmed;

  final TextEditingController ingredientController;
  final TextEditingController quantityController;

  _Candidate({
    required this.detectedId,
    required this.ingredient,
    required this.originalIngredient,
    required this.quantityEstimate,
    required this.originalQuantityEstimate,
    required this.confidence,
    required this.quantityConfidence,
    required this.quantitySource,
    required this.itemForm,
    required this.changeStatus,
    required this.previousQuantity,
    required this.previousUnit,
    required this.storageHint,
    required this.selected,
    required this.processed,
    required this.quantityConfirmed,
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

    final qcRaw = json['quantity_confidence'];
    final quantityConfidence = (qcRaw is num) ? qcRaw.toDouble().clamp(0.0, 1.0) : null;
    final quantitySource = json['quantity_source']?.toString();
    final itemForm = json['item_form']?.toString();

    final changeStatus = json['change_status']?.toString();
    final prevQtyRaw = json['previous_quantity'];
    final previousQuantity = (prevQtyRaw is num) ? prevQtyRaw.toDouble() : double.tryParse(prevQtyRaw?.toString() ?? '');
    final previousUnit = json['previous_unit']?.toString();

    // Low-confidence quantities must be explicitly confirmed/edited.
    final quantityConfirmed = (quantityEstimate == null || quantityEstimate.trim().isEmpty)
        ? true
        : (quantityConfidence != null && quantityConfidence >= _ScanIngredientsScreenState._lowQuantityConfidenceThreshold);

    final storageHint = null;

    return _Candidate(
      detectedId: detectedId,
      ingredient: detectedName,
      originalIngredient: detectedName,
      quantityEstimate: quantityEstimate,
      originalQuantityEstimate: quantityEstimate,
      confidence: confidence.clamp(0.0, 1.0),
      quantityConfidence: quantityConfidence,
      quantitySource: quantitySource,
      itemForm: itemForm,
      changeStatus: changeStatus,
      previousQuantity: previousQuantity,
      previousUnit: previousUnit,
      storageHint: storageHint,
      selected: true,
      processed: false,
      quantityConfirmed: quantityConfirmed,
    );
  }
}
