import 'dart:async';
import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

class MetricsService {
  MetricsService._();

  static final MetricsService instance = MetricsService._();

  final Map<String, int> _activeTimersMs = {};

  static String _timerActiveKey(String name) => 'savo.metrics.timer.$name.activeStartMs';
  static String _timerDurationsKey(String name) => 'savo.metrics.timer.$name.durationsMs';
  static String _eventTimestampsKey(String name) => 'savo.metrics.event.$name.timestampsMs';
  static String _workflowStepsKey(String workflow) => 'savo.metrics.workflow.$workflow.steps';

  Future<void> startTimer(String name) async {
    final startMs = DateTime.now().millisecondsSinceEpoch;
    _activeTimersMs[name] = startMs;

    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_timerActiveKey(name), startMs);
  }

  Future<int?> endTimer(String name, {int keepLastN = 50}) async {
    final endMs = DateTime.now().millisecondsSinceEpoch;

    int? startMs = _activeTimersMs.remove(name);
    final prefs = await SharedPreferences.getInstance();

    startMs ??= prefs.getInt(_timerActiveKey(name));
    if (startMs == null) return null;

    final durationMs = (endMs - startMs).clamp(0, 1000 * 60 * 60 * 6);

    final raw = prefs.getString(_timerDurationsKey(name));
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

    next.add(durationMs);
    if (next.length > keepLastN) {
      next.removeRange(0, next.length - keepLastN);
    }

    await prefs.remove(_timerActiveKey(name));
    await prefs.setString(_timerDurationsKey(name), json.encode(next));

    return durationMs;
  }

  Future<void> recordEvent(String name, {int keepLastN = 200}) async {
    final ts = DateTime.now().millisecondsSinceEpoch;
    final prefs = await SharedPreferences.getInstance();

    final raw = prefs.getString(_eventTimestampsKey(name));
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

    await prefs.setString(_eventTimestampsKey(name), json.encode(next));
  }

  Future<int> countEventsLastDays(String name, int days) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_eventTimestampsKey(name));
    if (raw == null || raw.isEmpty) return 0;

    final cutoffMs = DateTime.now().subtract(Duration(days: days)).millisecondsSinceEpoch;

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

  Future<void> recordWorkflowStep(String workflow, String step, {int keepLastN = 100}) async {
    final ts = DateTime.now().toIso8601String();
    final prefs = await SharedPreferences.getInstance();

    final raw = prefs.getString(_workflowStepsKey(workflow));
    final next = <Map<String, String>>[];
    if (raw != null && raw.isNotEmpty) {
      try {
        final decoded = json.decode(raw);
        if (decoded is List) {
          for (final v in decoded) {
            if (v is Map) {
              final m = Map<String, dynamic>.from(v);
              next.add({
                'step': (m['step'] ?? '').toString(),
                'ts': (m['ts'] ?? '').toString(),
              });
            }
          }
        }
      } catch (_) {
        // ignore
      }
    }

    next.add({'step': step, 'ts': ts});
    if (next.length > keepLastN) {
      next.removeRange(0, next.length - keepLastN);
    }

    await prefs.setString(_workflowStepsKey(workflow), json.encode(next));
  }
}

void fireAndForget(Future<void> future) {
  unawaited(future);
}
