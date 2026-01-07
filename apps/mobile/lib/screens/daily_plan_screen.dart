import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/planning.dart';
import '../models/profile_state.dart';
import '../services/api_client.dart';
import '../theme/app_theme.dart';
import '../ui/ui_principles.dart';
import 'planning_results_screen.dart';

class DailyPlanScreen extends StatefulWidget {
  const DailyPlanScreen({super.key});

  @override
  State<DailyPlanScreen> createState() => _DailyPlanScreenState();
}

class _DailyPlanScreenState extends State<DailyPlanScreen> {
  MenuPlanResponse? _latest;
  bool _loading = true;
  bool _generating = false;
  String? _error;

  Future<List<Map<String, dynamic>>> _fetchVerifyItems(ApiClient apiClient) async {
    try {
      final res = await apiClient.get('/api/scanning/pantry/summary?max_verify=5');
      if (res is Map && res['verify'] is List) {
        return (res['verify'] as List)
            .whereType<Map>()
            .map((e) => e.cast<String, dynamic>())
            .toList();
      }
    } catch (_) {
      // Best-effort only.
    }
    return const [];
  }

  Future<Map<String, bool>?> _askQuickInventoryCheck(List<Map<String, dynamic>> verify) async {
    if (verify.isEmpty) return const {};

    final Map<String, bool> selections = {};
    for (final item in verify) {
      final id = item['id']?.toString() ?? '';
      if (id.isEmpty) continue;
      selections[id] = true;
    }

    return showDialog<Map<String, bool>>(
      context: context,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (ctx, setLocal) {
            return AlertDialog(
              title: const Text('Quick inventory check'),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Text('Confirm a few items so today\'s plan is more accurate.'),
                    const SizedBox(height: 12),
                    for (final item in verify)
                      Builder(
                        builder: (_) {
                          final id = item['id']?.toString() ?? '';
                          if (id.isEmpty) return const SizedBox.shrink();
                          final label = (item['display_name']?.toString().trim().isNotEmpty == true)
                              ? item['display_name'].toString().trim()
                              : (item['ingredient_name']?.toString() ?? 'Item');
                          final checked = selections[id] ?? true;
                          return CheckboxListTile(
                            value: checked,
                            onChanged: (v) => setLocal(() => selections[id] = (v ?? true)),
                            title: Text(label),
                            controlAffinity: ListTileControlAffinity.leading,
                          );
                        },
                      ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(ctx),
                  child: const Text('Skip'),
                ),
                FilledButton(
                  onPressed: () => Navigator.pop(ctx, selections),
                  child: const Text('Continue'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  Future<void> _applyInventorySelections(
    ApiClient apiClient,
    List<Map<String, dynamic>> verify,
    Map<String, bool> selections,
  ) async {
    for (final item in verify) {
      final id = item['id']?.toString() ?? '';
      if (id.isEmpty) continue;

      final stillHave = selections[id] ?? true;
      if (!stillHave) {
        await apiClient.patch('/inventory-db/items/$id', {
          'is_current': false,
        });
      }
    }
  }

  @override
  void initState() {
    super.initState();
    _loadLatest();
  }

  Future<void> _loadLatest() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    final apiClient = Provider.of<ApiClient>(context, listen: false);
    try {
      final res = await apiClient.get('/plan/latest?plan_type=daily');
      if (!mounted) return;
      setState(() {
        _latest = MenuPlanResponse.fromJson(res);
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _latest = null;
        _loading = false;
        final msg = e.toString();
        _error = msg.contains('404') ? null : msg;
      });
    }
  }

  String _todayIsoDate() {
    final now = DateTime.now();
    final y = now.year.toString().padLeft(4, '0');
    final m = now.month.toString().padLeft(2, '0');
    final d = now.day.toString().padLeft(2, '0');
    return '$y-$m-$d';
  }

  Future<void> _deleteTodayPlan() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Remove plan'),
        content: const Text('Remove the saved daily plan so you can generate a new one?'),
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
      // Scope to today's date when possible.
      await apiClient.delete('/plan/latest?plan_type=daily&plan_date=${_todayIsoDate()}');
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Daily plan removed.')),
      );
      await _loadLatest();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to remove plan: $e')),
      );
    }
  }

  Future<void> _generateDailyPlan() async {
    if (_generating) return;
    setState(() {
      _generating = true;
      _error = null;
    });

    final apiClient = Provider.of<ApiClient>(context, listen: false);
    final profileState = Provider.of<ProfileState>(context, listen: false);

    try {
      final verify = await _fetchVerifyItems(apiClient);
      if (verify.isNotEmpty && mounted) {
        final selections = await _askQuickInventoryCheck(verify);
        if (selections != null && selections.isNotEmpty) {
          await _applyInventorySelections(apiClient, verify, selections);
        }
      }

      final body = <String, dynamic>{
        'time_available_minutes': 60,
        'servings': 4,
        'date': _todayIsoDate(),
      };

      // Reuse the inventory screen preference so planning can consider older (inactive) pantry items.
      try {
        final prefs = await SharedPreferences.getInstance();
        final includeInactive = prefs.getBool('savo.inventory.show_inactive_items') ?? false;
        if (includeInactive) {
          body['include_inactive_inventory'] = true;
        }
      } catch (_) {
        // Best-effort only
      }

      final preferred = profileState.favoriteCuisines;
      if (preferred.isNotEmpty) {
        body['cuisine_preferences'] = preferred;
      }

      final outputLang = (profileState.preferredLanguage?.trim().isNotEmpty == true)
          ? profileState.preferredLanguage!.trim()
          : (profileState.primaryLanguage?.trim().isNotEmpty == true)
              ? profileState.primaryLanguage!.trim()
              : 'en';
      body['output_language'] = outputLang;
      body['output_languages'] = outputLang == 'en' ? ['en'] : ['en', outputLang];

      final measurementSystem = profileState.measurementSystem;
      if (measurementSystem != null && measurementSystem.trim().isNotEmpty) {
        body['measurement_system'] = measurementSystem.trim();
      }

      // Prefer cached daily plans when available for reliability (especially on web).
      final response = await apiClient.post('/plan/daily', body);
      if (!mounted) return;

      final plan = MenuPlanResponse.fromJson(response);
      setState(() {
        _latest = plan;
        _generating = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _generating = false;
        _error = e.toString();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (kDebugMode || kProfileMode) {
      SavoUiGuards.warnIfTooManyChoices(
        screen: 'DailyPlanScreen',
        surface: 'Primary actions',
        choices: 1,
      );
    }

    final body = _loading
        ? const Center(child: CircularProgressIndicator())
        : _latest != null
            ? PlanningResultsScreen(
                menuPlan: _latest!,
                planType: 'daily',
                showScaffold: false,
              )
            : Center(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        _error ?? 'No saved plan yet',
                        textAlign: TextAlign.center,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      const SizedBox(height: 12),
                      FilledButton(
                        onPressed: _generating ? null : _generateDailyPlan,
                        child: Text(_generating ? 'Generating...' : 'Generate'),
                      ),
                    ],
                  ),
                ),
              );

    return Scaffold(
      appBar: AppBar(
        title: const Text('Daily Plan'),
        actions: [
          IconButton(
            tooltip: 'Remove plan',
            onPressed: (_latest == null || _generating) ? null : _deleteTodayPlan,
            icon: const Icon(Icons.delete_outline),
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(child: body),
          if (_latest != null)
            Padding(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: _generating ? null : _generateDailyPlan,
                  child: Text(_generating ? 'Generating...' : 'Regenerate'),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
