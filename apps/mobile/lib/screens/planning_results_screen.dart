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

  @override
  Widget build(BuildContext context) {
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
                      onPressed: _buildingShoppingList ? null : _createShoppingListFromPlan,
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
  bool _checkingExpiring = true;

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
        for (final ingredient in widget.recipe.ingredientsUsed) {
          final item = inventory.firstWhere(
            (inv) => inv['inventory_id'] == ingredient.inventoryId,
            orElse: () => {},
          );
          
          if (item.isNotEmpty) {
            final freshness = item['freshness_days_remaining'];
            if (freshness != null && freshness < 3) {
              setState(() {
                _usesExpiringItems = true;
                _checkingExpiring = false;
              });
              return;
            }
          }
        }
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
              Container(
                height: 100,
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [
                      const Color(0xFFFF6B6B).withOpacity(0.7),
                      const Color(0xFFFFB347).withOpacity(0.7),
                    ],
                  ),
                ),
                child: Center(
                  child: Icon(
                    Icons.restaurant_menu,
                    size: 56,
                    color: Colors.white.withOpacity(0.9),
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(12.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            widget.recipe.getLocalizedName('en'),
                            style: Theme.of(context).textTheme.titleSmall,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        if (_usesExpiringItems && !_checkingExpiring)
                          Padding(
                            padding: const EdgeInsets.only(left: 4.0),
                            child: Tooltip(
                              message: 'Uses expiring ingredients',
                              child: Icon(
                                Icons.eco,
                                size: 16,
                                color: Colors.orange[700],
                              ),
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        const Icon(Icons.timer, size: 14, color: Colors.white70),
                        const SizedBox(width: 4),
                        Text(
                          '${widget.recipe.estimatedTimes.totalMinutes} min',
                          style: const TextStyle(
                            fontSize: 12,
                            color: Colors.white70,
                          ),
                        ),
                        const SizedBox(width: 12),
                        const Icon(Icons.signal_cellular_alt, size: 14, color: Colors.white70),
                        const SizedBox(width: 4),
                        Text(
                          widget.recipe.difficulty,
                          style: const TextStyle(
                            fontSize: 12,
                            color: Colors.white70,
                          ),
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
