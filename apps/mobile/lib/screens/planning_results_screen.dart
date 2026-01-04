import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/api_client.dart';
import '../services/scanning_service.dart';
import '../models/planning.dart';
import '../models/cuisine.dart';
import 'recipe_detail_screen.dart';
import 'shopping_list_screen.dart';
import '../models/market_config_state.dart';

class PlanningResultsScreen extends StatefulWidget {
  final MenuPlanResponse menuPlan;
  final String planType; // 'daily', 'weekly', 'party'

  const PlanningResultsScreen({
    super.key,
    required this.menuPlan,
    required this.planType,
  });

  @override
  State<PlanningResultsScreen> createState() => _PlanningResultsScreenState();
}

class _PlanningResultsScreenState extends State<PlanningResultsScreen> {
  List<Cuisine> _cuisines = [];
  bool _loadingCuisines = true;
  String? _selectedCuisine;
  bool _buildingShoppingList = false;

  static const _shoppingListPrefsKey = 'savo.shopping_list.latest';

  @override
  void initState() {
    super.initState();
    _selectedCuisine = widget.menuPlan.selectedCuisine;
    _loadCuisines();
  }

  Future<void> _loadCuisines() async {
    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      // Load cuisines from the API
      final response = await apiClient.get('/cuisines');

      if (response is List) {
        setState(() {
          _cuisines = (response as List).map((json) => Cuisine.fromJson(json as Map<String, dynamic>)).toList();
          _loadingCuisines = false;
        });
      }
    } catch (e) {
      setState(() => _loadingCuisines = false);
    }
  }

  int _extractServings(Menu menu) {
    if (menu.servings.isEmpty) return 1;
    final total = menu.servings['total'];
    if (total is int && total > 0) return total;
    if (total is num && total > 0) return total.toInt();

    int sum = 0;
    for (final v in menu.servings.values) {
      if (v is int) sum += v;
      if (v is num) sum += v.toInt();
    }
    return sum > 0 ? sum : 1;
  }

  Future<void> _persistShoppingList(List<dynamic> items) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_shoppingListPrefsKey, json.encode(items));
  }

  List<Map<String, dynamic>> _mergeShoppingListItems(List<Map<String, dynamic>> raw) {
    final Map<String, Map<String, dynamic>> merged = {};
    for (final item in raw) {
      final name = (item['canonical_name'] ?? item['ingredient'] ?? item['name'] ?? '').toString().trim();
      final unit = (item['unit'] ?? '').toString().trim();
      final amount = item['amount'] ?? item['quantity'];
      final key = '${name.toLowerCase()}|${unit.toLowerCase()}';

      final num? qty = amount is num ? amount : num.tryParse(amount?.toString() ?? '');
      if (!merged.containsKey(key)) {
        merged[key] = {
          'canonical_name': name.isEmpty ? 'Item' : name,
          'amount': qty ?? amount,
          'unit': unit,
        };
      } else {
        final existing = merged[key]!;
        final existingAmount = existing['amount'];
        final num? existingQty = existingAmount is num ? existingAmount : num.tryParse(existingAmount?.toString() ?? '');
        if (existingQty != null && qty != null) {
          existing['amount'] = existingQty + qty;
        }
      }
    }
    return merged.values.toList();
  }

  Future<void> _createShoppingListFromPlan() async {
    if (_buildingShoppingList) return;

    setState(() => _buildingShoppingList = true);
    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final scanningService = ScanningService();

      final List<Map<String, dynamic>> combined = [];
      int successes = 0;

      for (final menu in widget.menuPlan.menus) {
        final servings = _extractServings(menu);
        for (final course in menu.courses) {
          if (course.recipeOptions.isEmpty) continue;
          final recipe = course.recipeOptions.first;
          final result = await scanningService.checkSufficiency(
            recipeId: recipe.recipeId,
            servings: servings,
            apiClient: apiClient,
          );
          if (result['success'] == true) {
            successes += 1;
            final list = result['shopping_list'];
            if (list is List) {
              for (final item in list) {
                if (item is Map) {
                  combined.add(Map<String, dynamic>.from(item));
                } else {
                  combined.add({'canonical_name': item.toString()});
                }
              }
            }
          }
        }
      }

      if (!mounted) return;
      if (successes == 0) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not build shopping list for this plan.')),
        );
        return;
      }

      final merged = _mergeShoppingListItems(combined);
      await _persistShoppingList(merged);

      if (!mounted) return;
      Navigator.push(
        context,
        MaterialPageRoute(builder: (_) => const ShoppingListScreen()),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to create shopping list: $e')),
      );
    } finally {
      if (mounted) setState(() => _buildingShoppingList = false);
    }
  }

  List<String> _buildLeftoversScheduleLines(MenuPlanResponse menuPlan) {
    if (widget.planType != 'weekly') return const [];

    final lines = <String>[];

    for (final menu in menuPlan.menus) {
      final dayIndex = (menu.dayIndex ?? 0) + 1;

      for (final course in menu.courses) {
        // Keep it simple + fast: use the top option per course.
        if (course.recipeOptions.isEmpty) continue;
        final recipe = course.recipeOptions.first;

        final forecast = recipe.leftoverForecast;
        if (forecast.isEmpty) continue;

        final expected = forecast['expected_leftover_servings'];
        final reuse = forecast['reuse_ideas'];

        final num? expectedNum =
            expected is num ? expected : num.tryParse(expected?.toString() ?? '');

        final reuseIdeas = <String>[];
        if (reuse is List) {
          for (final v in reuse) {
            final s = v.toString().trim();
            if (s.isEmpty) continue;
            if (s.toLowerCase() == 'n/a') continue;
            reuseIdeas.add(s);
          }
        }

        // Only show genuinely useful leftovers.
        final hasLeftovers =
            (expectedNum != null && expectedNum > 0) || reuseIdeas.isNotEmpty;
        if (!hasLeftovers) continue;

        final recipeName = recipe.getLocalizedName('en');
        final suffix = reuseIdeas.isNotEmpty ? reuseIdeas.first : 'Use within 1–2 days';
        lines.add('Day $dayIndex: $recipeName → $suffix');
      }
    }

    // Cap to keep the UI punchy.
    if (lines.length > 4) {
      return lines.take(4).toList();
    }
    return lines;
  }

  Widget _buildLeftoversScheduleCard(List<String> lines) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.kitchen, color: cs.primary),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    'Leftovers plan',
                    style: theme.textTheme.titleMedium
                        ?.copyWith(fontWeight: FontWeight.w700),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            for (final line in lines)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                  '• $line',
                  style: theme.textTheme.bodyMedium
                      ?.copyWith(color: cs.onSurface.withOpacity(0.85)),
                ),
              ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final market = Provider.of<MarketConfigState>(context);
    final showShoppingList = market.isEnabled('shopping_list', defaultValue: true);
    final leftoversScheduleLines = _buildLeftoversScheduleLines(widget.menuPlan);
    return Scaffold(
      appBar: AppBar(
        title: Text(_getPlanTitle()),
        actions: [
          if (!_loadingCuisines && _cuisines.isNotEmpty)
            PopupMenuButton<String>(
              icon: const Icon(Icons.restaurant),
              tooltip: 'Change Cuisine',
              onSelected: (cuisine) {
                setState(() {
                  _selectedCuisine = cuisine;
                });
                // TODO: Re-plan with new cuisine
              },
              itemBuilder: (context) => _cuisines
                  .where((c) => widget.planType == 'party'
                      ? c.partyEnabled
                      : c.dailyEnabled)
                  .map((c) => PopupMenuItem(
                        value: c.cuisineId,
                        child: Row(
                          children: [
                            Text(c.flag),
                            const SizedBox(width: 8),
                            Text(c.name),
                          ],
                        ),
                      ))
                  .toList(),
            ),
        ],
      ),
        body: widget.menuPlan.status == 'error'
          ? Center(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(Icons.error_outline, size: 64, color: Colors.red),
                    const SizedBox(height: 16),
                    Text(
                      widget.menuPlan.errorMessage ?? 'Planning failed',
                      style: Theme.of(context).textTheme.titleMedium,
                      textAlign: TextAlign.center,
                    ),
                  ],
                ),
              ),
            )
          : ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: widget.menuPlan.menus.length,
              itemBuilder: (context, menuIndex) {
                final menu = widget.menuPlan.menus[menuIndex];
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (menuIndex == 0 && widget.planType == 'weekly' && leftoversScheduleLines.isNotEmpty) ...[
                      _buildLeftoversScheduleCard(leftoversScheduleLines),
                      const SizedBox(height: 12),
                    ],
                    if (widget.planType == 'weekly') ...[
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 8.0),
                        child: Text(
                          _formatWeeklyDayTitle(menu),
                          style: Theme.of(context).textTheme.titleLarge?.copyWith(
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                      const Divider(),
                    ],
                    ...menu.courses.map((course) => _buildCourseSection(course)),
                    const SizedBox(height: 16),
                  ],
                );
              },
            ),
      bottomNavigationBar: widget.menuPlan.status == 'ok'
          ? Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surface,
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.1),
                    blurRadius: 8,
                    offset: const Offset(0, -2),
                  ),
                ],
              ),
              child: Row(
                children: [
                  Expanded(
                    child: FilledButton.tonal(
                      onPressed: _buildingShoppingList ? null : () {
                        if (showShoppingList) {
                          _createShoppingListFromPlan();
                        }
                      },
                      child: _buildingShoppingList
                          ? const SizedBox(
                              height: 18,
                              width: 18,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Text('Shopping List'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: FilledButton(
                      onPressed: _buildingShoppingList
                          ? null
                          : () {
                              // Navigate to first recipe in cook mode
                              if (widget.menuPlan.menus.isNotEmpty &&
                                  widget.menuPlan.menus.first.courses.isNotEmpty &&
                                  widget.menuPlan.menus.first.courses.first.recipeOptions.isNotEmpty) {
                                final firstRecipe = widget.menuPlan.menus.first.courses.first.recipeOptions.first;
                                Navigator.push(
                                  context,
                                  MaterialPageRoute(
                                    builder: (_) => RecipeDetailScreen(recipe: firstRecipe),
                                  ),
                                );
                              }
                            },
                      child: const Text('Start Cooking'),
                    ),
                  ),
                ],
              ),
            )
          : null,
    );
  }

  String _formatWeeklyDayTitle(Menu menu) {
    if (menu.date != null) {
      try {
        final dateTime = DateTime.parse(menu.date!);
        final weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
        final months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        final weekday = weekdays[dateTime.weekday - 1];
        final month = months[dateTime.month - 1];
        return 'Day ${(menu.dayIndex ?? 0) + 1} - $weekday, $month ${dateTime.day}';
      } catch (e) {
        return 'Day ${(menu.dayIndex ?? 0) + 1}';
      }
    }
    return 'Day ${(menu.dayIndex ?? 0) + 1}';
  }

  String _getPlanTitle() {
    switch (widget.planType) {
      case 'daily':
        return 'Today\'s Menu';
      case 'weekly':
        return 'Weekly Plan';
      case 'party':
        return 'Party Menu';
      default:
        return 'Menu Plan';
    }
  }

  Widget _buildCourseSection(Course course) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 8.0),
          child: Text(
            course.courseHeader,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
          ),
        ),
        SizedBox(
          height: 180,
          child: ListView.builder(
            scrollDirection: Axis.horizontal,
            itemCount: course.recipeOptions.length,
            itemBuilder: (context, index) {
              final recipe = course.recipeOptions[index];
              return _RecipeCard(recipe: recipe);
            },
          ),
        ),
      ],
    );
  }
}

class _RecipeCard extends StatefulWidget {
  final Recipe recipe;

  const _RecipeCard({required this.recipe});

  @override
  State<_RecipeCard> createState() => _RecipeCardState();
}

class _RecipeCardState extends State<_RecipeCard> {
  bool _usesExpiringItems = false;
  bool _usesLeftovers = false;
  bool _checkingExpiring = true;

  String? get _coverImageUrl {
    final refs = widget.recipe.youtubeReferences;
    if (refs.isNotEmpty) return refs.first.thumbnailUrl;

    final name = widget.recipe.getLocalizedName('en').trim();
    if (name.isEmpty) {
      return 'https://source.unsplash.com/featured/?food';
    }
    final encoded = Uri.encodeComponent(name);
    return 'https://source.unsplash.com/featured/?food,$encoded';
  }

  @override
  void initState() {
    super.initState();
    _checkExpiringIngredients();
  }

  Future<void> _checkExpiringIngredients() async {
    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final response = await apiClient.get('/inventory');

      if (response is List) {
        final inventory = (response as List)
            .map((json) => json as Map<String, dynamic>)
            .toList();

        // Check if any recipe ingredients are expiring (< 3 days)
        bool usesExpiring = false;
        bool usesLeftovers = false;
        for (final ingredient in widget.recipe.ingredientsUsed) {
          final item = inventory.firstWhere(
            (inv) => inv['inventory_id'] == ingredient.inventoryId,
            orElse: () => {},
          );
          
          if (item.isNotEmpty) {
            final freshness = item['freshness_days_remaining'];
            if (freshness != null && freshness < 3) {
              usesExpiring = true;
            }

            final state = item['state'];
            if (state is String && state.toLowerCase() == 'leftover') {
              usesLeftovers = true;
            }
          }
        }

        setState(() {
          _usesExpiringItems = usesExpiring;
          _usesLeftovers = usesLeftovers;
          _checkingExpiring = false;
        });
        return;
      }

      setState(() {
        _checkingExpiring = false;
      });
    } catch (e) {
      setState(() {
        _checkingExpiring = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;
    final title = widget.recipe.getLocalizedName('en');

    final expected = widget.recipe.leftoverForecast['expected_leftover_servings'];
    final num? expectedNum = expected is num ? expected : num.tryParse(expected?.toString() ?? '');
    final bool makesLeftovers = expectedNum != null && expectedNum > 0;

    return Container(
      width: 280,
      margin: const EdgeInsets.only(right: 12),
      child: Card(
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: () {
            Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => RecipeDetailScreen(recipe: widget.recipe),
              ),
            );
          },
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SizedBox(
                height: 140,
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    Image.network(
                      _coverImageUrl ?? 'https://source.unsplash.com/featured/?food',
                      fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => Container(
                        color: cs.surfaceVariant,
                        child: Icon(Icons.restaurant, color: cs.onSurfaceVariant, size: 40),
                      ),
                    ),
                    // Subtle scrim for readability.
                    Container(
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          begin: Alignment.topCenter,
                          end: Alignment.bottomCenter,
                          colors: [
                            cs.onSurface.withOpacity(0.05),
                            cs.onSurface.withOpacity(0.45),
                          ],
                        ),
                      ),
                    ),
                    Positioned(
                      left: 10,
                      right: 10,
                      bottom: 10,
                      child: Text(
                        title,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: theme.textTheme.titleSmall?.copyWith(
                          color: cs.surface,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(12.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        _Badge(
                          icon: Icons.timer,
                          label: '${widget.recipe.estimatedTimes.totalMinutes} min',
                        ),
                        _Badge(
                          icon: Icons.signal_cellular_alt,
                          label: widget.recipe.difficulty,
                        ),
                        if (makesLeftovers)
                          _Badge(
                            icon: Icons.kitchen,
                            label: 'Leftovers',
                          ),
                        if (_usesLeftovers && !_checkingExpiring)
                          _Badge(
                            icon: Icons.replay,
                            label: 'Uses leftovers',
                          ),
                        if (_usesExpiringItems && !_checkingExpiring)
                          _Badge(
                            icon: Icons.eco,
                            label: 'Expiring items',
                          ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _formatWeeklyDayTitle(Menu menu) {
    if (menu.date != null) {
      try {
        final dateTime = DateTime.parse(menu.date!);
        final weekday = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][dateTime.weekday - 1];
        final month = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][dateTime.month - 1];
        return 'Day ${(menu.dayIndex ?? 0) + 1} - $weekday, $month ${dateTime.day}';
      } catch (e) {
        // Fall through to default
      }
    }
    return 'Day ${(menu.dayIndex ?? 0) + 1}';
  }
}

class _Badge extends StatelessWidget {
  final IconData icon;
  final String label;

  const _Badge({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: cs.surfaceVariant,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: cs.onSurfaceVariant),
          const SizedBox(width: 6),
          Text(
            label,
            style: theme.textTheme.labelMedium?.copyWith(color: cs.onSurfaceVariant),
          ),
        ],
      ),
    );
  }
}
