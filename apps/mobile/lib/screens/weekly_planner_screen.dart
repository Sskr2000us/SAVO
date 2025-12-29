import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
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
      final response = await apiClient.post('/plan/weekly', {
        'start_date': DateFormat('yyyy-MM-dd').format(_startDate),
        'num_days': _numDays,
      });

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
