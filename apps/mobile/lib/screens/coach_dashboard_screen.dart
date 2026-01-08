import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models/coach_client.dart';
import '../models/planning.dart';
import '../services/api_client.dart';
import '../services/coach_clients_local_service.dart';
import '../services/entitlements_service.dart';
// PlanShareService is wired in a follow-up (share button in results).
import '../theme/app_theme.dart';
import '../widgets/pro_paywall_sheet.dart';
import 'planning_results_screen.dart';

class CoachDashboardScreen extends StatefulWidget {
  const CoachDashboardScreen({super.key});

  @override
  State<CoachDashboardScreen> createState() => _CoachDashboardScreenState();
}

class _CoachDashboardScreenState extends State<CoachDashboardScreen> {
  bool _loading = true;
  List<CoachClient> _clients = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final list = await CoachClientsLocalService.instance.list();
    if (!mounted) return;
    setState(() {
      _clients = list;
      _loading = false;
    });
  }

  Future<void> _saveClients(List<CoachClient> next) async {
    await CoachClientsLocalService.instance.saveAll(next);
    if (!mounted) return;
    setState(() => _clients = next);
  }

  Future<void> _addOrEditClient({CoachClient? existing}) async {
    final nameController = TextEditingController(text: existing?.name ?? '');
    final notesController = TextEditingController(text: existing?.notes ?? '');
    final cuisinesController = TextEditingController(text: (existing?.favoriteCuisines ?? const []).join(', '));

    String planningGoal = existing?.planningGoal ?? 'balanced';
    String measurementSystem = existing?.measurementSystem ?? '';
    String outputLanguage = existing?.outputLanguage ?? '';

    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) {
        return AlertDialog(
          title: Text(existing == null ? 'Add client' : 'Edit client'),
          content: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                TextField(
                  controller: nameController,
                  decoration: const InputDecoration(labelText: 'Client name'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: cuisinesController,
                  decoration: const InputDecoration(labelText: 'Favorite cuisines (comma-separated)'),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  value: planningGoal,
                  items: const [
                    DropdownMenuItem(value: 'balanced', child: Text('Balanced')),
                    DropdownMenuItem(value: 'high_protein', child: Text('High protein')),
                    DropdownMenuItem(value: 'low_cost', child: Text('Low cost')),
                    DropdownMenuItem(value: 'low_carb', child: Text('Low carb')),
                  ],
                  onChanged: (v) {
                    if (v == null) return;
                    planningGoal = v;
                  },
                  decoration: const InputDecoration(labelText: 'Planning goal'),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  value: measurementSystem.isEmpty ? 'auto' : measurementSystem,
                  items: const [
                    DropdownMenuItem(value: 'auto', child: Text('Auto')),
                    DropdownMenuItem(value: 'metric', child: Text('Metric')),
                    DropdownMenuItem(value: 'imperial', child: Text('Imperial')),
                  ],
                  onChanged: (v) {
                    if (v == null) return;
                    measurementSystem = v == 'auto' ? '' : v;
                  },
                  decoration: const InputDecoration(labelText: 'Measurement system'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: TextEditingController(text: outputLanguage),
                  decoration: const InputDecoration(
                    labelText: 'Output language (optional, e.g. en, hi)',
                  ),
                  onChanged: (v) => outputLanguage = v,
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: notesController,
                  decoration: const InputDecoration(labelText: 'Notes (optional)'),
                  maxLines: 3,
                ),
                const SizedBox(height: 8),
                Text(
                  'Note: In this MVP, client pantry/preferences are entered manually in this app.',
                  style: Theme.of(ctx).textTheme.bodySmall,
                ),
              ],
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Save')),
          ],
        );
      },
    );

    if (ok != true) return;

    final name = nameController.text.trim();
    if (name.isEmpty) return;

    final cuisines = cuisinesController.text
        .split(',')
        .map((s) => s.trim())
        .where((s) => s.isNotEmpty)
        .toList();

    final client = CoachClient(
      id: existing?.id ?? DateTime.now().microsecondsSinceEpoch.toString(),
      name: name,
      notes: notesController.text.trim(),
      favoriteCuisines: cuisines,
      planningGoal: planningGoal,
      measurementSystem: measurementSystem.isEmpty ? null : measurementSystem,
      outputLanguage: outputLanguage.trim().isEmpty ? null : outputLanguage.trim(),
    );

    final next = [..._clients];
    if (existing == null) {
      next.add(client);
    } else {
      final idx = next.indexWhere((c) => c.id == existing.id);
      if (idx >= 0) {
        next[idx] = client;
      } else {
        next.add(client);
      }
    }

    await _saveClients(next);
  }

  Future<void> _deleteClient(CoachClient client) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Remove client'),
        content: Text('Remove ${client.name}?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Remove')),
        ],
      ),
    );

    if (confirmed != true) return;
    final next = _clients.where((c) => c.id != client.id).toList();
    await _saveClients(next);
  }

  Future<void> _generateWeeklyPlanForClient(CoachClient client) async {
    final isPro = await EntitlementsService.instance.isPro();
    if (!isPro && mounted) {
      await showProPaywallSheet(
        context,
        title: 'Upgrade to SAVO Pro',
        ctaLabel: 'Upgrade to weekly planning',
        reason: 'Weekly planning is a Pro feature. Pro saves you time by generating a full week plus a shopping list in one tap.',
          trigger: 'coach_dashboard_gate',
        );
      return;
    }

    final apiClient = Provider.of<ApiClient>(context, listen: false);

    final start = DateTime.now();
    final startDate = DateFormat('yyyy-MM-dd').format(start);

    final body = <String, dynamic>{
      'start_date': startDate,
      'num_days': 7,
      // Client overrides (manual MVP)
      if (client.favoriteCuisines.isNotEmpty) 'cuisine_preferences': client.favoriteCuisines,
      if (client.planningGoal.trim().isNotEmpty && client.planningGoal != 'balanced') 'planning_goal': client.planningGoal,
      if (client.measurementSystem != null) 'measurement_system': client.measurementSystem,
      if (client.outputLanguage != null) 'output_language': client.outputLanguage,
      if (client.outputLanguage != null)
        'output_languages': client.outputLanguage == 'en' ? ['en'] : ['en', client.outputLanguage],
    };

    try {
      final res = await apiClient.post('/plan/weekly', body);
      if (!mounted) return;

      if (res['status'] == 'ok') {
        final plan = MenuPlanResponse.fromJson(res);
        await Navigator.push(
          context,
          MaterialPageRoute(
            settings: const RouteSettings(name: '/coach_planning_results'),
            builder: (_) => PlanningResultsScreen(menuPlan: plan, planType: 'weekly'),
          ),
        );
        return;
      }

      final msg = (res['error_message'] ?? 'Planning failed').toString();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Planning failed: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Coach dashboard'),
        actions: [
          IconButton(
            tooltip: 'Add client',
            onPressed: _loading ? null : () => _addOrEditClient(),
            icon: const Icon(Icons.person_add_alt_1),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _loading ? null : () => _addOrEditClient(),
        child: const Icon(Icons.add),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView.builder(
                padding: const EdgeInsets.all(AppSpacing.md),
                itemCount: _clients.isEmpty ? 1 : _clients.length,
                itemBuilder: (context, index) {
                  if (_clients.isEmpty) {
                    return Card(
                      child: Padding(
                        padding: const EdgeInsets.all(AppSpacing.md),
                        child: Text(
                          'No clients yet. Tap + to add one.',
                          style: Theme.of(context).textTheme.bodyMedium,
                        ),
                      ),
                    );
                  }

                  final client = _clients[index];
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
                                  client.name,
                                  style: Theme.of(context).textTheme.titleMedium,
                                ),
                              ),
                              IconButton(
                                tooltip: 'Edit',
                                onPressed: () => _addOrEditClient(existing: client),
                                icon: const Icon(Icons.edit_outlined),
                              ),
                              IconButton(
                                tooltip: 'Remove',
                                onPressed: () => _deleteClient(client),
                                icon: const Icon(Icons.delete_outline),
                              ),
                            ],
                          ),
                          if (client.favoriteCuisines.isNotEmpty) ...[
                            const SizedBox(height: 4),
                            Text(
                              'Cuisines: ${client.favoriteCuisines.join(', ')}',
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                          ],
                          if (client.notes.trim().isNotEmpty) ...[
                            const SizedBox(height: 4),
                            Text(
                              client.notes,
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                          ],
                          const SizedBox(height: 12),
                          SizedBox(
                            width: double.infinity,
                            child: FilledButton(
                              onPressed: () => _generateWeeklyPlanForClient(client),
                              child: const Text('Generate weekly plan'),
                            ),
                          ),
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
    );
  }
}
