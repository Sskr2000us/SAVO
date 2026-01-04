import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
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

          return AlertDialog(
            title: const Text('Add to inventory'),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
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
              ],
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: () async {
                  final q = double.tryParse(qtyController.text.trim()) ?? 1.0;
                  final u = unitController.text.trim().isEmpty ? 'pcs' : unitController.text.trim();

                  await apiClient.post('/inventory-db/items', {
                    'canonical_name': nameController.text.trim(),
                    'display_name': nameController.text.trim(),
                    'quantity': q,
                    'unit': u,
                    'storage_location': 'pantry',
                    'item_state': 'raw',
                    'source': 'scan',
                    'scan_confidence': 1.0,
                    'barcode': digits,
                    'product_name': productName.isNotEmpty ? productName : null,
                    'brand': brand.isNotEmpty ? brand : null,
                    'image_url': imageUrl.isNotEmpty ? imageUrl : null,
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
