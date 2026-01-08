import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import 'scanning_service.dart';

class PendingScanSyncService {
  PendingScanSyncService._();

  static final PendingScanSyncService instance = PendingScanSyncService._();

  static const String _prefsKey = 'savo.pending_scan_actions.v1';

  bool _flushing = false;

  Future<void> enqueueConfirmSingle({
    required String ingredientName,
    required double quantity,
    required String unit,
    required String scanType,
  }) async {
    final name = ingredientName.trim();
    if (name.isEmpty) return;

    final prefs = await SharedPreferences.getInstance();
    final items = await _readQueue(prefs);
    items.add({
      'type': 'confirm_single',
      'ingredient_name': name,
      'quantity': quantity,
      'unit': unit,
      'scan_type': scanType,
      'created_at': DateTime.now().toIso8601String(),
    });
    await prefs.setString(_prefsKey, jsonEncode(items));
  }

  Future<void> enqueueConfirmIngredients({
    required String scanId,
    required List<Map<String, dynamic>> confirmations,
  }) async {
    final sid = scanId.trim();
    if (sid.isEmpty) return;
    if (confirmations.isEmpty) return;

    final prefs = await SharedPreferences.getInstance();
    final items = await _readQueue(prefs);
    items.add({
      'type': 'confirm_ingredients',
      'scan_id': sid,
      'confirmations': confirmations,
      'created_at': DateTime.now().toIso8601String(),
    });
    await prefs.setString(_prefsKey, jsonEncode(items));
  }

  Future<int> flush() async {
    if (_flushing) return 0;
    _flushing = true;

    try {
      final prefs = await SharedPreferences.getInstance();
      final items = await _readQueue(prefs);
      if (items.isEmpty) return 0;

      final scanningService = ScanningService();
      final remaining = <Map<String, dynamic>>[];
      int flushed = 0;

      for (final item in items) {
        final type = item['type']?.toString();
        if (type == 'confirm_single') {
          final name = item['ingredient_name']?.toString() ?? '';
          final qtyRaw = item['quantity'];
          final qty = (qtyRaw is num) ? qtyRaw.toDouble() : double.tryParse(qtyRaw?.toString() ?? '') ?? 1.0;
          final unit = item['unit']?.toString() ?? 'pieces';
          final scanType = item['scan_type']?.toString() ?? 'pantry';

          final res = await scanningService.confirmSingleIngredient(
            ingredientName: name,
            quantity: qty,
            unit: unit,
            scanType: scanType,
            queueOnFailure: false,
          );

          if (res['success'] == true) {
            flushed += 1;
            continue;
          }

          // If we are unauthenticated, keep remaining items and stop.
          final err = res['error']?.toString().toLowerCase() ?? '';
          if (err.contains('not authenticated') || err.contains('log in')) {
            remaining.add(item);
            remaining.addAll(items.skip(items.indexOf(item) + 1));
            break;
          }

          // Network still down or transient error: keep and stop.
          remaining.add(item);
          remaining.addAll(items.skip(items.indexOf(item) + 1));
          break;
        } else if (type == 'confirm_ingredients') {
          final scanId = item['scan_id']?.toString() ?? '';
          final confirmationsRaw = item['confirmations'];
          final confirmations = <Map<String, dynamic>>[];
          if (confirmationsRaw is List) {
            for (final c in confirmationsRaw) {
              if (c is Map<String, dynamic>) confirmations.add(c);
              if (c is Map) confirmations.add(c.cast<String, dynamic>());
            }
          }

          final res = await scanningService.confirmIngredients(
            scanId: scanId,
            confirmations: confirmations,
            queueOnFailure: false,
          );

          if (res['success'] == true) {
            flushed += 1;
            continue;
          }

          final err = res['error']?.toString().toLowerCase() ?? '';
          if (err.contains('not authenticated') || err.contains('log in')) {
            remaining.add(item);
            remaining.addAll(items.skip(items.indexOf(item) + 1));
            break;
          }

          remaining.add(item);
          remaining.addAll(items.skip(items.indexOf(item) + 1));
          break;
        } else {
          // Unknown item type; drop it rather than looping forever.
          flushed += 1;
        }
      }

      await prefs.setString(_prefsKey, jsonEncode(remaining));
      return flushed;
    } finally {
      _flushing = false;
    }
  }

  Future<List<Map<String, dynamic>>> _readQueue(SharedPreferences prefs) async {
    final raw = prefs.getString(_prefsKey);
    if (raw == null || raw.trim().isEmpty) return <Map<String, dynamic>>[];

    try {
      final decoded = jsonDecode(raw);
      if (decoded is! List) return <Map<String, dynamic>>[];
      return decoded
          .whereType<Map>()
          .map((e) => e.cast<String, dynamic>())
          .toList();
    } catch (_) {
      return <Map<String, dynamic>>[];
    }
  }
}
