import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../config/app_config.dart';
import '../services/api_client.dart';
import '../theme/app_theme.dart';
import '../ui/ui_principles.dart';
import '../widgets/savo_widgets.dart';
import 'pantry_camera_screen.dart';
import 'pantry/manual_entry_screen.dart';

class PantryUpdateEntryScreen extends StatefulWidget {
  const PantryUpdateEntryScreen({super.key});

  @override
  State<PantryUpdateEntryScreen> createState() => _PantryUpdateEntryScreenState();
}

class _PantryUpdateEntryScreenState extends State<PantryUpdateEntryScreen> {
  bool _scanningReceipt = false;
  final ImagePicker _picker = ImagePicker();

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
      final res = await api.postMultipart(
        '/api/scanning/scan-receipt',
        file: image,
        fields: const {
          'storage_location': 'pantry',
        },
      );

      if (!mounted) return;

      final success = res['success'] == true;
      if (!success) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Receipt scan failed. Please try again.')),
        );
        setState(() => _scanningReceipt = false);
        return;
      }

      final added = (res['added_count'] is num) ? (res['added_count'] as num).toInt() : 0;
      final updated = (res['updated_count'] is num) ? (res['updated_count'] as num).toInt() : 0;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Receipt scanned. Added $added, updated $updated items.')),
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
                  AppMotion.createRoute(const PantryCameraScreen()),
                );
              },
              child: const Row(
                children: [
                  Icon(Icons.photo_camera),
                  SizedBox(width: AppSpacing.md),
                  Expanded(
                    child: Text('Scan pantry shelf'),
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
