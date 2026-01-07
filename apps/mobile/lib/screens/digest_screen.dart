import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../services/daily_habit_service.dart';

/// Daily Digest Screen
/// Displays morning/evening digest with personalized recommendations
class DigestScreen extends StatefulWidget {
  final String digestType; // 'morning' or 'evening'

  const DigestScreen({
    Key? key,
    required this.digestType,
  }) : super(key: key);

  @override
  State<DigestScreen> createState() => _DigestScreenState();
}

class _DigestScreenState extends State<DigestScreen> {
  final DailyHabitService _habitService = DailyHabitService();
  Map<String, dynamic>? _digest;
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadDigest();
    _markDigestOpened();
  }

  Future<void> _loadDigest() async {
    try {
      setState(() {
        _isLoading = true;
        _error = null;
      });

      final userId = Supabase.instance.client.auth.currentUser?.id;
      if (userId == null) {
        throw Exception('User not logged in');
      }

      final digest = widget.digestType == 'morning'
          ? await _habitService.generateMorningDigest(userId)
          : await _habitService.generateEveningDigest(userId);

      setState(() {
        _digest = digest;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  Future<void> _markDigestOpened() async {
    try {
      final userId = Supabase.instance.client.auth.currentUser?.id;
      if (userId == null) return;

      await _habitService.markDigestOpened(userId, widget.digestType);
    } catch (e) {
      print('Error marking digest opened: $e');
    }
  }

  Future<void> _respondToQuestion(
    String questionId,
    String response,
  ) async {
    try {
      // Mark digest as actioned
      final userId = Supabase.instance.client.auth.currentUser?.id;
      if (userId == null) return;

      await _habitService.markDigestActioned(userId, widget.digestType);

      // Show success message
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Response recorded: $response'),
            backgroundColor: Colors.green,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDarkMode = Theme.of(context).brightness == Brightness.dark;

    return Scaffold(
      appBar: AppBar(
        title: Text(
          widget.digestType == 'morning' ? 'Morning Digest' : 'Evening Check-in',
        ),
        backgroundColor: widget.digestType == 'morning'
            ? Colors.orange.shade300
            : Colors.indigo.shade400,
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _buildErrorView()
              : _buildDigestContent(isDarkMode),
    );
  }

  Widget _buildErrorView() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.error_outline,
              size: 64,
              color: Colors.red.shade300,
            ),
            const SizedBox(height: 16),
            Text(
              'Failed to load digest',
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
              onPressed: _loadDigest,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDigestContent(bool isDarkMode) {
    if (_digest == null) return const SizedBox.shrink();

    return RefreshIndicator(
      onRefresh: _loadDigest,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Greeting
            _buildGreeting(isDarkMode),
            const SizedBox(height: 24),

            // Streak Display
            _buildStreakDisplay(isDarkMode),
            const SizedBox(height: 24),

            // Questions
            if (widget.digestType == 'morning')
              _buildMorningQuestions(isDarkMode)
            else
              _buildEveningQuestions(isDarkMode),

            const SizedBox(height: 24),

            // Daily Tip
            _buildDailyTip(isDarkMode),
          ],
        ),
      ),
    );
  }

  Widget _buildGreeting(bool isDarkMode) {
    final greeting = _digest!['greeting'] ?? 'Hello!';
    final timeEmoji = widget.digestType == 'morning' ? '🌅' : '🌙';

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: widget.digestType == 'morning'
              ? [Colors.orange.shade300, Colors.yellow.shade300]
              : [Colors.indigo.shade400, Colors.purple.shade400],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          Text(
            timeEmoji,
            style: const TextStyle(fontSize: 48),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  greeting,
                  style: const TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  widget.digestType == 'morning'
                      ? 'Let\'s make today count!'
                      : 'Quick check-in for the day',
                  style: const TextStyle(
                    fontSize: 14,
                    color: Colors.white70,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStreakDisplay(bool isDarkMode) {
    final streaks = _digest!['streaks'] as Map<String, dynamic>? ?? {};

    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.local_fire_department,
                    color: Colors.orange.shade600),
                const SizedBox(width: 8),
                Text(
                  'Your Streaks',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            _buildStreakRow(
              '🚫🗑️ No Waste',
              streaks['no_waste'] ?? 0,
              isDarkMode,
            ),
            const SizedBox(height: 12),
            _buildStreakRow(
              '📸 Daily Scan',
              streaks['daily_scan'] ?? 0,
              isDarkMode,
            ),
            const SizedBox(height: 12),
            _buildStreakRow(
              '👨‍🍳 Daily Cook',
              streaks['daily_cook'] ?? 0,
              isDarkMode,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStreakRow(String label, int count, bool isDarkMode) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: Theme.of(context).textTheme.bodyLarge),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(
            color: count > 0
                ? Colors.orange.shade100
                : (isDarkMode ? Colors.grey.shade800 : Colors.grey.shade200),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Text(
            '$count ${count == 1 ? 'day' : 'days'}',
            style: TextStyle(
              fontWeight: FontWeight.bold,
              color: count > 0
                  ? Colors.orange.shade900
                  : (isDarkMode ? Colors.grey.shade400 : Colors.grey.shade600),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildMorningQuestions(bool isDarkMode) {
    final questions = _digest!['questions'] as List<dynamic>? ?? [];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Today\'s Questions',
          style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold,
              ),
        ),
        const SizedBox(height: 16),
        ...questions.map((q) => _buildQuestionCard(
              q['id'],
              q['question'],
              q['emoji'],
              q['options'] as List<dynamic>,
              isDarkMode,
            )),
      ],
    );
  }

  Widget _buildEveningQuestions(bool isDarkMode) {
    final questions = _digest!['questions'] as List<dynamic>? ?? [];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Evening Check-in',
          style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold,
              ),
        ),
        const SizedBox(height: 16),
        ...questions.map((q) => _buildQuestionCard(
              q['id'],
              q['question'],
              q['emoji'],
              q['options'] as List<dynamic>,
              isDarkMode,
            )),
      ],
    );
  }

  Widget _buildQuestionCard(
    String questionId,
    String question,
    String emoji,
    List<dynamic> options,
    bool isDarkMode,
  ) {
    return Card(
      elevation: 1,
      margin: const EdgeInsets.only(bottom: 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(emoji, style: const TextStyle(fontSize: 24)),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    question,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: options.map((option) {
                return ActionChip(
                  label: Text(option['label']),
                  avatar: Text(option['emoji']),
                  onPressed: () =>
                      _respondToQuestion(questionId, option['value']),
                  backgroundColor: isDarkMode
                      ? Colors.grey.shade800
                      : Colors.grey.shade100,
                );
              }).toList(),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDailyTip(bool isDarkMode) {
    final tip = _digest!['daily_tip'] as String? ?? 'Keep up the great work!';

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isDarkMode ? Colors.blue.shade900 : Colors.blue.shade50,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isDarkMode ? Colors.blue.shade700 : Colors.blue.shade200,
        ),
      ),
      child: Row(
        children: [
          Icon(
            Icons.lightbulb_outline,
            color: isDarkMode ? Colors.blue.shade300 : Colors.blue.shade700,
            size: 28,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Daily Tip',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color:
                        isDarkMode ? Colors.blue.shade300 : Colors.blue.shade900,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  tip,
                  style: TextStyle(
                    color:
                        isDarkMode ? Colors.blue.shade100 : Colors.blue.shade800,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Daily Habit Service for digest generation
class DailyHabitService {
  final supabase = Supabase.instance.client;

  Future<Map<String, dynamic>> generateMorningDigest(String userId) async {
    // Fetch user streaks
    final streaksResponse = await supabase
        .from('user_streaks')
        .select()
        .eq('user_id', userId)
        .eq('is_active', true);

    final streaks = <String, int>{};
    for (final streak in streaksResponse) {
      streaks[streak['streak_type']] = streak['current_count'] ?? 0;
    }

    // Fetch expiring ingredients
    final expiringResponse = await supabase
        .from('user_inventory')
        .select('ingredient_id, expiry_date')
        .eq('user_id', userId)
        .gte('expiry_date', DateTime.now().toIso8601String())
        .lte(
          'expiry_date',
          DateTime.now().add(const Duration(days: 2)).toIso8601String(),
        )
        .limit(5);

    final greeting = _getGreeting();

    return {
      'greeting': greeting,
      'streaks': streaks,
      'questions': [
        {
          'id': 'cook_today',
          'question': 'Are you cooking today?',
          'emoji': '👨‍🍳',
          'options': [
            {'label': 'Yes!', 'emoji': '✅', 'value': 'yes'},
            {'label': 'Maybe', 'emoji': '🤔', 'value': 'maybe'},
            {'label': 'No', 'emoji': '❌', 'value': 'no'},
          ],
        },
        {
          'id': 'expiring_check',
          'question':
              'You have ${expiringResponse.length} items expiring soon. Check them?',
          'emoji': '⏰',
          'options': [
            {'label': 'View Now', 'emoji': '👀', 'value': 'view'},
            {'label': 'Later', 'emoji': '⏳', 'value': 'later'},
          ],
        },
      ],
      'daily_tip': _getDailyTip(),
    };
  }

  Future<Map<String, dynamic>> generateEveningDigest(String userId) async {
    final streaksResponse = await supabase
        .from('user_streaks')
        .select()
        .eq('user_id', userId)
        .eq('is_active', true);

    final streaks = <String, int>{};
    for (final streak in streaksResponse) {
      streaks[streak['streak_type']] = streak['current_count'] ?? 0;
    }

    return {
      'greeting': 'Good Evening!',
      'streaks': streaks,
      'questions': [
        {
          'id': 'cooked_today',
          'question': 'Did you cook anything today?',
          'emoji': '🍳',
          'options': [
            {'label': 'Yes', 'emoji': '✅', 'value': 'yes'},
            {'label': 'No', 'emoji': '❌', 'value': 'no'},
          ],
        },
        {
          'id': 'waste_today',
          'question': 'Any food waste today?',
          'emoji': '🗑️',
          'options': [
            {'label': 'None', 'emoji': '🎉', 'value': 'none'},
            {'label': 'Some', 'emoji': '⚠️', 'value': 'some'},
          ],
        },
      ],
      'daily_tip': 'Great job today! Keep up the momentum.',
    };
  }

  Future<void> markDigestOpened(String userId, String digestType) async {
    await supabase.from('daily_digests').update({
      'was_opened': true,
      'opened_at': DateTime.now().toIso8601String(),
    }).match({
      'user_id': userId,
      'digest_type': digestType,
      'digest_date': DateTime.now().toIso8601String().split('T')[0],
    });
  }

  Future<void> markDigestActioned(String userId, String digestType) async {
    await supabase.from('daily_digests').update({
      'was_actioned': true,
      'actioned_at': DateTime.now().toIso8601String(),
    }).match({
      'user_id': userId,
      'digest_type': digestType,
      'digest_date': DateTime.now().toIso8601String().split('T')[0],
    });
  }

  String _getGreeting() {
    final hour = DateTime.now().hour;
    if (hour < 12) return 'Good Morning!';
    if (hour < 17) return 'Good Afternoon!';
    return 'Good Evening!';
  }

  String _getDailyTip() {
    final tips = [
      'Store herbs in water like flowers to keep them fresh longer.',
      'Freeze overripe bananas for smoothies later.',
      'First in, first out - rotate your fridge items.',
      'Prep vegetables on Sunday for quick weekday meals.',
      'Check your fridge daily to stay aware of what needs using.',
    ];
    return tips[DateTime.now().day % tips.length];
  }
}
