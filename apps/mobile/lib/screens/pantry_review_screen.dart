import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../services/metrics_service.dart';
import '../services/scanning_service.dart';
import '../theme/app_theme.dart';
import '../ui/ui_principles.dart';

class PantryReviewScreen extends StatefulWidget {
  final String scanId;

  /// Map of detected_id -> {action, confirmed_name?}
  final Map<String, Map<String, dynamic>> choices;

  final int totalItems;

  const PantryReviewScreen({
    super.key,
    required this.scanId,
    required this.choices,
    required this.totalItems,
  });

  @override
  State<PantryReviewScreen> createState() => _PantryReviewScreenState();
}

class _PantryReviewScreenState extends State<PantryReviewScreen> {
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    fireAndForget(MetricsService.instance.recordWorkflowStep('SnapPantry', 'Confirm'));
  }

  int _itemCount() {
    var count = 0;
    for (final entry in widget.choices.values) {
      final action = entry['action']?.toString();
      if (action == 'confirmed' || action == 'modified') count++;
    }
    return count;
  }

  List<Map<String, dynamic>> _buildConfirmations() {
    final confirmations = <Map<String, dynamic>>[];

    widget.choices.forEach((detectedId, payload) {
      final action = payload['action']?.toString();
      if (action == null) return;

      final json = <String, dynamic>{
        'detected_id': detectedId,
        'action': action,
      };
      final confirmedName = payload['confirmed_name']?.toString();
      if (confirmedName != null && confirmedName.trim().isNotEmpty) {
        json['confirmed_name'] = confirmedName.trim();
      }
      confirmations.add(json);
    });

    return confirmations;
  }

  Future<void> _save() async {
    setState(() => _saving = true);

    try {
      final svc = ScanningService();
      final res = await svc.confirmIngredients(
        scanId: widget.scanId,
        confirmations: _buildConfirmations(),
      );

      if (!mounted) return;

      if (res['success'] == true) {
        fireAndForget(MetricsService.instance.recordWorkflowStep('SnapPantry', 'Save'));
        fireAndForget(MetricsService.instance.endTimer('scan_to_confirm_time'));
        fireAndForget(MetricsService.instance.recordEvent('pantry_scan_completed'));
        final added = res['pantry_items_added'];
        final addedCount = (added is num) ? added.toInt() : _itemCount();

        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Saved $addedCount items to pantry')),
        );

        // Exit the SnapPantry flow.
        Navigator.of(context).popUntil((route) => route.isFirst);
      } else {
        final msg = res['error']?.toString() ?? 'Save failed';
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(msg)),
        );
        setState(() => _saving = false);
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Save failed: $e')),
      );
      setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (kDebugMode || kProfileMode) {
      SavoUiGuards.warnIfMultiplePrimaryActions(
        screen: 'PantryReviewScreen',
        surface: 'Actions',
        primaryActions: 1,
      );
    }

    final count = _itemCount();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Review'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Adding $count items',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const Spacer(),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: _saving ? null : _save,
                child: Text(_saving ? 'Saving…' : 'Save inventory'),
              ),
            ),
            const SizedBox(height: AppSpacing.sm),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton(
                onPressed: _saving ? null : () => Navigator.pop(context),
                child: const Text('Go back'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
