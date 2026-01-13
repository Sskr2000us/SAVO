import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../config/app_config.dart';
import '../services/api_client.dart';
import '../theme/app_theme.dart';
import '../ui/ui_principles.dart';
import '../widgets/savo_widgets.dart';
import 'barcode_scan_screen.dart';
import 'cook_now_entry_screen.dart';
import 'scanning/continuous_camera_screen.dart';
import 'scan_ingredients_screen.dart';
import 'pantry/manual_entry_screen.dart';

class PantryUpdateEntryScreen extends StatefulWidget {
  const PantryUpdateEntryScreen({super.key});

  @override
  State<PantryUpdateEntryScreen> createState() => _PantryUpdateEntryScreenState();
}

class _PantryUpdateEntryScreenState extends State<PantryUpdateEntryScreen> {
  bool _scanningReceipt = false;
  final ImagePicker _picker = ImagePicker();

  void _showCookNowNudge() {
    if (!mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    messenger.hideCurrentSnackBar();
    messenger.showSnackBar(
      SnackBar(
        content: const Text('Pantry updated. Ready to pick a recipe?'),
        action: SnackBarAction(
          label: 'Cook',
          onPressed: () {
            if (!mounted) return;
            Navigator.of(context).push(
              AppMotion.createRoute(const CookNowEntryScreen()),
            );
          },
        ),
      ),
    );
  }

  Future<void> _startPantryScan(String mode) async {
    if (!mounted) return;

    dynamic result;
    if (mode == 'realtime' && !kIsWeb) {
      result = await Navigator.push<List<Map<String, dynamic>>>(
        context,
        MaterialPageRoute(
          builder: (_) => const ContinuousCameraScanScreen(),
        ),
      );
    } else if (mode == 'video30' && !kIsWeb) {
      result = await Navigator.push<bool>(
        context,
        AppMotion.createRoute(const ScanIngredientsScreen(autoStartVideoScan: true)),
      );
    } else if (mode == 'barcode' && !kIsWeb) {
      result = await Navigator.push<bool>(
        context,
        MaterialPageRoute(
          builder: (_) => const BarcodeScanScreen(),
        ),
      );
    } else {
      // photo (and web fallback)
      result = await Navigator.push<bool>(
        context,
        AppMotion.createRoute(const ScanIngredientsScreen()),
      );
    }

    final changed = (result is bool)
        ? result == true
        : (result is List)
            ? result.isNotEmpty
            : false;

    if (changed) {
      _showCookNowNudge();
    }
  }

  Future<void> _openScanOptionsSheet() async {
    final res = await showModalBottomSheet<String>(
      context: context,
      showDragHandle: true,
      builder: (ctx) {
        final titleStyle = Theme.of(ctx).textTheme.titleMedium;

        Widget tile({
          required IconData icon,
          required String label,
          required String value,
          String? subtitle,
        }) {
          return ListTile(
            leading: Icon(icon),
            title: Text(label, style: titleStyle),
            subtitle: subtitle != null ? Text(subtitle) : null,
            onTap: () => Navigator.of(ctx).pop(value),
          );
        }

        return SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.sm),
                child: Text('Choose a scan mode', style: titleStyle),
              ),
              if (!kIsWeb)
                tile(
                  icon: Icons.videocam,
                  label: 'Real-time scan',
                  subtitle: 'Fastest on mobile',
                  value: 'realtime',
                ),
              if (!kIsWeb)
                tile(
                  icon: Icons.video_camera_back_outlined,
                  label: 'Video scan (30s)',
                  subtitle: 'Scan many items at once',
                  value: 'video30',
                ),
              if (!kIsWeb)
                tile(
                  icon: Icons.qr_code_scanner,
                  label: 'Barcode scan',
                  subtitle: 'Packaged items',
                  value: 'barcode',
                ),
              tile(
                icon: Icons.photo_camera,
                label: kIsWeb ? 'Upload photo' : 'Take photo',
                subtitle: 'Single item',
                value: 'photo',
              ),
              const SizedBox(height: AppSpacing.sm),
            ],
          ),
        );
      },
    );

    if (res == null) return;
    await _startPantryScan(res);
  }

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

  Future<void> _scanReceipt() async {
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

      if (!mounted) return;

      final added = (confirmRes['added_count'] is num) ? (confirmRes['added_count'] as num).toInt() : 0;
      final updated = (confirmRes['updated_count'] is num) ? (confirmRes['updated_count'] as num).toInt() : 0;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Inventory updated. Added $added, updated $updated items.')),
      );

      if ((added + updated) > 0) {
        _showCookNowNudge();
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Receipt scan failed: $e')),
      );
    } finally {
      if (mounted) {
        setState(() => _scanningReceipt = false);
      }
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
              onTap: _openScanOptionsSheet,
              child: const Row(
                children: [
                  Icon(Icons.photo_camera),
                  SizedBox(width: AppSpacing.md),
                  Expanded(
                    child: Text('Scan pantry (realtime / video / barcode / photo)'),
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
              onTap: _scanningReceipt ? null : _scanReceipt,
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
