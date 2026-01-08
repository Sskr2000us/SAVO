import 'package:shared_preferences/shared_preferences.dart';

class EntitlementsService {
  EntitlementsService._();

  static final EntitlementsService instance = EntitlementsService._();

  // ---- Product settings (defaults) ----
  // These are intentionally centralized so we can later source them from remote config.
  static const int freeDailyScanLimit = 20;
  static const int freeDailySuggestionSessionsLimit = 3;
  static const int freeDailyRegenerateLimit = 1;
  static const int freeDailySwapLimit = 1;

  static const String _isProKey = 'savo.entitlements.is_pro';

  static const String _scanDateKey = 'savo.usage.scan.date';
  static const String _scanCountKey = 'savo.usage.scan.count';

  static const String _suggestionDateKey = 'savo.usage.suggestions.date';
  static const String _suggestionCountKey = 'savo.usage.suggestions.count';

  static const String _regenDateKey = 'savo.usage.regenerate.date';
  static const String _regenCountKey = 'savo.usage.regenerate.count';

  static const String _swapDateKey = 'savo.usage.swap.date';
  static const String _swapCountKey = 'savo.usage.swap.count';

  String _todayKey() {
    final now = DateTime.now();
    final y = now.year.toString().padLeft(4, '0');
    final m = now.month.toString().padLeft(2, '0');
    final d = now.day.toString().padLeft(2, '0');
    return '$y-$m-$d';
  }

  Future<bool> isPro() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      return prefs.getBool(_isProKey) ?? false;
    } catch (_) {
      return false;
    }
  }

  Future<void> setPro(bool value) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_isProKey, value);
    } catch (_) {
      // Best-effort.
    }
  }

  Future<_GateState> _getGateState({required String dateKey, required String countKey}) async {
    final prefs = await SharedPreferences.getInstance();
    final today = _todayKey();

    final storedDate = prefs.getString(dateKey);
    if (storedDate != today) {
      await prefs.setString(dateKey, today);
      await prefs.setInt(countKey, 0);
      return _GateState(today: today, count: 0);
    }

    final count = prefs.getInt(countKey) ?? 0;
    return _GateState(today: today, count: count);
  }

  Future<GateResult> _consume({
    required String dateKey,
    required String countKey,
    required int limit,
    required int amount,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    final state = await _getGateState(dateKey: dateKey, countKey: countKey);

    final next = state.count + amount;
    if (state.count >= limit) {
      return GateResult(allowed: false, used: state.count, limit: limit);
    }

    final clamped = next > limit ? limit : next;
    await prefs.setInt(countKey, clamped);
    return GateResult(allowed: true, used: clamped, limit: limit);
  }

  Future<GateResult> tryConsumeScan({int amount = 1}) async {
    if (await isPro()) return GateResult(allowed: true, used: 0, limit: 0);
    return _consume(
      dateKey: _scanDateKey,
      countKey: _scanCountKey,
      limit: freeDailyScanLimit,
      amount: amount,
    );
  }

  Future<GateResult> tryConsumeSuggestionSession({int amount = 1}) async {
    if (await isPro()) return GateResult(allowed: true, used: 0, limit: 0);
    return _consume(
      dateKey: _suggestionDateKey,
      countKey: _suggestionCountKey,
      limit: freeDailySuggestionSessionsLimit,
      amount: amount,
    );
  }

  Future<GateResult> tryConsumeRegenerate({int amount = 1}) async {
    if (await isPro()) return GateResult(allowed: true, used: 0, limit: 0);
    return _consume(
      dateKey: _regenDateKey,
      countKey: _regenCountKey,
      limit: freeDailyRegenerateLimit,
      amount: amount,
    );
  }

  Future<GateResult> tryConsumeSwap({int amount = 1}) async {
    if (await isPro()) return GateResult(allowed: true, used: 0, limit: 0);
    return _consume(
      dateKey: _swapDateKey,
      countKey: _swapCountKey,
      limit: freeDailySwapLimit,
      amount: amount,
    );
  }
}

class _GateState {
  final String today;
  final int count;

  const _GateState({required this.today, required this.count});
}

class GateResult {
  final bool allowed;
  final int used;
  final int limit;

  const GateResult({required this.allowed, required this.used, required this.limit});

  int get remaining {
    if (limit <= 0) return 999999;
    final r = limit - used;
    return r < 0 ? 0 : r;
  }
}
