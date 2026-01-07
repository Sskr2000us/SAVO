import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

/// Metrics Dashboard Screen
/// Displays user performance metrics with trend charts
class MetricsDashboardScreen extends StatefulWidget {
  const MetricsDashboardScreen({Key? key}) : super(key: key);

  @override
  State<MetricsDashboardScreen> createState() => _MetricsDashboardScreenState();
}

class _MetricsDashboardScreenState extends State<MetricsDashboardScreen> {
  final supabase = Supabase.instance.client;
  Map<String, dynamic>? _metrics;
  bool _isLoading = true;
  String? _error;
  String _selectedPeriod = '7d'; // 7d, 30d, 90d

  @override
  void initState() {
    super.initState();
    _loadMetrics();
  }

  Future<void> _loadMetrics() async {
    try {
      setState(() {
        _isLoading = true;
        _error = null;
      });

      final userId = supabase.auth.currentUser?.id;
      if (userId == null) {
        throw Exception('User not logged in');
      }

      // Fetch success metrics
      final days = _selectedPeriod == '7d'
          ? 7
          : _selectedPeriod == '30d'
              ? 30
              : 90;

      final startDate = DateTime.now().subtract(Duration(days: days));

      // Get scan-to-action rate
      final scansResponse = await supabase
          .from('visual_scan_results')
          .select('id, created_at')
          .eq('user_id', userId)
          .gte('created_at', startDate.toIso8601String());

      final actionsResponse = await supabase
          .from('ingredient_actions')
          .select('id, created_at')
          .eq('user_id', userId)
          .gte('created_at', startDate.toIso8601String());

      final scanToActionRate = scansResponse.isNotEmpty
          ? (actionsResponse.length / scansResponse.length) * 100
          : 0.0;

      // Get waste reduction (mock for now)
      final wasteReduction = 18.5; // TODO: Calculate from actual data

      // Get time saved (mock for now)
      final timeSaved = 42; // minutes per week

      // Get weekly return rate (mock for now)
      final weeklyReturn = 45.0; // percentage

      // Get daily metrics for chart
      final dailyMetrics = await _getDailyMetrics(userId, days);

      setState(() {
        _metrics = {
          'scanToActionRate': scanToActionRate,
          'wasteReduction': wasteReduction,
          'timeSaved': timeSaved,
          'weeklyReturn': weeklyReturn,
          'dailyMetrics': dailyMetrics,
          'totalScans': scansResponse.length,
          'totalActions': actionsResponse.length,
        };
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  Future<List<Map<String, dynamic>>> _getDailyMetrics(
    String userId,
    int days,
  ) async {
    final metrics = <Map<String, dynamic>>[];
    final now = DateTime.now();

    for (int i = days - 1; i >= 0; i--) {
      final date = now.subtract(Duration(days: i));
      final dateStr = date.toIso8601String().split('T')[0];

      // Get scan count for this day
      final scansResponse = await supabase
          .from('visual_scan_results')
          .select('id')
          .eq('user_id', userId)
          .gte('created_at', '$dateStr 00:00:00')
          .lt('created_at', '$dateStr 23:59:59');

      // Get action count for this day
      final actionsResponse = await supabase
          .from('ingredient_actions')
          .select('id')
          .eq('user_id', userId)
          .gte('created_at', '$dateStr 00:00:00')
          .lt('created_at', '$dateStr 23:59:59');

      metrics.add({
        'date': date,
        'scans': scansResponse.length,
        'actions': actionsResponse.length,
      });
    }

    return metrics;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Performance Metrics'),
        backgroundColor: Colors.deepPurple,
        actions: [
          PopupMenuButton<String>(
            initialValue: _selectedPeriod,
            onSelected: (value) {
              setState(() {
                _selectedPeriod = value;
              });
              _loadMetrics();
            },
            itemBuilder: (context) => [
              const PopupMenuItem(value: '7d', child: Text('Last 7 days')),
              const PopupMenuItem(value: '30d', child: Text('Last 30 days')),
              const PopupMenuItem(value: '90d', child: Text('Last 90 days')),
            ],
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _buildErrorView()
              : _buildMetricsContent(),
    );
  }

  Widget _buildErrorView() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.error_outline, size: 64, color: Colors.red.shade300),
            const SizedBox(height: 16),
            Text(
              'Failed to load metrics',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Text(
              _error ?? 'Unknown error',
              style: Theme.of(context).textTheme.bodyMedium,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: _loadMetrics,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMetricsContent() {
    if (_metrics == null) return const SizedBox.shrink();

    return RefreshIndicator(
      onRefresh: _loadMetrics,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            Text(
              'Your Impact',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            const SizedBox(height: 8),
            Text(
              'Showing data for the last ${_selectedPeriod == '7d' ? '7' : _selectedPeriod == '30d' ? '30' : '90'} days',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Colors.grey.shade600,
                  ),
            ),
            const SizedBox(height: 24),

            // Metric Cards
            _buildMetricCard(
              icon: Icons.trending_up,
              iconColor: Colors.green,
              title: 'Scan-to-Action Rate',
              value: '${_metrics!['scanToActionRate'].toStringAsFixed(1)}%',
              subtitle:
                  '${_metrics!['totalScans']} scans, ${_metrics!['totalActions']} actions',
              targetValue: 60.0,
              currentValue: _metrics!['scanToActionRate'],
              isHigherBetter: true,
            ),
            const SizedBox(height: 16),
            _buildMetricCard(
              icon: Icons.delete_outline,
              iconColor: Colors.orange,
              title: 'Waste Reduction',
              value: '${_metrics!['wasteReduction'].toStringAsFixed(1)}%',
              subtitle: 'Compared to baseline',
              targetValue: 20.0,
              currentValue: _metrics!['wasteReduction'],
              isHigherBetter: true,
            ),
            const SizedBox(height: 16),
            _buildMetricCard(
              icon: Icons.timer_outlined,
              iconColor: Colors.blue,
              title: 'Time Saved',
              value: '${_metrics!['timeSaved']} min',
              subtitle: 'Per week',
              targetValue: 30.0,
              currentValue: _metrics!['timeSaved'].toDouble(),
              isHigherBetter: true,
            ),
            const SizedBox(height: 16),
            _buildMetricCard(
              icon: Icons.repeat,
              iconColor: Colors.purple,
              title: 'Weekly Return Rate',
              value: '${_metrics!['weeklyReturn'].toStringAsFixed(1)}%',
              subtitle: 'Users returning weekly',
              targetValue: 40.0,
              currentValue: _metrics!['weeklyReturn'],
              isHigherBetter: true,
            ),

            const SizedBox(height: 32),

            // Activity Chart
            Text(
              'Activity Trend',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            const SizedBox(height: 16),
            _buildActivityChart(),

            const SizedBox(height: 32),

            // Insights
            _buildInsightsSection(),
          ],
        ),
      ),
    );
  }

  Widget _buildMetricCard({
    required IconData icon,
    required Color iconColor,
    required String title,
    required String value,
    required String subtitle,
    required double targetValue,
    required double currentValue,
    required bool isHigherBetter,
  }) {
    final progress = (currentValue / targetValue).clamp(0.0, 1.0);
    final isOnTarget = isHigherBetter
        ? currentValue >= targetValue
        : currentValue <= targetValue;

    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: iconColor.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(icon, color: iconColor, size: 28),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      Text(
                        subtitle,
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color: Colors.grey.shade600,
                            ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  value,
                  style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: isOnTarget ? Colors.green : Colors.orange,
                      ),
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      'Target: ${targetValue.toStringAsFixed(0)}${title.contains('%') || title.contains('Rate') ? '%' : ''}',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        Icon(
                          isOnTarget ? Icons.check_circle : Icons.trending_up,
                          size: 16,
                          color: isOnTarget ? Colors.green : Colors.orange,
                        ),
                        const SizedBox(width: 4),
                        Text(
                          isOnTarget ? 'On target' : 'In progress',
                          style:
                              Theme.of(context).textTheme.bodySmall?.copyWith(
                                    color: isOnTarget
                                        ? Colors.green
                                        : Colors.orange,
                                    fontWeight: FontWeight.w600,
                                  ),
                        ),
                      ],
                    ),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 12),
            LinearProgressIndicator(
              value: progress,
              backgroundColor: Colors.grey.shade200,
              valueColor: AlwaysStoppedAnimation<Color>(
                isOnTarget ? Colors.green : Colors.orange,
              ),
              minHeight: 8,
              borderRadius: BorderRadius.circular(4),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildActivityChart() {
    final dailyMetrics =
        _metrics!['dailyMetrics'] as List<Map<String, dynamic>>;

    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(20.0),
        child: SizedBox(
          height: 250,
          child: LineChart(
            LineChartData(
              gridData: FlGridData(
                show: true,
                drawVerticalLine: false,
                horizontalInterval: 2,
                getDrawingHorizontalLine: (value) {
                  return FlLine(
                    color: Colors.grey.shade200,
                    strokeWidth: 1,
                  );
                },
              ),
              titlesData: FlTitlesData(
                leftTitles: AxisTitles(
                  sideTitles: SideTitles(
                    showTitles: true,
                    reservedSize: 40,
                    interval: 2,
                  ),
                ),
                bottomTitles: AxisTitles(
                  sideTitles: SideTitles(
                    showTitles: true,
                    reservedSize: 30,
                    interval: 1,
                    getTitlesWidget: (value, meta) {
                      if (value.toInt() >= dailyMetrics.length) {
                        return const Text('');
                      }
                      final date =
                          dailyMetrics[value.toInt()]['date'] as DateTime;
                      return Padding(
                        padding: const EdgeInsets.only(top: 8.0),
                        child: Text(
                          '${date.month}/${date.day}',
                          style: const TextStyle(fontSize: 10),
                        ),
                      );
                    },
                  ),
                ),
                rightTitles: AxisTitles(
                  sideTitles: SideTitles(showTitles: false),
                ),
                topTitles: AxisTitles(
                  sideTitles: SideTitles(showTitles: false),
                ),
              ),
              borderData: FlBorderData(show: false),
              lineBarsData: [
                // Scans line
                LineChartBarData(
                  spots: List.generate(
                    dailyMetrics.length,
                    (index) => FlSpot(
                      index.toDouble(),
                      dailyMetrics[index]['scans'].toDouble(),
                    ),
                  ),
                  isCurved: true,
                  color: Colors.blue,
                  barWidth: 3,
                  dotData: FlDotData(show: true),
                  belowBarData: BarAreaData(
                    show: true,
                    color: Colors.blue.withOpacity(0.1),
                  ),
                ),
                // Actions line
                LineChartBarData(
                  spots: List.generate(
                    dailyMetrics.length,
                    (index) => FlSpot(
                      index.toDouble(),
                      dailyMetrics[index]['actions'].toDouble(),
                    ),
                  ),
                  isCurved: true,
                  color: Colors.green,
                  barWidth: 3,
                  dotData: FlDotData(show: true),
                  belowBarData: BarAreaData(
                    show: true,
                    color: Colors.green.withOpacity(0.1),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildInsightsSection() {
    final scanToActionRate = _metrics!['scanToActionRate'];
    final wasteReduction = _metrics!['wasteReduction'];

    final insights = <Map<String, dynamic>>[];

    if (scanToActionRate >= 60) {
      insights.add({
        'icon': Icons.celebration,
        'color': Colors.green,
        'title': 'Excellent engagement!',
        'description':
            'Your scan-to-action rate is above target. You\'re making great use of your scans!',
      });
    } else if (scanToActionRate < 40) {
      insights.add({
        'icon': Icons.tips_and_updates,
        'color': Colors.orange,
        'title': 'Opportunity to improve',
        'description':
            'Try acting on more of your scans. Set reminders for ingredients nearing expiry.',
      });
    }

    if (wasteReduction >= 20) {
      insights.add({
        'icon': Icons.eco,
        'color': Colors.green,
        'title': 'Waste reduction champion!',
        'description':
            'You\'ve exceeded the 20% waste reduction target. Keep it up!',
      });
    }

    if (insights.isEmpty) {
      insights.add({
        'icon': Icons.trending_up,
        'color': Colors.blue,
        'title': 'Keep going!',
        'description':
            'You\'re making progress. Consistency is key to better results.',
      });
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Insights',
          style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold,
              ),
        ),
        const SizedBox(height: 16),
        ...insights.map((insight) => Card(
              elevation: 1,
              margin: const EdgeInsets.only(bottom: 12),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: (insight['color'] as Color).withOpacity(0.1),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Icon(
                        insight['icon'] as IconData,
                        color: insight['color'] as Color,
                        size: 24,
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            insight['title'] as String,
                            style: Theme.of(context)
                                .textTheme
                                .titleMedium
                                ?.copyWith(
                                  fontWeight: FontWeight.w600,
                                ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            insight['description'] as String,
                            style:
                                Theme.of(context).textTheme.bodySmall?.copyWith(
                                      color: Colors.grey.shade600,
                                    ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            )),
      ],
    );
  }
}
