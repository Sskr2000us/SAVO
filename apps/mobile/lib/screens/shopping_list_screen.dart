import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:share_plus/share_plus.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../models/profile_state.dart';

class ShoppingListScreen extends StatefulWidget {
  const ShoppingListScreen({super.key});

  @override
  State<ShoppingListScreen> createState() => _ShoppingListScreenState();
}

class _ShoppingListScreenState extends State<ShoppingListScreen> {
  bool _loading = true;
  List<dynamic> _items = const [];
  Map<String, bool> _checked = const {};

  bool _syncLoading = false;
  String? _syncError;
  RealtimeChannel? _channel;

  static const _prefsKey = 'savo.shopping_list.latest';
  static const _checkedPrefsKey = 'savo.shopping_list.checked';
  static const _supabaseTable = 'household_shopping_items';

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _channel?.unsubscribe();
    super.dispose();
  }

  String? _householdId() {
    try {
      final profile = Provider.of<ProfileState>(context, listen: false);
      final hh = profile.household;
      final id = hh?['id'];
      final v = id?.toString().trim();
      if (v == null || v.isEmpty) return null;
      return v;
    } catch (_) {
      return null;
    }
  }

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_prefsKey);
    final rawChecked = prefs.getString(_checkedPrefsKey);
    List<dynamic> items = const [];
    if (raw != null && raw.isNotEmpty) {
      try {
        final parsed = json.decode(raw);
        if (parsed is List) items = parsed;
      } catch (_) {}
    }

    Map<String, bool> checked = const {};
    if (rawChecked != null && rawChecked.isNotEmpty) {
      try {
        final parsed = json.decode(rawChecked);
        if (parsed is Map) {
          checked = parsed.map((k, v) => MapEntry(k.toString(), v == true));
        }
      } catch (_) {}
    }

    if (!mounted) return;
    setState(() {
      _items = items;
      _checked = checked;
      _loading = false;
    });

    // Best-effort: enable sync after local load.
    await _initSupabaseSync();
  }

  Future<void> _initSupabaseSync() async {
    final session = Supabase.instance.client.auth.currentSession;
    final householdId = _householdId();

    if (session == null || householdId == null) {
      return;
    }

    if (_syncLoading) return;
    setState(() {
      _syncLoading = true;
      _syncError = null;
    });

    try {
      await _refreshFromSupabase(householdId);
      await _pushLocalToSupabaseIfRemoteEmpty(householdId);
      _subscribeRealtime(householdId);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _syncError = 'Sync unavailable (showing local list).';
      });
    } finally {
      if (mounted) {
        setState(() {
          _syncLoading = false;
        });
      }
    }
  }

  Future<void> _refreshFromSupabase(String householdId) async {
    final client = Supabase.instance.client;
    final List<dynamic> rows = await client
        .from(_supabaseTable)
        .select('item_key,item_json,checked,updated_at')
        .eq('household_id', householdId)
        .order('updated_at', ascending: false);

    final items = <dynamic>[];
    final checked = <String, bool>{};

    for (final r in rows) {
      final m = Map<String, dynamic>.from(r as Map);
      final key = (m['item_key'] ?? '').toString();
      final isChecked = m['checked'] == true;
      final itemJson = m['item_json'];

      if (itemJson is Map) {
        items.add(Map<String, dynamic>.from(itemJson));
      } else if (itemJson is String) {
        items.add(itemJson);
      }
      if (key.isNotEmpty) {
        checked[key] = isChecked;
      }
    }

    if (!mounted) return;
    setState(() {
      // Remote is authoritative when available.
      _items = items;
      _checked = checked;
    });

    // Keep a local cache for offline/unauthenticated viewing.
    await _persistItems(items);
    await _persistChecked(checked);
  }

  Future<void> _pushLocalToSupabaseIfRemoteEmpty(String householdId) async {
    if (_items.isEmpty) return;

    final client = Supabase.instance.client;
    final List<dynamic> existing = await client
        .from(_supabaseTable)
        .select('item_key')
        .eq('household_id', householdId)
        .limit(1);

    if (existing.isNotEmpty) {
      return;
    }

    final now = DateTime.now().toUtc().toIso8601String();
    final rows = <Map<String, dynamic>>[];
    for (final item in _items) {
      final key = _itemKey(item);
      if (key.trim().isEmpty) continue;
      rows.add({
        'household_id': householdId,
        'item_key': key,
        'item_json': item,
        'checked': _checked[key] == true,
        'updated_at': now,
      });
    }

    if (rows.isEmpty) return;

    // Requires a UNIQUE constraint on (household_id, item_key) to safely upsert.
    await client.from(_supabaseTable).upsert(rows);
  }

  void _subscribeRealtime(String householdId) {
    final client = Supabase.instance.client;

    _channel?.unsubscribe();
    _channel = client
        .channel('shopping_list:$householdId')
        .onPostgresChanges(
          event: PostgresChangeEvent.all,
          schema: 'public',
          table: _supabaseTable,
          filter: PostgresChangeFilter(
            type: PostgresChangeFilterType.eq,
            column: 'household_id',
            value: householdId,
          ),
          callback: (payload) async {
            // Simple + robust: re-fetch.
            try {
              await _refreshFromSupabase(householdId);
            } catch (_) {}
          },
        )
        .subscribe();
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

  String _itemName(dynamic item) {
    if (item is String) return item;
    if (item is Map) {
      final name = item['canonical_name'] ?? item['ingredient'] ?? item['name'];
      return (name ?? '').toString().trim();
    }
    return '';
  }

  String _itemQuantity(dynamic item) {
    if (item is Map) {
      final amount = item['amount'] ?? item['quantity'];
      final unit = item['unit'];
      final qty = [amount, unit].where((x) => x != null && x.toString().trim().isNotEmpty).join(' ');
      return qty.trim();
    }
    return '';
  }

  String _itemKey(dynamic item) {
    final name = _itemName(item).toLowerCase();
    final qty = _itemQuantity(item).toLowerCase();
    return '${name.trim()}|${qty.trim()}';
  }

  Future<void> _persistChecked(Map<String, bool> checked) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_checkedPrefsKey, json.encode(checked));
  }

  Future<void> _persistItems(List<dynamic> items) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_prefsKey, json.encode(items));
  }

  Future<void> _updateRemoteChecked(String itemKey, bool isChecked) async {
    final session = Supabase.instance.client.auth.currentSession;
    final householdId = _householdId();
    if (session == null || householdId == null) return;

    try {
      await Supabase.instance.client
          .from(_supabaseTable)
          .upsert({
            'household_id': householdId,
            'item_key': itemKey,
            'item_json': _items.firstWhere((it) => _itemKey(it) == itemKey, orElse: () => {'canonical_name': itemKey}),
            'checked': isChecked,
            'updated_at': DateTime.now().toUtc().toIso8601String(),
          });
    } catch (_) {
      // Ignore: local remains functional.
    }
  }

  String _categoryForName(String nameRaw) {
    final name = nameRaw.toLowerCase();

    // Produce
    const produce = [
      'tomato',
      'onion',
      'garlic',
      'ginger',
      'potato',
      'spinach',
      'lettuce',
      'cucumber',
      'carrot',
      'pepper',
      'chili',
      'lemon',
      'lime',
      'apple',
      'banana',
      'cilantro',
      'coriander',
      'mint',
      'basil',
    ];
    if (produce.any((k) => name.contains(k))) return 'Produce';

    // Dairy
    const dairy = ['milk', 'cheese', 'yogurt', 'curd', 'butter', 'ghee', 'cream'];
    if (dairy.any((k) => name.contains(k))) return 'Dairy';

    // Meat / seafood
    const meat = ['chicken', 'beef', 'pork', 'lamb', 'fish', 'shrimp', 'prawn', 'egg'];
    if (meat.any((k) => name.contains(k))) return 'Meat & Seafood';

    // Frozen
    const frozen = ['frozen', 'ice cream'];
    if (frozen.any((k) => name.contains(k))) return 'Frozen';

    // Bakery
    const bakery = ['bread', 'bun', 'roll', 'tortilla', 'naan', 'pita'];
    if (bakery.any((k) => name.contains(k))) return 'Bakery';

    // Pantry (default)
    return 'Pantry';
  }

  Map<String, List<dynamic>> _groupItems(List<dynamic> items) {
    final groups = <String, List<dynamic>>{
      'Produce': [],
      'Dairy': [],
      'Meat & Seafood': [],
      'Bakery': [],
      'Frozen': [],
      'Pantry': [],
      'Other': [],
    };

    for (final item in items) {
      final name = _itemName(item);
      if (name.isEmpty) {
        groups['Other']!.add(item);
        continue;
      }
      final cat = _categoryForName(name);
      (groups[cat] ?? groups['Other']!).add(item);
    }

    // Remove empty sections except keep stable ordering.
    return groups;
  }

  String _exportText(Map<String, List<dynamic>> grouped) {
    final lines = <String>[];
    lines.add('Shopping List');
    lines.add('');

    for (final entry in grouped.entries) {
      final sectionItems = entry.value;
      if (sectionItems.isEmpty) continue;
      lines.add(entry.key);
      for (final item in sectionItems) {
        final name = _itemName(item);
        final qty = _itemQuantity(item);
        if (name.isEmpty) continue;
        lines.add(qty.isNotEmpty ? '- $name ($qty)' : '- $name');
      }
      lines.add('');
    }

    return lines.join('\n').trim();
  }

  Future<void> _copyToClipboard(String text) async {
    await Clipboard.setData(ClipboardData(text: text));
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Shopping list copied')),
    );
  }

  Future<void> _share(String text) async {
    try {
      await Share.share(text, subject: 'SAVO Shopping List');
    } catch (_) {
      await _copyToClipboard(text);
    }
  }

  @override
  Widget build(BuildContext context) {
    final grouped = _groupItems(_items);
    final exportText = _exportText(grouped);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Shopping List'),
        actions: [
          if (!_loading && _items.isNotEmpty) ...[
            IconButton(
              tooltip: 'Copy',
              icon: const Icon(Icons.copy),
              onPressed: () => _copyToClipboard(exportText),
            ),
            IconButton(
              tooltip: 'Share',
              icon: const Icon(Icons.share),
              onPressed: () => _share(exportText),
            ),
          ],
        ],
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
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    if (_syncLoading)
                      const Padding(
                        padding: EdgeInsets.only(bottom: 10),
                        child: LinearProgressIndicator(minHeight: 2),
                      ),
                    if (_syncError != null)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: Text(
                          _syncError!,
                          style: Theme.of(context)
                              .textTheme
                              .bodySmall
                              ?.copyWith(color: Theme.of(context).colorScheme.onSurface.withAlpha(180)),
                        ),
                      ),
                    for (final entry in grouped.entries)
                      if (entry.value.isNotEmpty) ...[
                        Text(
                          entry.key,
                          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.bold,
                              ),
                        ),
                        const SizedBox(height: 8),
                        ...entry.value.map((item) {
                          final key = _itemKey(item);
                          final checked = _checked[key] == true;
                          return Card(
                            child: ListTile(
                              dense: true,
                              contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 2),
                              leading: Checkbox(
                                value: checked,
                                onChanged: (v) async {
                                  final isChecked = v == true;
                                  final next = Map<String, bool>.from(_checked);
                                  next[key] = isChecked;
                                  setState(() => _checked = next);
                                  await _persistChecked(next);
                                  await _updateRemoteChecked(key, isChecked);
                                },
                              ),
                              title: Text(
                                _itemTitle(item),
                                style: checked
                                    ? TextStyle(
                                        decoration: TextDecoration.lineThrough,
                                        color: Theme.of(context).textTheme.bodyMedium?.color,
                                      )
                                    : null,
                              ),
                              onTap: () async {
                                final nextValue = !checked;
                                final next = Map<String, bool>.from(_checked);
                                next[key] = nextValue;
                                setState(() => _checked = next);
                                await _persistChecked(next);
                                await _updateRemoteChecked(key, nextValue);
                              },
                            ),
                          );
                        }),
                        const SizedBox(height: 8),
                        const Divider(height: 24),
                      ],
                  ],
                ),
    );
  }
}
