import 'dart:math';

import '../models/inventory.dart';
import '../models/planning.dart';

class TonightSuggestionResult {
  final List<Recipe> rankedRecipes;
  final List<InventoryItem> expiringSoon;

  TonightSuggestionResult({
    required this.rankedRecipes,
    required this.expiringSoon,
  });
}

class TonightSuggestionService {
  static const int _expiringSoonDays = 3;

  TonightSuggestionResult rankRecipes({
    required List<Recipe> recipes,
    required List<InventoryItem> inventory,
  }) {
    final expiring = inventory
        .where((i) => i.isCurrent)
        .where((i) => i.freshnessDaysRemaining != null)
        .where((i) => i.freshnessDaysRemaining! <= _expiringSoonDays)
        .toList();

    expiring.sort((a, b) {
      final ad = a.freshnessDaysRemaining ?? 9999;
      final bd = b.freshnessDaysRemaining ?? 9999;
      return ad.compareTo(bd);
    });

    if (recipes.isEmpty) {
      return TonightSuggestionResult(rankedRecipes: const [], expiringSoon: expiring);
    }

    // No expiry signal → keep current order (already randomized upstream).
    if (expiring.isEmpty) {
      return TonightSuggestionResult(rankedRecipes: recipes, expiringSoon: const []);
    }

    final expiringByKey = <String, int>{};
    for (final item in expiring) {
      final key = _normalizeKey(item.canonicalName);
      if (key.isEmpty) continue;
      final d = item.freshnessDaysRemaining ?? 9999;
      expiringByKey[key] = min(expiringByKey[key] ?? 9999, d);

      final displayKey = _normalizeKey(item.displayLabel);
      if (displayKey.isNotEmpty) {
        expiringByKey[displayKey] = min(expiringByKey[displayKey] ?? 9999, d);
      }
    }

    final rng = Random(DateTime.now().microsecondsSinceEpoch);

    final scored = recipes.map((r) {
      var score = 0.0;
      for (final ing in r.ingredientsUsed) {
        final key = _normalizeKey(ing.canonicalName);
        final days = expiringByKey[key];
        if (days == null) continue;
        // Urgency weight: 0 days → 4, 1 day → 3, 2 days → 2, 3 days → 1.
        final weight = max(1, 4 - max(0, days));
        score += weight.toDouble();
      }

      // Gentle tiebreaker so swaps feel different.
      final jitter = rng.nextDouble() * 0.01;
      return _ScoredRecipe(recipe: r, score: score + jitter);
    }).toList();

    scored.sort((a, b) => b.score.compareTo(a.score));

    return TonightSuggestionResult(
      rankedRecipes: scored.map((s) => s.recipe).toList(),
      expiringSoon: expiring,
    );
  }

  String _normalizeKey(String raw) {
    return raw.replaceAll('_', ' ').trim().toLowerCase();
  }
}

class _ScoredRecipe {
  final Recipe recipe;
  final double score;

  _ScoredRecipe({required this.recipe, required this.score});
}
