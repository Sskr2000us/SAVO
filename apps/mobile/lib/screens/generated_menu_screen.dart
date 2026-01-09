import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/planning.dart';
import '../services/api_client.dart';
import '../services/entitlements_service.dart';
import '../services/metrics_service.dart';
import '../services/scanning_service.dart';
import '../services/shopping_list_storage.dart';
import '../theme/app_theme.dart';
import '../ui/ui_principles.dart';
import '../widgets/pro_paywall_sheet.dart';
import 'planning_results_screen.dart';
import 'shopping_list_screen.dart';

class GeneratedMenuScreen extends StatefulWidget {
  final MenuPlanResponse menuPlan;
  final Map<String, dynamic> requestBody;
  final String title;

  const GeneratedMenuScreen({
    super.key,
    required this.menuPlan,
    required this.requestBody,
    required this.title,
  });

  @override
  State<GeneratedMenuScreen> createState() => _GeneratedMenuScreenState();
}

class _GeneratedMenuScreenState extends State<GeneratedMenuScreen> {
  late MenuPlanResponse _plan;
  bool _swapping = false;
  bool _approving = false;
  String? _error;

  // Stored via ShoppingListStorage.

  @override
  void initState() {
    super.initState();
    _plan = widget.menuPlan;
  }

  int _extractServings(Menu menu) {
    if (menu.servings.isEmpty) return 1;
    final total = menu.servings['total'] ?? menu.servings['count'];
    if (total is int && total > 0) return total;
    if (total is num && total > 0) return total.toInt();

    int sum = 0;
    for (final entry in menu.servings.entries) {
      final key = entry.key.toString().toLowerCase();
      if (key == 'scaling_factor' || key == 'scale' || key == 'multiplier') continue;

      final v = entry.value;
      if (v is int) sum += v;
      if (v is num) sum += v.toInt();
    }
    return sum > 0 ? sum : 1;
  }



  Future<void> _approveMenu() async {
    if (_approving) return;
    setState(() {
      _approving = true;
      _error = null;
    });

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final scanningService = ScanningService();

      final List<Map<String, dynamic>> combined = [];
      int successes = 0;
      String? firstError;

      for (final menu in _plan.menus) {
        final servings = _extractServings(menu);
        for (final course in menu.courses) {
          if (course.recipeOptions.isEmpty) continue;
          final recipe = course.recipeOptions.first;
          if (recipe.ingredientsUsed.isEmpty) {
            firstError ??= 'A recipe is missing ingredient data.';
            continue;
          }

          final recipeIngredients = recipe.ingredientsUsed
              .map(
                (i) => {
                  'name': i.canonicalName,
                  'quantity': i.amount,
                  'unit': i.unit,
                },
              )
              .toList();

          final result = await scanningService.checkSufficiency(
            recipeId: recipe.recipeId,
            servings: servings,
            apiClient: apiClient,
            recipeIngredients: recipeIngredients,
            recipeServings: servings,
          );

          if (result['success'] == true) {
            successes += 1;
            final list = result['shopping_list'];
            if (list is List) {
              for (final item in list) {
                if (item is Map) {
                  combined.add(Map<String, dynamic>.from(item));
                } else {
                  combined.add({'canonical_name': item.toString()});
                }
              }
            }
          } else {
            final err = (result['error'] ?? result['message'] ?? '').toString().trim();
            if (err.isNotEmpty) firstError ??= err;
          }
        }
      }

      if (!mounted) return;

      if (successes == 0) {
        setState(() {
          _approving = false;
          _error = (firstError?.isNotEmpty == true)
              ? 'Could not build shopping list: $firstError'
              : 'Could not build shopping list for this menu.';
        });
        return;
      }

      // Merge into the existing cart/list (never overwrite).
      await ShoppingListStorage.mergeAndSaveIncoming(combined);

      fireAndForget(MetricsService.instance.recordWorkflowStep('PlanParty', 'Approve'));

      if (!mounted) return;

      await Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => const ShoppingListScreen()),
      );

      fireAndForget(MetricsService.instance.recordWorkflowStep('PlanParty', 'Shop'));

      if (!mounted) return;
      setState(() {
        _approving = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _approving = false;
        _error = e.toString();
      });
    }
  }

  Future<void> _deleteSavedPartyPlan() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Remove plan'),
        content: const Text('Remove the saved party plan so you can generate a new one?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Remove'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      await apiClient.delete('/plan/latest?plan_type=party');
      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Party plan removed.')),
      );

      if (Navigator.canPop(context)) {
        Navigator.pop(context);
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to remove plan: $e')),
      );
    }
  }

  Future<void> _swapItems() async {
    if (_swapping) return;

    final gate = await EntitlementsService.instance.tryConsumeSwap();
    if (!gate.allowed && mounted) {
      await showProPaywallSheet(
        context,
        title: 'Upgrade to SAVO Pro',
        ctaLabel: 'Upgrade for unlimited swaps',
        reason: 'You\'ve used today\'s free swap. Pro unlocks unlimited swaps/regenerates so you can refine plans faster.',
        trigger: 'weekly_planning_gate',
        );
      return;
    }

    setState(() {
      _swapping = true;
      _error = null;
    });

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final res = await apiClient.post('/plan/party?force_regenerate=true', widget.requestBody);
      final next = MenuPlanResponse.fromJson(res);
      if (!mounted) return;
      setState(() {
        _plan = next;
        _swapping = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _swapping = false;
        _error = e.toString();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (kDebugMode || kProfileMode) {
      SavoUiGuards.warnIfTooManyChoices(
        screen: 'GeneratedMenuScreen',
        surface: 'Actions',
        choices: 2,
      );
    }

    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.title),
        actions: [
          IconButton(
            tooltip: 'Remove plan',
            onPressed: _swapping || _approving ? null : _deleteSavedPartyPlan,
            icon: const Icon(Icons.delete_outline),
          ),
        ],
      ),
      body: Column(
        children: [
          if (_error != null)
            Padding(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: Text(
                _error!,
                style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.error),
              ),
            ),
          Expanded(
            child: PlanningResultsScreen(
              menuPlan: _plan,
              planType: 'party',
              showScaffold: false,
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: Row(
              children: [
                Expanded(
                  child: FilledButton(
                    onPressed: (_approving || _swapping) ? null : _approveMenu,
                    child: Text(_approving ? 'Approving…' : 'Approve menu'),
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: OutlinedButton(
                    onPressed: (_approving || _swapping) ? null : _swapItems,
                    child: Text(_swapping ? 'Swapping…' : 'Swap items'),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
