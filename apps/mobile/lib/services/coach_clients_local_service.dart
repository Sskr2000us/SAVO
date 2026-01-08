import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../models/coach_client.dart';

class CoachClientsLocalService {
  CoachClientsLocalService._();
  static final CoachClientsLocalService instance = CoachClientsLocalService._();

  static const _prefsKey = 'savo.coach.clients.v1';

  Future<List<CoachClient>> list() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_prefsKey);
    if (raw == null || raw.trim().isEmpty) return const [];

    try {
      final decoded = json.decode(raw);
      if (decoded is! List) return const [];
      return decoded
          .whereType<Map>()
          .map((m) => CoachClient.fromJson(m.cast<String, dynamic>()))
          .where((c) => c.id.trim().isNotEmpty && c.name.trim().isNotEmpty)
          .toList();
    } catch (_) {
      return const [];
    }
  }

  Future<void> saveAll(List<CoachClient> clients) async {
    final prefs = await SharedPreferences.getInstance();
    final payload = clients.map((c) => c.toJson()).toList();
    await prefs.setString(_prefsKey, json.encode(payload));
  }
}
