import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../models/planning.dart';

class ActiveCookSession {
  static const String prefsKey = 'savo.cook_session.active';

  final Recipe recipe;
  final int servings;
  final int? baseServings;
  final int currentStepIndex;
  final int stepSecondsRemaining;
  final int recipeTotalSeconds;
  final bool isStepTimerRunning;
  final bool isStepTimerPaused;
  final String? secondaryLanguageCode;
  final String? languageMode;
  final int savedAtMillis;

  const ActiveCookSession({
    required this.recipe,
    required this.servings,
    required this.baseServings,
    required this.currentStepIndex,
    required this.stepSecondsRemaining,
    required this.recipeTotalSeconds,
    required this.isStepTimerRunning,
    required this.isStepTimerPaused,
    required this.savedAtMillis,
    this.secondaryLanguageCode,
    this.languageMode,
  });

  Map<String, dynamic> toJson() {
    return {
      'version': 1,
      'saved_at_millis': savedAtMillis,
      'recipe': recipe.toJson(),
      'servings': servings,
      'base_servings': baseServings,
      'current_step_index': currentStepIndex,
      'step_seconds_remaining': stepSecondsRemaining,
      'recipe_total_seconds': recipeTotalSeconds,
      'is_step_timer_running': isStepTimerRunning,
      'is_step_timer_paused': isStepTimerPaused,
      if (secondaryLanguageCode != null)
        'secondary_language_code': secondaryLanguageCode,
      if (languageMode != null) 'language_mode': languageMode,
    };
  }

  factory ActiveCookSession.fromJson(Map<String, dynamic> json) {
    final recipeRaw = json['recipe'];
    if (recipeRaw is! Map) {
      throw const FormatException('Invalid cook session: missing recipe');
    }

    int readInt(dynamic v, {int fallback = 0}) {
      if (v is int) return v;
      if (v is num) return v.toInt();
      return fallback;
    }

    bool readBool(dynamic v, {bool fallback = false}) {
      if (v is bool) return v;
      return fallback;
    }

    final servings = readInt(json['servings'], fallback: 1);
    final currentStepIndex = readInt(json['current_step_index'], fallback: 0);

    return ActiveCookSession(
      recipe: Recipe.fromJson(Map<String, dynamic>.from(recipeRaw)),
      servings: servings > 0 ? servings : 1,
      baseServings: (json['base_servings'] is int)
          ? json['base_servings'] as int
          : (json['base_servings'] is num)
              ? (json['base_servings'] as num).toInt()
              : null,
      currentStepIndex: currentStepIndex >= 0 ? currentStepIndex : 0,
      stepSecondsRemaining: readInt(json['step_seconds_remaining']),
      recipeTotalSeconds: readInt(json['recipe_total_seconds']),
      isStepTimerRunning: readBool(json['is_step_timer_running']),
      isStepTimerPaused: readBool(json['is_step_timer_paused']),
      secondaryLanguageCode: (json['secondary_language_code'] is String)
          ? (json['secondary_language_code'] as String)
          : null,
      languageMode:
          (json['language_mode'] is String) ? (json['language_mode'] as String) : null,
      savedAtMillis: readInt(
        json['saved_at_millis'],
        fallback: DateTime.now().millisecondsSinceEpoch,
      ),
    );
  }

  static Future<ActiveCookSession?> load() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(prefsKey);
    if (raw == null || raw.trim().isEmpty) return null;

    try {
      final decoded = jsonDecode(raw);
      if (decoded is! Map) return null;
      return ActiveCookSession.fromJson(Map<String, dynamic>.from(decoded));
    } catch (_) {
      return null;
    }
  }

  Future<void> save() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(prefsKey, jsonEncode(toJson()));
  }

  static Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(prefsKey);
  }
}
