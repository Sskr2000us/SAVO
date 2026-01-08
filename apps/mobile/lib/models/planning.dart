import 'youtube.dart';

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
  final String? imageUrl;
  final String cuisine;
  final String difficulty;
  final EstimatedTimes estimatedTimes;
  final String cookingMethod;
  final List<RecipeIngredient> ingredientsUsed;
  final List<NewIngredientOptional> newIngredientsOptional;
  final List<RecipeStep> steps;
  final Map<String, dynamic> nutritionPerServing;
  final List<Map<String, String>>? healthBenefits;
  final Map<String, dynamic> leftoverForecast;
  final List<String> chefTips;
  final Map<String, dynamic>? culturalContext;
  final Map<String, dynamic>? dietaryInformation;
  final List<RankedVideo> youtubeReferences;

  Recipe({
    required this.recipeId,
    required this.recipeName,
    this.imageUrl,
    required this.cuisine,
    required this.difficulty,
    required this.estimatedTimes,
    required this.cookingMethod,
    required this.ingredientsUsed,
    this.newIngredientsOptional = const [],
    required this.steps,
    required this.nutritionPerServing,
    this.healthBenefits,
    required this.leftoverForecast,
    this.chefTips = const [],
    this.culturalContext,
    this.dietaryInformation,
    this.youtubeReferences = const [],
  });

  factory Recipe.fromJson(Map<String, dynamic> json) {
    final refs = <RankedVideo>[];
    final rawRefs = json['youtube_references'];
    if (rawRefs is List) {
      for (final v in rawRefs) {
        if (v is Map) {
          final m = Map<String, dynamic>.from(v);
          refs.add(
            RankedVideo(
              videoId: (m['video_id'] ?? '').toString(),
              title: (m['title'] ?? '').toString(),
              channel: (m['channel'] ?? '').toString(),
              trustScore: (m['trust_score'] ?? 0.0).toDouble(),
              matchScore: 0.0,
              reasons: const [],
            ),
          );
        }
      }
      // Drop invalid rows with no video id.
      refs.removeWhere((r) => r.videoId.trim().isEmpty);
    }

    final tips = <String>[];
    final rawTips = json['chef_tips'];
    if (rawTips is List) {
      for (final t in rawTips) {
        final s = t.toString().trim();
        if (s.isNotEmpty) tips.add(s);
      }
    }

    Map<String, dynamic>? cultural;
    final rawCultural = json['cultural_context'];
    if (rawCultural is Map) {
      cultural = Map<String, dynamic>.from(rawCultural);
    }

    Map<String, dynamic>? dietary;
    final rawDietary = json['dietary_information'];
    if (rawDietary is Map) {
      dietary = Map<String, dynamic>.from(rawDietary);
    }

    return Recipe(
      recipeId: json['recipe_id'] ?? '',
      recipeName: Map<String, String>.from(json['recipe_name'] ?? {'en': ''}),
      imageUrl: (json['image_url'] ?? '').toString().trim().isEmpty
          ? null
          : (json['image_url'] ?? '').toString().trim(),
      cuisine: json['cuisine'] ?? '',
      difficulty: json['difficulty'] ?? 'easy',
      estimatedTimes: EstimatedTimes.fromJson(json['estimated_times'] ?? {}),
      cookingMethod: json['cooking_method'] ?? '',
      ingredientsUsed: (json['ingredients_used'] as List?)
              ?.map((i) => RecipeIngredient.fromJson(i))
              .toList() ??
          [],
      newIngredientsOptional: (json['new_ingredients_optional'] as List?)
              ?.whereType<Map>()
              .map((i) => NewIngredientOptional.fromJson(Map<String, dynamic>.from(i)))
              .toList() ??
          const [],
      steps: (json['steps'] as List?)
              ?.map((s) => RecipeStep.fromJson(s))
              .toList() ??
          [],
      nutritionPerServing: json['nutrition_per_serving'] ?? {},
      healthBenefits: (json['health_benefits'] as List?)
              ?.map((b) => Map<String, String>.from(b as Map))
              .toList(),
      leftoverForecast: json['leftover_forecast'] ?? {},
      chefTips: tips,
      culturalContext: cultural,
      dietaryInformation: dietary,
      youtubeReferences: refs,
    );
  }

  String getLocalizedName(String languageCode) {
    if (recipeName.isEmpty) return recipeId;

    final en = recipeName['en'];
    if (en != null && en.trim().isNotEmpty) return en;

    final preferred = recipeName[languageCode];
    if (preferred != null && preferred.trim().isNotEmpty) return preferred;

    return recipeName.values.firstWhere(
      (v) => v.trim().isNotEmpty,
      orElse: () => recipeId,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'recipe_id': recipeId,
      'recipe_name': recipeName,
      if (imageUrl != null) 'image_url': imageUrl,
      'cuisine': cuisine,
      'difficulty': difficulty,
      'estimated_times': estimatedTimes.toJson(),
      'cooking_method': cookingMethod,
      'ingredients_used': ingredientsUsed.map((i) => i.toJson()).toList(),
      'new_ingredients_optional': newIngredientsOptional.map((i) => i.toJson()).toList(),
      'steps': steps.map((s) => s.toJson()).toList(),
      'nutrition_per_serving': nutritionPerServing,
      if (healthBenefits != null) 'health_benefits': healthBenefits,
      'leftover_forecast': leftoverForecast,
      if (chefTips.isNotEmpty) 'chef_tips': chefTips,
      if (culturalContext != null) 'cultural_context': culturalContext,
      if (dietaryInformation != null) 'dietary_information': dietaryInformation,
      'youtube_references': youtubeReferences.map((r) => r.toJson()).toList(),
    };
  }
}

class NewIngredientOptional {
  final String canonicalName;
  final double amount;
  final String unit;
  final String? amountDisplay;
  final String? notes;
  final String reason;

  NewIngredientOptional({
    required this.canonicalName,
    required this.amount,
    required this.unit,
    this.amountDisplay,
    this.notes,
    required this.reason,
  });

  factory NewIngredientOptional.fromJson(Map<String, dynamic> json) {
    return NewIngredientOptional(
      canonicalName: (json['canonical_name'] ?? '').toString(),
      amount: (json['amount'] ?? 0).toDouble(),
      unit: (json['unit'] ?? '').toString(),
      amountDisplay: (json['amount_display'] ?? '').toString().trim().isEmpty
          ? null
          : (json['amount_display'] ?? '').toString().trim(),
      notes: (json['notes'] ?? '').toString().trim().isEmpty ? null : (json['notes'] ?? '').toString().trim(),
      reason: (json['reason'] ?? '').toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'canonical_name': canonicalName,
      'amount': amount,
      'unit': unit,
      if (amountDisplay != null) 'amount_display': amountDisplay,
      if (notes != null) 'notes': notes,
      'reason': reason,
    };
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

  Map<String, dynamic> toJson() {
    return {
      'prep_minutes': prepMinutes,
      'cook_minutes': cookMinutes,
      'total_minutes': totalMinutes,
    };
  }
}

class RecipeIngredient {
  final String inventoryId;
  final String canonicalName;
  final double amount;
  final String unit;
  final String? amountDisplay;
  final String? notes;

  RecipeIngredient({
    required this.inventoryId,
    required this.canonicalName,
    required this.amount,
    required this.unit,
    this.amountDisplay,
    this.notes,
  });

  factory RecipeIngredient.fromJson(Map<String, dynamic> json) {
    return RecipeIngredient(
      inventoryId: json['inventory_id'] ?? '',
      canonicalName: json['canonical_name'] ?? '',
      amount: (json['amount'] ?? 0).toDouble(),
      unit: json['unit'] ?? '',
      amountDisplay: (json['amount_display'] ?? '').toString().trim().isEmpty
          ? null
          : (json['amount_display'] ?? '').toString().trim(),
      notes: (json['notes'] ?? '').toString().trim().isEmpty ? null : (json['notes'] ?? '').toString().trim(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'inventory_id': inventoryId,
      'canonical_name': canonicalName,
      'amount': amount,
      'unit': unit,
      if (amountDisplay != null) 'amount_display': amountDisplay,
      if (notes != null) 'notes': notes,
    };
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

  Map<String, dynamic> toJson() {
    return {
      'step': step,
      'instruction': instruction,
      'time_minutes': timeMinutes,
      'tips': tips,
    };
  }

  String getLocalizedInstruction(String languageCode) {
    if (instruction.isEmpty) return '';

    final en = instruction['en'];
    if (en != null && en.trim().isNotEmpty) return en;

    final preferred = instruction[languageCode];
    if (preferred != null && preferred.trim().isNotEmpty) return preferred;

    return instruction.values.firstWhere(
      (v) => v.trim().isNotEmpty,
      orElse: () => '',
    );
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
