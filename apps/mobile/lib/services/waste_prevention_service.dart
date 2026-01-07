import 'dart:convert';
import 'package:http/http.dart' as http;

/// Waste Prevention Service
/// Handles spoilage prediction, expiry tracking, storage alerts, and waste analytics
class WastePreventionService {
  final String baseUrl;
  final http.Client client;

  WastePreventionService({
    required this.baseUrl,
    http.Client? client,
  }) : client = client ?? http.Client();

  // ============================================================================
  // Data Models
  // ============================================================================

  /// Spoilage prediction result
  class SpoilagePrediction {
    final String inventoryItemId;
    final String ingredientName;
    final String category;
    final int ageDays;
    final int? daysUntilExpiry;
    final String spoilageRisk;
    final double confidence;
    final String predictedSpoilageDate;
    final int daysUntilSpoilage;
    final StorageQuality storageQuality;
    final List<String> recommendations;
    final List<dynamic> warningSigns;
    final bool shouldUseSoon;

    SpoilagePrediction({
      required this.inventoryItemId,
      required this.ingredientName,
      required this.category,
      required this.ageDays,
      this.daysUntilExpiry,
      required this.spoilageRisk,
      required this.confidence,
      required this.predictedSpoilageDate,
      required this.daysUntilSpoilage,
      required this.storageQuality,
      required this.recommendations,
      required this.warningSigns,
      required this.shouldUseSoon,
    });

    factory SpoilagePrediction.fromJson(Map<String, dynamic> json) {
      return SpoilagePrediction(
        inventoryItemId: json['inventory_item_id'],
        ingredientName: json['ingredient_name'],
        category: json['category'],
        ageDays: json['age_days'],
        daysUntilExpiry: json['days_until_expiry'],
        spoilageRisk: json['spoilage_risk'],
        confidence: json['confidence'].toDouble(),
        predictedSpoilageDate: json['predicted_spoilage_date'],
        daysUntilSpoilage: json['days_until_spoilage'],
        storageQuality: StorageQuality.fromJson(json['storage_quality']),
        recommendations: List<String>.from(json['recommendations']),
        warningSigns: json['warning_signs'] ?? [],
        shouldUseSoon: json['should_use_soon'],
      );
    }

    /// Get risk emoji
    String get riskEmoji {
      switch (spoilageRisk) {
        case 'critical':
          return '🚨';
        case 'high':
          return '⚠️';
        case 'medium':
          return '📅';
        case 'low':
          return '✅';
        default:
          return '❓';
      }
    }

    /// Get urgency message
    String get urgencyMessage {
      if (daysUntilSpoilage <= 0) return 'Spoiled - discard immediately';
      if (daysUntilSpoilage == 1) return 'Use today';
      if (daysUntilSpoilage <= 3) return 'Use within $daysUntilSpoilage days';
      return 'Use within $daysUntilSpoilage days';
    }
  }

  /// Storage quality assessment
  class StorageQuality {
    final double score;
    final String rating;
    final List<String> issues;

    StorageQuality({
      required this.score,
      required this.rating,
      required this.issues,
    });

    factory StorageQuality.fromJson(Map<String, dynamic> json) {
      return StorageQuality(
        score: json['score'].toDouble(),
        rating: json['rating'],
        issues: List<String>.from(json['issues'] ?? []),
      );
    }

    /// Get rating emoji
    String get ratingEmoji {
      switch (rating) {
        case 'excellent':
          return '🌟';
        case 'good':
          return '✅';
        case 'fair':
          return '😐';
        case 'poor':
          return '⚠️';
        case 'critical':
          return '🚨';
        default:
          return '❓';
      }
    }

    /// Has issues?
    bool get hasIssues => issues.isNotEmpty;
  }

  /// Expiring items response
  class ExpiringItems {
    final List<ExpiringItem> critical;
    final List<ExpiringItem> urgent;
    final List<ExpiringItem> warning;
    final List<ExpiringItem> caution;
    final int totalExpiring;
    final ExpiringSummary summary;
    final List<String> recommendations;

    ExpiringItems({
      required this.critical,
      required this.urgent,
      required this.warning,
      required this.caution,
      required this.totalExpiring,
      required this.summary,
      required this.recommendations,
    });

    factory ExpiringItems.fromJson(Map<String, dynamic> json) {
      return ExpiringItems(
        critical: (json['critical'] as List)
            .map((i) => ExpiringItem.fromJson(i))
            .toList(),
        urgent:
            (json['urgent'] as List).map((i) => ExpiringItem.fromJson(i)).toList(),
        warning: (json['warning'] as List)
            .map((i) => ExpiringItem.fromJson(i))
            .toList(),
        caution: (json['caution'] as List)
            .map((i) => ExpiringItem.fromJson(i))
            .toList(),
        totalExpiring: json['total_expiring'],
        summary: ExpiringSummary.fromJson(json['summary']),
        recommendations: List<String>.from(json['recommendations']),
      );
    }

    /// Get all items as flat list
    List<ExpiringItem> get allItems {
      return [...critical, ...urgent, ...warning, ...caution];
    }

    /// Get items by urgency level
    List<ExpiringItem> getByUrgency(String urgency) {
      switch (urgency) {
        case 'critical':
          return critical;
        case 'urgent':
          return urgent;
        case 'warning':
          return warning;
        case 'caution':
          return caution;
        default:
          return [];
      }
    }
  }

  /// Individual expiring item
  class ExpiringItem {
    final String id;
    final String ingredientId;
    final String ingredientName;
    final String category;
    final double quantity;
    final String unit;
    final String expiryDate;
    final int daysUntilExpiry;
    final String urgency;
    final Map<String, dynamic>? multiLanguageNames;
    final SpoilagePrediction? spoilagePrediction;

    ExpiringItem({
      required this.id,
      required this.ingredientId,
      required this.ingredientName,
      required this.category,
      required this.quantity,
      required this.unit,
      required this.expiryDate,
      required this.daysUntilExpiry,
      required this.urgency,
      this.multiLanguageNames,
      this.spoilagePrediction,
    });

    factory ExpiringItem.fromJson(Map<String, dynamic> json) {
      return ExpiringItem(
        id: json['id'],
        ingredientId: json['ingredient_id'],
        ingredientName: json['ingredient_name'],
        category: json['category'],
        quantity: json['quantity'].toDouble(),
        unit: json['unit'],
        expiryDate: json['expiry_date'],
        daysUntilExpiry: json['days_until_expiry'],
        urgency: json['urgency'],
        multiLanguageNames: json['multi_language_names'],
        spoilagePrediction: json['spoilage_prediction'] != null
            ? SpoilagePrediction.fromJson(json['spoilage_prediction'])
            : null,
      );
    }

    /// Get urgency emoji
    String get urgencyEmoji {
      switch (urgency) {
        case 'critical':
          return '🚨';
        case 'urgent':
          return '⚠️';
        case 'warning':
          return '📅';
        case 'caution':
          return '💡';
        default:
          return '❓';
      }
    }

    /// Is expired?
    bool get isExpired => daysUntilExpiry <= 0;
  }

  /// Expiring items summary
  class ExpiringSummary {
    final int criticalCount;
    final int urgentCount;
    final int warningCount;
    final int cautionCount;

    ExpiringSummary({
      required this.criticalCount,
      required this.urgentCount,
      required this.warningCount,
      required this.cautionCount,
    });

    factory ExpiringSummary.fromJson(Map<String, dynamic> json) {
      return ExpiringSummary(
        criticalCount: json['critical_count'],
        urgentCount: json['urgent_count'],
        warningCount: json['warning_count'],
        cautionCount: json['caution_count'],
      );
    }

    /// Total count
    int get totalCount =>
        criticalCount + urgentCount + warningCount + cautionCount;

    /// Has urgent items?
    bool get hasUrgentItems => criticalCount > 0 || urgentCount > 0;
  }

  /// Storage alerts response
  class StorageAlerts {
    final List<StorageAlert> alerts;
    final int totalAlerts;
    final int highSeverityCount;
    final List<String> summary;

    StorageAlerts({
      required this.alerts,
      required this.totalAlerts,
      required this.highSeverityCount,
      required this.summary,
    });

    factory StorageAlerts.fromJson(Map<String, dynamic> json) {
      return StorageAlerts(
        alerts: (json['alerts'] as List)
            .map((a) => StorageAlert.fromJson(a))
            .toList(),
        totalAlerts: json['total_alerts'],
        highSeverityCount: json['high_severity_count'],
        summary: List<String>.from(json['summary']),
      );
    }

    /// Has high severity alerts?
    bool get hasHighSeverity => highSeverityCount > 0;

    /// Get alerts by severity
    List<StorageAlert> getBySeverity(String severity) {
      return alerts.where((a) => a.severity == severity).toList();
    }
  }

  /// Individual storage alert
  class StorageAlert {
    final String inventoryItemId;
    final String ingredientId;
    final String ingredientName;
    final String category;
    final String? currentStorage;
    final String severity;
    final List<String> alertMessages;
    final String recommendedStorage;
    final Map<String, dynamic> idealConditions;

    StorageAlert({
      required this.inventoryItemId,
      required this.ingredientId,
      required this.ingredientName,
      required this.category,
      this.currentStorage,
      required this.severity,
      required this.alertMessages,
      required this.recommendedStorage,
      required this.idealConditions,
    });

    factory StorageAlert.fromJson(Map<String, dynamic> json) {
      return StorageAlert(
        inventoryItemId: json['inventory_item_id'],
        ingredientId: json['ingredient_id'],
        ingredientName: json['ingredient_name'],
        category: json['category'],
        currentStorage: json['current_storage'],
        severity: json['severity'],
        alertMessages: List<String>.from(json['alerts']),
        recommendedStorage: json['recommended_storage'],
        idealConditions: json['ideal_conditions'],
      );
    }

    /// Get severity emoji
    String get severityEmoji {
      switch (severity) {
        case 'high':
          return '🚨';
        case 'medium':
          return '⚠️';
        case 'low':
          return '💡';
        default:
          return 'ℹ️';
      }
    }
  }

  /// Recipe suggestions response
  class RecipeSuggestions {
    final List<RecipeSuggestion> suggestions;
    final int totalSuggestions;
    final ExpiringSummary expiringSummary;
    final List<String> recommendations;

    RecipeSuggestions({
      required this.suggestions,
      required this.totalSuggestions,
      required this.expiringSummary,
      required this.recommendations,
    });

    factory RecipeSuggestions.fromJson(Map<String, dynamic> json) {
      return RecipeSuggestions(
        suggestions: (json['suggestions'] as List)
            .map((s) => RecipeSuggestion.fromJson(s))
            .toList(),
        totalSuggestions: json['total_suggestions'],
        expiringSummary: ExpiringSummary.fromJson(json['expiring_summary']),
        recommendations: List<String>.from(json['recommendations']),
      );
    }

    /// Get high urgency suggestions
    List<RecipeSuggestion> get highUrgency {
      return suggestions.where((s) => s.urgency == 'high').toList();
    }
  }

  /// Individual recipe suggestion
  class RecipeSuggestion {
    final String ingredientId;
    final String ingredientName;
    final String category;
    final List<String> suggestedUses;
    final String urgency;

    RecipeSuggestion({
      required this.ingredientId,
      required this.ingredientName,
      required this.category,
      required this.suggestedUses,
      required this.urgency,
    });

    factory RecipeSuggestion.fromJson(Map<String, dynamic> json) {
      return RecipeSuggestion(
        ingredientId: json['ingredient_id'],
        ingredientName: json['ingredient_name'],
        category: json['category'],
        suggestedUses: List<String>.from(json['suggested_uses'] ?? []),
        urgency: json['urgency'],
      );
    }

    /// Get urgency emoji
    String get urgencyEmoji {
      return urgency == 'high' ? '🚨' : '📅';
    }
  }

  /// Waste analytics response
  class WasteAnalytics {
    final int periodDays;
    final int totalItems;
    final WasteStatistics wasteStatistics;
    final Map<String, int> categoryBreakdown;
    final List<String> insights;
    final List<String> recommendations;
    final HealthScore healthScore;

    WasteAnalytics({
      required this.periodDays,
      required this.totalItems,
      required this.wasteStatistics,
      required this.categoryBreakdown,
      required this.insights,
      required this.recommendations,
      required this.healthScore,
    });

    factory WasteAnalytics.fromJson(Map<String, dynamic> json) {
      return WasteAnalytics(
        periodDays: json['period_days'],
        totalItems: json['total_items'],
        wasteStatistics: WasteStatistics.fromJson(json['waste_statistics']),
        categoryBreakdown:
            Map<String, int>.from(json['category_breakdown'] ?? {}),
        insights: List<String>.from(json['insights']),
        recommendations: List<String>.from(json['recommendations']),
        healthScore: HealthScore.fromJson(json['health_score']),
      );
    }

    /// Get top waste category
    String? get topWasteCategory {
      if (categoryBreakdown.isEmpty) return null;
      return categoryBreakdown.entries
          .reduce((a, b) => a.value > b.value ? a : b)
          .key;
    }
  }

  /// Waste statistics
  class WasteStatistics {
    final int expiredCount;
    final int expiringSoonCount;
    final int highRiskCount;
    final int mediumRiskCount;
    final int lowRiskCount;
    final double wasteRiskPercentage;

    WasteStatistics({
      required this.expiredCount,
      required this.expiringSoonCount,
      required this.highRiskCount,
      required this.mediumRiskCount,
      required this.lowRiskCount,
      required this.wasteRiskPercentage,
    });

    factory WasteStatistics.fromJson(Map<String, dynamic> json) {
      return WasteStatistics(
        expiredCount: json['expired_count'],
        expiringSoonCount: json['expiring_soon_count'],
        highRiskCount: json['high_risk_count'],
        mediumRiskCount: json['medium_risk_count'],
        lowRiskCount: json['low_risk_count'],
        wasteRiskPercentage: json['waste_risk_percentage'].toDouble(),
      );
    }

    /// Total at-risk items
    int get totalAtRisk => expiredCount + expiringSoonCount + highRiskCount;

    /// Has critical issues?
    bool get hasCriticalIssues => expiredCount > 0 || expiringSoonCount > 0;
  }

  /// Health score
  class HealthScore {
    final int score;
    final String rating;
    final String message;

    HealthScore({
      required this.score,
      required this.rating,
      required this.message,
    });

    factory HealthScore.fromJson(Map<String, dynamic> json) {
      return HealthScore(
        score: json['score'],
        rating: json['rating'],
        message: json['message'],
      );
    }

    /// Get rating emoji
    String get ratingEmoji {
      switch (rating) {
        case 'excellent':
          return '🌟';
        case 'good':
          return '👍';
        case 'fair':
          return '📈';
        case 'poor':
          return '⚠️';
        case 'critical':
          return '🚨';
        default:
          return '❓';
      }
    }

    /// Get color indicator
    String get colorIndicator {
      if (score >= 90) return 'green';
      if (score >= 75) return 'lightgreen';
      if (score >= 60) return 'yellow';
      if (score >= 40) return 'orange';
      return 'red';
    }
  }

  // ============================================================================
  // API Methods
  // ============================================================================

  /// Predict spoilage for inventory item
  Future<SpoilagePrediction> predictSpoilage(
    String inventoryItemId, {
    double? currentTemperature,
    int? currentHumidity,
  }) async {
    try {
      final response = await client.post(
        Uri.parse('$baseUrl/api/waste/predict-spoilage'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'inventory_item_id': inventoryItemId,
          if (currentTemperature != null)
            'current_temperature': currentTemperature,
          if (currentHumidity != null) 'current_humidity': currentHumidity,
        }),
      );

      if (response.statusCode == 200) {
        return SpoilagePrediction.fromJson(json.decode(response.body));
      } else {
        throw Exception('Failed to predict spoilage: ${response.body}');
      }
    } catch (e) {
      print('Error predicting spoilage: $e');
      rethrow;
    }
  }

  /// Get expiring items
  Future<ExpiringItems> getExpiringItems(
    String userId, {
    int daysThreshold = 7,
    bool includePredictions = true,
  }) async {
    try {
      final response = await client.post(
        Uri.parse('$baseUrl/api/waste/expiring-items'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'user_id': userId,
          'days_threshold': daysThreshold,
          'include_predictions': includePredictions,
        }),
      );

      if (response.statusCode == 200) {
        return ExpiringItems.fromJson(json.decode(response.body));
      } else {
        throw Exception('Failed to get expiring items: ${response.body}');
      }
    } catch (e) {
      print('Error getting expiring items: $e');
      rethrow;
    }
  }

  /// Get storage alerts
  Future<StorageAlerts> getStorageAlerts(String userId) async {
    try {
      final response = await client.post(
        Uri.parse('$baseUrl/api/waste/storage-alerts'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'user_id': userId}),
      );

      if (response.statusCode == 200) {
        return StorageAlerts.fromJson(json.decode(response.body));
      } else {
        throw Exception('Failed to get storage alerts: ${response.body}');
      }
    } catch (e) {
      print('Error getting storage alerts: $e');
      rethrow;
    }
  }

  /// Get recipe suggestions for expiring items
  Future<RecipeSuggestions> getRecipeSuggestions(
    String userId, {
    int daysThreshold = 5,
  }) async {
    try {
      final response = await client.post(
        Uri.parse('$baseUrl/api/waste/recipe-suggestions'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'user_id': userId,
          'days_threshold': daysThreshold,
        }),
      );

      if (response.statusCode == 200) {
        return RecipeSuggestions.fromJson(json.decode(response.body));
      } else {
        throw Exception('Failed to get recipe suggestions: ${response.body}');
      }
    } catch (e) {
      print('Error getting recipe suggestions: $e');
      rethrow;
    }
  }

  /// Get waste analytics
  Future<WasteAnalytics> getWasteAnalytics(
    String userId, {
    int daysLookback = 30,
  }) async {
    try {
      final response = await client.post(
        Uri.parse('$baseUrl/api/waste/analytics'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'user_id': userId,
          'days_lookback': daysLookback,
        }),
      );

      if (response.statusCode == 200) {
        return WasteAnalytics.fromJson(json.decode(response.body));
      } else {
        throw Exception('Failed to get waste analytics: ${response.body}');
      }
    } catch (e) {
      print('Error getting waste analytics: $e');
      rethrow;
    }
  }

  /// Get storage requirements
  Future<Map<String, dynamic>> getStorageRequirements() async {
    try {
      final response =
          await client.get(Uri.parse('$baseUrl/api/waste/storage-requirements'));

      if (response.statusCode == 200) {
        return json.decode(response.body);
      } else {
        throw Exception('Failed to get storage requirements: ${response.body}');
      }
    } catch (e) {
      print('Error getting storage requirements: $e');
      rethrow;
    }
  }

  /// Get risk levels by category
  Future<Map<String, dynamic>> getRiskLevels() async {
    try {
      final response =
          await client.get(Uri.parse('$baseUrl/api/waste/risk-levels'));

      if (response.statusCode == 200) {
        return json.decode(response.body);
      } else {
        throw Exception('Failed to get risk levels: ${response.body}');
      }
    } catch (e) {
      print('Error getting risk levels: $e');
      rethrow;
    }
  }

  /// Health check
  Future<bool> checkHealth() async {
    try {
      final response = await client.get(Uri.parse('$baseUrl/api/waste/health'));
      return response.statusCode == 200;
    } catch (e) {
      print('Error checking health: $e');
      return false;
    }
  }

  /// Dispose resources
  void dispose() {
    client.close();
  }
}
