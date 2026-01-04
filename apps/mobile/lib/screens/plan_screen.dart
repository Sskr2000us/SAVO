import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/planning.dart';
import '../models/profile_state.dart';
import '../services/api_client.dart';
import 'planning_results_screen.dart';

class PlanScreen extends StatefulWidget {
  const PlanScreen({super.key});

  @override
  State<PlanScreen> createState() => _PlanScreenState();
}

class _PlanScreenState extends State<PlanScreen> {
  MenuPlanResponse? _latest;
  bool _loading = true;
  bool _generating = false;
  String? _error;
  String _planType = 'daily';

  @override
  void initState() {
    super.initState();
    _loadLatest();
  }

  void _setPlanType(String value) {
    if (_planType == value) return;
    setState(() {
      _planType = value;
      _latest = null;
      _error = null;
    });
    _loadLatest();
  }

  String _todayIsoDate() {
    final now = DateTime.now();
    final y = now.year.toString().padLeft(4, '0');
    final m = now.month.toString().padLeft(2, '0');
    final d = now.day.toString().padLeft(2, '0');
    return '$y-$m-$d';
  }

  Future<void> _loadLatest() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    final apiClient = Provider.of<ApiClient>(context, listen: false);
    try {
      final res = await apiClient.get('/plan/latest?plan_type=$_planType');
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
        // Treat 404 as "no saved plan" rather than a hard error.
        final msg = e.toString();
        _error = msg.contains('404') ? null : msg;
      });
    }
  }

  Future<void> _generatePlan() async {
    if (_generating) return;
    setState(() {
      _generating = true;
      _error = null;
    });

    final apiClient = Provider.of<ApiClient>(context, listen: false);
    final profileState = Provider.of<ProfileState>(context, listen: false);

    try {
      final body = <String, dynamic>{
        'time_available_minutes': 60,
        'servings': 4,
      };

      if (_planType == 'weekly') {
        body['start_date'] = _todayIsoDate();
        body['num_days'] = 7;
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

      // Only generate when the user taps Generate.
        final String endpoint = _planType == 'weekly'
          ? '/plan/weekly?force_regenerate=true'
          : '/plan/daily?force_regenerate=true';
      final response = await apiClient.post(endpoint, body);
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

  Future<void> _clearSavedPlan() async {
    if (_loading || _generating) return;
    setState(() {
      _error = null;
    });

    final apiClient = Provider.of<ApiClient>(context, listen: false);
    try {
      await apiClient.delete('/plan/latest?plan_type=$_planType');
      if (!mounted) return;
      setState(() {
        _latest = null;
      });
      await _loadLatest();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final body = _loading
        ? const Center(child: CircularProgressIndicator())
        : _latest != null
            ? PlanningResultsScreen(
                menuPlan: _latest!,
                planType: _planType,
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
                      ElevatedButton(
                        onPressed: _generating ? null : _generatePlan,
                        child: Text(_generating ? 'Generating...' : 'Generate'),
                      ),
                    ],
                  ),
                ),
              );

    return Scaffold(
      appBar: AppBar(
        title: const Text('Plan'),
        actions: [
          DropdownButtonHideUnderline(
            child: DropdownButton<String>(
              value: _planType,
              onChanged: (_loading || _generating)
                  ? null
                  : (v) {
                      if (v != null) _setPlanType(v);
                    },
              items: const [
                DropdownMenuItem(value: 'daily', child: Text('Daily')),
                DropdownMenuItem(value: 'weekly', child: Text('Weekly')),
              ],
            ),
          ),
          IconButton(
            tooltip: 'Refresh saved plan',
            onPressed: _loading ? null : _loadLatest,
            icon: const Icon(Icons.refresh),
          ),
          IconButton(
            tooltip: 'Clear saved plan',
            onPressed: (_loading || _generating) ? null : _clearSavedPlan,
            icon: const Icon(Icons.delete_outline),
          ),
          TextButton(
            onPressed: _generating ? null : _generatePlan,
            child: Text(_generating ? 'Generating...' : 'Generate'),
          ),
        ],
      ),
      body: body,
    );
  }
}
