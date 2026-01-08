import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

class WeeklyCookStreakService {
  static const String _eventsKey = 'savo.cook.events.timestampsMs';

  /// Records a cook event (best-effort, local only).
  Future<void> markCooked({int keepLastN = 200}) async {
    final ts = DateTime.now().millisecondsSinceEpoch;
    final prefs = await SharedPreferences.getInstance();

    final raw = prefs.getString(_eventsKey);
    final next = <int>[];

    if (raw != null && raw.isNotEmpty) {
      try {
        final decoded = json.decode(raw);
        if (decoded is List) {
          for (final v in decoded) {
            if (v is int) next.add(v);
            if (v is num) next.add(v.toInt());
          }
        }
      } catch (_) {
        // ignore
      }
    }

    next.add(ts);
    if (next.length > keepLastN) {
      next.removeRange(0, next.length - keepLastN);
    }

    await prefs.setString(_eventsKey, json.encode(next));
  }

  Future<int> cookedCountThisWeek() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_eventsKey);
    if (raw == null || raw.isEmpty) return 0;

    final now = DateTime.now();
    // Week starts Monday 00:00 local time.
    final weekday = now.weekday; // 1..7
    final weekStart = DateTime(now.year, now.month, now.day)
        .subtract(Duration(days: weekday - DateTime.monday));
    final cutoffMs = weekStart.millisecondsSinceEpoch;

    try {
      final decoded = json.decode(raw);
      if (decoded is! List) return 0;
      var count = 0;
      for (final v in decoded) {
        final ts = v is int ? v : (v is num ? v.toInt() : null);
        if (ts == null) continue;
        if (ts >= cutoffMs) count++;
      }
      return count;
    } catch (_) {
      return 0;
    }
  }
}
