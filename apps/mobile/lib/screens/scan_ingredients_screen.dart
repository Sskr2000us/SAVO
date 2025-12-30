import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../services/api_client.dart';

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

  Future<void> _pickAndScan({required ImageSource source}) async {
    setState(() {
      _loading = true;
      _candidates = [];
      _image = null;
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
        '/inventory/scan',
        file: image,
        fields: const {},
      );

      if (!mounted) return;

      final status = response['status'];
      if (status != 'ok') {
        final msg = response['error_message']?.toString() ?? 'Scan failed';
        _showError(msg);
        setState(() => _loading = false);
        return;
      }

      final items = response['scanned_items'];
      final parsed = <_Candidate>[];
      if (items is List) {
        for (final item in items) {
          if (item is Map<String, dynamic>) {
            parsed.add(_Candidate.fromJson(item));
          } else if (item is Map) {
            parsed.add(_Candidate.fromJson(item.cast<String, dynamic>()));
          }
        }
      }

      setState(() {
        _candidates = parsed;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      _showError(e.toString());
      setState(() => _loading = false);
    }
  }

  Future<void> _normalizeAndAddToInventory() async {
    if (_candidates.isEmpty) return;

    setState(() => _loading = true);

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);

      final rawItems = _candidates
          .where((c) => c.ingredient.trim().isNotEmpty)
          .map((c) => {
                'display_name': c.ingredient.trim(),
                'quantity_estimate': c.quantityEstimate?.trim(),
                'confidence': c.confidence,
                'storage_hint': c.storageHint,
              })
          .toList();

      final normalized = await apiClient.post('/inventory/normalize', {
        'raw_items': rawItems,
        'measurement_system': 'metric',
        'output_language': 'en',
      });

      final normItems = normalized['normalized_inventory'];
      if (normItems is! List) {
        throw Exception('Normalization response missing normalized_inventory');
      }

      for (final item in normItems) {
        if (item is! Map) continue;
        final json = item.cast<String, dynamic>();

        await apiClient.post('/inventory', {
          'canonical_name': json['canonical_name'] ?? '',
          'display_name': json['display_name'],
          'quantity': (json['quantity'] is num) ? (json['quantity'] as num).toDouble() : 1.0,
          'unit': json['unit'] ?? 'pcs',
          'state': json['state'] ?? 'raw',
          'storage': json['storage'] ?? 'pantry',
          'freshness_days_remaining': (json['freshness_days_remaining'] is num)
              ? (json['freshness_days_remaining'] as num).round()
              : 7,
          'notes': null,
        });
      }

      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Added scanned items to inventory')),
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

  @override
  Widget build(BuildContext context) {
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
                                    SizedBox(
                                      width: 110,
                                      child: Text(
                                        '${(c.confidence * 100).round()}%',
                                        textAlign: TextAlign.end,
                                        style: Theme.of(context).textTheme.labelLarge,
                                      ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 8),
                                TextField(
                                  controller: c.quantityController,
                                  decoration: const InputDecoration(
                                    labelText: 'Quantity (optional)',
                                  ),
                                  onChanged: (v) => c.quantityEstimate = v,
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
              onPressed: (!_loading && _candidates.isNotEmpty) ? _normalizeAndAddToInventory : null,
              child: const Text('Confirm & Add to Inventory'),
            ),
          ],
        ),
      ),
    );
  }
}

class _Candidate {
  String ingredient;
  String? quantityEstimate;
  double confidence;
  String? storageHint;

  final TextEditingController ingredientController;
  final TextEditingController quantityController;

  _Candidate({
    required this.ingredient,
    required this.quantityEstimate,
    required this.confidence,
    required this.storageHint,
  })  : ingredientController = TextEditingController(text: ingredient),
        quantityController = TextEditingController(text: quantityEstimate ?? '');

  factory _Candidate.fromJson(Map<String, dynamic> json) {
    final ingredient = (json['ingredient'] ?? '').toString();
    final quantityEstimate = json['quantity_estimate']?.toString();
    final confidenceRaw = json['confidence'];
    final confidence = (confidenceRaw is num) ? confidenceRaw.toDouble() : 0.0;
    final storageHint = json['storage_hint']?.toString();

    return _Candidate(
      ingredient: ingredient,
      quantityEstimate: quantityEstimate,
      confidence: confidence.clamp(0.0, 1.0),
      storageHint: storageHint,
    );
  }
}
