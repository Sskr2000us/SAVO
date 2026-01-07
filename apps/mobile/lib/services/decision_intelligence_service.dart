import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:flutter/material.dart';

/// Decision Intelligence Service
/// Provides auto-action recommendations with confidence scoring
class DecisionIntelligenceService {
  final _supabase = Supabase.instance.client;

  /// Evaluate a single ingredient and get recommendation
  Future<DecisionResult> evaluateIngredient(
    String ingredientId, {
    Map<String, dynamic>? context,
  }) async {
    try {
      final response = await _supabase.functions.invoke(
        'decision-evaluate-ingredient',
        body: {
          'ingredient_id': ingredientId,
          'context': context ?? {},
        },
      );

      if (response.data == null) {
        throw Exception('No data received from server');
      }

      return DecisionResult.fromJson(response.data as Map<String, dynamic>);
    } catch (e) {
      throw Exception('Failed to evaluate ingredient: $e');
    }
  }

  /// Evaluate entire inventory and get prioritized recommendations
  Future<List<DecisionResult>> evaluateInventory({int limit = 10}) async {
    try {
      final response = await _supabase.functions.invoke(
        'decision-evaluate-inventory',
        body: {'limit': limit},
      );

      if (response.data == null) {
        return [];
      }

      final List<dynamic> data = response.data as List<dynamic>;
      return data
          .map((item) => DecisionResult.fromJson(item as Map<String, dynamic>))
          .toList();
    } catch (e) {
      throw Exception('Failed to evaluate inventory: $e');
    }
  }

  /// Get recent recommended actions with optional filtering
  Future<List<Map<String, dynamic>>> getRecommendedActions({
    List<String>? actionTypes,
    int limit = 10,
  }) async {
    try {
      final params = StringBuffer();
      if (actionTypes != null && actionTypes.isNotEmpty) {
        params.write('action_types=${actionTypes.join(",")}');
      }
      params.write('${params.isEmpty ? "" : "&"}limit=$limit');

      final response = await _supabase.functions.invoke(
        'decision-recommended-actions?$params',
        method: HttpMethod.get,
      );

      if (response.data == null) {
        return [];
      }

      return List<Map<String, dynamic>>.from(response.data as List);
    } catch (e) {
      throw Exception('Failed to get recommended actions: $e');
    }
  }

  /// Provide feedback on a recommended action
  Future<void> provideFeedback({
    required String actionId,
    required String userResponse,
    String? userFinalAction,
    String? feedbackNotes,
  }) async {
    try {
      await _supabase.functions.invoke(
        'decision-apply-action',
        body: {
          'action_id': actionId,
          'user_response': userResponse,
          if (userFinalAction != null) 'user_final_action': userFinalAction,
          if (feedbackNotes != null) 'feedback_notes': feedbackNotes,
        },
      );
    } catch (e) {
      throw Exception('Failed to provide feedback: $e');
    }
  }

  /// Get decision statistics
  Future<Map<String, dynamic>> getStats({int days = 30}) async {
    try {
      final response = await _supabase.functions.invoke(
        'decision-stats?days=$days',
        method: HttpMethod.get,
      );

      if (response.data == null) {
        return {};
      }

      return response.data as Map<String, dynamic>;
    } catch (e) {
      throw Exception('Failed to get stats: $e');
    }
  }
}

/// Decision result model
class DecisionResult {
  final String ingredientId;
  final String ingredientName;
  final String recommendedAction;
  final double confidence;
  final String reason;
  final bool autoApply;
  final double urgencyScore;
  final String? actionId;

  DecisionResult({
    required this.ingredientId,
    required this.ingredientName,
    required this.recommendedAction,
    required this.confidence,
    required this.reason,
    required this.autoApply,
    required this.urgencyScore,
    this.actionId,
  });

  factory DecisionResult.fromJson(Map<String, dynamic> json) {
    return DecisionResult(
      ingredientId: json['ingredient_id'] as String,
      ingredientName: json['ingredient_name'] as String,
      recommendedAction: json['recommended_action'] as String,
      confidence: (json['confidence'] as num).toDouble(),
      reason: json['reason'] as String,
      autoApply: json['auto_apply'] as bool? ?? false,
      urgencyScore: (json['urgency_score'] as num?)?.toDouble() ?? 0.0,
      actionId: json['action_id'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'ingredient_id': ingredientId,
      'ingredient_name': ingredientName,
      'recommended_action': recommendedAction,
      'confidence': confidence,
      'reason': reason,
      'auto_apply': autoApply,
      'urgency_score': urgencyScore,
      if (actionId != null) 'action_id': actionId,
    };
  }

  /// Get emoji for action type
  String get actionEmoji {
    switch (recommendedAction) {
      case 'cook_now':
        return '🍳';
      case 'store_better':
        return '📦';
      case 'substitute':
        return '🔄';
      case 'buy':
        return '🛒';
      case 'do_not_buy':
        return '❌';
      case 'discard':
        return '🗑️';
      case 'monitor':
      default:
        return '👁️';
    }
  }

  /// Get human-readable action label
  String get actionLabel {
    switch (recommendedAction) {
      case 'cook_now':
        return 'Cook Now';
      case 'store_better':
        return 'Store Better';
      case 'substitute':
        return 'Substitute';
      case 'buy':
        return 'Buy';
      case 'do_not_buy':
        return 'Don\'t Buy';
      case 'discard':
        return 'Discard';
      case 'monitor':
      default:
        return 'Monitor';
    }
  }

  /// Get color for confidence level
  Color get confidenceColor {
    if (confidence >= 0.85) return Colors.green;
    if (confidence >= 0.60) return Colors.orange;
    return Colors.red;
  }

  /// Get confidence label
  String get confidenceLabel {
    if (confidence >= 0.85) return 'High';
    if (confidence >= 0.60) return 'Medium';
    return 'Low';
  }

  /// Get urgency label
  String get urgencyLabel {
    if (urgencyScore >= 70) return 'Critical';
    if (urgencyScore >= 50) return 'High';
    if (urgencyScore >= 30) return 'Medium';
    return 'Low';
  }

  /// Get urgency color
  Color get urgencyColor {
    if (urgencyScore >= 70) return Colors.red;
    if (urgencyScore >= 50) return Colors.orange;
    if (urgencyScore >= 30) return Colors.yellow[700]!;
    return Colors.green;
  }
}

/// User response types
enum UserResponse {
  accepted,
  rejected,
  ignored,
  modified;

  String get value => name;
}
