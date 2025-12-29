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
                        title: Text(item.canonicalName),
                        subtitle: Text(
                          '${item.quantity} ${item.unit} • ${item.storage}',
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
