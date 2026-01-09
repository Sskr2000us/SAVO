import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

class ShoppingListStorage {
  static const String prefsKey = 'savo.shopping_list.latest';
  static const String checkedPrefsKey = 'savo.shopping_list.checked';

  static String _itemName(dynamic item) {
    if (item is String) return item;
    if (item is Map) {
      final name = item['canonical_name'] ?? item['ingredient'] ?? item['name'];
      return (name ?? '').toString().trim();
    }
    return '';
  }

  static String _itemUnit(dynamic item) {
    if (item is Map) {
      final unit = item['unit'];
      return (unit ?? '').toString().trim();
    }
    return '';
  }

  static dynamic _itemAmount(dynamic item) {
    if (item is Map) {
      if (item.containsKey('amount')) return item['amount'];
      if (item.containsKey('quantity')) return item['quantity'];
    }
    return null;
  }

  static num? _toNum(dynamic v) {
    if (v is num) return v;
    if (v == null) return null;
    return num.tryParse(v.toString());
  }

  static String itemKey(dynamic item) {
    final name = _itemName(item).toLowerCase().trim();
    final unit = _itemUnit(item).toLowerCase().trim();
    if (name.isEmpty) return '';
    return '$name|$unit';
  }

  static List<Map<String, dynamic>> mergeItems(
    List<dynamic> existing,
    List<dynamic> incoming,
  ) {
    final Map<String, Map<String, dynamic>> merged = {};

    void add(dynamic raw) {
      if (raw == null) return;

      final key = itemKey(raw);
      final name = _itemName(raw);
      if (key.isEmpty || name.isEmpty) return;

      final unit = _itemUnit(raw);
      final amount = _itemAmount(raw);
      final num? qty = _toNum(amount);

      if (!merged.containsKey(key)) {
        merged[key] = {
          'canonical_name': name,
          if (unit.isNotEmpty) 'unit': unit,
          if (amount != null) 'amount': amount,
        };
        return;
      }

      final cur = merged[key]!;
      final curAmount = cur['amount'];
      final num? curQty = _toNum(curAmount);

      if (curQty != null && qty != null) {
        cur['amount'] = curQty + qty;
      } else if ((curAmount == null || curAmount.toString().trim().isEmpty) && amount != null) {
        cur['amount'] = amount;
      }

      if ((cur['unit'] == null || cur['unit'].toString().trim().isEmpty) && unit.isNotEmpty) {
        cur['unit'] = unit;
      }
    }

    for (final it in existing) {
      add(it);
    }
    for (final it in incoming) {
      add(it);
    }

    return merged.values.toList();
  }

  static Future<List<dynamic>> loadRaw() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(prefsKey);
    if (raw == null || raw.isEmpty) return const [];
    try {
      final parsed = json.decode(raw);
      if (parsed is List) return parsed;
    } catch (_) {}
    return const [];
  }

  static Future<void> saveRaw(List<dynamic> items) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(prefsKey, json.encode(items));
  }

  static Future<List<Map<String, dynamic>>> mergeAndSaveIncoming(List<dynamic> incoming) async {
    final existing = await loadRaw();
    final merged = mergeItems(existing, incoming);
    await saveRaw(merged);
    return merged;
  }
}
