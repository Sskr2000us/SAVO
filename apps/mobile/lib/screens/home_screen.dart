import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_client.dart';
import '../models/planning.dart';
import 'planning_results_screen.dart';
import 'weekly_planner_screen.dart';
import 'party_planner_screen.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('SAVO'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'What would you like to cook today?',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 24),
            _PlanningOptionCard(
              title: 'Daily Menu',
              description: 'Plan today\'s meals',
              icon: Icons.today,
              color: Colors.blue,
              onTap: () => _planDaily(context),
            ),
            const SizedBox(height: 16),
            _PlanningOptionCard(
              title: 'Weekly Planner',
              description: 'Plan 1-4 days ahead',
              icon: Icons.calendar_today,
              color: Colors.green,
              onTap: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => const WeeklyPlannerScreen(),
                  ),
                );
              },
            ),
            const SizedBox(height: 16),
            _PlanningOptionCard(
              title: 'Party Menu',
              description: 'Plan for guests',
              icon: Icons.celebration,
              color: Colors.orange,
              onTap: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => const PartyPlannerScreen(),
                  ),
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _planDaily(BuildContext context) async {
    final apiClient = Provider.of<ApiClient>(context, listen: false);
    
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => const Center(child: CircularProgressIndicator()),
    );

    try {
      print('DEBUG: Sending daily plan request with time=60, servings=4');
      final response = await apiClient.post('/plan/daily', {
        'time_available_minutes': 60,
        'servings': 4,
      });
      print('DEBUG: Received response: ${response.toString().substring(0, 100)}');
      Navigator.pop(context); // Close loading

      if (response['status'] == 'ok') {
        final menuPlan = MenuPlanResponse.fromJson(response);
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => PlanningResultsScreen(
              menuPlan: menuPlan,
              planType: 'daily',
            ),
          ),
        );
      } else {
        _showError(context, response['error_message'] ?? 'Planning failed');
      }
    } catch (e) {
      Navigator.pop(context);
      _showError(context, e.toString());
    }
  }

  void _showError(BuildContext context, String message) {
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
}

class _PlanningOptionCard extends StatelessWidget {
  final String title;
  final String description;
  final IconData icon;
  final Color color;
  final VoidCallback onTap;

  const _PlanningOptionCard({
    required this.title,
    required this.description,
    required this.icon,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 2,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(20.0),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: color.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(icon, color: color, size: 32),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.bold,
                          ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      description,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                            color: Colors.grey[600],
                          ),
                    ),
                  ],
                ),
              ),
              const Icon(Icons.arrow_forward_ios, size: 16),
            ],
          ),
        ),
      ),
    );
  }
}
