import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_client.dart';
import '../models/inventory.dart';
import 'scan_ingredients_screen.dart';
import 'realtime_scan_screen_stub.dart'
    if (dart.library.io) 'realtime_scan_screen.dart';

class InventoryScreen extends StatefulWidget {
  const InventoryScreen({super.key});

  @override
  State<InventoryScreen> createState() => _InventoryScreenState();
}

class _InventoryScreenState extends State<InventoryScreen> {
  List<InventoryItem> _items = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadInventory();
  }

  Future<void> _loadInventory() async {
    setState(() => _loading = true);

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      // Use database endpoint with user header
      final response = await apiClient.get('/inventory-db/items');

      if (response is Map && response['items'] is List) {
        setState(() {
          _items = (response['items'] as List)
              .map((json) => InventoryItem.fromJson(json as Map<String, dynamic>))
              .toList();
          _loading = false;
        });
      } else if (response is List) {
        setState(() {
          _items = (response as List)
              .map((json) => InventoryItem.fromJson(json as Map<String, dynamic>))
              .toList();
          _loading = false;
        });
      }
    } catch (e) {
      setState(() => _loading = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error loading inventory from database: $e')),
        );
      }
    }
  }

  Future<void> _deleteItem(String inventoryId) async {
    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      // Use database endpoint with user header
      await apiClient.delete('/inventory-db/items/$inventoryId');
      _loadInventory();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error deleting from database: $e')),
        );
      }
    }
  }

  void _showAddItemDialog() {
    final nameController = TextEditingController();
    final quantityController = TextEditingController();
    final unitController = TextEditingController();
    String selectedStorage = 'refrigerator';
    String selectedState = 'raw';

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Add Item'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: nameController,
                decoration: const InputDecoration(labelText: 'Name'),
              ),
              TextField(
                controller: quantityController,
                decoration: const InputDecoration(labelText: 'Quantity'),
                keyboardType: TextInputType.number,
              ),
              TextField(
                controller: unitController,
                decoration: const InputDecoration(labelText: 'Unit'),
              ),
              DropdownButtonFormField<String>(
                value: selectedStorage,
                decoration: const InputDecoration(labelText: 'Storage'),
                items: ['refrigerator', 'freezer', 'pantry']
                    .map((s) => DropdownMenuItem(value: s, child: Text(s)))
                    .toList(),
                onChanged: (value) {
                  selectedStorage = value ?? 'refrigerator';
                },
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () async {
              final item = {
                'canonical_name': nameController.text,
                'display_name': nameController.text,
                'quantity': double.tryParse(quantityController.text) ?? 1.0,
                'unit': unitController.text,
                'storage_location': selectedStorage,  // Match database field name
                'item_state': selectedState,  // Match database field name
              };

              try {
                final apiClient = Provider.of<ApiClient>(context, listen: false);
                // Use database endpoint with user header
                await apiClient.post('/inventory-db/items', item);
                Navigator.pop(context);
                _loadInventory();
              } catch (e) {
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('Error adding to database: $e')),
                  );
                }
              }
            },
            child: const Text('Add'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Inventory'),
        actions: [
          PopupMenuButton<String>(
            icon: const Icon(Icons.photo_camera),
            tooltip: 'Scan ingredients',
            onSelected: (value) async {
              dynamic result;
              if (value == 'realtime' && !kIsWeb) {
                result = await Navigator.push<List<String>>(
                  context,
                  MaterialPageRoute(
                    builder: (_) => const RealtimeScanScreen(),
                  ),
                );
                // TODO: Process realtime scan results
                if (result != null && result is List<String>) {
                  // Show ingredients were scanned
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('Scanned ${result.length} ingredients')),
                  );
                  _loadInventory();
                }
              } else {
                final added = await Navigator.push<bool>(
                  context,
                  MaterialPageRoute(
                    builder: (_) => const ScanIngredientsScreen(),
                  ),
                );
                if (added == true) {
                  _loadInventory();
                }
              }
            },
            itemBuilder: (context) => [
              if (!kIsWeb)
                const PopupMenuItem(
                  value: 'realtime',
                  child: Row(
                    children: [
                      Icon(Icons.videocam),
                      SizedBox(width: 8),
                      Text('Real-time Scan'),
                    ],
                  ),
                ),
              const PopupMenuItem(
                value: 'photo',
                child: Row(
                  children: [
                    Icon(Icons.photo_camera),
                    SizedBox(width: 8),
                    Text('Take Photo'),
                  ],
                ),
              ),
            ],
          ),
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadInventory,
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _items.isEmpty
              ? const Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.inventory_2, size: 64, color: Colors.grey),
                      SizedBox(height: 16),
                      Text(
                        'No items in inventory',
                        style: TextStyle(fontSize: 18, color: Colors.grey),
                      ),
                    ],
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: _items.length,
                  itemBuilder: (context, index) {
                    final item = _items[index];
                    return Card(
                      margin: const EdgeInsets.only(bottom: 12),
                      color: item.isExpiringSoon
                          ? Colors.orange[50]
                          : null,
                      child: ListTile(
                        leading: CircleAvatar(
                          backgroundColor: item.isExpiringSoon
                              ? Colors.orange
                              : item.isLeftover
                                  ? Colors.blue
                                  : Colors.green,
                          child: Icon(
                            item.isLeftover
                                ? Icons.restaurant
                                : Icons.inventory,
                            color: Colors.white,
                          ),
                        ),
                        title: Text(item.canonicalName),
                        subtitle: Text(
                          '${item.quantity} ${item.unit} • ${item.storage}',
                        ),
                        trailing: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            if (item.isExpiringSoon)
                              Chip(
                                label: Text(
                                  '${item.freshnessDaysRemaining}d',
                                  style: const TextStyle(fontSize: 12),
                                ),
                                backgroundColor: Colors.orange,
                              ),
                            IconButton(
                              icon: const Icon(Icons.delete, color: Colors.red),
                              onPressed: () => _deleteItem(item.inventoryId),
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
      floatingActionButton: FloatingActionButton(
        onPressed: _showAddItemDialog,
        child: const Icon(Icons.add),
      ),
    );
  }
}
