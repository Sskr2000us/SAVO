import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../services/metrics_service.dart';
import '../theme/app_theme.dart';
import '../ui/ui_principles.dart';
import 'pantry_review_screen.dart';

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

  @override
  void initState() {
    super.initState();

    fireAndForget(MetricsService.instance.recordWorkflowStep('SnapPantry', 'Suggest'));

    // Default behavior: do not auto-save; user reviews explicitly.
    // We do not auto-confirm here to match trust-first flow.
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
  }

  void _remove(String id) {
    setState(() {
      _choices[id] = {
        'action': 'rejected',
      };
    });
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
  }

  @override
  Widget build(BuildContext context) {
    if (kDebugMode || kProfileMode) {
      // Flow B requires explicit review before save.
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
                onPressed: () {
                  Navigator.push(
                    context,
                    AppMotion.createRoute(
                      PantryReviewScreen(
                        scanId: widget.scanId,
                        choices: _choices,
                        totalItems: widget.items.length,
                      ),
                    ),
                  );
                },
                child: const Text('Review before save'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
