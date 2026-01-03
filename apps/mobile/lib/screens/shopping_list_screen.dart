import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

class ShoppingListScreen extends StatefulWidget {
  const ShoppingListScreen({super.key});

  @override
  State<ShoppingListScreen> createState() => _ShoppingListScreenState();
}

class _ShoppingListScreenState extends State<ShoppingListScreen> {
  bool _loading = true;
  List<dynamic> _items = const [];

  static const _prefsKey = 'savo.shopping_list.latest';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_prefsKey);
    List<dynamic> items = const [];
    if (raw != null && raw.isNotEmpty) {
      try {
        final parsed = json.decode(raw);
        if (parsed is List) items = parsed;
      } catch (_) {}
    }

    if (!mounted) return;
    setState(() {
      _items = items;
      _loading = false;
    });
  }

  String _itemTitle(dynamic item) {
    if (item is String) return item;
    if (item is Map) {
      final name = item['canonical_name'] ?? item['ingredient'] ?? item['name'];
      final amount = item['amount'] ?? item['quantity'];
      final unit = item['unit'];
      final parts = <String>[];
      if (name != null) parts.add(name.toString());
      final qty = [amount, unit].where((x) => x != null && x.toString().trim().isNotEmpty).join(' ');
      if (qty.isNotEmpty) parts.add(qty);
      return parts.isNotEmpty ? parts.join(' — ') : 'Item';
    }
    return 'Item';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Shopping List'),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _items.isEmpty
              ? Padding(
                  padding: const EdgeInsets.all(16),
                  child: Text(
                    'No shopping list yet. Generate one from a plan (“Shopping List”) or from a recipe (“Check if I have enough”).',
                    style: TextStyle(color: Colors.grey.shade600),
                  ),
                )
              : ListView.separated(
                  padding: const EdgeInsets.all(16),
                  itemCount: _items.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (context, index) {
                    final item = _items[index];
                    return ListTile(
                      leading: const Icon(Icons.local_grocery_store_outlined),
                      title: Text(_itemTitle(item)),
                    );
                  },
                ),
    );
  }
}
