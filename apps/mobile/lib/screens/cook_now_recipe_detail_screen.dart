import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/planning.dart';
import '../services/api_client.dart';
import '../services/metrics_service.dart';
import '../services/scanning_service.dart';
import 'cook_mode_screen.dart';
import 'plan_screen.dart';

class CookNowRecipeDetailScreen extends StatefulWidget {
  final Recipe recipe;

  const CookNowRecipeDetailScreen({super.key, required this.recipe});

  @override
  State<CookNowRecipeDetailScreen> createState() => _CookNowRecipeDetailScreenState();
}

class _CookNowRecipeDetailScreenState extends State<CookNowRecipeDetailScreen> {
  bool _checking = true;
  Map<String, dynamic>? _sufficiency;

  @override
  void initState() {
    super.initState();
    _check();
  }

  List<Map<String, dynamic>> _recipeIngredientsPayload() {
    return widget.recipe.ingredientsUsed
        .where((i) => i.canonicalName.trim().isNotEmpty)
        .map(
          (i) => {
            'name': i.canonicalName.trim(),
            'quantity': i.amount,
            'unit': i.unit,
          },
        )
        .toList();
  }

  Future<void> _check() async {
    setState(() {
      _checking = true;
      _sufficiency = null;
    });

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final scanningService = ScanningService();

      final result = await scanningService.checkSufficiency(
        recipeId: widget.recipe.recipeId,
        servings: 4,
        apiClient: apiClient,
        recipeIngredients: _recipeIngredientsPayload(),
        recipeServings: 4,
      );

      if (!mounted) return;
      setState(() {
        _checking = false;
        _sufficiency = result;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _checking = false;
        _sufficiency = null;
      });
    }
  }

  Set<String> _missingNameSet() {
    final result = _sufficiency;
    if (result == null || result['success'] != true) return <String>{};
    final raw = result['missing'];
    if (raw is! List) return <String>{};
    return raw
        .whereType<Map>()
        .map((m) => Map<String, dynamic>.from(m))
        .map((m) => (m['name'] ?? m['ingredient'] ?? '').toString().trim().toLowerCase())
        .where((s) => s.isNotEmpty)
        .toSet();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;

    final recipe = widget.recipe;
    final title = recipe.getLocalizedName('en');

    final missingSet = _missingNameSet();

    final missing = <Map<String, dynamic>>[];
    final rawMissing = _sufficiency != null ? _sufficiency!['missing'] : null;
    if (rawMissing is List) {
      for (final row in rawMissing) {
        if (row is Map) missing.add(Map<String, dynamic>.from(row));
      }
    }

    final have = recipe.ingredientsUsed.where((i) {
      final name = i.canonicalName.trim().toLowerCase();
      if (name.isEmpty) return true;
      return !missingSet.contains(name);
    }).toList();

    return Scaffold(
      appBar: AppBar(
        title: Text(title),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _SectionTitle(text: 'Ingredients', color: cs.primary),
          const SizedBox(height: 8),
          if (_checking)
            Text('Checking what you have…', style: theme.textTheme.bodyMedium)
          else if (recipe.ingredientsUsed.isEmpty)
            Text('No ingredients listed.', style: theme.textTheme.bodyMedium)
          else if (_sufficiency != null && _sufficiency!['success'] == true) ...[
            if (missing.isNotEmpty) ...[
              Text('Missing', style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700)),
              const SizedBox(height: 6),
              ...missing.map((m) {
                final name = (m['name'] ?? m['ingredient'] ?? 'Ingredient').toString().trim();
                final qty = m['quantity'];
                final unit = (m['unit'] ?? '').toString().trim();
                final qtyText = (qty is num && qty != 0)
                    ? (qty % 1 == 0 ? qty.toInt().toString() : qty.toStringAsFixed(1))
                    : (qty?.toString().trim().isNotEmpty == true ? qty.toString().trim() : '');
                final suffix = qtyText.isEmpty ? '' : ' — $qtyText${unit.isNotEmpty ? ' $unit' : ''}';
                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Text('• $name$suffix', style: theme.textTheme.bodyMedium?.copyWith(color: cs.error)),
                );
              }),
              const SizedBox(height: 12),
            ],
            if (have.isNotEmpty) ...[
              Text('You have', style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700)),
              const SizedBox(height: 6),
              ...have.map((i) {
                final name = i.canonicalName.trim().isNotEmpty ? i.canonicalName.trim() : 'Ingredient';
                final amount = i.amount;
                final unit = i.unit.trim();
                final suffix = (amount == 0 && unit.isEmpty)
                    ? ''
                    : ' — ${amount.toString()}${unit.isNotEmpty ? ' $unit' : ''}';
                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Text('• $name$suffix', style: theme.textTheme.bodyMedium),
                );
              }),
            ],
          ] else ...[
            ...recipe.ingredientsUsed.map((i) {
              final name = i.canonicalName.trim().isNotEmpty ? i.canonicalName.trim() : 'Ingredient';
              final amount = i.amount;
              final unit = i.unit.trim();
              final suffix = (amount == 0 && unit.isEmpty)
                  ? ''
                  : ' — ${amount.toString()}${unit.isNotEmpty ? ' $unit' : ''}';
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 6),
                child: Text('• $name$suffix', style: theme.textTheme.bodyMedium),
              );
            }),
            const SizedBox(height: 8),
            Text(
              'Pantry check unavailable.',
              style: theme.textTheme.bodySmall?.copyWith(color: cs.onSurfaceVariant),
            ),
          ],
          const SizedBox(height: 16),

          // Steps collapsed by default
          _SectionTitle(text: 'Steps', color: cs.primary),
          const SizedBox(height: 8),
          if (recipe.steps.isEmpty)
            Text('No steps available.', style: theme.textTheme.bodyMedium)
          else
            Card(
              clipBehavior: Clip.antiAlias,
              child: ExpansionTile(
                title: const Text('Show steps'),
                childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                children: recipe.steps.map((s) {
                  final instruction = s.getLocalizedInstruction('en').trim();
                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 10),
                    child: Text(
                      '${s.step}. ${instruction.isNotEmpty ? instruction : 'Step'}',
                      style: theme.textTheme.bodyMedium,
                    ),
                  );
                }).toList(),
              ),
            ),
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
