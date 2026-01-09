import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../config/app_config.dart';
import '../services/api_client.dart';
import '../theme/app_theme.dart';
import '../ui/ui_principles.dart';
import '../widgets/savo_widgets.dart';
import 'pantry/manual_entry_screen.dart';
import 'scanning/continuous_camera_screen.dart';

class PantryUpdateEntryScreen extends StatefulWidget {
  const PantryUpdateEntryScreen({super.key});

  @override
  State<PantryUpdateEntryScreen> createState() => _PantryUpdateEntryScreenState();
}

class _PantryUpdateEntryScreenState extends State<PantryUpdateEntryScreen> {
  bool _scanningReceipt = false;
  final ImagePicker _picker = ImagePicker();

  Future<List<Map<String, dynamic>>?> _confirmReceiptItems(
    BuildContext context,
    List<dynamic> items,
  ) async {
    final parsed = items
        .whereType<Map>()
        .map((m) => m.cast<String, dynamic>())
        .toList();

    if (parsed.isEmpty) {
      await showDialog<void>(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text('Nothing found'),
          content: const Text('Could not detect items from this receipt. Try a clearer photo. '),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('OK'),
            ),
          ],
        ),
      );
      return null;
    }

    final selections = <int, bool>{
      for (var i = 0; i < parsed.length; i++) i: true,
    };

    return showDialog<List<Map<String, dynamic>>>(
      context: context,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (ctx, setLocal) {
            return AlertDialog(
              title: const Text('Confirm receipt items'),
              content: SizedBox(
                width: double.maxFinite,
                child: SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Text('Select items to add to your inventory.'),
                      const SizedBox(height: 12),
                      for (var i = 0; i < parsed.length; i++)
                        Builder(
                          builder: (_) {
                            final item = parsed[i];
                            final rawName = (item['raw_name']?.toString().trim().isNotEmpty == true)
                                ? item['raw_name'].toString().trim()
                                : (item['canonical_name']?.toString() ?? 'Item');
                            final qty = item['quantity'];
                            final unit = item['unit'];
                            final subtitleParts = <String>[];
                            if (qty != null) subtitleParts.add('$qty');
                            if (unit != null && unit.toString().trim().isNotEmpty) subtitleParts.add(unit.toString());
                            final subtitle = subtitleParts.isEmpty ? null : subtitleParts.join(' ');

                            return CheckboxListTile(
                              value: selections[i] ?? true,
                              onChanged: (v) => setLocal(() => selections[i] = (v ?? true)),
                              title: Text(rawName),
                              subtitle: subtitle != null ? Text(subtitle) : null,
                              controlAffinity: ListTileControlAffinity.leading,
                            );
                          },
                        ),
                    ],
                  ),
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(ctx),
                  child: const Text('Cancel'),
                ),
                FilledButton(
                  onPressed: () {
                    final selected = <Map<String, dynamic>>[];
                    for (var i = 0; i < parsed.length; i++) {
                      if (selections[i] == true) selected.add(parsed[i]);
                    }
                    Navigator.pop(ctx, selected);
                  },
                  child: const Text('Add to inventory'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  Future<void> _scanReceipt(BuildContext context) async {
    if (_scanningReceipt) return;

    setState(() => _scanningReceipt = true);
    try {
      final image = await _picker.pickImage(
        source: kIsWeb ? ImageSource.gallery : ImageSource.camera,
        imageQuality: 85,
        maxWidth: 1800,
      );

      if (image == null) {
        if (mounted) setState(() => _scanningReceipt = false);
        return;
      }

      final api = ApiClient(baseUrl: Config.apiBaseUrl);
      final preview = await api.postMultipart(
        '/api/scanning/scan-receipt/preview',
        file: image,
        fields: const {
          'storage_location': 'pantry',
        },
      );

      if (!mounted) return;

      final success = preview['success'] == true;
      if (!success) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Receipt scan failed. Please try again.')),
        );
        setState(() => _scanningReceipt = false);
        return;
      }

      final receiptId = preview['receipt_id']?.toString() ?? '';
      final items = (preview['items'] is List) ? (preview['items'] as List) : const [];

      final selected = await _confirmReceiptItems(context, items);
      if (!mounted) return;
      if (selected == null || selected.isEmpty) {
        setState(() => _scanningReceipt = false);
        return;
      }

      final confirmRes = await api.post(
        '/api/scanning/scan-receipt/confirm',
        {
          'receipt_id': receiptId,
          'storage_location': 'pantry',
          'items': selected,
        },
      );

      final added = (confirmRes['added_count'] is num) ? (confirmRes['added_count'] as num).toInt() : 0;
      final updated = (confirmRes['updated_count'] is num) ? (confirmRes['updated_count'] as num).toInt() : 0;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Inventory updated. Added $added, updated $updated items.')),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Receipt scan failed: $e')),
      );
    } finally {
      if (!mounted) return;
      setState(() => _scanningReceipt = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (kDebugMode || kProfileMode) {
      SavoUiGuards.warnIfTooManyChoices(
        screen: 'PantryUpdateEntryScreen',
        surface: 'Entry options',
        choices: 3,
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Update Pantry'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'How would you like to update your pantry?',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: AppSpacing.md),
            SavoCard(
              elevated: true,
              onTap: () {
                Navigator.push(
                  context,
                  AppMotion.createRoute(const ContinuousCameraScanScreen()),
                );
              },
              child: const Row(
                children: [
                  Icon(Icons.center_focus_strong),
                  SizedBox(width: AppSpacing.md),
                  Expanded(
                    child: Text('Scan items (one by one)'),
                  ),
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            SavoCard(
              elevated: true,
              onTap: () {
                Navigator.push(
                  context,
                  AppMotion.createRoute(const ManualEntryScreen()),
                );
              },
              child: const Row(
                children: [
                  Icon(Icons.edit_note),
                  SizedBox(width: AppSpacing.md),
                  Expanded(
                    child: Text('Add manually'),
                  ),
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            if (_scanningReceipt) const LinearProgressIndicator(),
            if (_scanningReceipt) const SizedBox(height: AppSpacing.md),
            SavoCard(
              elevated: false,
              onTap: _scanningReceipt ? null : () => _scanReceipt(context),
              child: Row(
                children: [
                  Icon(
                    Icons.receipt_long,
                    color: _scanningReceipt ? Theme.of(context).disabledColor : null,
                  ),
                  const SizedBox(width: AppSpacing.md),
                  Expanded(
                    child: Text(
                      _scanningReceipt ? 'Scanning receipt…' : 'Scan receipt',
                      style: _scanningReceipt
                          ? TextStyle(color: Theme.of(context).disabledColor)
                          : null,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
