import 'package:supabase_flutter/supabase_flutter.dart';

import 'api_client.dart';

class WasteAnalyticsSummary {
  final int score;
  final String rating;
  final String message;
  final int expiredCount;
  final int expiringSoonCount;
  final double wasteRiskPercentage;

  WasteAnalyticsSummary({
    required this.score,
    required this.rating,
    required this.message,
    required this.expiredCount,
    required this.expiringSoonCount,
    required this.wasteRiskPercentage,
  });

  factory WasteAnalyticsSummary.fromJson(Map<String, dynamic> json) {
    final stats = (json['waste_statistics'] is Map)
        ? Map<String, dynamic>.from(json['waste_statistics'] as Map)
        : const <String, dynamic>{};

    final hs = (json['health_score'] is Map)
        ? Map<String, dynamic>.from(json['health_score'] as Map)
        : const <String, dynamic>{};

    return WasteAnalyticsSummary(
      score: (hs['score'] ?? 0) is int ? (hs['score'] as int) : (hs['score'] as num?)?.toInt() ?? 0,
      rating: (hs['rating'] ?? '').toString(),
      message: (hs['message'] ?? '').toString(),
      expiredCount: (stats['expired_count'] as num?)?.toInt() ?? 0,
      expiringSoonCount: (stats['expiring_soon_count'] as num?)?.toInt() ?? 0,
      wasteRiskPercentage: (stats['waste_risk_percentage'] as num?)?.toDouble() ?? 0.0,
    );
  }
}

class WasteAnalyticsService {
  Future<WasteAnalyticsSummary?> fetchMonthly(ApiClient apiClient) async {
    final userId = Supabase.instance.client.auth.currentUser?.id;
    if (userId == null || userId.trim().isEmpty) return null;

    final res = await apiClient.post(
      '/api/waste/analytics',
      {
        'user_id': userId,
        'days_lookback': 30,
      },
    );

    return WasteAnalyticsSummary.fromJson(res);
  }
}
