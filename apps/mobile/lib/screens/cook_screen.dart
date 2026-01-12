import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/planning.dart';
import '../models/profile_state.dart';
import '../services/api_client.dart';
import '../services/cook_session_storage.dart';
import 'cook_mode_screen.dart';
import 'plan_screen.dart';

class CookScreen extends StatefulWidget {
  const CookScreen({super.key});

  @override
  State<CookScreen> createState() => _CookScreenState();
}

class _CookScreenState extends State<CookScreen> {
  MenuPlanResponse? _latest;
  bool _loading = true;
  String? _error;
  ActiveCookSession? _activeSession;
  bool _loadingSession = true;

  List<Map<String, dynamic>> _recentlyCooked = const [];
  bool _loadingRecent = true;

  String _preferredLanguageKey(BuildContext context) {
    try {
      final profileState = Provider.of<ProfileState>(context, listen: false);
      final raw = (profileState.preferredLanguage?.trim().isNotEmpty == true)
          ? profileState.preferredLanguage!.trim()
          : (profileState.primaryLanguage?.trim().isNotEmpty == true)
              ? profileState.primaryLanguage!.trim()
              : Localizations.localeOf(context).languageCode;
      final lowered = raw.trim().toLowerCase();
      if (lowered.isEmpty) return 'en';
      return lowered.split(RegExp('[-_]')).first;
    } catch (_) {
      return 'en';
    }
  }

  @override
  void initState() {
    super.initState();
    _loadActiveSession();
    _loadLatest();
    _loadRecentlyCooked();
  }

  Future<void> _loadRecentlyCooked() async {
    setState(() {
      _loadingRecent = true;
    });

    final apiClient = Provider.of<ApiClient>(context, listen: false);
    try {
      final res = await apiClient.get('/history/recipes?limit=10');
      if (!mounted) return;

      if (res is List) {
        setState(() {
          _recentlyCooked = res
              .whereType<Map>()
              .map((m) => Map<String, dynamic>.from(m))
              .toList();
          _loadingRecent = false;
        });
        return;
      }

      setState(() {
        _recentlyCooked = const [];
        _loadingRecent = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _recentlyCooked = const [];
        _loadingRecent = false;
      });
    }
  }

  String _historyTitle(Map<String, dynamic> row) {
    final name = row['recipe_name'];
    if (name is String && name.trim().isNotEmpty) return name.trim();
    return 'Recipe';
  }

  String? _historySubtitle(Map<String, dynamic> row) {
    final cuisine = row['cuisine'];
    if (cuisine is String && cuisine.trim().isNotEmpty) return cuisine.trim();
    return null;
  }

  Future<void> _loadActiveSession() async {
    setState(() {
      _loadingSession = true;
    });

    final session = await ActiveCookSession.load();
    if (!mounted) return;
    setState(() {
      _activeSession = session;
      _loadingSession = false;
    });
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
      final msg = e.toString();
      setState(() {
        _latest = null;
        _loading = false;
        // Treat 404 as "no plan".
        _error = msg.contains('404') ? null : msg;
      });
    }
  }

  Future<void> _deleteLatestDailyPlan() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Remove plan'),
        content: const Text('Remove the saved daily plan so you can generate a new one?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Remove'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      await apiClient.delete('/plan/latest?plan_type=daily');
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Daily plan removed.')),
      );
      await _loadLatest();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to remove plan: $e')),
      );
    }
  }

  int _extractServings(Menu menu) {
    if (menu.servings.isEmpty) return 1;
    final total = menu.servings['total'] ?? menu.servings['count'];
    if (total is int && total > 0) return total;
    if (total is num && total > 0) return total.toInt();

    int sum = 0;
    for (final entry in menu.servings.entries) {
      final key = entry.key.toString().toLowerCase();
      if (key == 'scaling_factor' || key == 'scale' || key == 'multiplier') continue;

      final v = entry.value;
      if (v is int) sum += v;
      if (v is num) sum += v.toInt();
    }
    return sum > 0 ? sum : 1;
  }

  void _openPlan() {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => const PlanScreen()),
    );
  }

  Future<void> _resumeCooking() async {
    final session = _activeSession;
    if (session == null) return;

    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => CookModeScreen(
          recipe: session.recipe,
          servings: session.servings,
          baseServings: session.baseServings,
          initialStepIndex: session.currentStepIndex,
          initialStepSecondsRemaining: session.stepSecondsRemaining,
          initialRecipeTotalSeconds: session.recipeTotalSeconds,
          initialIsStepTimerRunning: session.isStepTimerRunning,
          initialIsStepTimerPaused: session.isStepTimerPaused,
          initialSecondaryLanguageCode: session.secondaryLanguageCode,
          initialStartBilingual: session.languageMode == 'bilingual',
        ),
      ),
    );

    // Session may have been cleared on completion.
    await _loadActiveSession();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final lang = _preferredLanguageKey(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Cook'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: _loading ? null : _loadLatest,
            icon: const Icon(Icons.refresh),
          ),
          IconButton(
            tooltip: 'Remove plan',
            onPressed: (_loading || _latest == null) ? null : _deleteLatestDailyPlan,
            icon: const Icon(Icons.delete_outline),
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                if (_loadingSession)
                  const Padding(
                    padding: EdgeInsets.only(bottom: 12),
                    child: LinearProgressIndicator(),
                  )
                else if (_activeSession != null) ...[
                  Card(
                    child: ListTile(
                      title: const Text('Resume cooking'),
                      subtitle: Text(
                        _activeSession!.recipe.getLocalizedName(lang),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                      trailing: FilledButton(
                        onPressed: _resumeCooking,
                        child: const Text('Resume'),
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                ],

                Text(
                  'Recently cooked',
                  style: theme.textTheme.titleMedium,
                ),
                const SizedBox(height: 12),
                if (_loadingRecent)
                  const LinearProgressIndicator()
                else if (_recentlyCooked.isEmpty)
                  Text(
                    'No cooking history yet',
                    style: theme.textTheme.bodyMedium,
                  )
                else
                  Card(
                    child: Column(
                      children: _recentlyCooked.take(6).map((row) {
                        final subtitle = _historySubtitle(row);
                        return ListTile(
                          title: Text(_historyTitle(row)),
                          subtitle: subtitle != null ? Text(subtitle) : null,
                        );
                      }).toList(),
                    ),
                  ),
                const SizedBox(height: 16),

                if (_latest == null)
                  Center(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(vertical: 40, horizontal: 16),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Text(
                            _error ?? 'No saved plan yet',
                            textAlign: TextAlign.center,
                            style: theme.textTheme.titleMedium,
                          ),
                          const SizedBox(height: 12),
                          ElevatedButton(
                            onPressed: _openPlan,
                            child: const Text('Open Plan'),
                          ),
                        ],
                      ),
                    ),
                  )
                else ...[
                  Text(
                    'Cook from your latest plan',
                    style: theme.textTheme.titleMedium,
                  ),
                  const SizedBox(height: 12),
                  ..._latest!.menus.expand((menu) {
                    final servings = _extractServings(menu);
                    return menu.courses.expand((course) {
                      if (course.recipeOptions.isEmpty) return const <Widget>[];
                      final recipe = course.recipeOptions.first;
                      final title = recipe.getLocalizedName(lang);
                      return [
                        Card(
                          child: ListTile(
                            title: Text(course.courseHeader),
                            subtitle: Text(title),
                            trailing: FilledButton(
                              onPressed: () async {
                                await Navigator.push(
                                  context,
                                  MaterialPageRoute(
                                    builder: (_) => CookModeScreen(
                                      recipe: recipe,
                                      servings: servings,
                                      baseServings: servings,
                                    ),
                                  ),
                                );
                                await _loadActiveSession();
                                await _loadRecentlyCooked();
                              },
                              child: const Text('Cook'),
                            ),
                          ),
                        ),
                      ];
                    });
                  }),
                ],
              ],
            ),
    );
  }
}
