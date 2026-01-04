import 'package:flutter/foundation.dart';

import '../models/market_config.dart';
import '../services/api_client.dart';
import '../services/market_config_service.dart';

class MarketConfigState extends ChangeNotifier {
  MarketConfig? _config;
  bool _loading = false;
  String? _error;

  MarketConfig? get config => _config;
  bool get loading => _loading;
  String? get error => _error;

  bool isEnabled(String key, {bool defaultValue = false}) {
    return _config?.isEnabled(key, defaultValue: defaultValue) ?? defaultValue;
  }

  bool get isSuperAdmin => _config?.isSuperAdmin == true;
  String get region => _config?.region ?? 'US';

  Future<void> refresh(ApiClient apiClient) async {
    if (_loading) return;
    _loading = true;
    _error = null;
    notifyListeners();

    try {
      final service = MarketConfigService(apiClient);
      _config = await service.getMarketConfig();
    } catch (e) {
      _error = e.toString();
    } finally {
      _loading = false;
      notifyListeners();
    }
  }
}
