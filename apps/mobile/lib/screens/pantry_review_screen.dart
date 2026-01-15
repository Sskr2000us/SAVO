import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../services/api_client.dart';
import '../services/cook_now_service.dart';
import '../services/entitlements_service.dart';
import '../services/metrics_service.dart';
import '../services/scanning_service.dart';
import '../models/profile_state.dart';
import '../widgets/cook_context_picker_sheet.dart';
import 'recipe_options_screen.dart';
import '../theme/app_theme.dart';
import '../ui/ui_principles.dart';

class _ReviewItem {
  final String detectedId;
  final String name;
  final String action;

  const _ReviewItem({
    required this.detectedId,
    required this.name,
    required this.action,
  });
}

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
  late Map<String, Map<String, dynamic>> _choices;

  @override
  void initState() {
    super.initState();
    fireAndForget(MetricsService.instance.recordWorkflowStep('SnapPantry', 'Confirm'));
    _choices = Map<String, Map<String, dynamic>>.from(widget.choices);
  }

  int _itemCount() {
    var count = 0;
    for (final entry in _choices.values) {
      final action = entry['action']?.toString();
      if (action == 'confirmed' || action == 'modified') count++;
    }
    return count;
  }

  List<_ReviewItem> _reviewItems() {
    final out = <_ReviewItem>[];
    _choices.forEach((detectedId, payload) {
      final action = payload['action']?.toString();
      if (action != 'confirmed' && action != 'modified') return;
      final name = payload['confirmed_name']?.toString().trim();
      if (name == null || name.isEmpty) return;
      out.add(_ReviewItem(detectedId: detectedId, name: name, action: action!));
    });
    out.sort((a, b) => a.name.toLowerCase().compareTo(b.name.toLowerCase()));
    return out;
  }

  Future<void> _editItemName(_ReviewItem item) async {
    final controller = TextEditingController(text: item.name);
    final res = await showDialog<String>(
      context: context,
      builder: (ctx) {
        return AlertDialog(
          title: const Text('Edit ingredient'),
          content: TextField(
            controller: controller,
            autofocus: true,
            decoration: const InputDecoration(labelText: 'Name'),
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
      _choices[item.detectedId] = {
        'action': 'modified',
        'confirmed_name': next,
      };
    });

    fireAndForget(MetricsService.instance.recordEvent('pantry_review_item_edited'));
  }

  void _removeItem(_ReviewItem item) {
    setState(() {
      _choices[item.detectedId] = {
        'action': 'rejected',
      };
    });

    fireAndForget(MetricsService.instance.recordEvent('pantry_review_item_removed'));
  }

  List<Map<String, dynamic>> _buildConfirmations() {
    final confirmations = <Map<String, dynamic>>[];

    _choices.forEach((detectedId, payload) {
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

    final messenger = ScaffoldMessenger.of(context);
    final navigator = Navigator.of(context);

    try {
      final svc = ScanningService();
      Map<String, dynamic>? saveResult;

      final saveFuture = svc
          .confirmIngredients(
            scanId: widget.scanId,
            confirmations: _buildConfirmations(),
          )
          .then((res) {
        saveResult = res;
        if (!mounted) return;

        if (res['success'] == true) {
          fireAndForget(MetricsService.instance.recordWorkflowStep('SnapPantry', 'Save'));
          fireAndForget(MetricsService.instance.endTimer('scan_to_confirm_time'));
          fireAndForget(MetricsService.instance.recordEvent('pantry_scan_completed'));
          // Explicit confirm/save completion for activation funnel.
          fireAndForget(MetricsService.instance.recordEvent('pantry_confirm_completed'));
          // Time-to-first-value: best-effort end on first successful scan save.
          fireAndForget(MetricsService.instance.endTimer('ttfv'));

          // Activation funnel reporting (best-effort; ignore failures).
          fireAndForget(() async {
            try {
              final apiClient = ApiClient();
              await apiClient.post('/analytics/events', {
                'events': [
                  {
                    'name': 'pantry_confirm_completed',
                    'ts': DateTime.now().toIso8601String(),
                  }
                ],
              });
            } catch (_) {
              // ignore
            }
          }());

          final added = res['pantry_items_added'];
          final addedCount = (added is num) ? added.toInt() : _itemCount();
          final queued = res['queued'] == true;
          messenger.showSnackBar(
            SnackBar(
              content: Text(
                queued
                    ? 'Saved $addedCount items (will sync when online)'
                    : 'Saved $addedCount items to pantry',
              ),
            ),
          );
          return;
        }

        final msg = res['error']?.toString() ?? 'Save failed';
        messenger.showSnackBar(
          SnackBar(content: Text(msg)),
        );
      }).catchError((e) {
        if (!mounted) return;
        messenger.showSnackBar(
          SnackBar(content: Text('Save failed: $e')),
        );
      });

      // Optimistic/background save. Brief grace window before meal ideas so fast
      // connections include the newly saved ingredients.
      try {
        await saveFuture.timeout(const Duration(milliseconds: 900));
      } catch (_) {
        // Ignore; proceed with best-effort meal ideas.
      }

      if (!mounted) return;
      if (saveResult != null && saveResult!['success'] != true) {
        setState(() => _saving = false);
        return;
      }

      // Immediately present recipe options (best-effort) so the user gets value
      // without needing to press a separate "Generate recipes" button.
      try {
        final gate = await EntitlementsService.instance.tryConsumeSuggestionSession();
        if (!mounted) return;
        if (gate.allowed) {
          final picked = await showCookContextPickerSheet(
            context,
            title: 'What are you cooking for?',
          );
          if (!mounted) return;
          final dayType = picked?.dayType ?? inferDayType();
          final mealType = picked?.mealType ?? inferMealType();

          final apiClient = Provider.of<ApiClient>(context, listen: false);
          final profileState = Provider.of<ProfileState>(context, listen: false);
          final service = CookNowService();

          final options = await service.generateRecipeOptions(
            apiClient: apiClient,
            profileState: profileState,
            maxOptions: 5,
            avoidRecentRecipes: 3,
            dayType: dayType,
            mealType: mealType,
          );

          if (!mounted) return;
          if (options.isNotEmpty) {
            await navigator.pushAndRemoveUntil(
              MaterialPageRoute(
                settings: const RouteSettings(name: '/recipe_options'),
                builder: (_) => RecipeOptionsScreen(
                  recipes: options,
                  showIngredientMatch: true,
                  titleOverride: formatCookContextTitle(dayType: dayType, mealType: mealType),
                  skipSuggestionSessionGate: true,
                ),
              ),
              (route) => route.isFirst,
            );
            return;
          }
        }
      } catch (_) {
        // Best-effort only.
      }

      // Exit the SnapPantry flow.
      navigator.popUntil((route) => route.isFirst);
    } catch (e) {
      if (!mounted) return;
      messenger.showSnackBar(
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
    final items = _reviewItems();

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
              'Review pantry update',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: AppSpacing.xs),
            Text(
              'Adding $count items',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: AppSpacing.md),
            Expanded(
              child: items.isEmpty
                  ? ListView(
                      children: [
                        Text(
                          'No items selected.',
                          style: Theme.of(context).textTheme.bodyMedium,
                        ),
                      ],
                    )
                  : ListView.separated(
                      itemCount: items.length,
                      separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
                      itemBuilder: (context, index) {
                        final item = items[index];
                        return Card(
                          child: ListTile(
                            title: Text(item.name),
                            subtitle: Text(item.action == 'modified' ? 'Edited' : 'Confirmed'),
                            trailing: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                IconButton(
                                  tooltip: 'Edit',
                                  icon: const Icon(Icons.edit),
                                  onPressed: _saving ? null : () => _editItemName(item),
                                ),
                                IconButton(
                                  tooltip: 'Remove',
                                  icon: const Icon(Icons.close),
                                  onPressed: _saving ? null : () => _removeItem(item),
                                ),
                              ],
                            ),
                          ),
                        );
                      },
                    ),
            ),
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
