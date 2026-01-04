import 'package:flutter/material.dart';

import '../models/planning.dart';
import '../services/metrics_service.dart';
import 'cook_now_recipe_detail_screen.dart';

class RecipeOptionsScreen extends StatefulWidget {
  final List<Recipe> recipes;

  const RecipeOptionsScreen({super.key, required this.recipes});

  @override
  State<RecipeOptionsScreen> createState() => _RecipeOptionsScreenState();
}

class _RecipeOptionsScreenState extends State<RecipeOptionsScreen> {
  bool _timerStarted = false;

  @override
  void initState() {
    super.initState();
    _timerStarted = true;
    fireAndForget(MetricsService.instance.startTimer('open_to_recipe_decision'));
    fireAndForget(MetricsService.instance.recordEvent('cook_now_opened'));
  }

  @override
  void dispose() {
    if (_timerStarted) {
      fireAndForget(MetricsService.instance.endTimer('open_to_recipe_decision'));
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;
    final options = widget.recipes.take(5).toList();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Recipe options'),
      ),
      body: options.isEmpty
          ? Center(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Text(
                  'No recipe options right now. Try again after updating your pantry.',
                  style: theme.textTheme.bodyMedium,
                  textAlign: TextAlign.center,
                ),
              ),
            )
          : ListView.separated(
              padding: const EdgeInsets.all(16),
              itemCount: options.length,
              separatorBuilder: (_, __) => const SizedBox(height: 12),
              itemBuilder: (context, index) {
                final recipe = options[index];
                final title = recipe.getLocalizedName('en');
                final why = _whyItWorks(recipe);
                final imageUrl = _imageUrl(recipe);

                return Card(
                  clipBehavior: Clip.antiAlias,
                  child: InkWell(
                    onTap: () {
                      if (_timerStarted) {
                        _timerStarted = false;
                        fireAndForget(MetricsService.instance.endTimer('open_to_recipe_decision'));
                      }
                      fireAndForget(MetricsService.instance.recordEvent('recipe_decision_made'));
                      Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => CookNowRecipeDetailScreen(recipe: recipe),
                        ),
                      );
                    },
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        SizedBox(
                          height: 150,
                          child: Stack(
                            fit: StackFit.expand,
                            children: [
                              if (imageUrl != null)
                                Image.network(
                                  imageUrl,
                                  fit: BoxFit.cover,
                                  errorBuilder: (_, __, ___) => Container(
                                    color: cs.surfaceVariant,
                                    child: Icon(Icons.restaurant, color: cs.onSurfaceVariant, size: 40),
                                  ),
                                )
                              else
                                Container(
                                  color: cs.surfaceVariant,
                                  child: Icon(Icons.restaurant, color: cs.onSurfaceVariant, size: 40),
                                ),
                              Container(
                                decoration: BoxDecoration(
                                  gradient: LinearGradient(
                                    begin: Alignment.topCenter,
                                    end: Alignment.bottomCenter,
                                    colors: [
                                      cs.onSurface.withOpacity(0.05),
                                      cs.onSurface.withOpacity(0.55),
                                    ],
                                  ),
                                ),
                              ),
                              Positioned(
                                left: 12,
                                right: 12,
                                bottom: 12,
                                child: Text(
                                  title,
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                  style: theme.textTheme.titleMedium?.copyWith(
                                    color: cs.surface,
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                        Padding(
                          padding: const EdgeInsets.all(12),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                why,
                                style: theme.textTheme.bodyMedium,
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                              ),
                              const SizedBox(height: 10),
                              Wrap(
                                spacing: 8,
                                runSpacing: 8,
                                children: [
                                  _Badge(icon: Icons.signal_cellular_alt, label: recipe.difficulty),
                                  _Badge(icon: Icons.timer, label: '${recipe.estimatedTimes.totalMinutes} min'),
                                ],
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
    );
  }

  String _whyItWorks(Recipe recipe) {
    final ingredients = recipe.ingredientsUsed
        .map((i) => i.canonicalName.trim())
        .where((s) => s.isNotEmpty)
        .toList();

    if (ingredients.isEmpty) {
      return 'Based on what\'s in your pantry';
    }

    final top = ingredients.take(3).toList();
    final suffix = ingredients.length > 3 ? '…' : '';
    return 'Uses: ${top.join(', ')}$suffix';
  }

  String? _imageUrl(Recipe recipe) {
    final refs = recipe.youtubeReferences;
    if (refs.isNotEmpty) {
      final url = refs.first.thumbnailUrl;
      if (url.trim().isNotEmpty) return url;
    }

    final name = recipe.getLocalizedName('en').trim();
    if (name.isEmpty) return null;
    final encoded = Uri.encodeComponent(name);
    return 'https://source.unsplash.com/featured/?food,$encoded';
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
        color: cs.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: cs.onSurfaceVariant),
          const SizedBox(width: 6),
          Text(label, style: theme.textTheme.labelMedium),
        ],
      ),
    );
  }
}
