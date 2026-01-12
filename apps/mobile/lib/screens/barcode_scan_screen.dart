import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:provider/provider.dart';

import '../services/api_client.dart';

class BarcodeScanScreen extends StatefulWidget {
  const BarcodeScanScreen({super.key});

  @override
  State<BarcodeScanScreen> createState() => _BarcodeScanScreenState();
}

class _BarcodeScanScreenState extends State<BarcodeScanScreen> {
  final MobileScannerController _controller = MobileScannerController(
    detectionSpeed: DetectionSpeed.normal,
    facing: CameraFacing.back,
    torchEnabled: false,
  );

  bool _handling = false;

  static const List<String> _categoryOptions = [
    'vegetables',
    'fruits',
    'dairy',
    'proteins',
    'condiments',
    'beverages',
    'leftovers',
    'grains',
    'pulses',
    'flours',
    'spices',
    'powders',
    'oils',
    'snacks',
    'canned',
    'baking',
    'frozen_vegetables',
    'frozen_fruits',
    'meat_seafood',
    'prepared_meals',
    'desserts',
    'produce',
    'breads',
    'other',
  ];

  static String _prettyToken(String raw) {
    final s = raw.trim().replaceAll('_', ' ');
    if (s.isEmpty) return s;
    return s.split(RegExp(r'\s+')).map((w) {
      if (w.isEmpty) return w;
      return w[0].toUpperCase() + w.substring(1);
    }).join(' ');
  }

  static String? _cleanOptional(String? raw) {
    final trimmed = raw?.trim();
    if (trimmed == null || trimmed.isEmpty) return null;
    return trimmed;
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _handleBarcode(String raw) async {
    if (_handling) return;
    final digits = raw.replaceAll(RegExp(r'\D'), '').trim();
    if (digits.isEmpty) return;

    setState(() => _handling = true);

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final res = await apiClient.get('/barcode/lookup/$digits');

      if (!mounted) return;

      if (res is! Map) {
        throw Exception('Unexpected barcode lookup response');
      }

      final success = res['success'] == true;
      if (!success) {
        throw Exception('Barcode not found');
      }

      final productName = (res['product_name'] ?? '').toString().trim();
      final brand = (res['brand'] ?? '').toString().trim();
      final imageUrl = (res['image_url'] ?? '').toString().trim();
      final packageSizeText = (res['package_size_text'] ?? '').toString().trim();

      // Inventory quantity defaults:
      // - if package size looks like a single net weight/volume, store that as quantity/unit
      // - otherwise default to 1 pcs and put pack text in package_size_text.
      final pkgQty = res['package_quantity'];
      final pkgUnit = (res['package_unit'] ?? '').toString().trim();

      double quantity = 1.0;
      String unit = 'pcs';

      if (pkgQty is num && pkgQty > 0 && pkgUnit.isNotEmpty) {
        quantity = pkgQty.toDouble();
        unit = pkgUnit;
      }

      final nameForInventory = productName.isNotEmpty
          ? productName
          : (brand.isNotEmpty ? brand : digits);

      final confirm = await showDialog<bool>(
        context: context,
        builder: (_) {
          final nameController = TextEditingController(text: nameForInventory);
          final qtyController = TextEditingController(text: quantity.toString());
          final unitController = TextEditingController(text: unit);

          String? category;
          final subcategoryController = TextEditingController();

          // Image is mandatory. Prefer product image from lookup; otherwise require a user photo upload.
          String? chosenImageUrl = imageUrl.isNotEmpty ? imageUrl : null;
          bool uploadingImage = false;

          return AlertDialog(
            title: const Text('Add to inventory'),
            content: StatefulBuilder(
              builder: (context, setDialogState) {
                final canAdd = (chosenImageUrl != null && chosenImageUrl!.trim().isNotEmpty) && !uploadingImage;

                Widget imageWidget;
                if (chosenImageUrl != null && chosenImageUrl!.trim().isNotEmpty) {
                  imageWidget = ClipRRect(
                    borderRadius: BorderRadius.circular(12),
                    child: Image.network(
                      chosenImageUrl!,
                      height: 140,
                      width: double.infinity,
                      fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) {
                        return Container(
                          height: 140,
                          width: double.infinity,
                          color: Colors.grey.shade200,
                          alignment: Alignment.center,
                          child: const Text('Image unavailable'),
                        );
                      },
                    ),
                  );
                } else {
                  imageWidget = Container(
                    height: 140,
                    width: double.infinity,
                    decoration: BoxDecoration(
                      color: Colors.grey.shade100,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: Colors.grey.shade300),
                    ),
                    alignment: Alignment.center,
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.photo_outlined, size: 28, color: Colors.grey),
                        const SizedBox(height: 6),
                        Text(
                          'Package photo required',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                    ),
                  );
                }

                return SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      imageWidget,
                      const SizedBox(height: 8),
                      OutlinedButton.icon(
                        onPressed: uploadingImage
                            ? null
                            : () async {
                                try {
                                  setDialogState(() => uploadingImage = true);
                                  final picker = ImagePicker();
                                  final XFile? photo = await picker.pickImage(
                                    source: ImageSource.camera,
                                    maxWidth: 1920,
                                    maxHeight: 1080,
                                    imageQuality: 85,
                                  );
                                  if (photo == null) {
                                    setDialogState(() => uploadingImage = false);
                                    return;
                                  }

                                  final uploadRes = await apiClient.postMultipart(
                                    '/inventory-db/upload-image',
                                    file: photo,
                                    fieldName: 'image',
                                  );

                                  final url = (uploadRes['image_url'] ?? '').toString().trim();
                                  if (url.isEmpty) {
                                    throw Exception('Upload succeeded but image_url missing');
                                  }

                                  setDialogState(() {
                                    chosenImageUrl = url;
                                    uploadingImage = false;
                                  });
                                } catch (e) {
                                  setDialogState(() => uploadingImage = false);
                                  if (!context.mounted) return;
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    SnackBar(content: Text('Failed to upload photo: $e')),
                                  );
                                }
                              },
                        icon: uploadingImage
                            ? const SizedBox(
                                width: 16,
                                height: 16,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Icon(Icons.photo_camera_outlined),
                        label: Text(uploadingImage ? 'Uploading…' : 'Capture package photo'),
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: nameController,
                        decoration: const InputDecoration(labelText: 'Name'),
                      ),
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          Expanded(
                            child: TextField(
                              controller: qtyController,
                              keyboardType: const TextInputType.numberWithOptions(decimal: true),
                              decoration: const InputDecoration(labelText: 'Quantity'),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: TextField(
                              controller: unitController,
                              decoration: const InputDecoration(labelText: 'Unit'),
                            ),
                          ),
                        ],
                      ),
                      if (packageSizeText.isNotEmpty) ...[
                        const SizedBox(height: 8),
                        Align(
                          alignment: Alignment.centerLeft,
                          child: Text(
                            'Package: $packageSizeText',
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                        ),
                      ],
                      const SizedBox(height: 12),
                      DropdownButtonFormField<String?>(
                        value: category,
                        decoration: const InputDecoration(
                          labelText: 'Category (recommended)',
                        ),
                        items: [
                          const DropdownMenuItem<String?>(value: null, child: Text('Uncategorized')),
                          ..._categoryOptions.map(
                            (c) => DropdownMenuItem<String?>(value: c, child: Text(_prettyToken(c))),
                          ),
                        ],
                        onChanged: (value) {
                          setDialogState(() {
                            category = value;
                          });
                        },
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: subcategoryController,
                        decoration: const InputDecoration(
                          labelText: 'Subcategory (optional)',
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        'Note: You can change category later in Pantry/Inventory.',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                      if (!canAdd) ...[
                        const SizedBox(height: 8),
                        Text(
                          'Please provide a package photo to continue.',
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.red),
                        ),
                      ],
                    ],
                  ),
                );
              },
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: () async {
                  if (chosenImageUrl == null || chosenImageUrl!.trim().isEmpty) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Package photo is required.')),
                    );
                    return;
                  }

                  final q = double.tryParse(qtyController.text.trim()) ?? 1.0;
                  final u = unitController.text.trim().isEmpty ? 'pcs' : unitController.text.trim();

                  await apiClient.post('/inventory-db/items', {
                    'canonical_name': nameController.text.trim(),
                    'display_name': nameController.text.trim(),
                    'category': _cleanOptional(category),
                    'subcategory': _cleanOptional(subcategoryController.text),
                    'quantity': q,
                    'unit': u,
                    'storage_location': 'pantry',
                    'item_state': 'raw',
                    'source': 'barcode',
                    'scan_confidence': 1.0,
                    'barcode': digits,
                    'product_name': productName.isNotEmpty ? productName : null,
                    'brand': brand.isNotEmpty ? brand : null,
                    'image_url': chosenImageUrl,
                    'package_size_text': packageSizeText.isNotEmpty ? packageSizeText : null,
                  });

                  if (context.mounted) {
                    Navigator.pop(context, true);
                  }
                },
                child: const Text('Add'),
              ),
            ],
          );
        },
      );

      if (!mounted) return;
      if (confirm == true) {
        Navigator.pop(context, true);
      } else {
        setState(() => _handling = false);
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Barcode scan failed: $e')),
      );
      setState(() => _handling = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (kIsWeb) {
      return Scaffold(
        appBar: AppBar(title: const Text('Barcode Scan')),
        body: const Center(child: Text('Barcode scanning is not available on web.')),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Barcode Scan'),
        actions: [
          IconButton(
            icon: const Icon(Icons.flash_on),
            onPressed: () => _controller.toggleTorch(),
          ),
          IconButton(
            icon: const Icon(Icons.cameraswitch),
            onPressed: () => _controller.switchCamera(),
          ),
        ],
      ),
      body: Stack(
        children: [
          MobileScanner(
            controller: _controller,
            onDetect: (capture) {
              final barcodes = capture.barcodes;
              if (barcodes.isEmpty) return;
              final raw = barcodes.first.rawValue;
              if (raw == null || raw.trim().isEmpty) return;
              _handleBarcode(raw);
            },
          ),
          Positioned(
            left: 16,
            right: 16,
            bottom: 16,
            child: Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.black.withOpacity(0.65),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Row(
                children: [
                  const Icon(Icons.qr_code_scanner, color: Colors.white),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      _handling ? 'Looking up barcode…' : 'Point camera at a barcode',
                      style: const TextStyle(color: Colors.white),
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
