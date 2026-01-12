import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../ui/ui_principles.dart';
import '../services/api_client.dart';
import '../services/cook_now_service.dart';
import '../services/profile_service.dart';
import '../services/entitlements_service.dart';
import '../services/tonight_suggestion_service.dart';
import '../models/profile_state.dart';
import '../models/planning.dart';
import '../theme/app_theme.dart';
import '../widgets/savo_widgets.dart';
import '../widgets/pro_paywall_sheet.dart';
import 'plan_screen.dart';
import 'pantry_update_entry_screen.dart';
import 'account_settings_screen.dart';
import 'onboarding/onboarding_coordinator.dart';
import 'recipe_detail_screen.dart';
import '../models/inventory.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  static const String _prefsTonightOptionsKey = 'savo.tonight.options.v1';
  static const String _prefsTonightOptionsAtKey = 'savo.tonight.options_at.v1';

  bool _loadingOnboarding = true;
  Map<String, dynamic>? _onboardingStatus;

  bool _loadingTonight = true;
  String? _tonightError;
  List<Recipe> _tonightOptions = const [];
  int _tonightIndex = 0;

  bool _loadingInventory = true;
  List<InventoryItem> _inventory = const [];

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
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _refreshOnboardingStatus();
      _loadTonightFromCache().whenComplete(() {
        _loadTonight(allowStaleSuggestion: true);
      });
    });
  }

  Future<void> _loadTonightFromCache() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_prefsTonightOptionsKey);
      if (raw == null || raw.trim().isEmpty) return;

      final decoded = jsonDecode(raw);
      if (decoded is! List) return;

      final recipes = decoded
          .whereType<Map>()
          .map((m) => Recipe.fromJson(m.cast<String, dynamic>()))
          .where((r) => r.recipeId.trim().isNotEmpty)
          .toList(growable: false);

      if (recipes.isEmpty) return;
      if (!mounted) return;
      setState(() {
        _tonightOptions = recipes;
        _tonightIndex = 0;
        _tonightError = null;
        // Keep the CTA enabled while we refresh in the background.
        _loadingTonight = false;
      });
    } catch (_) {
      // Best-effort only.
    }
  }

  Future<void> _saveTonightCache(List<Recipe> recipes) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final payload = jsonEncode(recipes.take(5).map((r) => r.toJson()).toList());
      await prefs.setString(_prefsTonightOptionsKey, payload);
      await prefs.setInt(_prefsTonightOptionsAtKey, DateTime.now().millisecondsSinceEpoch);
    } catch (_) {
      // Best-effort only.
    }
  }

  Future<void> _loadTonight({bool allowStaleSuggestion = false}) async {
    if (mounted) {
      setState(() {
        // If we already have a cached suggestion, don't block the CTA while refreshing.
        _loadingTonight = allowStaleSuggestion ? (_tonightRecipe == null) : true;
        _tonightError = null;
      });
    }

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final profileState = Provider.of<ProfileState>(context, listen: false);

      final inventory = await _fetchInventory(apiClient);
      final cookNowService = CookNowService();
      final options = await cookNowService.generateRecipeOptions(
        apiClient: apiClient,
        profileState: profileState,
        maxOptions: 5,
        avoidRecentRecipes: 3,
        preferCachedFirst: true,
      );

      final tonight = TonightSuggestionService().rankRecipes(
        recipes: options,
        inventory: inventory,
      );

      if (!mounted) return;
      setState(() {
        _inventory = inventory;
        _loadingInventory = false;
        _tonightOptions = tonight.rankedRecipes;
        _tonightIndex = 0;
        _loadingTonight = false;
      });

      // Cache the latest options for instant load next time.
      await _saveTonightCache(_tonightOptions);
    } catch (e) {
      if (!mounted) return;
      final msg = e.toString().replaceFirst(RegExp(r'^Exception:\s*'), '');
      setState(() {
        // If we have a suggestion already, keep CTA enabled and show no blocking state.
        _loadingTonight = (_tonightRecipe == null) ? false : false;
        _loadingInventory = false;
        _tonightError = msg;
      });
    }
  }

  Future<List<InventoryItem>> _fetchInventory(ApiClient apiClient) async {
    final res = await apiClient.get('/inventory-db/items?include_inactive=true');

    if (res is Map && res['items'] is List) {
      return (res['items'] as List)
          .whereType<Map>()
          .map((j) => InventoryItem.fromJson(j.cast<String, dynamic>()))
          .toList();
    }

    if (res is List) {
      return res
          .whereType<Map>()
          .map((j) => InventoryItem.fromJson(j.cast<String, dynamic>()))
          .toList();
    }

    return const [];
  }

  Recipe? get _tonightRecipe {
    if (_tonightOptions.isEmpty) return null;
    if (_tonightIndex < 0 || _tonightIndex >= _tonightOptions.length) return _tonightOptions.first;
    return _tonightOptions[_tonightIndex];
  }

  void _swapTonight() {
    if (_tonightOptions.length < 2) return;
    setState(() {
      _tonightIndex = (_tonightIndex + 1) % _tonightOptions.length;
    });
  }

  String _whyItWorks(Recipe recipe) {
    final ingredients = recipe.ingredientsUsed
        .map((i) => i.canonicalName.replaceAll('_', ' ').trim())
        .where((s) => s.isNotEmpty)
        .toList();

    if (ingredients.isEmpty) {
      return 'Based on what\'s in your pantry';
    }

    final top = ingredients.take(3).toList();
    final suffix = ingredients.length > 3 ? '…' : '';
    return 'Uses: ${top.join(', ')}$suffix';
  }

  List<InventoryItem> get _expiringSoon {
    final list = _inventory
        .where((i) => i.isCurrent)
        .where((i) => i.freshnessDaysRemaining != null)
        .where((i) => i.freshnessDaysRemaining! <= 3)
        .toList();

    list.sort((a, b) {
      final ad = a.freshnessDaysRemaining ?? 9999;
      final bd = b.freshnessDaysRemaining ?? 9999;
      return ad.compareTo(bd);
    });

    return list;
  }

  Future<void> _refreshOnboardingStatus() async {
    if (mounted) {
      setState(() {
        _loadingOnboarding = true;
      });
    }
    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final profileState = Provider.of<ProfileState>(context, listen: false);
      final profileService = ProfileService(apiClient);
      final status = await profileService.getOnboardingStatus();
      profileState.updateOnboardingStatus(status);

      if (!mounted) return;
      setState(() {
        _onboardingStatus = status;
        _loadingOnboarding = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loadingOnboarding = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (kDebugMode || kProfileMode) {
      // v1: TodayHome should present 1 primary + 2 secondary actions.
      SavoUiGuards.warnIfTooManyChoices(
        screen: 'HomeScreen',
        surface: 'Today actions',
        choices: 3,
      );
      SavoUiGuards.warnIfMultiplePrimaryActions(
        screen: 'HomeScreen',
        surface: 'Today hero',
        primaryActions: 1,
      );
    }

    // Check authentication on every build
    final session = Supabase.instance.client.auth.currentSession;
    if (session == null) {
      // Redirect to login if no session
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (context.mounted) {
          Navigator.of(context).pushReplacementNamed('/login');
        }
      });
      // Return loading screen while redirecting
      return const Scaffold(
        body: Center(
          child: CircularProgressIndicator(),
        ),
      );
    }
    
    return Scaffold(
      appBar: AppBar(
        title: const Text('SAVO'),
        actions: [
          IconButton(
            tooltip: 'User profile',
            icon: const Icon(Icons.person_outline),
            onPressed: () {
              Navigator.push(
                context,
                AppMotion.createRoute(const UserProfileScreen()),
              );
            },
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              _greetingWithName(context),
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: AppSpacing.sm),
            SavoCard(
              elevated: true,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          'Tonight',
                          style: Theme.of(context).textTheme.headlineSmall,
                        ),
                      ),
                      IconButton(
                        tooltip: 'Swap suggestion',
                        onPressed: (_loadingTonight || (_tonightOptions.length < 2)) ? null : _swapTonight,
                        icon: const Icon(Icons.swap_horiz),
                      ),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  if (_loadingTonight) ...[
                    Text(
                      'Finding a dinner idea…',
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                  ] else if (_tonightRecipe != null) ...[
                    Text(
                      _tonightRecipe!.getLocalizedName(_preferredLanguageKey(context)),
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: AppSpacing.xs),
                    Text(
                      _whyItWorks(_tonightRecipe!),
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                    if (_expiringSoon.isNotEmpty) ...[
                      const SizedBox(height: AppSpacing.xs),
                      Text(
                        'Use soon: ${_expiringSoon.take(2).map((i) => i.displayLabel).join(', ')}',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color: Theme.of(context).colorScheme.onSurfaceVariant,
                            ),
                      ),
                    ],
                  ] else ...[
                    Text(
                      _tonightError ?? 'No dinner idea yet. Update pantry to enable Cook tonight.',
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                  ],
                  const SizedBox(height: AppSpacing.md),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      onPressed: (_loadingTonight || _tonightRecipe == null)
                          ? null
                          : () {
                              Navigator.push(
                                context,
                                AppMotion.createRoute(
                                  RecipeDetailScreen(recipe: _tonightRecipe!),
                                ),
                              );
                            },
                      child: const Text('Cook tonight'),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () {
                      Navigator.push(
                        context,
                        AppMotion.createRoute(const PlanScreen()),
                      );
                    },
                    child: const Text('Plan a meal / party'),
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: OutlinedButton(
                    onPressed: () async {
                      final gate = await EntitlementsService.instance.tryConsumeScan();
                      if (!gate.allowed && context.mounted) {
                        await showProPaywallSheet(
                          context,
                          title: 'Upgrade to SAVO Pro',
                          ctaLabel: 'Upgrade for unlimited scans',
                          reason: 'You\'ve hit today\'s free scan limit. Upgrade to keep scanning and get unlimited suggestions.',
                          trigger: 'scan_limit',
                        );
                        return;
                      }

                      if (!context.mounted) return;
                      Navigator.push(
                        context,
                        AppMotion.createRoute(const PantryUpdateEntryScreen()),
                      );
                    },
                    child: const Text('Update pantry'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.lg),

            if (!_loadingOnboarding) ...[
              _SetupBanner(
                onboardingStatus: _onboardingStatus,
                onResume: () {
                  Navigator.push(
                    context,
                    AppMotion.createRoute(const OnboardingCoordinator()),
                  );
                },
                onRefresh: _refreshOnboardingStatus,
              ),
              const SizedBox(height: AppSpacing.lg),
            ],
          ],
        ),
      ),
    );
  }

  String _greeting() {
    final h = DateTime.now().hour;
    if (h < 12) return 'Good morning';
    if (h < 17) return 'Good afternoon';
    return 'Good evening';
  }

  String _greetingWithName(BuildContext context) {
    final base = _greeting();
    final name = _resolveUserName(context);
    if (name == null || name.trim().isEmpty) return base;
    return '$base, $name';
  }

  String? _resolveUserName(BuildContext context) {
    try {
      final profileState = Provider.of<ProfileState>(context, listen: false);
      final profile = profileState.profile;
      final household = profileState.household;

      final candidates = <Object?>[
        profile?['display_name'],
        profile?['full_name'],
        profile?['name'],
        profile?['first_name'],
        household?['name'],
      ];

      for (final c in candidates) {
        final s = c?.toString().trim();
        if (s != null && s.isNotEmpty) return s;
      }
    } catch (_) {
      // Best-effort only.
    }

    final session = Supabase.instance.client.auth.currentSession;
    final meta = session?.user.userMetadata;
    if (meta != null) {
      for (final key in const ['full_name', 'name', 'display_name', 'first_name']) {
        final v = meta[key];
        final s = v?.toString().trim();
        if (s != null && s.isNotEmpty) return s;
      }
    }

    final email = session?.user.email;
    if (email != null && email.contains('@')) {
      final prefix = email.split('@').first.trim();
      if (prefix.isNotEmpty) return prefix;
    }

    return null;
  }
}

class _SetupBanner extends StatelessWidget {
  final Map<String, dynamic>? onboardingStatus;
  final VoidCallback onResume;
  final VoidCallback onRefresh;

  const _SetupBanner({
    required this.onboardingStatus,
    required this.onResume,
    required this.onRefresh,
  });

  bool get _completed => onboardingStatus?['completed'] == true;

  List<String> get _missingLabels {
    final raw = onboardingStatus?['missing_fields'];
    if (raw is! List) return const [];

    final labels = <String>[];
    for (final v in raw) {
      final s = v.toString().trim().toLowerCase();
      if (s.isEmpty) continue;

      if (s.contains('household')) {
        labels.add('Household');
      } else if (s.contains('allerg') || s.contains('safety')) {
        labels.add('Allergens');
      } else if (s.contains('diet')) {
        labels.add('Dietary');
      } else if (s.contains('spice')) {
        labels.add('Spice');
      } else if (s.contains('pantry')) {
        labels.add('Pantry');
      } else if (s.contains('language')) {
        labels.add('Language');
      }
    }
    return labels.toSet().toList()..sort();
  }

  @override
  Widget build(BuildContext context) {
    if (_completed) return const SizedBox.shrink();

    final theme = Theme.of(context);
    final cs = theme.colorScheme;

    return Card(
      color: cs.primaryContainer,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.auto_fix_high, color: cs.onPrimaryContainer),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Finish setup to personalize your menus',
                    style: theme.textTheme.titleMedium?.copyWith(
                      color: cs.onPrimaryContainer,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                IconButton(
                  tooltip: 'Refresh',
                  onPressed: onRefresh,
                  icon: Icon(Icons.refresh, color: cs.onPrimaryContainer),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              'Set your household, allergens, and dietary preferences so SAVO can plan safely and accurately.',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: cs.onPrimaryContainer,
              ),
            ),
            if (_missingLabels.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                'Missing: ${_missingLabels.join(', ')}',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: cs.onPrimaryContainer,
                ),
              ),
            ],
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: onResume,
                icon: const Icon(Icons.play_arrow),
                label: const Text('Complete setup'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
