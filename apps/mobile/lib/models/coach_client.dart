class CoachClient {
  final String id;
  final String name;
  final String notes;
  final List<String> favoriteCuisines;
  final String planningGoal; // balanced, low_cost, high_protein, etc.
  final String? measurementSystem;
  final String? outputLanguage;

  const CoachClient({
    required this.id,
    required this.name,
    this.notes = '',
    this.favoriteCuisines = const [],
    this.planningGoal = 'balanced',
    this.measurementSystem,
    this.outputLanguage,
  });

  factory CoachClient.fromJson(Map<String, dynamic> json) {
    final rawCuisines = json['favorite_cuisines'];
    final cuisines = <String>[];
    if (rawCuisines is List) {
      for (final c in rawCuisines) {
        final s = c.toString().trim();
        if (s.isNotEmpty) cuisines.add(s);
      }
    }

    return CoachClient(
      id: (json['id'] ?? '').toString(),
      name: (json['name'] ?? '').toString(),
      notes: (json['notes'] ?? '').toString(),
      favoriteCuisines: cuisines,
      planningGoal: (json['planning_goal'] ?? 'balanced').toString(),
      measurementSystem: (json['measurement_system'] ?? '').toString().trim().isEmpty
          ? null
          : (json['measurement_system'] ?? '').toString().trim(),
      outputLanguage: (json['output_language'] ?? '').toString().trim().isEmpty
          ? null
          : (json['output_language'] ?? '').toString().trim(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'notes': notes,
      'favorite_cuisines': favoriteCuisines,
      'planning_goal': planningGoal,
      'measurement_system': measurementSystem,
      'output_language': outputLanguage,
    };
  }
}
