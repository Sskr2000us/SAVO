import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../services/metrics_service.dart';
import '../services/scanning_service.dart';
import '../services/cook_now_service.dart';
import '../services/entitlements_service.dart';
import '../services/api_client.dart';
import '../models/profile_state.dart';
import '../theme/app_theme.dart';
import '../ui/ui_principles.dart';
import 'recipe_options_screen.dart';

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
  final Map<String, GlobalKey> _itemKeys = {};
  bool _saving = false;

  GlobalKey _keyFor(String id) {
    return _itemKeys.putIfAbsent(id, () => GlobalKey());
  }

  bool _isLowConfidence(Map<String, dynamic> item) {
    final conf = item['confidence_category']?.toString().toLowerCase().trim();
    return conf == 'low';
  }

  void _jumpToFirstLowConfidence() {
    for (final idx in _orderedIndices()) {
      final raw = widget.items[idx];
      if (raw is! Map) continue;
      final item = raw.cast<String, dynamic>();
      if (!_isLowConfidence(item)) continue;

      final id = _idFor(item, idx);
      final ctx = _itemKeys[id]?.currentContext;
      if (ctx == null) return;

      fireAndForget(Scrollable.ensureVisible(
        ctx,
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeInOut,
        alignment: 0.15,
      ));
      return;
    }
  }

  List<int> _orderedIndices() {
    final indexed = <int>[];
    for (var i = 0; i < widget.items.length; i++) {
      indexed.add(i);
    }

    int weightFor(dynamic raw) {
      if (raw is! Map) return 1;
      final item = raw.cast<String, dynamic>();
      final conf = item['confidence_category']?.toString().toLowerCase().trim();
      if (conf == 'low') return 0;
      if (conf == 'medium') return 1;
      return 2;
    }

    indexed.sort((a, b) {
      final wa = weightFor(widget.items[a]);
      final wb = weightFor(widget.items[b]);
      if (wa != wb) return wa.compareTo(wb);
      return a.compareTo(b);
    });

    return indexed;
  }

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
    if (raw == 'high') return 'High';
    if (raw == 'medium') return 'Medium';
    return 'Low';
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
      case 'High':
        return cs.tertiary;
      case 'Medium':
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

  void _chooseAlternative(String id, String name) {
    setState(() {
      _choices[id] = {
        'action': 'modified',
        'confirmed_name': name,
      };
    });

    fireAndForget(MetricsService.instance.recordEvent('pantry_ai_suggestion_chosen'));
  }

  List<String> _suggestionsFor(Map<String, dynamic> item, String currentName) {
    final raw = (item['close_alternatives'] ?? item['alternatives'] ?? item['candidates']);
    if (raw is! List) return const <String>[];

    final current = currentName.trim().toLowerCase();
    final out = <String>[];
    for (final r in raw) {
      final s = r?.toString().trim();
      if (s == null || s.isEmpty) continue;
      if (s.trim().toLowerCase() == current) continue;
      if (out.contains(s)) continue;
      out.add(s);
      if (out.length >= 3) break;
    }
    return out;
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

    final navigator = Navigator.of(context);
    final messenger = ScaffoldMessenger.of(context);

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

        messenger.showSnackBar(
          SnackBar(content: Text('Saved $addedCount items to pantry')),
        );

        // Fast value: immediately show 3–5 meal ideas after confirm.
        try {
          fireAndForget(MetricsService.instance.recordEvent('post_scan_meal_ideas_requested'));
          final apiClient = Provider.of<ApiClient>(context, listen: false);
          final profileState = Provider.of<ProfileState>(context, listen: false);
          final service = CookNowService();

          // Avoid interrupting the core scan->save flow: if the user has hit
          // their daily suggestions limit, just skip meal ideas.
          final gate = await EntitlementsService.instance.tryConsumeSuggestionSession();
          if (!mounted) return;
          if (!gate.allowed) {
            messenger.showSnackBar(
              const SnackBar(
                content: Text(
                  'Today\'s free meal ideas are used up. Upgrade to Pro for unlimited suggestions.',
                ),
              ),
            );
            navigator.popUntil((route) => route.isFirst);
            return;
          }

          final options = await service.generateRecipeOptions(
            apiClient: apiClient,
            profileState: profileState,
            maxOptions: 5,
            avoidRecentRecipes: 3,
          );

          if (!mounted) return;

          if (options.isEmpty) {
            navigator.popUntil((route) => route.isFirst);
            return;
          }

          await navigator.pushReplacement(
            MaterialPageRoute(
              settings: const RouteSettings(name: '/recipe_options'),
              builder: (_) => RecipeOptionsScreen(
                recipes: options,
                showIngredientMatch: true,
                titleOverride: 'Meals you can cook tonight',
                skipSuggestionSessionGate: true,
              ),
            ),
          );
          return;
        } catch (_) {
          // If suggestions fail, fall back to returning home.
          navigator.popUntil((route) => route.isFirst);
          return;
        }
      }

      final msg = res['error']?.toString() ?? 'Save failed';
      messenger.showSnackBar(
        SnackBar(content: Text(msg)),
      );
      setState(() => _saving = false);
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

    final ordered = _orderedIndices();
    final hasLow = widget.items.any((raw) {
      if (raw is! Map) return false;
      final item = raw.cast<String, dynamic>();
      return _isLowConfidence(item);
    });

    var lowCount = 0;
    var mediumCount = 0;
    var highCount = 0;
    for (final raw in widget.items) {
      if (raw is! Map) continue;
      final item = raw.cast<String, dynamic>();
      final label = _confidenceFor(item);
      if (label == 'High') {
        highCount++;
      } else if (label == 'Medium') {
        mediumCount++;
      } else {
        lowCount++;
      }
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Review ingredients'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          children: [
            Align(
              alignment: Alignment.centerLeft,
              child: Text(
                'Low: $lowCount • Medium: $mediumCount • High: $highCount',
                style: Theme.of(context).textTheme.labelMedium?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                      fontWeight: FontWeight.w700,
                    ),
              ),
            ),
            const SizedBox(height: AppSpacing.sm),
            if (hasLow) ...[
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: () {
                    fireAndForget(MetricsService.instance.recordEvent('pantry_ai_jump_low_confidence'));
                    _jumpToFirstLowConfidence();
                  },
                  icon: const Icon(Icons.arrow_downward),
                  label: const Text('Review low confidence first'),
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
            ],
            Expanded(
              child: ListView.separated(
                itemCount: widget.items.length,
                separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
                itemBuilder: (context, index) {
                  final raw = widget.items[ordered[index]];
                  if (raw is! Map) return const SizedBox.shrink();
                  final item = raw.cast<String, dynamic>();

                  final originalIndex = ordered[index];
                  final id = _idFor(item, originalIndex);
                  final name = _labelFor(item);
                  final confidence = _confidenceFor(item);
                  final confColor = _confidenceColor(context, confidence);
                  final qty = _quantityGuessFor(item);

                  final choice = _choices[id];
                  final action = choice?['action']?.toString();

                  final isRemoved = action == 'rejected';
                  final isConfirmed = action == 'confirmed' || action == 'modified';

                  final requiresEditForLow = confidence == 'Low' && action != 'modified';
                  final canConfirm = !isRemoved && !requiresEditForLow;

                  final suggestions = (confidence == 'High') ? const <String>[] : _suggestionsFor(item, name);

                  return Container(
                    key: _keyFor(id),
                    child: Card(
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
                                    color: confColor.withAlpha(31),
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
                            if (!isRemoved && suggestions.isNotEmpty) ...[
                              const SizedBox(height: AppSpacing.sm),
                              Text(
                                'Suggestions',
                                style: Theme.of(context).textTheme.labelMedium?.copyWith(
                                      fontWeight: FontWeight.w700,
                                    ),
                              ),
                              const SizedBox(height: AppSpacing.xs),
                              Wrap(
                                spacing: AppSpacing.xs,
                                runSpacing: AppSpacing.xs,
                                children: suggestions
                                    .map(
                                      (s) => ActionChip(
                                        label: Text(s),
                                        onPressed: () => _chooseAlternative(id, s),
                                      ),
                                    )
                                    .toList(),
                              ),
                            ],
                            const SizedBox(height: AppSpacing.sm),
                            Row(
                              children: [
                                Expanded(
                                  child: OutlinedButton.icon(
                                    onPressed: canConfirm ? () => _confirm(id, name) : null,
                                    icon: const Icon(Icons.check),
                                    label: Text(
                                      isConfirmed
                                          ? 'Confirmed'
                                          : (requiresEditForLow ? 'Pick or edit' : 'Confirm'),
                                    ),
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
