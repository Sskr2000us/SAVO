import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/planning.dart';
import '../services/api_client.dart';
import '../services/entitlements_service.dart';
import '../services/metrics_service.dart';
import '../services/scanning_service.dart';
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

  static const _shoppingListPrefsKey = 'savo.shopping_list.latest';

  @override
  void initState() {
    super.initState();
    _plan = widget.menuPlan;
  }

  int _extractServings(Menu menu) {
    if (menu.servings.isEmpty) return 1;
    final total = menu.servings['total'];
    if (total is int && total > 0) return total;
    if (total is num && total > 0) return total.toInt();

    int sum = 0;
    for (final v in menu.servings.values) {
      if (v is int) sum += v;
      if (v is num) sum += v.toInt();
    }
    return sum > 0 ? sum : 1;
  }

  List<Map<String, dynamic>> _mergeShoppingListItems(List<Map<String, dynamic>> raw) {
    final Map<String, Map<String, dynamic>> merged = {};
    for (final item in raw) {
      final name = (item['canonical_name'] ?? item['ingredient'] ?? item['name'] ?? '').toString().trim();
      final unit = (item['unit'] ?? '').toString().trim();
      final amount = item['amount'] ?? item['quantity'];
      final key = '${name.toLowerCase()}|${unit.toLowerCase()}';

      final num? qty = amount is num ? amount : num.tryParse(amount?.toString() ?? '');
      if (!merged.containsKey(key)) {
        merged[key] = {
          'canonical_name': name.isEmpty ? 'Item' : name,
          'amount': qty ?? amount,
          'unit': unit,
        };
      } else {
        final existing = merged[key]!;
        final existingAmount = existing['amount'];
        final num? existingQty = existingAmount is num ? existingAmount : num.tryParse(existingAmount?.toString() ?? '');
        if (existingQty != null && qty != null) {
          existing['amount'] = existingQty + qty;
        }
      }
    }
    return merged.values.toList();
  }

  Future<void> _persistShoppingList(List<dynamic> items) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_shoppingListPrefsKey, json.encode(items));
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

      final merged = _mergeShoppingListItems(combined);
      await _persistShoppingList(merged);

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
