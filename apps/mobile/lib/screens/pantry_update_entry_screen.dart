import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import '../ui/ui_principles.dart';
import '../widgets/savo_widgets.dart';
import 'pantry_camera_screen.dart';
import 'pantry/manual_entry_screen.dart';

class PantryUpdateEntryScreen extends StatelessWidget {
  const PantryUpdateEntryScreen({super.key});

  void _comingSoon(BuildContext context) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Scan receipt is coming soon.')),
    );
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
            SavoCard(
              elevated: false,
              onTap: () => _comingSoon(context),
              child: Row(
                children: [
                  Icon(Icons.receipt_long, color: Theme.of(context).disabledColor),
                  const SizedBox(width: AppSpacing.md),
                  Expanded(
                    child: Text(
                      'Scan receipt (coming soon)',
                      style: TextStyle(color: Theme.of(context).disabledColor),
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
