import 'dart:convert';
import 'dart:math';

import 'package:shared_preferences/shared_preferences.dart';

class CuisinePreferenceService {
  CuisinePreferenceService._();

  static final CuisinePreferenceService instance = CuisinePreferenceService._();

  static const String _learnedCountsKey = 'savo.cuisine.learned_counts.v1';
  static const String _manualOverridesKey = 'savo.cuisine.manual_overrides.v1';

  String _normalizeCuisine(String input) {
    final s = input.trim().toLowerCase();
    if (s.isEmpty) return '';
    return s.replaceAll(RegExp(r'\s+'), ' ');
  }

  String _displayCuisine(String normalized) {
    if (normalized.isEmpty) return normalized;
    // Title-case-ish for display (keeps multi-word cuisines readable).
    return normalized
        .split(' ')
        .map((w) => w.isEmpty ? w : '${w[0].toUpperCase()}${w.substring(1)}')
        .join(' ');
  }

  Future<Map<String, int>> _loadIntMap(String key) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(key);
      if (raw == null || raw.trim().isEmpty) return {};
      final decoded = jsonDecode(raw);
      if (decoded is! Map) return {};

      final out = <String, int>{};
      for (final e in decoded.entries) {
        final k = _normalizeCuisine(e.key.toString());
        if (k.isEmpty) continue;
        final v = e.value;
        if (v is int) {
          out[k] = v;
        } else if (v is num) {
          out[k] = v.toInt();
        } else {
          final parsed = int.tryParse(v.toString());
          if (parsed != null) out[k] = parsed;
        }
      }
      return out;
    } catch (_) {
      return {};
    }
  }

  Future<void> _saveIntMap(String key, Map<String, int> map) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(key, jsonEncode(map));
    } catch (_) {
      // Best-effort only.
    }
  }

  Future<Map<String, int>> getLearnedCuisineCounts() async {
    return _loadIntMap(_learnedCountsKey);
  }

  Future<Map<String, int>> getManualCuisineOverrides() async {
    // -1 = dislike, 0 = neutral, 1 = like
    final raw = await _loadIntMap(_manualOverridesKey);
    raw.removeWhere((_, v) => v < -1 || v > 1);
    return raw;
  }

  Future<void> setManualOverride({required String cuisine, required int value}) async {
    final k = _normalizeCuisine(cuisine);
    if (k.isEmpty) return;
    final v = value.clamp(-1, 1);

    final overrides = await getManualCuisineOverrides();
    if (v == 0) {
      overrides.remove(k);
    } else {
      overrides[k] = v;
    }
    await _saveIntMap(_manualOverridesKey, overrides);
  }

  Future<void> resetLearned() async {
    await _saveIntMap(_learnedCountsKey, {});
  }

  Future<void> recordSavedCuisine(String? cuisine) async {
    await _recordCuisine(cuisine, weight: 1);
  }

  Future<void> recordCookStartedCuisine(String? cuisine) async {
    await _recordCuisine(cuisine, weight: 2);
  }

  Future<void> _recordCuisine(String? cuisine, {required int weight}) async {
    if (cuisine == null) return;
    final k = _normalizeCuisine(cuisine);
    if (k.isEmpty) return;

    final learned = await getLearnedCuisineCounts();
    final prev = learned[k] ?? 0;
    // Cap to avoid unbounded growth.
    learned[k] = min(prev + max(1, weight), 1000000);
    await _saveIntMap(_learnedCountsKey, learned);
  }

  Future<List<MapEntry<String, int>>> getTopLearned({int maxItems = 8}) async {
    final learned = await getLearnedCuisineCounts();
    final entries = learned.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    return entries.take(maxItems).toList();
  }

  Future<Map<String, int>> getCombinedScores() async {
    // Higher is better.
    // manual override dominates learned count so users can correct the model.
    final learned = await getLearnedCuisineCounts();
    final overrides = await getManualCuisineOverrides();

    final keys = <String>{...learned.keys, ...overrides.keys};
    final out = <String, int>{};
    for (final k in keys) {
      final c = learned[k] ?? 0;
      final o = overrides[k] ?? 0;
      out[k] = c + (o * 1000);
    }
    return out;
  }

  Future<int> scoreForCuisine(String? cuisine) async {
    if (cuisine == null) return 0;
    final k = _normalizeCuisine(cuisine);
    if (k.isEmpty) return 0;
    final combined = await getCombinedScores();
    return combined[k] ?? 0;
  }

  // Synchronous helpers for UI that already has loaded maps.
  int scoreForCuisineFromMaps({required String cuisine, required Map<String, int> learned, required Map<String, int> overrides}) {
    final k = _normalizeCuisine(cuisine);
    if (k.isEmpty) return 0;
    return (learned[k] ?? 0) + ((overrides[k] ?? 0) * 1000);
  }

  String displayName(String cuisine) => _displayCuisine(_normalizeCuisine(cuisine));
}
