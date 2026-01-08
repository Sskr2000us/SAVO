import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../services/api_client.dart';
import '../services/decision_intelligence_service.dart';

/// Smart Actions Screen
/// Shows prioritized ingredient recommendations
class SmartActionsScreen extends StatefulWidget {
  const SmartActionsScreen({Key? key}) : super(key: key);

  @override
  State<SmartActionsScreen> createState() => _SmartActionsScreenState();
}

class _SmartActionsScreenState extends State<SmartActionsScreen> {
  DecisionIntelligenceService? _service;
  bool _started = false;
  List<DecisionResult> _actions = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _service ??=
        DecisionIntelligenceService(Provider.of<ApiClient>(context, listen: false));

    if (!_started) {
      _started = true;
      _loadActions();
    }
  }

  Future<void> _loadActions() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final service = _service;
      if (service == null) return;

      final actions = await service.evaluateInventory(limit: 20);
      setState(() {
        _actions = actions;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Smart Actions'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadActions,
            tooltip: 'Refresh',
          ),
        ],
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const Center(
        child: CircularProgressIndicator(),
      );
    }

    if (_error != null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.error_outline,
              size: 64,
              color: Colors.red,
            ),
            const SizedBox(height: 16),
            Text(
              'Error loading actions',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Text(
              _error!,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _loadActions,
              child: const Text('Retry'),
            ),
          ],
        ),
      );
    }

    if (_actions.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.check_circle_outline,
              size: 64,
              color: Colors.green,
            ),
            const SizedBox(height: 16),
            Text(
              'All clear!',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            const Text(
              'No urgent actions needed right now.',
              textAlign: TextAlign.center,
            ),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadActions,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _actions.length,
        itemBuilder: (context, index) {
          final action = _actions[index];
          return ActionCard(
            action: action,
            onFeedback: (response) => _handleFeedback(action, response),
          );
        },
      ),
    );
  }

  Future<void> _handleFeedback(DecisionResult action, String response) async {
    if (action.actionId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No action ID available')),
      );
      return;
    }

    try {
      final service = _service;
      if (service == null) return;

      await service.provideFeedback(
        actionId: action.actionId!,
        userResponse: response,
      );

      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Feedback recorded!')),
      );

      // Remove action from list
      setState(() {
        _actions.removeWhere((a) => a.actionId == action.actionId);
      });
    } catch (e) {
      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to record feedback: $e')),
      );
    }
  }
}

/// Action card widget
class ActionCard extends StatelessWidget {
  final DecisionResult action;
  final Function(String) onFeedback;

  const ActionCard({
    Key? key,
    required this.action,
    required this.onFeedback,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 2,
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header: Ingredient name + urgency
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Text(
                    action.ingredientName,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                  ),
                ),
                _buildUrgencyBadge(context),
              ],
            ),
            const SizedBox(height: 12),

            // Action recommendation
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: action.confidenceColor.withOpacity(0.1),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: action.confidenceColor.withOpacity(0.3),
                ),
              ),
              child: Row(
                children: [
                  Text(
                    action.actionEmoji,
                    style: const TextStyle(fontSize: 24),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          action.actionLabel,
                          style:
                              Theme.of(context).textTheme.titleSmall?.copyWith(
                                    fontWeight: FontWeight.bold,
                                    color: action.confidenceColor,
                                  ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          action.reason,
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),

            // Confidence indicator
            Row(
              children: [
                Icon(
                  Icons.analytics_outlined,
                  size: 16,
                  color: Colors.grey[600],
                ),
                const SizedBox(width: 4),
                Text(
                  'Confidence: ${action.confidenceLabel}',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                const SizedBox(width: 4),
                Text(
                  '(${(action.confidence * 100).toStringAsFixed(0)}%)',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: action.confidenceColor,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 12),

            // Action buttons
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                TextButton.icon(
                  onPressed: () => onFeedback('accepted'),
                  icon: const Icon(Icons.check_circle_outline, size: 20),
                  label: const Text('Accept'),
                  style: TextButton.styleFrom(
                    foregroundColor: Colors.green,
                  ),
                ),
                TextButton.icon(
                  onPressed: () => onFeedback('rejected'),
                  icon: const Icon(Icons.cancel_outlined, size: 20),
                  label: const Text('Dismiss'),
                  style: TextButton.styleFrom(
                    foregroundColor: Colors.red,
                  ),
                ),
                TextButton.icon(
                  onPressed: () => onFeedback('modified'),
                  icon: const Icon(Icons.edit_outlined, size: 20),
                  label: const Text('Modify'),
                  style: TextButton.styleFrom(
                    foregroundColor: Colors.blue,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildUrgencyBadge(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: action.urgencyColor.withOpacity(0.2),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: action.urgencyColor,
          width: 1,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.priority_high,
            size: 14,
            color: action.urgencyColor,
          ),
          const SizedBox(width: 4),
          Text(
            action.urgencyLabel,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.bold,
              color: action.urgencyColor,
            ),
          ),
        ],
      ),
    );
  }
}

/// Stats screen for decision intelligence
class DecisionStatsScreen extends StatefulWidget {
  const DecisionStatsScreen({Key? key}) : super(key: key);

  @override
  State<DecisionStatsScreen> createState() => _DecisionStatsScreenState();
}

class _DecisionStatsScreenState extends State<DecisionStatsScreen> {
  DecisionIntelligenceService? _service;
  bool _started = false;
  Map<String, dynamic>? _stats;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _service ??=
        DecisionIntelligenceService(Provider.of<ApiClient>(context, listen: false));

    if (!_started) {
      _started = true;
      _loadStats();
    }
  }

  Future<void> _loadStats() async {
    setState(() => _loading = true);

    try {
      final service = _service;
      if (service == null) return;

      final stats = await service.getStats(days: 30);
      setState(() {
        _stats = stats;
        _loading = false;
      });
    } catch (e) {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Decision Stats'),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _stats == null
              ? const Center(child: Text('No stats available'))
              : SingleChildScrollView(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _buildStatCard(
                        'Total Recommendations',
                        '${_stats!['total_recommendations'] ?? 0}',
                        Icons.lightbulb_outline,
                        Colors.blue,
                      ),
                      const SizedBox(height: 12),
                      _buildStatCard(
                        'Acceptance Rate',
                        '${_stats!['acceptance_rate'] ?? 0}%',
                        Icons.check_circle_outline,
                        Colors.green,
                      ),
                      const SizedBox(height: 12),
                      _buildStatCard(
                        'Auto-Applied',
                        '${_stats!['auto_applied_count'] ?? 0}',
                        Icons.flash_on,
                        Colors.orange,
                      ),
                    ],
                  ),
                ),
    );
  }

  Widget _buildStatCard(
      String title, String value, IconData icon, Color color) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Icon(icon, size: 48, color: color),
            const SizedBox(width: 16),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
                const SizedBox(height: 4),
                Text(
                  value,
                  style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: color,
                      ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
