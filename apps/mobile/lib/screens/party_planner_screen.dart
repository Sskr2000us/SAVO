import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/profile_state.dart';
import '../services/api_client.dart';
import '../services/entitlements_service.dart';
import '../models/planning.dart';
import '../models/cuisine.dart';
import '../widgets/pro_paywall_sheet.dart';
import 'planning_results_screen.dart';

class PartyPlannerScreen extends StatefulWidget {
  const PartyPlannerScreen({super.key});

  @override
  State<PartyPlannerScreen> createState() => _PartyPlannerScreenState();
}

class _PartyPlannerScreenState extends State<PartyPlannerScreen> {
  int _child0To12 = 0;
  int _teen13To17 = 0;
  int _adult18Plus = 10;
  bool _planning = false;

  List<Cuisine> _cuisines = const [];
  bool _loadingCuisines = true;
  String _selectedCuisine = 'auto';

  int _countAppetizers = 2;
  int _countMains = 2;
  int _countSides = 2;
  int _countDesserts = 1;

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

  @override
  void initState() {
    super.initState();
    _loadCuisines();
  }

  Future<void> _loadCuisines() async {
    setState(() => _loadingCuisines = true);
    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final response = await apiClient.get('/cuisines');
      if (!mounted) return;

      if (response is List) {
        setState(() {
          _cuisines = response
              .whereType<Map>()
              .map((m) => Cuisine.fromJson(Map<String, dynamic>.from(m)))
              .toList();
          _loadingCuisines = false;
        });
        return;
      }
    } catch (_) {
      // ignore
    }
    if (!mounted) return;
    setState(() => _loadingCuisines = false);
  }

  int _totalGuests() => _child0To12 + _teen13To17 + _adult18Plus;

  Future<void> _planParty() async {
    if (_totalGuests() <= 0) {
      _showError('Please enter at least 1 guest');
      return;
    }

    final isPro = await EntitlementsService.instance.isPro();
    if (!isPro && mounted) {
      await showProPaywallSheet(
        context,
        title: 'Upgrade to SAVO Pro',
        ctaLabel: 'Upgrade to family planning',
        reason: 'Planning for groups and events is a Pro feature. Upgrade to generate menus faster and reduce waste with better shopping lists.',
        trigger: 'party_planning_gate',
      );
      return;
    }

    setState(() => _planning = true);

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
        final profileState = Provider.of<ProfileState>(context, listen: false);
      final body = <String, dynamic>{
        'selected_cuisine': _selectedCuisine,
        'party_settings': {
          'guest_count': _totalGuests(),
          'age_group_counts': {
            'child_0_12': _child0To12,
            'teen_13_17': _teen13To17,
            'adult_18_plus': _adult18Plus,
          },
        },
        'party_course_counts': {
          'appetizers': _countAppetizers,
          'mains': _countMains,
          'sides': _countSides,
          'desserts': _countDesserts,
        },
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

      final response = await apiClient.post('/plan/party?force_regenerate=true', body);

      if (response['status'] == 'ok') {
        final menuPlan = MenuPlanResponse.fromJson(response);
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(
            settings: const RouteSettings(name: '/planning_results'),
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
      body: SingleChildScrollView(
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
                      'Cuisine',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 8),
                    _loadingCuisines
                        ? const LinearProgressIndicator()
                        : DropdownButtonFormField<String>(
                            value: _selectedCuisine,
                            decoration: const InputDecoration(
                              labelText: 'Cuisine type',
                              border: OutlineInputBorder(),
                            ),
                            items: [
                              const DropdownMenuItem(
                                value: 'auto',
                                child: Text('Auto'),
                              ),
                              ..._cuisines
                                  .where((c) => c.partyEnabled)
                                  .map(
                                    (c) => DropdownMenuItem<String>(
                                      value: c.cuisineId,
                                      child: Text(c.name),
                                    ),
                                  ),
                            ],
                            onChanged: (value) {
                              if (value == null) return;
                              setState(() => _selectedCuisine = value);
                            },
                          ),
                    const SizedBox(height: 16),
                    Text(
                      'Courses',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 8),
                    _CourseCountStepper(
                      label: 'Appetizers',
                      value: _countAppetizers,
                      onChanged: (v) => setState(() => _countAppetizers = v),
                    ),
                    const SizedBox(height: 8),
                    _CourseCountStepper(
                      label: 'Mains',
                      value: _countMains,
                      onChanged: (v) => setState(() => _countMains = v),
                    ),
                    const SizedBox(height: 8),
                    _CourseCountStepper(
                      label: 'Sides',
                      value: _countSides,
                      onChanged: (v) => setState(() => _countSides = v),
                    ),
                    const SizedBox(height: 8),
                    _CourseCountStepper(
                      label: 'Desserts',
                      value: _countDesserts,
                      onChanged: (v) => setState(() => _countDesserts = v),
                    ),
                  ],
                ),
              ),
            ),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Guests',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 12),
                    Text(
                      'Total: ${_totalGuests()} guests',
                      style: Theme.of(context).textTheme.titleMedium,
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
                        'Total: ${_totalGuests()} guests',
                        style: TextStyle(color: Colors.green[700]),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: _planning ? null : _planParty,
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

class _CourseCountStepper extends StatelessWidget {
  final String label;
  final int value;
  final ValueChanged<int> onChanged;

  const _CourseCountStepper({
    required this.label,
    required this.value,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(child: Text(label)),
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
          onPressed: value < 6 ? () => onChanged(value + 1) : null,
        ),
      ],
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
