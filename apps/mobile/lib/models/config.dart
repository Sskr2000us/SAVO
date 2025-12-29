class AppConfiguration {
  final HouseholdProfile householdProfile;
  final GlobalSettings globalSettings;
  final BehaviorSettings behaviorSettings;

  AppConfiguration({
    required this.householdProfile,
    required this.globalSettings,
    required this.behaviorSettings,
  });

  factory AppConfiguration.fromJson(Map<String, dynamic> json) {
    return AppConfiguration(
      householdProfile: HouseholdProfile.fromJson(json['household_profile'] ?? {}),
      globalSettings: GlobalSettings.fromJson(json['global_settings'] ?? {}),
      behaviorSettings: BehaviorSettings.fromJson(json['behavior_settings'] ?? {}),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'household_profile': householdProfile.toJson(),
      'global_settings': globalSettings.toJson(),
      'behavior_settings': behaviorSettings.toJson(),
    };
  }
}

class HouseholdProfile {
  final List<FamilyMember> members;
  final NutritionTargets nutritionTargets;

  HouseholdProfile({
    this.members = const [],
    required this.nutritionTargets,
  });

  factory HouseholdProfile.fromJson(Map<String, dynamic> json) {
    return HouseholdProfile(
      members: (json['members'] as List?)
              ?.map((m) => FamilyMember.fromJson(m))
              .toList() ??
          [],
      nutritionTargets: NutritionTargets.fromJson(json['nutrition_targets'] ?? {}),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'members': members.map((m) => m.toJson()).toList(),
      'nutrition_targets': nutritionTargets.toJson(),
    };
  }
}

class FamilyMember {
  final String memberId;
  final String name;
  final int age;
  final List<String> dietaryRestrictions;
  final List<String> allergens;

  FamilyMember({
    required this.memberId,
    required this.name,
    required this.age,
    this.dietaryRestrictions = const [],
    this.allergens = const [],
  });

  factory FamilyMember.fromJson(Map<String, dynamic> json) {
    return FamilyMember(
      memberId: json['member_id'] ?? '',
      name: json['name'] ?? '',
      age: json['age'] ?? 0,
      dietaryRestrictions: List<String>.from(json['dietary_restrictions'] ?? []),
      allergens: List<String>.from(json['allergens'] ?? []),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'member_id': memberId,
      'name': name,
      'age': age,
      'dietary_restrictions': dietaryRestrictions,
      'allergens': allergens,
    };
  }
}

class NutritionTargets {
  final int? dailyCaloriesPerPerson;
  final int? maxSodiumMg;

  NutritionTargets({
    this.dailyCaloriesPerPerson,
    this.maxSodiumMg,
  });

  factory NutritionTargets.fromJson(Map<String, dynamic> json) {
    return NutritionTargets(
      dailyCaloriesPerPerson: json['daily_calories_per_person'],
      maxSodiumMg: json['max_sodium_mg'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'daily_calories_per_person': dailyCaloriesPerPerson,
      'max_sodium_mg': maxSodiumMg,
    };
  }
}

class GlobalSettings {
  final String primaryLanguage;
  final String measurementSystem;
  final String timezone;
  final List<String> availableEquipment;

  GlobalSettings({
    this.primaryLanguage = 'en',
    this.measurementSystem = 'metric',
    this.timezone = 'UTC',
    this.availableEquipment = const ['stovetop', 'oven', 'microwave', 'refrigerator'],
  });

  factory GlobalSettings.fromJson(Map<String, dynamic> json) {
    return GlobalSettings(
      primaryLanguage: json['primary_language'] ?? 'en',
      measurementSystem: json['measurement_system'] ?? 'metric',
      timezone: json['timezone'] ?? 'UTC',
      availableEquipment: List<String>.from(json['available_equipment'] ?? []),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'primary_language': primaryLanguage,
      'measurement_system': measurementSystem,
      'timezone': timezone,
      'available_equipment': availableEquipment,
    };
  }
}

class BehaviorSettings {
  final int avoidRepetitionDays;
  final bool rotateCuisines;
  final bool rotateMethods;
  final bool preferExpiringIngredients;
  final int maxRepeatCuisinePerWeek;

  BehaviorSettings({
    this.avoidRepetitionDays = 7,
    this.rotateCuisines = true,
    this.rotateMethods = true,
    this.preferExpiringIngredients = true,
    this.maxRepeatCuisinePerWeek = 2,
  });

  factory BehaviorSettings.fromJson(Map<String, dynamic> json) {
    return BehaviorSettings(
      avoidRepetitionDays: json['avoid_repetition_days'] ?? 7,
      rotateCuisines: json['rotate_cuisines'] ?? true,
      rotateMethods: json['rotate_methods'] ?? true,
      preferExpiringIngredients: json['prefer_expiring_ingredients'] ?? true,
      maxRepeatCuisinePerWeek: json['max_repeat_cuisine_per_week'] ?? 2,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'avoid_repetition_days': avoidRepetitionDays,
      'rotate_cuisines': rotateCuisines,
      'rotate_methods': rotateMethods,
      'prefer_expiring_ingredients': preferExpiringIngredients,
      'max_repeat_cuisine_per_week': maxRepeatCuisinePerWeek,
    };
  }
}
