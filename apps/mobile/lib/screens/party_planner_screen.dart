import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_client.dart';
import '../models/planning.dart';
import 'planning_results_screen.dart';

class PartyPlannerScreen extends StatefulWidget {
  const PartyPlannerScreen({super.key});

  @override
  State<PartyPlannerScreen> createState() => _PartyPlannerScreenState();
}

class _PartyPlannerScreenState extends State<PartyPlannerScreen> {
  int _guestCount = 10;
  int _child0To12 = 0;
  int _teen13To17 = 0;
  int _adult18Plus = 10;
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

  String? _validationError;

  void _validateAgeGroups() {
    final sum = _child0To12 + _teen13To17 + _adult18Plus;
    if (sum != _guestCount) {
      _validationError = 'Age groups must sum to $_guestCount guests';
    } else {
      _validationError = null;
    }
  }

  void _updateGuestCount(int newCount) {
    setState(() {
      _guestCount = newCount;
      // Redistribute proportionally
      final total = _child0To12 + _teen13To17 + _adult18Plus;
      if (total > 0) {
        _child0To12 = (_child0To12 * newCount / total).round();
        _teen13To17 = (_teen13To17 * newCount / total).round();
        _adult18Plus = newCount - _child0To12 - _teen13To17;
      } else {
        _adult18Plus = newCount;
      }
      _validateAgeGroups();
    });
  }

  Future<void> _planParty() async {
    _validateAgeGroups();
    if (_validationError != null) {
      _showError(_validationError!);
      return;
    }

    setState(() => _planning = true);

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final body = <String, dynamic>{
        'party_settings': {
          'guest_count': _guestCount,
          'age_group_counts': {
            'child_0_12': _child0To12,
            'teen_13_17': _teen13To17,
            'adult_18_plus': _adult18Plus,
          },
        },
      };

      if (_planningGoal != 'balanced') {
        body['planning_goal'] = _planningGoal;
      }
      if (_avoidWaste) {
        body['avoid_waste'] = true;
      }

      if (!_useLeftovers) {
        body['use_leftovers'] = false;
      }

      final response = await apiClient.post('/plan/party', body);

      if (response['status'] == 'ok') {
        final menuPlan = MenuPlanResponse.fromJson(response);
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(
            builder: (_) => PlanningResultsScreen(
              menuPlan: menuPlan,
              planType: 'party',
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
        title: const Text('Party Planner'),
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
                      'Guest Count',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Expanded(
                          child: Slider(
                            value: _guestCount.toDouble(),
                            min: 2,
                            max: 80,
                            divisions: 78,
                            label: '$_guestCount guests',
                            onChanged: (value) => _updateGuestCount(value.toInt()),
                          ),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 12,
                            vertical: 6,
                          ),
                          decoration: BoxDecoration(
                            color: Theme.of(context).colorScheme.primaryContainer,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            '$_guestCount',
                            style: Theme.of(context)
                                .textTheme
                                .titleMedium
                                ?.copyWith(
                                  color: Theme.of(context)
                                      .colorScheme
                                      .onPrimaryContainer,
                                ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Age Groups',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 16),
                    _AgeGroupStepper(
                      label: 'Children (0-12)',
                      value: _child0To12,
                      onChanged: (value) {
                        setState(() {
                          _child0To12 = value;
                          _validateAgeGroups();
                        });
                      },
                    ),
                    const SizedBox(height: 12),
                    _AgeGroupStepper(
                      label: 'Teens (13-17)',
                      value: _teen13To17,
                      onChanged: (value) {
                        setState(() {
                          _teen13To17 = value;
                          _validateAgeGroups();
                        });
                      },
                    ),
                    const SizedBox(height: 12),
                    _AgeGroupStepper(
                      label: 'Adults (18+)',
                      value: _adult18Plus,
                      onChanged: (value) {
                        setState(() {
                          _adult18Plus = value;
                          _validateAgeGroups();
                        });
                      },
                    ),
                    const SizedBox(height: 16),
                    const Divider(),
                    const SizedBox(height: 8),
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
                      subtitle: const Text('Prioritize expiring items and leftover reuse'),
                      onChanged: (v) => setState(() => _avoidWaste = v),
                    ),
                    SwitchListTile.adaptive(
                      value: _useLeftovers,
                      contentPadding: EdgeInsets.zero,
                      title: const Text('Use leftovers (when available)'),
                      subtitle: const Text('Schedule leftovers sooner when safe'),
                      onChanged: (v) => setState(() => _useLeftovers = v),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            if (_validationError != null)
              Card(
                color: Colors.red[50],
                child: Padding(
                  padding: const EdgeInsets.all(12.0),
                  child: Row(
                    children: [
                      Icon(Icons.error, color: Colors.red[700]),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          _validationError!,
                          style: TextStyle(color: Colors.red[700]),
                        ),
                      ),
                    ],
                  ),
                ),
              )
            else
              Card(
                color: Colors.green[50],
                child: Padding(
                  padding: const EdgeInsets.all(12.0),
                  child: Row(
                    children: [
                      Icon(Icons.check_circle, color: Colors.green[700]),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'Total: ${_child0To12 + _teen13To17 + _adult18Plus} guests',
                          style: TextStyle(color: Colors.green[700]),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            const Spacer(),
            FilledButton(
              onPressed: (_planning || _validationError != null) ? null : _planParty,
              child: _planning
                  ? const SizedBox(
                      height: 20,
                      width: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Text('Generate Party Menu'),
            ),
          ],
        ),
      ),
    );
  }
}

class _AgeGroupStepper extends StatelessWidget {
  final String label;
  final int value;
  final ValueChanged<int> onChanged;

  const _AgeGroupStepper({
    required this.label,
    required this.value,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Text(label),
        ),
        IconButton(
          icon: const Icon(Icons.remove_circle_outline),
          onPressed: value > 0 ? () => onChanged(value - 1) : null,
        ),
        Container(
          width: 40,
          alignment: Alignment.center,
          child: Text(
            '$value',
            style: Theme.of(context).textTheme.titleMedium,
          ),
        ),
        IconButton(
          icon: const Icon(Icons.add_circle_outline),
          onPressed: () => onChanged(value + 1),
        ),
      ],
    );
  }
}
