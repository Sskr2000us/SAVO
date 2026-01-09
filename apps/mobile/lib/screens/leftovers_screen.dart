import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_client.dart';
import '../models/inventory.dart';

class LeftoversScreen extends StatefulWidget {
  const LeftoversScreen({super.key});

  @override
  State<LeftoversScreen> createState() => _LeftoversScreenState();
}

class _LeftoversScreenState extends State<LeftoversScreen> {
  List<InventoryItem> _leftovers = [];
  bool _loading = true;

  String _pretty(String raw) {
    final s = raw.trim().replaceAll('_', ' ');
    if (s.isEmpty) return s;
    return s.split(RegExp(r'\s+')).map((w) {
      if (w.isEmpty) return w;
      return w[0].toUpperCase() + w.substring(1);
    }).join(' ');
  }

  String _formatQty(double qty) {
    if (qty == qty.roundToDouble()) return qty.toInt().toString();
    return qty
        .toStringAsFixed(2)
        .replaceAll(RegExp(r'0+$'), '')
        .replaceAll(RegExp(r'\.$'), '');
  }

  String _formatDate(DateTime d) {
    return '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
  }

  @override
  void initState() {
    super.initState();
    _loadLeftovers();
  }

  Future<void> _loadLeftovers() async {
    setState(() => _loading = true);

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final response = await apiClient.get('/inventory');

      if (response is List) {
        final allItems = (response as List)
            .map((json) => InventoryItem.fromJson(json as Map<String, dynamic>))
            .toList();
        
        setState(() {
          _leftovers = allItems.where((item) => item.isLeftover).toList();
          _loading = false;
        });
      }
    } catch (e) {
      setState(() => _loading = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error loading leftovers: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Leftovers Center'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadLeftovers,
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _leftovers.isEmpty
              ? const Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.kitchen, size: 64, color: Colors.grey),
                      SizedBox(height: 16),
                      Text(
                        'No leftovers',
                        style: TextStyle(fontSize: 18, color: Colors.grey),
                      ),
                    ],
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: _leftovers.length,
                  itemBuilder: (context, index) {
                    final item = _leftovers[index];
                    return Card(
                      margin: const EdgeInsets.only(bottom: 12),
                      child: ListTile(
                        leading: const CircleAvatar(
                          child: Icon(Icons.restaurant),
                        ),
                        title: Text(item.displayLabel),
                        subtitle: Builder(
                          builder: (context) {
                            final theme = Theme.of(context);
                            final category = (item.category ?? '').trim();
                            final subcategory = (item.subcategory ?? '').trim();
                            final cuisine = (item.cuisine ?? '').trim();
                            final expiry = item.expiryDate;

                            final taxonomyLabel = () {
                              if (category.isEmpty && subcategory.isEmpty) return 'Category: Uncategorized';
                              if (category.isNotEmpty && subcategory.isNotEmpty) {
                                return 'Category: ${_pretty(category)} / ${_pretty(subcategory)}';
                              }
                              if (category.isNotEmpty) return 'Category: ${_pretty(category)}';
                              return 'Category: ${_pretty(subcategory)}';
                            }();

                            final metaParts = <String>[
                              taxonomyLabel,
                              'Expiry: ${expiry == null ? '—' : _formatDate(expiry)}',
                              if (cuisine.isNotEmpty) 'Cuisine: ${_pretty(cuisine)}',
                            ];

                            return Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text('${_formatQty(item.quantity)} ${item.unit} • ${item.storage} • ${_pretty(item.state)}'),
                                const SizedBox(height: 2),
                                Text(metaParts.join(' • '), style: theme.textTheme.bodySmall),
                              ],
                            );
                          },
                        ),
                        trailing: item.isExpiringSoon
                            ? Chip(
                                label: Text(
                                  '${item.freshnessDaysRemaining} days',
                                  style: const TextStyle(fontSize: 12),
                                ),
                                backgroundColor: Colors.orange[100],
                              )
                            : null,
                      ),
                    );
                  },
                ),
    );
  }
}
