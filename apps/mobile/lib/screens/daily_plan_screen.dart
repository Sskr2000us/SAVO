import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

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

  Future<void> _generateDailyPlan() async {
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
        'date': _todayIsoDate(),
      };

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
