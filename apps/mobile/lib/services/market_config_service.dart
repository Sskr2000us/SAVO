import '../services/api_client.dart';
import '../models/market_config.dart';

class MarketConfigService {
  final ApiClient apiClient;

  MarketConfigService(this.apiClient);

  Future<MarketConfig> getMarketConfig() async {
    final resp = await apiClient.get('/market/config');
    if (resp is Map<String, dynamic>) {
      return MarketConfig.fromJson(resp);
    }
    if (resp is Map) {
      return MarketConfig.fromJson(Map<String, dynamic>.from(resp));
    }
    throw Exception('Invalid market config response');
  }
}
