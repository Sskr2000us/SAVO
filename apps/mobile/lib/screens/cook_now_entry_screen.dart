import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/profile_state.dart';
import '../services/api_client.dart';
import '../services/cook_now_service.dart';
import '../services/entitlements_service.dart';
import '../services/metrics_service.dart';
import '../ui/ui_principles.dart';
import '../widgets/pro_paywall_sheet.dart';
import 'recipe_options_screen.dart';

class CookNowEntryScreen extends StatefulWidget {
  const CookNowEntryScreen({super.key});

  @override
  State<CookNowEntryScreen> createState() => _CookNowEntryScreenState();
}

class _CookNowEntryScreenState extends State<CookNowEntryScreen> {
  bool _generating = false;
  String? _error;

  String _creativity = 'standard';

  String _dayType = 'weekday';
  String _mealType = 'dinner';

  bool _checkingSavedPlan = true;
  bool _hasSavedPlan = false;

  @override
  void initState() {
    super.initState();
    _dayType = _inferDayType();
    _mealType = _inferMealType();
    _checkSavedPlan();
  }

  String _inferDayType() {
    final wd = DateTime.now().weekday;
    // DateTime: Mon=1 ... Sun=7
    if (wd == DateTime.saturday || wd == DateTime.sunday) return 'weekend';
    return 'weekday';
  }

  String _inferMealType() {
    final hour = DateTime.now().hour;
    if (hour < 11) return 'breakfast';
    if (hour < 16) return 'lunch';
    return 'dinner';
  }

  Future<void> _checkSavedPlan() async {
    setState(() {
      _checkingSavedPlan = true;
    });

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      await apiClient.get('/plan/latest?plan_type=daily');
      if (!mounted) return;
      setState(() {
        _hasSavedPlan = true;
        _checkingSavedPlan = false;
      });
    } catch (e) {
      if (!mounted) return;
      // 404 => no saved plan. Anything else: be conservative and hide delete.
      final msg = e.toString();
      setState(() {
        _hasSavedPlan = !msg.contains('404');
        _checkingSavedPlan = false;
      });
    }
  }

  Future<void> _deleteSavedPlan() async {
    final apiClient = Provider.of<ApiClient>(context, listen: false);
    final messenger = ScaffoldMessenger.of(context);

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
      await apiClient.delete('/plan/latest?plan_type=daily');
      if (!mounted) return;
      setState(() {
        _hasSavedPlan = false;
      });
      messenger.showSnackBar(
        const SnackBar(content: Text('Plan removed.')),
      );
    } catch (e) {
      if (!mounted) return;
      messenger.showSnackBar(
        SnackBar(content: Text('Failed to remove plan: $e')),
      );
    }
  }

  Future<void> _generate() async {
    if (_generating) return;

    // Free tier: limit daily suggestion sessions.
    final gate = await EntitlementsService.instance.tryConsumeSuggestionSession();
    if (!gate.allowed && mounted) {
      await showProPaywallSheet(
        context,
        title: 'Upgrade to SAVO Pro',
        ctaLabel: 'Upgrade for unlimited suggestions',
        reason: 'You\'ve used today\'s free recipe suggestions. Pro unlocks unlimited daily suggestions plus weekly planning and shopping lists.',
        trigger: 'suggestions_limit',
      );
      return;
    }

    setState(() {
      _generating = true;
      _error = null;
    });

    try {
      fireAndForget(MetricsService.instance.recordWorkflowStep('CookNow', 'CheckInventory'));
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final profileState = Provider.of<ProfileState>(context, listen: false);
      final service = CookNowService();

      final options = await service.generateRecipeOptions(
        apiClient: apiClient,
        profileState: profileState,
        maxOptions: 5,
        avoidRecentRecipes: 3,
        creativity: _creativity,
        mealType: _mealType,
        dayType: _dayType,
      );

      if (!mounted) return;

      if (options.isEmpty) {
        setState(() {
          _generating = false;
          _error = 'No recipe options right now. Try again after updating your pantry.';
        });
        return;
      }

      fireAndForget(MetricsService.instance.recordWorkflowStep('CookNow', 'Generate'));

      await Navigator.of(context).push(
        MaterialPageRoute(
          settings: const RouteSettings(name: '/recipe_options'),
          builder: (_) => RecipeOptionsScreen(
            recipes: options,
            showIngredientMatch: true,
            skipSuggestionSessionGate: true,
          ),
        ),
      );

      if (!mounted) return;
      setState(() {
        _generating = false;
      });
    } catch (e) {
      if (!mounted) return;
      final msg = e.toString().replaceFirst(RegExp(r'^Exception:\s*'), '');
      setState(() {
        _generating = false;
        _error = msg;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (kDebugMode || kProfileMode) {
      SavoUiGuards.warnIfTooManyChoices(
        screen: 'CookNowEntryScreen',
        surface: 'Primary actions',
        choices: 1,
      );
    }

    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Cook'),
        actions: [
          IconButton(
            tooltip: 'Remove plan',
            onPressed: (_checkingSavedPlan || !_hasSavedPlan || _generating) ? null : _deleteSavedPlan,
            icon: const Icon(Icons.delete_outline),
          ),
        ],
      ),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 520),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  'Cook now',
                  style: theme.textTheme.headlineSmall,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                Text(
                  'Generate recipes based on what\'s in your pantry.',
                  style: theme.textTheme.bodyMedium,
                  textAlign: TextAlign.center,
                ),
                if (_error != null) ...[
                  const SizedBox(height: 16),
                  Text(
                    _error!,
                    style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.error),
                    textAlign: TextAlign.center,
                  ),
                ],
                const SizedBox(height: 24),
                Align(
                  alignment: Alignment.center,
                  child: Wrap(
                    spacing: 12,
                    runSpacing: 8,
                    alignment: WrapAlignment.center,
                    children: [
                      ChoiceChip(
                        label: const Text('Standard'),
                        selected: _creativity == 'standard',
                        onSelected: _generating
                            ? null
                            : (v) {
                                if (!v) return;
                                setState(() => _creativity = 'standard');
                              },
                      ),
                      ChoiceChip(
                        label: const Text('Native/Innovative'),
                        selected: _creativity == 'high',
                        onSelected: _generating
                            ? null
                            : (v) {
                                if (!v) return;
                                setState(() => _creativity = 'high');
                              },
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                Text(
                  'When are you cooking?',
                  style: theme.textTheme.titleSmall,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                Align(
                  alignment: Alignment.center,
                  child: Wrap(
                    spacing: 10,
                    runSpacing: 8,
                    alignment: WrapAlignment.center,
                    children: [
                      ChoiceChip(
                        label: const Text('Weekday'),
                        selected: _dayType == 'weekday',
                        onSelected: _generating
                            ? null
                            : (v) {
                                if (!v) return;
                                setState(() => _dayType = 'weekday');
                              },
                      ),
                      ChoiceChip(
                        label: const Text('Weekend'),
                        selected: _dayType == 'weekend',
                        onSelected: _generating
                            ? null
                            : (v) {
                                if (!v) return;
                                setState(() => _dayType = 'weekend');
                              },
                      ),
                      ChoiceChip(
                        label: const Text('Holiday'),
                        selected: _dayType == 'holiday',
                        onSelected: _generating
                            ? null
                            : (v) {
                                if (!v) return;
                                setState(() => _dayType = 'holiday');
                              },
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
                Align(
                  alignment: Alignment.center,
                  child: Wrap(
                    spacing: 10,
                    runSpacing: 8,
                    alignment: WrapAlignment.center,
                    children: [
                      ChoiceChip(
                        label: const Text('Breakfast'),
                        selected: _mealType == 'breakfast',
                        onSelected: _generating
                            ? null
                            : (v) {
                                if (!v) return;
                                setState(() => _mealType = 'breakfast');
                              },
                      ),
                      ChoiceChip(
                        label: const Text('Lunch'),
                        selected: _mealType == 'lunch',
                        onSelected: _generating
                            ? null
                            : (v) {
                                if (!v) return;
                                setState(() => _mealType = 'lunch');
                              },
                      ),
                      ChoiceChip(
                        label: const Text('Dinner'),
                        selected: _mealType == 'dinner',
                        onSelected: _generating
                            ? null
                            : (v) {
                                if (!v) return;
                                setState(() => _mealType = 'dinner');
                              },
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 20),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton(
                    onPressed: _generating ? null : _generate,
                    child: Text(_generating ? 'Generating…' : 'Generate recipes'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
