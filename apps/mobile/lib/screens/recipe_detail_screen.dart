import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_client.dart';
import '../models/planning.dart';
import 'cook_mode_screen.dart';

class RecipeDetailScreen extends StatelessWidget {
  final Recipe recipe;

  const RecipeDetailScreen({super.key, required this.recipe});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(recipe.getLocalizedName('en')),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Header with badges
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              Chip(
                avatar: const Icon(Icons.timer, size: 16),
                label: Text('${recipe.estimatedTimes.totalMinutes} min'),
              ),
              Chip(
                avatar: const Icon(Icons.signal_cellular_alt, size: 16),
                label: Text(recipe.difficulty),
              ),
              Chip(
                avatar: const Icon(Icons.restaurant, size: 16),
                label: Text(recipe.cuisine),
              ),
              Chip(
                avatar: const Icon(Icons.whatshot, size: 16),
                label: Text(recipe.cookingMethod),
              ),
            ],
          ),
          const SizedBox(height: 24),

          // Ingredients
          Text(
            'Ingredients',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 12),
          ...recipe.ingredientsUsed.map((ingredient) => Padding(
                padding: const EdgeInsets.symmetric(vertical: 4.0),
                child: Row(
                  children: [
                    const Icon(Icons.check_circle_outline, size: 20),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        '${ingredient.amount} ${ingredient.unit} ${ingredient.canonicalName}',
                      ),
                    ),
                  ],
                ),
              )),
          const SizedBox(height: 24),

          // Steps preview
          Text(
            'Steps',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 12),
          ...recipe.steps.take(3).map((step) => Card(
                margin: const EdgeInsets.only(bottom: 8),
                child: ListTile(
                  leading: CircleAvatar(
                    child: Text('${step.step}'),
                  ),
                  title: Text(
                    step.getLocalizedInstruction('en'),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  trailing: step.timeMinutes > 0
                      ? Chip(
                          label: Text('${step.timeMinutes}m'),
                          backgroundColor: Colors.blue[100],
                        )
                      : null,
                ),
              )),
          if (recipe.steps.length > 3)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8.0),
              child: Text(
                '+ ${recipe.steps.length - 3} more steps',
                style: Theme.of(context).textTheme.bodySmall,
                textAlign: TextAlign.center,
              ),
            ),
        ],
      ),
      bottomNavigationBar: Container(
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
        child: FilledButton.icon(
          onPressed: () {
            Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => CookModeScreen(recipe: recipe),
              ),
            );
          },
          icon: const Icon(Icons.play_arrow),
          label: const Text('Start Cook Mode'),
        ),
      ),
    );
  }
}
