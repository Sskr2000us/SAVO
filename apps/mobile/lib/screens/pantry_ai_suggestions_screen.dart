import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../services/metrics_service.dart';
import '../services/scanning_service.dart';
import '../theme/app_theme.dart';
import '../ui/ui_principles.dart';

class PantryAiSuggestionsScreen extends StatefulWidget {
  final String scanId;
  final List<dynamic> items;

  const PantryAiSuggestionsScreen({
    super.key,
    required this.scanId,
    required this.items,
  });

  @override
  State<PantryAiSuggestionsScreen> createState() =>
      _PantryAiSuggestionsScreenState();
}

class _PantryAiSuggestionsScreenState extends State<PantryAiSuggestionsScreen> {
  final Map<String, Map<String, dynamic>> _choices = {};
  bool _saving = false;

  @override
  void initState() {
    super.initState();

    fireAndForget(MetricsService.instance.recordWorkflowStep('SnapPantry', 'Suggest'));

    // High-confidence speed-up: pre-confirm HIGH items, but still require
    // an explicit review+save path (trust-first).
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _preconfirmHighConfidence();
    });

    // Default behavior: do not auto-save; user reviews explicitly.
    // We do not auto-confirm here to match trust-first flow.
  }

  void _preconfirmHighConfidence() {
    var changed = false;
    var any = false;

    for (var index = 0; index < widget.items.length; index++) {
      final raw = widget.items[index];
      if (raw is! Map) continue;
      final item = raw.cast<String, dynamic>();
      final id = _idFor(item, index);

      final conf = item['confidence_category']?.toString().toLowerCase().trim();
      if (conf != 'high') continue;

      any = true;
      if (_choices.containsKey(id)) continue;

      final name = _labelFor(item);
      _choices[id] = {
        'action': 'confirmed',
        'confirmed_name': name,
      };
      changed = true;
    }

    if (!mounted) return;
    if (any) {
      fireAndForget(MetricsService.instance.recordEvent('pantry_ai_autoconfirm_high'));
    }
    if (changed) {
      setState(() {});
    }
  }

  String _idFor(Map<String, dynamic> item, int index) {
    final raw = item['id'];
    if (raw != null) return raw.toString();
    return 'idx_$index';
  }

  String _labelFor(Map<String, dynamic> item) {
    final v = item['canonical_name'] ?? item['detected_name'] ?? item['ingredient'] ?? item['name'];
    final s = v?.toString().trim();
    return (s == null || s.isEmpty) ? 'Unknown' : s;
  }

  String _confidenceFor(Map<String, dynamic> item) {
    final raw = item['confidence_category']?.toString().toLowerCase().trim();
    if (raw == 'high') return 'HIGH';
    if (raw == 'medium') return 'MEDIUM';
    return 'LOW';
  }

  String? _quantityGuessFor(Map<String, dynamic> item) {
    final q = item['quantity'];
    final unit = item['unit']?.toString().trim();

    if (q == null) return null;
    if (q is num) {
      final n = q.toDouble();
      if (n == 0) return null;

      // Show ints cleanly.
      final qText = (n % 1 == 0) ? n.toInt().toString() : n.toStringAsFixed(1);
      if (unit != null && unit.isNotEmpty) return '$qText $unit';
      return qText;
    }

    final s = q.toString().trim();
    if (s.isEmpty) return null;
    if (unit != null && unit.isNotEmpty) return '$s $unit';
    return s;
  }

  Color _confidenceColor(BuildContext context, String label) {
    final cs = Theme.of(context).colorScheme;
    switch (label) {
      case 'HIGH':
        return cs.tertiary;
      case 'MEDIUM':
        return cs.secondary;
      default:
        return cs.error;
    }
  }

  void _confirm(String id, String name) {
    setState(() {
      _choices[id] = {
        'action': 'confirmed',
        'confirmed_name': name,
      };
    });

    fireAndForget(MetricsService.instance.recordEvent('pantry_ai_item_confirmed'));
  }

  void _remove(String id) {
    setState(() {
      _choices[id] = {
        'action': 'rejected',
      };
    });

    fireAndForget(MetricsService.instance.recordEvent('pantry_ai_item_removed'));
  }

  Future<void> _edit(String id, String currentName) async {
    final controller = TextEditingController(text: currentName);

    final res = await showDialog<String>(
      context: context,
      builder: (ctx) {
        return AlertDialog(
          title: const Text('Edit ingredient'),
          content: TextField(
            controller: controller,
            autofocus: true,
            decoration: const InputDecoration(
              labelText: 'Name',
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(ctx, controller.text.trim()),
              child: const Text('Save'),
            ),
          ],
        );
      },
    );

    final next = res?.trim();
    if (next == null || next.isEmpty) return;

    setState(() {
      _choices[id] = {
        'action': 'modified',
        'confirmed_name': next,
      };
    });

    fireAndForget(MetricsService.instance.recordEvent('pantry_ai_item_edited'));
  }

  List<Map<String, dynamic>> _buildConfirmations() {
    final confirmations = <Map<String, dynamic>>[];

    for (var index = 0; index < widget.items.length; index++) {
      final raw = widget.items[index];
      if (raw is! Map) continue;
      final item = raw.cast<String, dynamic>();
      final id = _idFor(item, index);

      final choice = _choices[id];
      final action = choice?['action']?.toString() ?? 'rejected';

      final json = <String, dynamic>{
        'detected_id': id,
        'action': action,
      };

      final confirmedName = choice?['confirmed_name']?.toString();
      if (confirmedName != null && confirmedName.trim().isNotEmpty) {
        json['confirmed_name'] = confirmedName.trim();
      }
      confirmations.add(json);
    }

    return confirmations;
  }

  Future<void> _save() async {
    if (_saving) return;
    setState(() => _saving = true);

    try {
      fireAndForget(MetricsService.instance.recordWorkflowStep('SnapPantry', 'Save'));

      final svc = ScanningService();
      final res = await svc.confirmIngredients(
        scanId: widget.scanId,
        confirmations: _buildConfirmations(),
      );

      if (!mounted) return;

      if (res['success'] == true) {
        fireAndForget(MetricsService.instance.endTimer('scan_to_confirm_time'));
        fireAndForget(MetricsService.instance.recordEvent('pantry_scan_completed'));

        final added = res['pantry_items_added'];
        final addedCount = (added is num)
            ? added.toInt()
            : _choices.values
                .where((v) => v['action'] == 'confirmed' || v['action'] == 'modified')
                .length;

        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Saved $addedCount items to pantry')),
        );

        Navigator.of(context).popUntil((route) => route.isFirst);
        return;
      }

      final msg = res['error']?.toString() ?? 'Save failed';
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(msg)),
      );
      setState(() => _saving = false);
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
      // Explicit user review exists on this screen (confirm/edit/remove),
      // followed by a single Save action.
      SavoUiGuards.warnIfAiConfirmationNotExplicit(
        flow: 'SnapPantry',
        surface: 'PantryAISuggestions',
        hasExplicitReviewStep: true,
      );

      // Primary action should be singular.
      SavoUiGuards.warnIfMultiplePrimaryActions(
        screen: 'PantryAiSuggestionsScreen',
        surface: 'Footer',
        primaryActions: 1,
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Review ingredients'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          children: [
            Expanded(
              child: ListView.separated(
                itemCount: widget.items.length,
                separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
                itemBuilder: (context, index) {
                  final raw = widget.items[index];
                  if (raw is! Map) return const SizedBox.shrink();
                  final item = raw.cast<String, dynamic>();

                  final id = _idFor(item, index);
                  final name = _labelFor(item);
                  final confidence = _confidenceFor(item);
                  final confColor = _confidenceColor(context, confidence);
                  final qty = _quantityGuessFor(item);

                  final choice = _choices[id];
                  final action = choice?['action']?.toString();

                  final isRemoved = action == 'rejected';
                  final isConfirmed = action == 'confirmed' || action == 'modified';

                  return Card(
                    child: Padding(
                      padding: const EdgeInsets.all(AppSpacing.md),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Expanded(
                                child: Text(
                                  choice?['confirmed_name']?.toString() ?? name,
                                  style: Theme.of(context).textTheme.titleMedium,
                                ),
                              ),
                              Container(
                                decoration: BoxDecoration(
                                  color: confColor.withOpacity(0.12),
                                  borderRadius: BorderRadius.circular(AppRadius.sm),
                                ),
                                padding: const EdgeInsets.symmetric(
                                  horizontal: AppSpacing.sm,
                                  vertical: AppSpacing.xs,
                                ),
                                child: Text(
                                  confidence,
                                  style: Theme.of(context).textTheme.labelMedium?.copyWith(
                                        color: confColor,
                                        fontWeight: FontWeight.w700,
                                      ),
                                ),
                              ),
                            ],
                          ),
                          if (qty != null) ...[
                            const SizedBox(height: AppSpacing.xs),
                            Text(
                              'Qty: $qty',
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                          ],
                          const SizedBox(height: AppSpacing.sm),
                          Row(
                            children: [
                              Expanded(
                                child: OutlinedButton.icon(
                                  onPressed: isRemoved ? null : () => _confirm(id, name),
                                  icon: const Icon(Icons.check),
                                  label: Text(isConfirmed ? 'Confirmed' : 'Confirm'),
                                ),
                              ),
                              const SizedBox(width: AppSpacing.sm),
                              Expanded(
                                child: OutlinedButton.icon(
                                  onPressed: isRemoved ? null : () => _edit(id, name),
                                  icon: const Icon(Icons.edit),
                                  label: const Text('Edit'),
                                ),
                              ),
                              const SizedBox(width: AppSpacing.sm),
                              Expanded(
                                child: OutlinedButton.icon(
                                  onPressed: () => _remove(id),
                                  icon: const Icon(Icons.close),
                                  label: Text(isRemoved ? 'Removed' : 'Remove'),
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: _saving ? null : _save,
                child: Text(_saving ? 'Saving…' : 'Save to inventory'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
