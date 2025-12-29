class MenuPlanResponse {
  final String status;
  final String selectedCuisine;
  final Map<String, dynamic>? planningWindow;
  final List<String> menuHeaders;
  final List<Menu> menus;
  final List<String> needsClarificationQuestions;
  final String? errorMessage;

  MenuPlanResponse({
    required this.status,
    required this.selectedCuisine,
    this.planningWindow,
    required this.menuHeaders,
    required this.menus,
    this.needsClarificationQuestions = const [],
    this.errorMessage,
  });

  factory MenuPlanResponse.fromJson(Map<String, dynamic> json) {
    return MenuPlanResponse(
      status: json['status'] ?? 'ok',
      selectedCuisine: json['selected_cuisine'] ?? '',
      planningWindow: json['planning_window'],
      menuHeaders: List<String>.from(json['menu_headers'] ?? []),
      menus: (json['menus'] as List?)
              ?.map((m) => Menu.fromJson(m))
              .toList() ??
          [],
      needsClarificationQuestions:
          List<String>.from(json['needs_clarification_questions'] ?? []),
      errorMessage: json['error_message'],
    );
  }
}

class Menu {
  final String menuType; // daily, party, weekly_day
  final int? dayIndex;
  final String? date;
  final Map<String, dynamic> servings;
  final List<Course> courses;

  Menu({
    required this.menuType,
    this.dayIndex,
    this.date,
    required this.servings,
    required this.courses,
  });

  factory Menu.fromJson(Map<String, dynamic> json) {
    return Menu(
      menuType: json['menu_type'] ?? 'daily',
      dayIndex: json['day_index'],
      date: json['date'],
      servings: json['servings'] ?? {},
      courses: (json['courses'] as List?)
              ?.map((c) => Course.fromJson(c))
              .toList() ??
          [],
    );
  }
}

class Course {
  final String courseHeader;
  final List<Recipe> recipeOptions;

  Course({
    required this.courseHeader,
    required this.recipeOptions,
  });

  factory Course.fromJson(Map<String, dynamic> json) {
    return Course(
      courseHeader: json['course_header'] ?? '',
      recipeOptions: (json['recipe_options'] as List?)
              ?.map((r) => Recipe.fromJson(r))
              .toList() ??
          [],
    );
  }
}

class Recipe {
  final String recipeId;
  final Map<String, String> recipeName;
  final String cuisine;
  final String difficulty;
  final EstimatedTimes estimatedTimes;
  final String cookingMethod;
  final List<RecipeIngredient> ingredientsUsed;
  final List<RecipeStep> steps;
  final Map<String, dynamic> nutritionPerServing;
  final Map<String, dynamic> leftoverForecast;

  Recipe({
    required this.recipeId,
    required this.recipeName,
    required this.cuisine,
    required this.difficulty,
    required this.estimatedTimes,
    required this.cookingMethod,
    required this.ingredientsUsed,
    required this.steps,
    required this.nutritionPerServing,
    required this.leftoverForecast,
  });

  factory Recipe.fromJson(Map<String, dynamic> json) {
    return Recipe(
      recipeId: json['recipe_id'] ?? '',
      recipeName: Map<String, String>.from(json['recipe_name'] ?? {'en': ''}),
      cuisine: json['cuisine'] ?? '',
      difficulty: json['difficulty'] ?? 'easy',
      estimatedTimes: EstimatedTimes.fromJson(json['estimated_times'] ?? {}),
      cookingMethod: json['cooking_method'] ?? '',
      ingredientsUsed: (json['ingredients_used'] as List?)
              ?.map((i) => RecipeIngredient.fromJson(i))
              .toList() ??
          [],
      steps: (json['steps'] as List?)
              ?.map((s) => RecipeStep.fromJson(s))
              .toList() ??
          [],
      nutritionPerServing: json['nutrition_per_serving'] ?? {},
      leftoverForecast: json['leftover_forecast'] ?? {},
    );
  }

  String getLocalizedName(String languageCode) {
    return recipeName[languageCode] ?? recipeName['en'] ?? recipeId;
  }
}

class EstimatedTimes {
  final int prepMinutes;
  final int cookMinutes;
  final int totalMinutes;

  EstimatedTimes({
    required this.prepMinutes,
    required this.cookMinutes,
    required this.totalMinutes,
  });

  factory EstimatedTimes.fromJson(Map<String, dynamic> json) {
    return EstimatedTimes(
      prepMinutes: json['prep_minutes'] ?? 0,
      cookMinutes: json['cook_minutes'] ?? 0,
      totalMinutes: json['total_minutes'] ?? 0,
    );
  }
}

class RecipeIngredient {
  final String inventoryId;
  final String canonicalName;
  final double amount;
  final String unit;

  RecipeIngredient({
    required this.inventoryId,
    required this.canonicalName,
    required this.amount,
    required this.unit,
  });

  factory RecipeIngredient.fromJson(Map<String, dynamic> json) {
    return RecipeIngredient(
      inventoryId: json['inventory_id'] ?? '',
      canonicalName: json['canonical_name'] ?? '',
      amount: (json['amount'] ?? 0).toDouble(),
      unit: json['unit'] ?? '',
    );
  }
}

class RecipeStep {
  final int step;
  final Map<String, String> instruction;
  final int timeMinutes;
  final List<String> tips;

  RecipeStep({
    required this.step,
    required this.instruction,
    required this.timeMinutes,
    this.tips = const [],
  });

  factory RecipeStep.fromJson(Map<String, dynamic> json) {
    return RecipeStep(
      step: json['step'] ?? 0,
      instruction: Map<String, String>.from(json['instruction'] ?? {'en': ''}),
      timeMinutes: json['time_minutes'] ?? 0,
      tips: List<String>.from(json['tips'] ?? []),
    );
  }

  String getLocalizedInstruction(String languageCode) {
    return instruction[languageCode] ?? instruction['en'] ?? '';
  }
}

class AgeGroupCounts {
  final int child0To12;
  final int teen13To17;
  final int adult18Plus;

  AgeGroupCounts({
    this.child0To12 = 0,
    this.teen13To17 = 0,
    this.adult18Plus = 0,
  });

  int get total => child0To12 + teen13To17 + adult18Plus;

  Map<String, dynamic> toJson() {
    return {
      'child_0_12': child0To12,
      'teen_13_17': teen13To17,
      'adult_18_plus': adult18Plus,
    };
  }
}

class PartySettings {
  final int guestCount;
  final AgeGroupCounts ageGroupCounts;

  PartySettings({
    required this.guestCount,
    required this.ageGroupCounts,
  });

  Map<String, dynamic> toJson() {
    return {
      'guest_count': guestCount,
      'age_group_counts': ageGroupCounts.toJson(),
    };
  }
}
