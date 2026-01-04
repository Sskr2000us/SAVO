import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_client.dart';
import '../models/inventory.dart';
import '../widgets/quantity_picker.dart';
import 'scan_ingredients_screen.dart';
import 'pantry/manual_entry_screen.dart';
import 'barcode_scan_screen.dart';
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
  bool _mergingDuplicates = false;

  bool _showInactiveItems = false;

  static const List<String> _storageOptions = ['pantry', 'fridge', 'freezer', 'counter'];

  Future<void> _saveRealtimeScanResults(List<String> ingredients) async {
    if (ingredients.isEmpty) return;

    setState(() => _loading = true);
    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);

      final rawItems = ingredients
          .where((i) => i.trim().isNotEmpty)
          .map((i) => {
                'display_name': i.trim(),
                'quantity_estimate': null,
                'confidence': 1.0,
                'storage_hint': 'pantry',
              })
          .toList();

      final normalized = await apiClient.post('/inventory/normalize', {
        'raw_items': rawItems,
        'measurement_system': 'metric',
        'output_language': 'en',
      });

      final normItems = normalized['normalized_inventory'];
      if (normItems is! List) {
        throw Exception('Normalization response missing normalized_inventory');
      }

      if (!mounted) return;

      // Require explicit confirmation before saving (prevents auto-save for uncertain cases).
      final confirmedToSave = await _showConfirmNormalizedItemsDialog(normItems);
      if (confirmedToSave == null || confirmedToSave.isEmpty) {
        if (mounted) setState(() => _loading = false);
        return;
      }

      for (final payload in confirmedToSave) {
        await apiClient.post('/inventory-db/items', payload);
      }

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Saved ${confirmedToSave.length} scanned items to inventory')),
      );
      await _loadInventory();
    } catch (e) {
      if (!mounted) return;
      setState(() => _loading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to save scan results: $e')),
      );
    }
  }

  Future<List<Map<String, dynamic>>?> _showConfirmNormalizedItemsDialog(List normItems) async {
    final candidates = <_NormalizedCandidate>[];
    for (final item in normItems) {
      if (item is! Map) continue;
      final json = Map<String, dynamic>.from(item);
      final display = (json['display_name'] ?? '').toString().trim();
      if (display.isEmpty) continue;
      final qty = (json['quantity'] is num) ? (json['quantity'] as num).toDouble() : 1.0;
      final unit = (json['unit'] ?? 'pcs').toString();
      final storage = (json['storage'] ?? 'pantry').toString();
      final state = (json['state'] ?? 'raw').toString();
      final confidence = (json['confidence'] is num) ? (json['confidence'] as num).toDouble() : null;
      candidates.add(
        _NormalizedCandidate(
          nameController: TextEditingController(text: display),
          quantity: qty,
          unit: unit,
          storage: _storageOptions.contains(storage) ? storage : 'pantry',
          state: state,
          scanConfidence: confidence,
        ),
      );
    }

    if (candidates.isEmpty) return null;

    return showDialog<List<Map<String, dynamic>>>(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              title: const Text('Review scanned items'),
              content: SizedBox(
                width: 520,
                child: ListView.separated(
                  shrinkWrap: true,
                  itemCount: candidates.length,
                  separatorBuilder: (_, __) => const Divider(height: 12),
                  itemBuilder: (context, index) {
                    final c = candidates[index];
                    final availableUnits = getSmartUnitSuggestions(null, c.nameController.text);
                    final mergedUnits = <String>{c.unit, ...availableUnits}.toList();

                    return Opacity(
                      opacity: c.include ? 1.0 : 0.5,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Row(
                            children: [
                              Checkbox(
                                value: c.include,
                                onChanged: (v) {
                                  setDialogState(() => c.include = v ?? true);
                                },
                              ),
                              Expanded(
                                child: TextField(
                                  controller: c.nameController,
                                  enabled: c.include,
                                  decoration: const InputDecoration(
                                    labelText: 'Name',
                                    border: OutlineInputBorder(),
                                  ),
                                  onChanged: (_) {
                                    setDialogState(() {});
                                  },
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),
                          Center(
                            child: QuantityPicker(
                              initialQuantity: c.quantity,
                              initialUnit: c.unit,
                              availableUnits: mergedUnits,
                              enabled: c.include,
                              onChanged: (newQty, newUnit) {
                                setDialogState(() {
                                  c.quantity = newQty;
                                  c.unit = newUnit;
                                });
                              },
                            ),
                          ),
                          const SizedBox(height: 8),
                          DropdownButtonFormField<String>(
                            value: c.storage,
                            decoration: const InputDecoration(
                              labelText: 'Storage',
                              border: OutlineInputBorder(),
                            ),
                            items: _storageOptions
                                .map((s) => DropdownMenuItem(value: s, child: Text(s)))
                                .toList(),
                            onChanged: c.include
                                ? (value) {
                                    setDialogState(() => c.storage = value ?? 'pantry');
                                  }
                                : null,
                          ),
                        ],
                      ),
                    );
                  },
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Cancel'),
                ),
                FilledButton(
                  onPressed: () {
                    final payloads = <Map<String, dynamic>>[];
                    for (final c in candidates) {
                      if (!c.include) continue;
                      final display = c.nameController.text.trim();
                      if (display.isEmpty) continue;
                      payloads.add(
                        {
                          'canonical_name': _canonicalizeName(display),
                          'display_name': display,
                          'quantity': c.quantity,
                          'unit': c.unit,
                          'item_state': c.state,
                          'storage_location': c.storage,
                          'source': 'scan',
                          'scan_confidence': c.scanConfidence,
                        },
                      );
                    }
                    Navigator.pop(context, payloads);
                  },
                  child: const Text('Save to inventory'),
                ),
              ],
            );
          },
        );
      },
    );
  }

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
      final response = await apiClient.get(
        _showInactiveItems ? '/inventory-db/items?include_inactive=true' : '/inventory-db/items',
      );

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

  Future<void> _setItemCurrent(InventoryItem item, bool isCurrent) async {
    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      await apiClient.patch('/inventory-db/items/${item.inventoryId}', {
        'is_current': isCurrent,
      });
      await _loadInventory();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to update item: $e')),
      );
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

  String _prettyName(String raw) {
    final cleaned = raw.replaceAll('_', ' ').trim();
    if (cleaned.isEmpty) return raw;
    return cleaned[0].toUpperCase() + cleaned.substring(1);
  }

  List<List<InventoryItem>> _findDuplicateGroups() {
    final Map<String, List<InventoryItem>> groups = {};
    for (final item in _items) {
      final key = item.canonicalName.trim().toLowerCase();
      if (key.isEmpty) continue;
      groups.putIfAbsent(key, () => []).add(item);
    }
    final dupes = groups.values.where((g) => g.length > 1).toList();
    dupes.sort((a, b) => a.first.canonicalName.compareTo(b.first.canonicalName));
    return dupes;
  }

  Future<void> _mergeDuplicateGroup(List<InventoryItem> group) async {
    if (group.length < 2) return;
    final unit = group.first.unit;
    final storage = group.first.storage;
    final state = group.first.state;
    final allMergeable = group.every((i) => i.unit == unit && i.storage == storage && i.state == state);
    if (!allMergeable) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Can only auto-merge duplicates with same unit, storage, and state.')),
      );
      return;
    }

    final keep = group.first;
    final totalQty = group.fold<double>(0, (sum, i) => sum + i.quantity);
    final toDelete = group.skip(1).toList();

    setState(() => _mergingDuplicates = true);
    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      await apiClient.patch('/inventory-db/items/${keep.inventoryId}', {
        'quantity': totalQty,
      });

      for (final item in toDelete) {
        await apiClient.delete('/inventory-db/items/${item.inventoryId}');
      }

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Merged ${group.length} duplicates into one item.')),
      );
      await _loadInventory();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to merge duplicates: $e')),
      );
    } finally {
      if (mounted) setState(() => _mergingDuplicates = false);
    }
  }

  Future<void> _showMergeDuplicatesDialog() async {
    final groups = _findDuplicateGroups();
    if (groups.isEmpty) return;

    await showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Merge Duplicates'),
        content: SizedBox(
          width: 420,
          child: ListView.separated(
            shrinkWrap: true,
            itemCount: groups.length,
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemBuilder: (context, index) {
              final group = groups[index];
              final name = _prettyName(group.first.displayLabel);
              final total = group.fold<double>(0, (sum, i) => sum + i.quantity);
              final sameUnit = group.every((i) => i.unit == group.first.unit);
              final mergeable = group.every((i) => i.unit == group.first.unit && i.storage == group.first.storage && i.state == group.first.state);
              final subtitleParts = <String>[
                '${group.length} items',
                if (sameUnit) '${total.toStringAsFixed(2).replaceAll(RegExp(r'0+$'), '').replaceAll(RegExp(r'\.$'), '')} ${group.first.unit}',
              ];
              return ListTile(
                title: Text(name),
                subtitle: Text(subtitleParts.join(' • ')),
                trailing: TextButton(
                  onPressed: _mergingDuplicates || !mergeable
                      ? null
                      : () async {
                          Navigator.pop(context);
                          await _mergeDuplicateGroup(group);
                        },
                  child: Text(mergeable ? 'Merge' : 'Not mergeable'),
                ),
              );
            },
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  String _canonicalizeName(String display) {
    final trimmed = display.trim().toLowerCase();
    final collapsed = trimmed.replaceAll(RegExp(r'\s+'), '_');
    return collapsed;
  }

  Future<void> _showEditItemSheet(InventoryItem item) async {
    final nameController = TextEditingController(text: _prettyName(item.displayLabel));
    final categoryController = TextEditingController(text: item.category ?? '');
    final notesController = TextEditingController(text: item.notes ?? '');

    double qty = item.quantity;
    String unit = item.unit;
    String storage = item.storage;
    String state = item.state;
    DateTime? expiry = item.expiryDate;
    bool isCurrent = item.isCurrent;

    await showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setModalState) {
            final availableUnits = getSmartUnitSuggestions(null, nameController.text);
            final mergedUnits = <String>{unit, ...availableUnits}.toList();
            final theme = Theme.of(context);
            return Padding(
              padding: EdgeInsets.only(
                left: 16,
                right: 16,
                top: 8,
                bottom: 16 + MediaQuery.of(context).viewInsets.bottom,
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text('Edit item', style: theme.textTheme.titleLarge),
                  const SizedBox(height: 12),
                  TextField(
                    controller: nameController,
                    textInputAction: TextInputAction.next,
                    decoration: const InputDecoration(
                      labelText: 'Name',
                      border: OutlineInputBorder(),
                    ),
                    onChanged: (_) {
                      setModalState(() {});
                    },
                  ),
                  const SizedBox(height: 12),
                  Center(
                    child: QuantityPicker(
                      initialQuantity: qty,
                      initialUnit: unit,
                      availableUnits: mergedUnits,
                      onChanged: (newQty, newUnit) {
                        setModalState(() {
                          qty = newQty;
                          unit = newUnit;
                        });
                      },
                      enabled: true,
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: categoryController,
                    textInputAction: TextInputAction.next,
                    decoration: const InputDecoration(
                      labelText: 'Category (optional)',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: DropdownButtonFormField<String>(
                          value: storage,
                          decoration: const InputDecoration(
                            labelText: 'Storage',
                            border: OutlineInputBorder(),
                          ),
                          items: const ['pantry', 'fridge', 'freezer', 'counter']
                              .map((s) => DropdownMenuItem(value: s, child: Text(s)))
                              .toList(),
                          onChanged: (value) {
                            setModalState(() {
                              storage = value ?? 'pantry';
                            });
                          },
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: DropdownButtonFormField<String>(
                          value: state,
                          decoration: const InputDecoration(
                            labelText: 'State',
                            border: OutlineInputBorder(),
                          ),
                          items: const ['raw', 'cooked', 'prepared', 'leftover', 'frozen']
                              .map((s) => DropdownMenuItem(value: s, child: Text(s)))
                              .toList(),
                          onChanged: (value) {
                            setModalState(() {
                              state = value ?? 'raw';
                            });
                          },
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Expiry date'),
                    subtitle: Text(() {
                      final e = expiry;
                      if (e == null) return 'Not set';
                      return '${e.year.toString().padLeft(4, '0')}-${e.month.toString().padLeft(2, '0')}-${e.day.toString().padLeft(2, '0')}';
                    }()),
                    trailing: Wrap(
                      spacing: 8,
                      children: [
                        TextButton(
                          onPressed: expiry == null
                              ? null
                              : () {
                                  setModalState(() {
                                    expiry = null;
                                  });
                                },
                          child: const Text('Clear'),
                        ),
                        FilledButton.tonal(
                          onPressed: () async {
                            final initial = expiry ?? DateTime.now().add(const Duration(days: 3));
                            final picked = await showDatePicker(
                              context: context,
                              initialDate: initial,
                              firstDate: DateTime.now().subtract(const Duration(days: 1)),
                              lastDate: DateTime.now().add(const Duration(days: 365)),
                            );
                            if (picked != null) {
                              setModalState(() {
                                expiry = picked;
                              });
                            }
                          },
                          child: const Text('Set'),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: notesController,
                    minLines: 2,
                    maxLines: 4,
                    decoration: const InputDecoration(
                      labelText: 'Notes (optional)',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 12),
                  CheckboxListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Use for recipe generation'),
                    subtitle: const Text('If unchecked, this item is ignored for planning.'),
                    value: isCurrent,
                    onChanged: (value) {
                      setModalState(() {
                        isCurrent = value ?? true;
                      });
                    },
                  ),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton(
                          onPressed: () => Navigator.pop(context),
                          child: const Text('Cancel'),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: FilledButton(
                          onPressed: () async {
                            final display = nameController.text.trim();
                            if (display.isEmpty) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(content: Text('Name cannot be empty.')),
                              );
                              return;
                            }
                            final updates = <String, dynamic>{
                              'display_name': display,
                              'canonical_name': _canonicalizeName(display),
                              'category': categoryController.text.trim().isEmpty ? null : categoryController.text.trim(),
                              'quantity': qty,
                              'unit': unit,
                              'storage_location': storage,
                              'item_state': state,
                              'notes': notesController.text.trim().isEmpty ? null : notesController.text.trim(),
                              'is_current': isCurrent,
                            };
                            if (expiry != null) {
                              updates['expiry_date'] = '${expiry!.year.toString().padLeft(4, '0')}-${expiry!.month.toString().padLeft(2, '0')}-${expiry!.day.toString().padLeft(2, '0')}';
                            } else {
                              updates['expiry_date'] = null;
                            }

                            try {
                              final apiClient = Provider.of<ApiClient>(context, listen: false);
                              await apiClient.patch('/inventory-db/items/${item.inventoryId}', updates);
                              if (!context.mounted) return;
                              Navigator.pop(context);
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(content: Text('Item updated.')),
                              );
                              await _loadInventory();
                            } catch (e) {
                              if (!context.mounted) return;
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(content: Text('Failed to update item: $e')),
                              );
                            }
                          },
                          child: const Text('Save'),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }

  void _showAddItemDialog() {
    final nameController = TextEditingController();
    final categoryController = TextEditingController();
    final quantityController = TextEditingController();
    final unitController = TextEditingController();
    String selectedStorage = 'fridge';
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
                controller: categoryController,
                decoration: const InputDecoration(labelText: 'Category (optional)'),
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
                items: ['pantry', 'fridge', 'freezer', 'counter']
                    .map((s) => DropdownMenuItem(value: s, child: Text(s)))
                    .toList(),
                onChanged: (value) {
                  selectedStorage = value ?? 'fridge';
                },
              ),
              DropdownButtonFormField<String>(
                value: selectedState,
                decoration: const InputDecoration(labelText: 'State'),
                items: ['raw', 'cooked', 'prepared', 'leftover', 'frozen']
                    .map((s) => DropdownMenuItem(value: s, child: Text(s)))
                    .toList(),
                onChanged: (value) {
                  selectedState = value ?? 'raw';
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
                'category': categoryController.text.trim().isEmpty ? null : categoryController.text.trim(),
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
    final duplicateGroups = _findDuplicateGroups();
    final expiring = _items.where((i) => i.isExpiringSoon).toList();
    final notExpiring = _items.where((i) => !i.isExpiringSoon).toList();
    notExpiring.sort((a, b) => a.displayLabel.toLowerCase().compareTo(b.displayLabel.toLowerCase()));

    final Map<String, List<InventoryItem>> byStorage = {
      'pantry': [],
      'fridge': [],
      'freezer': [],
      'counter': [],
    };
    for (final item in notExpiring) {
      final storage = byStorage.containsKey(item.storage) ? item.storage : 'pantry';
      byStorage[storage]!.add(item);
    }

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
                if (result != null && result is List<String>) {
                  if (!context.mounted) return;
                  await _saveRealtimeScanResults(result);
                }
              } else if (value == 'barcode' && !kIsWeb) {
                final added = await Navigator.push<bool>(
                  context,
                  MaterialPageRoute(
                    builder: (_) => const BarcodeScanScreen(),
                  ),
                );
                if (added == true) {
                  if (!context.mounted) return;
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
                  if (!context.mounted) return;
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
              if (!kIsWeb)
                const PopupMenuItem(
                  value: 'barcode',
                  child: Row(
                    children: [
                      Icon(Icons.qr_code_scanner),
                      SizedBox(width: 8),
                      Text('Barcode Scan'),
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
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    Card(
                      elevation: 0,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                        side: BorderSide(color: Colors.grey.shade200),
                      ),
                      child: SwitchListTile(
                        title: const Text('Show previous (inactive) items'),
                        subtitle: const Text('Lets you re-activate older scan results.'),
                        value: _showInactiveItems,
                        onChanged: (value) async {
                          setState(() => _showInactiveItems = value);
                          await _loadInventory();
                        },
                      ),
                    ),
                    const SizedBox(height: 12),
                    if (duplicateGroups.isNotEmpty)
                      MaterialBanner(
                        content: Text(
                          'Duplicates found (${duplicateGroups.length}). Merge to improve accuracy.',
                        ),
                        actions: [
                          TextButton(
                            onPressed: _mergingDuplicates ? null : _showMergeDuplicatesDialog,
                            child: _mergingDuplicates
                                ? const SizedBox(
                                    width: 16,
                                    height: 16,
                                    child: CircularProgressIndicator(strokeWidth: 2),
                                  )
                                : const Text('Merge'),
                          ),
                        ],
                      ),
                    if (expiring.isNotEmpty) ...[
                      Padding(
                        padding: const EdgeInsets.only(top: 8, bottom: 8),
                        child: Text(
                          'Expiring soon',
                          style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                        ),
                      ),
                      ...expiring.map((item) => _InventoryCard(
                            item: item,
                            prettyName: _prettyName,
                            onEdit: () => _showEditItemSheet(item),
                            onDelete: () => _deleteItem(item.inventoryId),
                            onUse: item.isCurrent ? null : () => _setItemCurrent(item, true),
                          )),
                      const SizedBox(height: 8),
                    ],
                    Padding(
                      padding: const EdgeInsets.only(top: 8, bottom: 8),
                      child: Text(
                        'All items',
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                      ),
                    ),
                    ..._storageOptions.expand((storage) {
                      final items = byStorage[storage] ?? const <InventoryItem>[];
                      if (items.isEmpty) return const <Widget>[];
                      final title = storage[0].toUpperCase() + storage.substring(1);
                      return <Widget>[
                        Padding(
                          padding: const EdgeInsets.only(top: 8, bottom: 8),
                          child: Text(
                            title,
                            style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.bold),
                          ),
                        ),
                        ...items.map((item) => _InventoryCard(
                              item: item,
                              prettyName: _prettyName,
                              onEdit: () => _showEditItemSheet(item),
                              onDelete: () => _deleteItem(item.inventoryId),
                              onUse: item.isCurrent ? null : () => _setItemCurrent(item, true),
                            )),
                      ];
                    }),
                  ],
                ),
      floatingActionButton: Column(
        mainAxisAlignment: MainAxisAlignment.end,
        children: [
          FloatingActionButton(
            heroTag: 'manual_entry_btn',
            onPressed: () async {
              final result = await Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => const ManualEntryScreen(),
                ),
              );
              if (result == true) {
                _loadInventory(); // Reload inventory after adding
              }
            },
            backgroundColor: const Color(0xFF4CAF50),
            child: const Icon(Icons.edit),
            tooltip: 'Add manually',
          ),
          const SizedBox(height: 12),
          FloatingActionButton(
            heroTag: 'scan_btn',
            onPressed: _showAddItemDialog,
            child: const Icon(Icons.add),
            tooltip: 'Add item',
          ),
        ],
      ),
    );
  }
}

class _NormalizedCandidate {
  final TextEditingController nameController;
  double quantity;
  String unit;
  String storage;
  final String state;
  final double? scanConfidence;
  bool include = true;

  _NormalizedCandidate({
    required this.nameController,
    required this.quantity,
    required this.unit,
    required this.storage,
    required this.state,
    required this.scanConfidence,
  });
}

class _InventoryCard extends StatelessWidget {
  final InventoryItem item;
  final String Function(String raw) prettyName;
  final VoidCallback onEdit;
  final VoidCallback onDelete;
  final VoidCallback? onUse;

  const _InventoryCard({
    required this.item,
    required this.prettyName,
    required this.onEdit,
    required this.onDelete,
    this.onUse,
  });

  String _formatQty(double qty) {
    if (qty == qty.roundToDouble()) return qty.toInt().toString();
    return qty
        .toStringAsFixed(2)
        .replaceAll(RegExp(r'0+$'), '')
        .replaceAll(RegExp(r'\.$'), '');
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final freshness = item.freshnessDaysRemaining;
    final showExpiryChip = freshness != null;

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      color: item.isExpiringSoon ? Colors.orange[50] : null,
      child: ListTile(
        onTap: onEdit,
        leading: CircleAvatar(
          backgroundColor: item.isExpiringSoon
              ? Colors.orange
              : item.isLeftover
                  ? Colors.blue
                  : Colors.green,
          child: Icon(
            item.isLeftover ? Icons.restaurant : Icons.inventory,
            color: Colors.white,
          ),
        ),
        title: Row(
          children: [
            Expanded(child: Text(prettyName(item.displayLabel))),
            if (!item.isCurrent)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.grey.shade200,
                  borderRadius: BorderRadius.circular(999),
                ),
                child: const Text('Inactive', style: TextStyle(fontSize: 12)),
              ),
          ],
        ),
        subtitle: Text(
          '${_formatQty(item.quantity)} ${item.unit} • ${item.storage}',
        ),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (onUse != null)
              TextButton(
                onPressed: onUse,
                child: const Text('Use'),
              ),
            if (showExpiryChip)
              Padding(
                padding: const EdgeInsets.only(right: 8),
                child: Chip(
                  label: Text(
                    '${freshness}d',
                    style: theme.textTheme.labelSmall?.copyWith(color: Colors.white) ??
                        const TextStyle(fontSize: 12, color: Colors.white),
                  ),
                  backgroundColor: item.isExpiringSoon ? Colors.orange : Colors.grey,
                ),
              ),
            IconButton(
              icon: const Icon(Icons.edit_outlined),
              onPressed: onEdit,
              tooltip: 'Edit',
            ),
            IconButton(
              icon: const Icon(Icons.delete, color: Colors.red),
              onPressed: onDelete,
              tooltip: 'Delete',
            ),
          ],
        ),
      ),
    );
  }
}
