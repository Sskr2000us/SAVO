import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/cuisine.dart';
import '../models/planning.dart';
import '../models/profile_state.dart';
import '../services/api_client.dart';
import '../services/metrics_service.dart';
import '../theme/app_theme.dart';
import '../ui/ui_principles.dart';
import '../widgets/savo_widgets.dart';
import 'generated_menu_screen.dart';

enum PartyPlanningMode { dinnerParty, festival }

enum _DietChoice { none, vegetarian, vegan }

enum _MealTypeChoice { casual, standard, formal }

class PartySetupScreen extends StatefulWidget {
  final PartyPlanningMode mode;

  const PartySetupScreen({super.key, required this.mode});

  @override
  State<PartySetupScreen> createState() => _PartySetupScreenState();
}

class _PartySetupScreenState extends State<PartySetupScreen> {
  int _stepIndex = 0;

  int _child0To12 = 0;
  int _teen13To17 = 0;
  int _adult18Plus = 6;
  _MealTypeChoice _mealType = _MealTypeChoice.standard;
  _DietChoice _diet = _DietChoice.none;

  List<Cuisine> _cuisines = const [];
  bool _loadingCuisines = true;

  static const String _prefsPlanningIncludeInactiveKey = 'savo.planning.include_inactive_inventory';
  static const String _prefsInventoryShowInactiveKey = 'savo.inventory.show_inactive_items';
  bool _includeInactiveInventory = false;

  @override
  void initState() {
    super.initState();
    fireAndForget(MetricsService.instance.recordWorkflowStep('PlanParty', 'CollectInputs'));
    _loadIncludeInactivePreference();
    _loadCuisines();
  }

  Future<void> _loadIncludeInactivePreference() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final includeInactive = prefs.containsKey(_prefsPlanningIncludeInactiveKey)
          ? (prefs.getBool(_prefsPlanningIncludeInactiveKey) ?? false)
          : (prefs.getBool(_prefsInventoryShowInactiveKey) ?? false);
      if (!mounted) return;
      setState(() {
        _includeInactiveInventory = includeInactive;
      });
    } catch (_) {
      // Best-effort only.
    }
  }

  void _setIncludeInactiveInventory(bool value) {
    setState(() {
      _includeInactiveInventory = value;
    });

    () async {
      try {
        final prefs = await SharedPreferences.getInstance();
        await prefs.setBool(_prefsPlanningIncludeInactiveKey, value);
      } catch (_) {
        // Best-effort only.
      }
    }();
  }

  Future<void> _loadCuisines() async {
    setState(() => _loadingCuisines = true);
    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final res = await apiClient.get('/cuisines');
      if (!mounted) return;
      if (res is List) {
        setState(() {
          _cuisines = res
              .whereType<Map>()
              .map((m) => Cuisine.fromJson(Map<String, dynamic>.from(m)))
              .where((c) => c.partyEnabled)
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

  String _title() {
    switch (widget.mode) {
      case PartyPlanningMode.dinnerParty:
        return 'Dinner party';
      case PartyPlanningMode.festival:
        return 'Festival';
    }
  }

  String _stepTitle() {
    switch (_stepIndex) {
      case 0:
        return 'Guests';
      case 1:
        return 'Meal type';
      case 2:
        return 'Diet';
      case 3:
        return 'Cuisine';
      default:
        return '';
    }
  }

  void _goBack() {
    if (_stepIndex == 0) {
      Navigator.of(context).maybePop();
      return;
    }
    setState(() {
      _stepIndex -= 1;
    });
  }

  int _totalGuests() => _child0To12 + _teen13To17 + _adult18Plus;

  void _updateGuests({int? child0To12, int? teen13To17, int? adult18Plus}) {
    setState(() {
      if (child0To12 != null) _child0To12 = child0To12;
      if (teen13To17 != null) _teen13To17 = teen13To17;
      if (adult18Plus != null) _adult18Plus = adult18Plus;
    });
  }

  void _nextFromGuests() {
    if (_totalGuests() <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter at least 1 guest.')),
      );
      return;
    }
    setState(() {
      _stepIndex = 1;
    });
  }

  void _selectMealType(_MealTypeChoice type) {
    setState(() {
      _mealType = type;
      _stepIndex = 2;
    });
  }

  void _selectDiet(_DietChoice diet) {
    setState(() {
      _diet = diet;
      _stepIndex = 3;
    });
  }

  List<Cuisine> _topCuisineChoices() {
    final profileState = Provider.of<ProfileState>(context, listen: false);
    final favs = profileState.favoriteCuisines.map((s) => s.trim()).where((s) => s.isNotEmpty).toList();

    final byId = <String, Cuisine>{for (final c in _cuisines) c.cuisineId: c};

    final choices = <Cuisine>[];
    for (final id in favs) {
      final c = byId[id];
      if (c != null) choices.add(c);
      if (choices.length >= 2) break;
    }

    if (choices.length < 2) {
      for (final c in _cuisines) {
        if (choices.any((x) => x.cuisineId == c.cuisineId)) continue;
        choices.add(c);
        if (choices.length >= 2) break;
      }
    }

    return choices.take(2).toList();
  }

  Map<String, dynamic> _familyProfileOverride() {
    final restrictions = <String>[];
    switch (_diet) {
      case _DietChoice.none:
        break;
      case _DietChoice.vegetarian:
        restrictions.add('vegetarian');
        break;
      case _DietChoice.vegan:
        restrictions.add('vegan');
        break;
    }

    if (restrictions.isEmpty) return {};

    return {
      'members': [
        {
          'name': 'Household',
          'age': 30,
          'dietary_restrictions': restrictions,
          'allergens': [],
          'health_conditions': [],
          'spice_tolerance': 'medium',
        }
      ],
      'household_allergens': [],
      'dietary_restrictions': restrictions,
      'skill_level': 3,
    };
  }

  String _planningGoal() {
    switch (_mealType) {
      case _MealTypeChoice.casual:
        return 'fastest';
      case _MealTypeChoice.standard:
        return 'balanced';
      case _MealTypeChoice.formal:
        return 'balanced';
    }
  }

  Map<String, dynamic> _partyCourseCounts() {
    if (widget.mode == PartyPlanningMode.festival) {
      return {
        'appetizers': 3,
        'mains': 3,
        'sides': 3,
        'desserts': 2,
      };
    }

    return {
      'appetizers': 2,
      'mains': 2,
      'sides': 2,
      'desserts': 1,
    };
  }

  Future<void> _selectCuisineAndGenerate(String selectedCuisine) async {
    final apiClient = Provider.of<ApiClient>(context, listen: false);
    final profileState = Provider.of<ProfileState>(context, listen: false);

    final body = <String, dynamic>{
      'selected_cuisine': selectedCuisine,
      'party_settings': {
        'guest_count': _totalGuests(),
        'age_group_counts': {
          'child_0_12': _child0To12,
          'teen_13_17': _teen13To17,
          'adult_18_plus': _adult18Plus,
        },
      },
      'party_course_counts': _partyCourseCounts(),
      'planning_goal': _planningGoal(),
      'avoid_waste': true,
      'use_leftovers': true,
    };

    if (_includeInactiveInventory) {
      body['include_inactive_inventory'] = true;
    }

    final familyOverride = _familyProfileOverride();
    if (familyOverride.isNotEmpty) {
      body['family_profile'] = familyOverride;
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

    final res = await apiClient.post('/plan/party', body);
    final plan = MenuPlanResponse.fromJson(res);

    fireAndForget(MetricsService.instance.recordWorkflowStep('PlanParty', 'GenerateMenu'));

    if (!mounted) return;

    await Navigator.of(context).pushReplacement(
      AppMotion.createRoute(
        GeneratedMenuScreen(
          menuPlan: plan,
          requestBody: body,
          title: _title(),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (kDebugMode || kProfileMode) {
      SavoUiGuards.warnIfTooManyChoices(
        screen: 'PartySetupScreen',
        surface: _stepTitle(),
        choices: 3,
      );
    }

    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: Text(_title()),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: _goBack,
        ),
      ),
      body: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              _stepTitle(),
              style: theme.textTheme.titleMedium,
            ),
            const SizedBox(height: AppSpacing.md),
            Expanded(child: _buildStepBody(context)),
          ],
        ),
      ),
    );
  }

  Widget _buildStepBody(BuildContext context) {
    switch (_stepIndex) {
      case 0:
        return _GuestsStep(
          child0To12: _child0To12,
          teen13To17: _teen13To17,
          adult18Plus: _adult18Plus,
          includeInactiveInventory: _includeInactiveInventory,
          onIncludeInactiveChanged: _setIncludeInactiveInventory,
          onChanged: (c, t, a) => _updateGuests(
            child0To12: c,
            teen13To17: t,
            adult18Plus: a,
          ),
          onNext: _nextFromGuests,
        );
      case 1:
        return _MealTypeStep(onSelect: _selectMealType);
      case 2:
        return _DietStep(onSelect: _selectDiet);
      case 3:
        return _CuisineStep(
          loading: _loadingCuisines,
          topCuisines: _topCuisineChoices(),
          onSelect: _selectCuisineAndGenerate,
        );
      default:
        return const SizedBox.shrink();
    }
  }
}

class _GuestsStep extends StatelessWidget {
  final int child0To12;
  final int teen13To17;
  final int adult18Plus;
  final bool includeInactiveInventory;
  final ValueChanged<bool> onIncludeInactiveChanged;
  final void Function(int child0To12, int teen13To17, int adult18Plus) onChanged;
  final VoidCallback onNext;

  const _GuestsStep({
    required this.child0To12,
    required this.teen13To17,
    required this.adult18Plus,
    required this.includeInactiveInventory,
    required this.onIncludeInactiveChanged,
    required this.onChanged,
    required this.onNext,
  });

  int get _total => child0To12 + teen13To17 + adult18Plus;

  Widget _countRow({
    required BuildContext context,
    required String label,
    required int value,
    required VoidCallback? onDecrement,
    required VoidCallback onIncrement,
  }) {
    final theme = Theme.of(context);
    return Row(
      children: [
        Expanded(child: Text(label, style: theme.textTheme.bodyMedium)),
        IconButton(
          icon: const Icon(Icons.remove_circle_outline),
          onPressed: onDecrement,
        ),
        SizedBox(
          width: 44,
          child: Center(
            child: Text(
              '$value',
              style: theme.textTheme.titleMedium,
            ),
          ),
        ),
        IconButton(
          icon: const Icon(Icons.add_circle_outline),
          onPressed: onIncrement,
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SavoCard(
          elevated: true,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _countRow(
                context: context,
                label: 'Kids (0–12)',
                value: child0To12,
                onDecrement: child0To12 > 0
                    ? () => onChanged(child0To12 - 1, teen13To17, adult18Plus)
                    : null,
                onIncrement: () => onChanged(child0To12 + 1, teen13To17, adult18Plus),
              ),
              const SizedBox(height: AppSpacing.sm),
              _countRow(
                context: context,
                label: 'Teens (13–17)',
                value: teen13To17,
                onDecrement: teen13To17 > 0
                    ? () => onChanged(child0To12, teen13To17 - 1, adult18Plus)
                    : null,
                onIncrement: () => onChanged(child0To12, teen13To17 + 1, adult18Plus),
              ),
              const SizedBox(height: AppSpacing.sm),
              _countRow(
                context: context,
                label: 'Adults (18+)',
                value: adult18Plus,
                onDecrement: adult18Plus > 0
                    ? () => onChanged(child0To12, teen13To17, adult18Plus - 1)
                    : null,
                onIncrement: () => onChanged(child0To12, teen13To17, adult18Plus + 1),
              ),
              const SizedBox(height: AppSpacing.md),
              Text(
                'Total: $_total',
                style: Theme.of(context).textTheme.titleSmall,
              ),
              const SizedBox(height: AppSpacing.md),
              SwitchListTile.adaptive(
                value: includeInactiveInventory,
                contentPadding: EdgeInsets.zero,
                title: const Text('Use older pantry items'),
                subtitle: const Text('Include inactive items from previous scans'),
                onChanged: onIncludeInactiveChanged,
              ),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        FilledButton(
          onPressed: _total > 0 ? onNext : null,
          child: const Text('Continue'),
        ),
      ],
    );
  }
}

class _MealTypeStep extends StatelessWidget {
  final void Function(_MealTypeChoice) onSelect;

  const _MealTypeStep({required this.onSelect});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SavoCard(
          elevated: true,
          onTap: () => onSelect(_MealTypeChoice.casual),
          child: const Row(
            children: [
              Icon(Icons.timer_outlined),
              SizedBox(width: AppSpacing.md),
              Expanded(child: Text('Casual')),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        SavoCard(
          elevated: true,
          onTap: () => onSelect(_MealTypeChoice.standard),
          child: const Row(
            children: [
              Icon(Icons.restaurant_outlined),
              SizedBox(width: AppSpacing.md),
              Expanded(child: Text('Standard')),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        SavoCard(
          elevated: true,
          onTap: () => onSelect(_MealTypeChoice.formal),
          child: const Row(
            children: [
              Icon(Icons.celebration_outlined),
              SizedBox(width: AppSpacing.md),
              Expanded(child: Text('Formal')),
            ],
          ),
        ),
      ],
    );
  }
}

class _DietStep extends StatelessWidget {
  final void Function(_DietChoice) onSelect;

  const _DietStep({required this.onSelect});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SavoCard(
          elevated: true,
          onTap: () => onSelect(_DietChoice.none),
          child: const Row(
            children: [
              Icon(Icons.restaurant_menu_outlined),
              SizedBox(width: AppSpacing.md),
              Expanded(child: Text('No preference')),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        SavoCard(
          elevated: true,
          onTap: () => onSelect(_DietChoice.vegetarian),
          child: const Row(
            children: [
              Icon(Icons.eco_outlined),
              SizedBox(width: AppSpacing.md),
              Expanded(child: Text('Vegetarian')),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        SavoCard(
          elevated: true,
          onTap: () => onSelect(_DietChoice.vegan),
          child: const Row(
            children: [
              Icon(Icons.spa_outlined),
              SizedBox(width: AppSpacing.md),
              Expanded(child: Text('Vegan')),
            ],
          ),
        ),
      ],
    );
  }
}

class _CuisineStep extends StatefulWidget {
  final bool loading;
  final List<Cuisine> topCuisines;
  final Future<void> Function(String) onSelect;

  const _CuisineStep({
    required this.loading,
    required this.topCuisines,
    required this.onSelect,
  });

  @override
  State<_CuisineStep> createState() => _CuisineStepState();
}

class _CuisineStepState extends State<_CuisineStep> {
  bool _generating = false;
  String? _error;

  Future<void> _handleSelect(String cuisineId) async {
    if (_generating) return;
    setState(() {
      _generating = true;
      _error = null;
    });

    try {
      await widget.onSelect(cuisineId);
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
    if (widget.loading) {
      return const Center(child: CircularProgressIndicator());
    }

    final theme = Theme.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SavoCard(
          elevated: true,
          onTap: _generating ? null : () => _handleSelect('auto'),
          child: Row(
            children: [
              const Icon(Icons.auto_awesome_outlined),
              const SizedBox(width: AppSpacing.md),
              const Expanded(child: Text('Auto')),
              if (_generating) ...[
                const SizedBox(width: AppSpacing.sm),
                const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
              ],
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        ...widget.topCuisines.map((c) {
          return Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.md),
            child: SavoCard(
              elevated: true,
              onTap: _generating ? null : () => _handleSelect(c.cuisineId),
              child: Row(
                children: [
                  Text(c.flag),
                  const SizedBox(width: AppSpacing.md),
                  Expanded(child: Text(c.name)),
                ],
              ),
            ),
          );
        }),
        if (_error != null)
          Padding(
            padding: const EdgeInsets.only(top: AppSpacing.sm),
            child: Text(
              _error!,
              style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.error),
            ),
          ),
      ],
    );
  }
}
