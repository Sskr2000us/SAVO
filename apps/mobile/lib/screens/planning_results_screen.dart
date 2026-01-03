import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_client.dart';
import '../models/planning.dart';
import '../models/cuisine.dart';
import 'recipe_detail_screen.dart';

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
              child: FilledButton(
                onPressed: () {
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
                color: Colors.grey[300],
                child: Center(
                  child: Icon(
                    Icons.restaurant,
                    size: 48,
                    color: Colors.grey[600],
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
