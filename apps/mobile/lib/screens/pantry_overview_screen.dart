import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/inventory.dart';
import '../services/api_client.dart';
import '../theme/app_theme.dart';
import '../ui/ui_principles.dart';

class PantryOverviewScreen extends StatefulWidget {
  const PantryOverviewScreen({super.key});

  @override
  State<PantryOverviewScreen> createState() => _PantryOverviewScreenState();
}

class _PantryOverviewScreenState extends State<PantryOverviewScreen> {
  bool _loading = true;
  List<InventoryItem> _items = const [];
  bool _cleaning = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final response = await apiClient.get('/inventory-db/items?include_inactive=true');

      List<InventoryItem> parsed;
      if (response is Map && response['items'] is List) {
        parsed = (response['items'] as List)
            .whereType<Map>()
            .map((json) => InventoryItem.fromJson(json.cast<String, dynamic>()))
            .toList();
      } else if (response is List) {
        parsed = response
            .whereType<Map>()
            .map((json) => InventoryItem.fromJson(json.cast<String, dynamic>()))
            .toList();
      } else {
        parsed = const [];
      }

      if (!mounted) return;
      setState(() {
        _items = parsed;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _loading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error loading pantry: $e')),
      );
    }
  }

  Future<void> _weeklyCleanup() async {
    if (_cleaning) return;
    setState(() => _cleaning = true);

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final res = await apiClient.post(
        '/api/scanning/pantry/weekly-cleanup?stale_days=30',
        const {},
      );

      if (!mounted) return;

      final msg = (res is Map && res['message'] != null)
          ? res['message'].toString()
          : 'Cleanup complete.';

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(msg)),
      );

      await _load();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Cleanup failed: $e')),
      );
    } finally {
      if (!mounted) return;
      setState(() => _cleaning = false);
    }
  }

  List<InventoryItem> get _useSoon {
    final list = _items
        .where((i) => i.isCurrent)
        .where((i) => i.freshnessDaysRemaining != null)
        .where((i) => i.freshnessDaysRemaining! <= 3)
        .toList();

    list.sort((a, b) {
      final ad = a.freshnessDaysRemaining ?? 9999;
      final bd = b.freshnessDaysRemaining ?? 9999;
      return ad.compareTo(bd);
    });

    return list;
  }

  List<InventoryItem> get _available {
    final list = _items
        .where((i) => i.isCurrent)
        .where((i) => !(i.freshnessDaysRemaining != null && i.freshnessDaysRemaining! <= 3))
        .toList();

    list.sort((a, b) => a.displayLabel.toLowerCase().compareTo(b.displayLabel.toLowerCase()));
    return list;
  }

  List<InventoryItem> get _missing {
    final list = _items.where((i) => !i.isCurrent).toList();
    list.sort((a, b) => a.displayLabel.toLowerCase().compareTo(b.displayLabel.toLowerCase()));
    return list;
  }

  @override
  Widget build(BuildContext context) {
    if (kDebugMode || kProfileMode) {
      SavoUiGuards.warnIfTooManyChoices(
        screen: 'PantryOverviewScreen',
        surface: 'Tabs',
        choices: 3,
      );
    }

    return DefaultTabController(
      length: 3,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Pantry'),
          actions: [
            IconButton(
              tooltip: 'Weekly cleanup',
              onPressed: _cleaning ? null : _weeklyCleanup,
              icon: Icon(_cleaning ? Icons.hourglass_top : Icons.cleaning_services_outlined),
            ),
          ],
          bottom: const TabBar(
            tabs: [
              Tab(text: 'UseSoon'),
              Tab(text: 'Available'),
              Tab(text: 'Missing'),
            ],
          ),
        ),
        body: _loading
            ? const Center(child: CircularProgressIndicator())
            : RefreshIndicator(
                onRefresh: _load,
                child: TabBarView(
                  children: [
                    _PantryList(items: _useSoon),
                    _PantryList(items: _available),
                    _PantryList(items: _missing),
                  ],
                ),
              ),
      ),
    );
  }
}

class _PantryList extends StatelessWidget {
  final List<InventoryItem> items;

  const _PantryList({required this.items});

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) {
      return ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(AppSpacing.md),
        children: [
          Text(
            'No items yet.',
            style: Theme.of(context).textTheme.bodyMedium,
          ),
        ],
      );
    }

    return ListView.separated(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(AppSpacing.md),
      itemCount: items.length,
      separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
      itemBuilder: (context, index) {
        final item = items[index];
        return Card(
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: Row(
              children: [
                _FreshnessIndicator(item: item),
                const SizedBox(width: AppSpacing.md),
                _StorageIcon(item: item),
                const SizedBox(width: AppSpacing.md),
                Expanded(
                  child: Text(
                    item.displayLabel,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _StorageIcon extends StatelessWidget {
  final InventoryItem item;

  const _StorageIcon({required this.item});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    final storage = item.storage.trim().toLowerCase();
    IconData icon;
    String label;

    if (storage == 'fridge' || storage == 'refrigerator') {
      icon = Icons.kitchen_outlined;
      label = 'Fridge';
    } else if (storage == 'freezer') {
      icon = Icons.ac_unit;
      label = 'Freezer';
    } else {
      icon = Icons.inventory_2_outlined;
      label = 'Pantry';
    }

    return Tooltip(
      message: label,
      child: Container(
        width: 40,
        height: 32,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: cs.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(AppRadius.md),
        ),
        child: Icon(icon, size: 18, color: cs.onSurfaceVariant),
      ),
    );
  }
}

class _FreshnessIndicator extends StatelessWidget {
  final InventoryItem item;

  const _FreshnessIndicator({required this.item});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    final days = item.freshnessDaysRemaining;
    final String label;
    final Color color;

    if (days == null) {
      label = '—';
      color = cs.outlineVariant;
    } else if (days <= 0) {
      label = 'Today';
      color = cs.error;
    } else if (days <= 3) {
      label = '${days}d';
      color = cs.secondary;
    } else {
      label = '${days}d';
      color = cs.tertiary;
    }

    return Container(
      width: 56,
      height: 32,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(AppRadius.md),
      ),
      child: Text(
        label,
        style: Theme.of(context).textTheme.labelLarge?.copyWith(
              color: color,
              fontWeight: FontWeight.w700,
            ),
      ),
    );
  }
}
