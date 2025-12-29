class Cuisine {
  final String cuisineId;
  final String name;
  final String flag;
  final String description;
  final bool dailyEnabled;
  final bool partyEnabled;

  Cuisine({
    required this.cuisineId,
    required this.name,
    required this.flag,
    required this.description,
    required this.dailyEnabled,
    required this.partyEnabled,
  });

  factory Cuisine.fromJson(Map<String, dynamic> json) {
    return Cuisine(
      cuisineId: json['cuisine_id'] ?? '',
      name: json['name'] ?? '',
      flag: json['flag'] ?? '',
      description: json['description'] ?? '',
      dailyEnabled: json['daily_enabled'] ?? false,
      partyEnabled: json['party_enabled'] ?? false,
    );
  }
}

class HistoryRecipe {
  final String recipeId;
  final DateTime timestamp;
  final Map<String, dynamic> metadata;

  HistoryRecipe({
    required this.recipeId,
    required this.timestamp,
    this.metadata = const {},
  });

  factory HistoryRecipe.fromJson(Map<String, dynamic> json) {
    return HistoryRecipe(
      recipeId: json['recipe_id'] ?? '',
      timestamp: DateTime.parse(json['timestamp']),
      metadata: json['metadata'] ?? {},
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'recipe_id': recipeId,
      'timestamp': timestamp.toIso8601String(),
      'metadata': metadata,
    };
  }
}
