import 'package:flutter/material.dart';

import '../models/planning.dart';
import '../services/metrics_service.dart';
import 'cook_mode_screen.dart';
import 'plan_screen.dart';

class CookNowRecipeDetailScreen extends StatelessWidget {
  final Recipe recipe;

  const CookNowRecipeDetailScreen({super.key, required this.recipe});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;

    final title = recipe.getLocalizedName('en');

    return Scaffold(
      appBar: AppBar(
        title: Text(title),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _SectionTitle(text: 'Ingredients', color: cs.primary),
          const SizedBox(height: 8),
          if (recipe.ingredientsUsed.isEmpty)
            Text('No ingredients listed.', style: theme.textTheme.bodyMedium)
          else
            ...recipe.ingredientsUsed.map((i) {
              final name = i.canonicalName.trim().isNotEmpty ? i.canonicalName.trim() : 'Ingredient';
              final amount = i.amount;
              final unit = i.unit.trim();
              final qty = (amount == 0 && unit.isEmpty) ? '' : ' — ${amount.toString()}${unit.isNotEmpty ? ' $unit' : ''}';
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 6),
                child: Text('• $name$qty', style: theme.textTheme.bodyMedium),
              );
            }),
          const SizedBox(height: 16),

          _SectionTitle(text: 'Steps', color: cs.primary),
          const SizedBox(height: 8),
          if (recipe.steps.isEmpty)
            Text('No steps available.', style: theme.textTheme.bodyMedium)
          else
            ...recipe.steps.map((s) {
              final instruction = s.getLocalizedInstruction('en').trim();
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 10),
                child: Text(
                  '${s.step}. ${instruction.isNotEmpty ? instruction : 'Step'}',
                  style: theme.textTheme.bodyMedium,
                ),
              );
            }),
          const SizedBox(height: 16),

          _SectionTitle(text: 'Meta', color: cs.primary),
          const SizedBox(height: 8),
          _MetaRow(label: 'Cuisine', value: recipe.cuisine),
          _MetaRow(label: 'Difficulty', value: recipe.difficulty),
          _MetaRow(label: 'Time', value: '${recipe.estimatedTimes.totalMinutes} min'),
          _MetaRow(label: 'Method', value: recipe.cookingMethod),
          const SizedBox(height: 24),

          SizedBox(
            width: double.infinity,
            child: FilledButton(
              onPressed: () {
                fireAndForget(MetricsService.instance.recordWorkflowStep('CookNow', 'Cook'));
                Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => CookModeScreen(
                      recipe: recipe,
                      servings: 4,
                      baseServings: 4,
                      enablePostCookFeedback: true,
                    ),
                  ),
                );
              },
              child: const Text('Start cooking'),
            ),
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton(
              onPressed: () {
                Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => const PlanScreen()),
                );
              },
              child: const Text('Add to plan'),
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  final String text;
  final Color color;

  const _SectionTitle({required this.text, required this.color});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Text(
      text,
      style: theme.textTheme.titleMedium?.copyWith(
        fontWeight: FontWeight.w700,
        color: color,
      ),
    );
  }
}

class _MetaRow extends StatelessWidget {
  final String label;
  final String value;

  const _MetaRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final v = value.trim().isEmpty ? '—' : value.trim();
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 90,
            child: Text(label, style: theme.textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600)),
          ),
          Expanded(child: Text(v, style: theme.textTheme.bodyMedium)),
        ],
      ),
    );
  }
}
