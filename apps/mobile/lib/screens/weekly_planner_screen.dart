import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../models/profile_state.dart';
import '../services/api_client.dart';
import '../models/planning.dart';
import 'planning_results_screen.dart';

class WeeklyPlannerScreen extends StatefulWidget {
  const WeeklyPlannerScreen({super.key});

  @override
  State<WeeklyPlannerScreen> createState() => _WeeklyPlannerScreenState();
}

class _WeeklyPlannerScreenState extends State<WeeklyPlannerScreen> {
  DateTime _startDate = DateTime.now();
  int _numDays = 3;
  bool _planning = false;

  static const Map<String, String> _planningGoalLabels = {
    'balanced': 'Balanced',
    'fastest': 'Fastest',
    'healthiest': 'Healthiest',
    'kid_friendly': 'Kid-friendly',
    'budget': 'Budget',
    'use_what_i_have': 'Use what I have',
  };

  String _planningGoal = 'balanced';
  bool _avoidWaste = false;
  bool _useLeftovers = true;

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
      selections[id] = true; // default: assume they still have it
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
                    const Text('Confirm a few items so the plan is more accurate.'),
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

  Future<void> _applyInventorySelections(ApiClient apiClient, List<Map<String, dynamic>> verify, Map<String, bool> selections) async {
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

  Future<void> _selectStartDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _startDate,
      firstDate: DateTime.now(),
      lastDate: DateTime.now().add(const Duration(days: 30)),
    );

    if (picked != null) {
      setState(() {
        _startDate = picked;
      });
    }
  }

  Future<void> _planWeekly() async {
    setState(() => _planning = true);

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);

      // Best-effort: verify up to 5 uncertain items (prevents planning on stale pantry state).
      final verify = await _fetchVerifyItems(apiClient);
      if (verify.isNotEmpty && mounted) {
        final selections = await _askQuickInventoryCheck(verify);
        if (selections != null && selections.isNotEmpty) {
          await _applyInventorySelections(apiClient, verify, selections);
        }
      }

      final profileState = Provider.of<ProfileState>(context, listen: false);
      final body = <String, dynamic>{
        'start_date': DateFormat('yyyy-MM-dd').format(_startDate),
        'num_days': _numDays,
      };

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

      if (_planningGoal != 'balanced') {
        body['planning_goal'] = _planningGoal;
      }
      if (_avoidWaste) {
        body['avoid_waste'] = true;
      }
      if (!_useLeftovers) {
        body['use_leftovers'] = false;
      }

      final response = await apiClient.post('/plan/weekly', body);

      if (response['status'] == 'ok') {
        final menuPlan = MenuPlanResponse.fromJson(response);
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(
            builder: (_) => PlanningResultsScreen(
              menuPlan: menuPlan,
              planType: 'weekly',
            ),
          ),
        );
      } else {
        _showError(response['error_message'] ?? 'Planning failed');
      }
    } catch (e) {
      _showError(e.toString());
    } finally {
      setState(() => _planning = false);
    }
  }

  void _showError(String message) {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Error'),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Weekly Planner'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Plan ahead',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 16),
                    ListTile(
                      title: const Text('Start Date'),
                      trailing: Text(
                        DateFormat('MMM d, yyyy').format(_startDate),
                      ),
                      onTap: _selectStartDate,
                    ),
                    const Divider(),
                    ListTile(
                      title: const Text('Number of Days'),
                      trailing: DropdownButton<int>(
                        value: _numDays,
                        items: [1, 2, 3, 4]
                            .map((d) => DropdownMenuItem(
                                  value: d,
                                  child: Text('$d ${d == 1 ? 'day' : 'days'}'),
                                ))
                            .toList(),
                        onChanged: (value) {
                          setState(() {
                            _numDays = value ?? 3;
                          });
                        },
                      ),
                    ),
                    const Divider(),
                    Text(
                      'Advanced options (optional)',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 8),
                    DropdownButtonFormField<String>(
                      value: _planningGoal,
                      decoration: const InputDecoration(
                        labelText: 'Planning goal',
                        border: OutlineInputBorder(),
                      ),
                      items: _planningGoalLabels.entries
                          .map(
                            (e) => DropdownMenuItem<String>(
                              value: e.key,
                              child: Text(e.value),
                            ),
                          )
                          .toList(),
                      onChanged: (value) {
                        if (value == null) return;
                        setState(() => _planningGoal = value);
                      },
                    ),
                    SwitchListTile.adaptive(
                      value: _avoidWaste,
                      contentPadding: EdgeInsets.zero,
                      title: const Text('Avoid waste'),
                      subtitle: const Text('Use expiring items earlier, reuse leftovers'),
                      onChanged: (v) => setState(() => _avoidWaste = v),
                    ),
                    SwitchListTile.adaptive(
                      value: _useLeftovers,
                      contentPadding: EdgeInsets.zero,
                      title: const Text('Use leftovers (when available)'),
                      subtitle: const Text('Schedule leftover meals sooner when safe'),
                      onChanged: (v) => setState(() => _useLeftovers = v),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            Card(
              color: Colors.blue[50],
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Row(
                  children: [
                    Icon(Icons.calendar_today, color: Colors.blue[700]),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        'Planning for $_numDays ${_numDays == 1 ? 'day' : 'days'} starting ${DateFormat('MMM d').format(_startDate)}',
                        style: TextStyle(color: Colors.blue[700]),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const Spacer(),
            FilledButton(
              onPressed: _planning ? null : _planWeekly,
              child: _planning
                  ? const SizedBox(
                      height: 20,
                      width: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Text('Generate Weekly Plan'),
            ),
          ],
        ),
      ),
    );
  }
}
