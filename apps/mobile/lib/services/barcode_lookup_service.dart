import 'dart:convert';

import 'package:http/http.dart' as http;

class BarcodeLookupService {
  Future<Map<String, dynamic>?> lookupProduct(String barcode) async {
    final code = barcode.trim();
    if (code.isEmpty) return null;

    final uri = Uri.parse('https://world.openfoodfacts.org/api/v2/product/$code.json');

    final res = await http
        .get(uri, headers: const {'Accept': 'application/json'})
        .timeout(const Duration(seconds: 12));

    if (res.statusCode != 200) return null;

    final decoded = jsonDecode(res.body);
    if (decoded is! Map) return null;

    final status = decoded['status'];
    if (status is num && status.toInt() != 1) return null;

    final product = decoded['product'];
    if (product is! Map) return null;

    final rawName = (product['product_name'] ?? product['product_name_en'] ?? '').toString().trim();
    final cleanedName = rawName.isEmpty ? null : _cleanProductName(rawName);

    final rawQty = (product['quantity'] ?? '').toString().trim();
    final parsed = _parseQuantity(rawQty);

    if (cleanedName == null && parsed == null) return null;

    return {
      'name': cleanedName,
      if (parsed != null) ...parsed,
    };
  }

  Future<String?> lookupName(String barcode) async {
    final code = barcode.trim();
    if (code.isEmpty) return null;

    // OpenFoodFacts product lookup (no API key required for basic usage).
    final uri = Uri.parse('https://world.openfoodfacts.org/api/v2/product/$code.json');

    final res = await http
        .get(uri, headers: const {'Accept': 'application/json'})
        .timeout(const Duration(seconds: 12));

    if (res.statusCode != 200) return null;

    final decoded = jsonDecode(res.body);
    if (decoded is! Map) return null;

    final status = decoded['status'];
    if (status is num && status.toInt() != 1) return null;

    final product = decoded['product'];
    if (product is! Map) return null;

    final rawName = (product['product_name'] ?? product['product_name_en'] ?? '').toString().trim();
    if (rawName.isEmpty) return null;

    return _cleanProductName(rawName);
  }

  Map<String, dynamic>? _parseQuantity(String raw) {
    final s = raw.trim();
    if (s.isEmpty) return null;

    // Common formats: "500 g", "1kg", "16 oz", "2 x 250 g"
    final m = RegExp(r'(\d+(?:\.\d+)?)\s*(kg|g|mg|l|ml|oz|lb|lbs)\b', caseSensitive: false).firstMatch(s);
    if (m == null) return null;
    final qty = double.tryParse(m.group(1) ?? '');
    final unit = (m.group(2) ?? '').toLowerCase();
    if (qty == null) return null;

    String normUnit = unit;
    if (unit == 'lbs') normUnit = 'lb';

    return {
      'quantity': qty,
      'unit': normUnit,
      'raw_quantity': s,
    };
  }

  String _cleanProductName(String raw) {
    var s = raw.trim();

    // Strip bracketed suffixes like "(500g)" or "[Brand]".
    s = s.replaceAll(RegExp(r'\s*[\(\[].*?[\)\]]\s*'), ' ');

    // Remove common marketing words that make pantry items messy.
    const drop = <String>{
      'organic',
      'fresh',
      'natural',
      'original',
      'classic',
      'premium',
      'pack',
      'family',
      'value',
      'gluten free',
      'gluten-free',
      'non gmo',
      'non-gmo',
    };

    final lowered = s.toLowerCase();
    for (final w in drop) {
      if (lowered.contains(w)) {
        s = s.replaceAll(RegExp(RegExp.escape(w), caseSensitive: false), ' ');
      }
    }

    s = s.replaceAll(RegExp(r'[^a-zA-Z0-9\s]'), ' ');
    s = s.replaceAll(RegExp(r'\s+'), ' ').trim();

    // Keep it short and pantry-like.
    if (s.length > 60) s = s.substring(0, 60).trim();

    return s;
  }
}
