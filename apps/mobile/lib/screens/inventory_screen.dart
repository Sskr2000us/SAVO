import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../ui/ui_principles.dart';
import '../services/api_client.dart';
import '../models/inventory.dart';
import '../models/profile_state.dart';
import '../widgets/quantity_picker.dart';
import 'scan_ingredients_screen.dart';
import 'pantry/manual_entry_screen.dart';
import 'barcode_scan_screen.dart';
import 'scanning/continuous_camera_screen.dart';  // Use new continuous scanning

class InventoryScreen extends StatefulWidget {
  const InventoryScreen({super.key});

  @override
  State<InventoryScreen> createState() => _InventoryScreenState();
}
class _InventoryThumb extends StatelessWidget {
  const _InventoryThumb({required this.imageUrl});

  final String? imageUrl;

  @override
  Widget build(BuildContext context) {
    final url = (imageUrl ?? '').trim();
    if (url.isEmpty) {
      return CircleAvatar(
        backgroundColor: Colors.grey.shade200,
        child: const Icon(Icons.inventory_2_outlined, color: Colors.black54),
      );
    }

    return CircleAvatar(
      backgroundColor: Colors.grey.shade200,
      backgroundImage: NetworkImage(url),
      onBackgroundImageError: (_, __) {},
      child: const SizedBox.shrink(),
    );
  }
}

class _InventoryScreenState extends State<InventoryScreen> {
  final Set<String> _uploadingImageIds = <String>{};
  List<InventoryItem> _items = [];
  bool _loading = true;
  bool _mergingDuplicates = false;

  bool _showInactiveItems = false;

  String? _selectedCuisine;

  static const String _prefsShowInactiveKey = 'savo.inventory.show_inactive_items';

  static const List<String> _storageOptions = ['pantry', 'fridge', 'freezer', 'counter'];

  static const List<String> _cuisineOptions = [
    'indian',
    'italian',
    'mexican',
    'middle_east',
    'south_east_asian',
    'global',
  ];

  String? _suggestCuisineFromName(String rawName) {
    final key = _canonicalizeName(rawName);
    if (key.isEmpty) return null;

    final tokens = key.split('_').where((t) => t.trim().isNotEmpty).toList(growable: false);

    bool _hasToken(String t) => tokens.contains(t);
    bool _hasAnyToken(Set<String> any) => tokens.any(any.contains);
    bool _startsWithAny(Set<String> prefixes) => prefixes.any((p) => key.startsWith(p));

    // Indian
    const indian = <String>{
      'paneer',
      'curd',
      'hung_curd',
      'buttermilk',
      'ghee',
      'basmati_rice',
      'idli_rice',
      'poha',
      'toor_dal',
      'moong_dal',
      'masoor_dal',
      'urad_dal',
      'chana_dal',
      'besan',
      'asafoetida',
      'kasuri_methi',
      'garam_masala',
      'sambar_powder',
      'rasam_powder',
      'biryani_masala',
      'pav_bhaji_masala',
      'chai_masala',
      'tandoori_masala',
      'chana_masala',
      'chaat_masala',
      'kitchen_king_masala',
      'curry_leaves',
      'tamarind_pulp',
      'jaggery',
    };
    if (indian.contains(key)) return 'indian';

    // Common variants: "paneer cubes", "urad dal", "garam masala" etc.
    if (_startsWithAny({'paneer'}) || _hasToken('paneer')) return 'indian';
    if (_hasAnyToken({'toor', 'moong', 'masoor', 'urad', 'chana'}) && _hasToken('dal')) return 'indian';
    if (_hasToken('garam') && _hasToken('masala')) return 'indian';
    if (_hasToken('sambar') && _hasToken('powder')) return 'indian';
    if (_hasToken('rasam') && _hasToken('powder')) return 'indian';
    if (_hasToken('biryani') && _hasToken('masala')) return 'indian';
    if (_hasToken('tandoori') && _hasToken('masala')) return 'indian';
    if (_hasToken('chaat') && _hasToken('masala')) return 'indian';
    if (_hasToken('kitchen') && _hasToken('king')) return 'indian';

    // Italian
    const italian = <String>{
      'parmesan',
      'pecorino',
      'burrata',
      'mozzarella',
      'ricotta',
      'mascarpone',
      'pesto',
      'marinara_sauce',
      'arrabbiata_sauce',
      'alfredo_sauce',
      'lasagna_sheets',
      'spaghetti',
      'penne',
      'fusilli',
      'farfalle',
      'rigatoni',
      'linguine',
      'fettuccine',
      'tagliatelle',
      'orzo',
      'gnocchi',
      '00_flour',
      'balsamic_vinegar',
    };
    if (italian.contains(key)) return 'italian';

    // Common variants: "parmigiano reggiano", "parmesan grated", "pasta penne".
    if (_hasAnyToken({'parmigiano', 'reggiano'})) return 'italian';
    if (_startsWithAny({'parmesan'}) || _hasToken('parmesan')) return 'italian';
    if (_hasToken('pasta') && _hasAnyToken({'spaghetti', 'penne', 'fusilli', 'farfalle', 'rigatoni', 'linguine', 'fettuccine', 'tagliatelle', 'orzo', 'gnocchi'})) {
      return 'italian';
    }

    // Mexican
    const mexican = <String>{
      'masa_harina',
      'corn_tortillas',
      'flour_tortillas',
      'taco_shells',
      'tostadas',
      'tortilla_chips',
      'nachos',
      'jalapeno',
      'chipotle_powder',
      'ancho_chili_powder',
      'guajillo_chili_powder',
      'canned_chipotle_in_adobo',
      'taco_seasoning',
      'fajita_seasoning',
      'adobo_seasoning',
      'salsa',
      'pico_de_gallo',
      'guacamole',
      'tomatillo',
      'canned_tomatillos',
    };
    if (mexican.contains(key)) return 'mexican';

    // Common variants: "corn tortilla", "tortilla wraps", "chipotle in adobo".
    if (_hasAnyToken({'tortilla', 'tortillas', 'tostada', 'tostadas'})) return 'mexican';
    if (_hasToken('masa') && (_hasToken('harina') || _hasToken('corn'))) return 'mexican';
    if (_hasAnyToken({'jalapeno', 'tomatillo', 'chipotle', 'guajillo', 'ancho'})) return 'mexican';
    if (_hasToken('adobo') && _hasToken('chipotle')) return 'mexican';

    // Middle East / MENA
    const middleEast = <String>{
      'tahini',
      'zaatar',
      'dukkah',
      'ras_el_hanout',
      'baharat',
      'sumac',
      'pomegranate_molasses',
      'labneh',
      'halloumi',
      'bulgur_fine',
      'bulgur_coarse',
      'freekeh',
      'harissa',
      'orange_blossom_water',
      'rose_water',
    };
    if (middleEast.contains(key)) return 'middle_east';

    // Common variants: "za'atar", "bulgur wheat", "falafel frozen".
    if (_hasAnyToken({'tahini', 'zaatar', 'dukkah', 'baharat', 'sumac', 'labneh', 'halloumi', 'bulgur', 'freekeh', 'harissa'})) {
      return 'middle_east';
    }
    if (_hasToken('falafel')) return 'middle_east';

    // South East Asian
    const sea = <String>{
      'lemongrass',
      'galangal',
      'thai_basil',
      'thai_chili',
      'birdseye_chili',
      'fish_sauce',
      'oyster_sauce',
      'rice_paper',
      'pho_noodles',
      'rice_vermicelli',
      'glass_noodles',
      'curry_paste_green',
      'curry_paste_red',
      'curry_paste_yellow',
      'jasmine_rice',
      'sticky_rice',
    };
    if (sea.contains(key)) return 'south_east_asian';

    // Common variants: "rice paper wrappers", "fish sauce", "pho noodles".
    if (_hasAnyToken({'lemongrass', 'galangal'})) return 'south_east_asian';
    if (_hasToken('fish') && _hasToken('sauce')) return 'south_east_asian';
    if (_hasToken('rice') && _hasToken('paper')) return 'south_east_asian';
    if (_hasToken('pho') && _hasAnyToken({'noodles', 'noodle'})) return 'south_east_asian';
    if (_hasAnyToken({'vermicelli', 'glass'}) && _hasAnyToken({'noodles', 'noodle'})) return 'south_east_asian';

    return null;
  }

  // Storage -> Category -> Subcategories
  static const Map<String, Map<String, List<String>>> _inventoryTaxonomy = {
    'fridge': {
      'vegetables': ['leafy', 'root', 'cruciferous', 'other'],
      'fruits': ['berries', 'citrus', 'tropical', 'other'],
      'dairy': ['milk', 'cheese', 'yogurt', 'butter', 'other'],
      'proteins': ['eggs', 'paneer', 'meat', 'fish', 'other'],
      'condiments': ['sauces', 'pickles', 'spreads', 'other'],
      'beverages': ['juice', 'soft_drinks', 'other'],
      'leftovers': ['cooked', 'prepared', 'other'],
    },
    'pantry': {
      'grains': ['rice', 'millets', 'wheat', 'oats', 'other'],
      'pulses': ['lentils', 'beans', 'chickpeas', 'other'],
      'flours': ['wheat_flour', 'rice_flour', 'besan', 'other'],
      'spices': ['whole', 'powdered', 'blends', 'other'],
      'powders': ['baking', 'protein', 'other'],
      'oils': ['cooking_oils', 'ghee', 'vinegar', 'other'],
      'snacks': ['chips', 'biscuits', 'nuts', 'other'],
      'canned': ['vegetables', 'beans', 'fish', 'other'],
      'baking': ['sugar', 'baking_powder', 'cocoa', 'other'],
    },
    'freezer': {
      'frozen_vegetables': ['mixed', 'leafy', 'other'],
      'frozen_fruits': ['berries', 'other'],
      'meat_seafood': ['meat', 'fish', 'other'],
      'prepared_meals': ['leftovers', 'ready_to_cook', 'other'],
      'desserts': ['ice_cream', 'other'],
    },
    'counter': {
      'produce': ['fruits', 'vegetables', 'other'],
      'breads': ['bread', 'buns', 'other'],
      'snacks': ['chips', 'biscuits', 'nuts', 'other'],
      'other': ['other'],
    },
  };

  static String? _cleanOptional(String? raw) {
    final trimmed = raw?.trim();
    if (trimmed == null || trimmed.isEmpty) return null;
    return trimmed;
  }

  List<String> _categoryOptionsForStorage(String storage, {String? includeValue}) {
    final categories = (_inventoryTaxonomy[storage]?.keys.toList() ?? <String>[]);
    if (includeValue != null && includeValue.trim().isNotEmpty && !categories.contains(includeValue)) {
      categories.add(includeValue);
    }
    categories.sort();
    return categories;
  }

  List<String> _subcategoryOptionsFor(String storage, String category, {String? includeValue}) {
    final subcategories = List<String>.from(_inventoryTaxonomy[storage]?[category] ?? const <String>[]);
    if (includeValue != null && includeValue.trim().isNotEmpty && !subcategories.contains(includeValue)) {
      subcategories.add(includeValue);
    }
    subcategories.sort();
    return subcategories;
  }

  Future<void> _saveRealtimeScanResults(List<String> ingredients) async {
    if (ingredients.isEmpty) return;

    setState(() => _loading = true);
    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final profileState = Provider.of<ProfileState>(context, listen: false);

      final rawLang = (profileState.preferredLanguage?.trim().isNotEmpty == true)
          ? profileState.preferredLanguage!.trim()
          : (profileState.primaryLanguage?.trim().isNotEmpty == true)
              ? profileState.primaryLanguage!.trim()
              : Localizations.localeOf(context).languageCode;
      final outputLang = rawLang.trim().toLowerCase().split(RegExp('[-_]')).first;

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
        'output_language': outputLang.isNotEmpty ? outputLang : 'en',
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
    final Map<_NormalizedCandidate, String?> candidateCuisine = {};
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
      final cuisine = (json['cuisine'] == null) ? null : json['cuisine'].toString().trim();
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
      candidateCuisine[candidates.last] = (cuisine != null && cuisine.isNotEmpty) ? cuisine : null;
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
                          'cuisine': candidateCuisine[c],
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
    _init();
  }

  Future<void> _init() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final saved = prefs.getBool(_prefsShowInactiveKey);
      if (saved != null && mounted) {
        setState(() => _showInactiveItems = saved);
      }
    } catch (_) {
      // Best-effort only; defaults to false.
    }

    await _loadInventory();
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

  List<List<InventoryItem>> _findDuplicateGroups([List<InventoryItem>? items]) {
    final Map<String, List<InventoryItem>> groups = {};
    for (final item in (items ?? _items)) {
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

              final category = (group.first.category ?? '').trim();
              final subcategory = (group.first.subcategory ?? '').trim();
              final cuisine = (group.first.cuisine ?? '').trim();
              final expiry = group
                  .map((i) => i.expiryDate)
                  .whereType<DateTime>()
                  .fold<DateTime?>(null, (min, d) => min == null || d.isBefore(min) ? d : min);

              String formatDate(DateTime d) =>
                  '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

              final taxonomyLabel = () {
                if (category.isEmpty && subcategory.isEmpty) return 'Category: Uncategorized';
                if (category.isNotEmpty && subcategory.isNotEmpty) {
                  return 'Category: ${_prettyName(category)} / ${_prettyName(subcategory)}';
                }
                if (category.isNotEmpty) return 'Category: ${_prettyName(category)}';
                return 'Category: ${_prettyName(subcategory)}';
              }();

              final subtitleParts = <String>[
                '${group.length} items',
                if (sameUnit) '${total.toStringAsFixed(2).replaceAll(RegExp(r'0+$'), '').replaceAll(RegExp(r'\.$'), '')} ${group.first.unit}',
              ];
              final metaParts = <String>[
                taxonomyLabel,
                'Expiry: ${expiry == null ? '—' : formatDate(expiry)}',
                if (cuisine.isNotEmpty) 'Cuisine: ${_prettyName(cuisine)}',
              ];
              return ListTile(
                title: Text(name),
                subtitle: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(subtitleParts.join(' • ')),
                    const SizedBox(height: 2),
                    Text(metaParts.join(' • '), style: Theme.of(context).textTheme.bodySmall),
                  ],
                ),
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
    final notesController = TextEditingController(text: item.notes ?? '');

    String? category = _cleanOptional(item.category);
    String? subcategory = _cleanOptional(item.subcategory);
    String? cuisine = _cleanOptional(item.cuisine);
    bool cuisineTouched = false;

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

                      if (!cuisineTouched && (cuisine?.trim().isEmpty ?? true)) {
                        final suggested = _suggestCuisineFromName(nameController.text);
                        if (suggested != null) {
                          cuisine = suggested;
                        }
                      }
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
                  DropdownButtonFormField<String>(
                    value: category,
                    decoration: const InputDecoration(
                      labelText: 'Category (optional)',
                      border: OutlineInputBorder(),
                    ),
                    items: _categoryOptionsForStorage(storage, includeValue: category)
                        .map((c) => DropdownMenuItem(value: c, child: Text(_prettyName(c))))
                        .toList(),
                    onChanged: (value) {
                      setModalState(() {
                        category = value;
                        // Reset subcategory when category changes.
                        subcategory = null;
                      });
                    },
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    value: subcategory,
                    decoration: const InputDecoration(
                      labelText: 'Subcategory (optional)',
                      border: OutlineInputBorder(),
                    ),
                    items: (category == null)
                        ? const <DropdownMenuItem<String>>[]
                        : _subcategoryOptionsFor(storage, category!, includeValue: subcategory)
                            .map((sc) => DropdownMenuItem(value: sc, child: Text(_prettyName(sc))))
                            .toList(),
                    onChanged: (category == null)
                        ? null
                        : (value) {
                            setModalState(() {
                              subcategory = value;
                            });
                          },
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    value: cuisine,
                    decoration: const InputDecoration(
                      labelText: 'Cuisine (optional)',
                      border: OutlineInputBorder(),
                    ),
                    items: [
                      const DropdownMenuItem<String>(value: null, child: Text('None')),
                      ..._cuisineOptions.map((c) => DropdownMenuItem(value: c, child: Text(_prettyName(c)))),
                    ],
                    onChanged: (value) {
                      setModalState(() {
                        cuisine = value;
                        cuisineTouched = true;
                      });
                    },
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

                              // If the chosen category isn't valid for this storage, clear it.
                              final validCategories = _categoryOptionsForStorage(storage);
                              if (category != null && !validCategories.contains(category)) {
                                category = null;
                                subcategory = null;
                              }
                              if (category != null) {
                                final validSubcategories = _subcategoryOptionsFor(storage, category!);
                                if (subcategory != null && !validSubcategories.contains(subcategory)) {
                                  subcategory = null;
                                }
                              }
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
                              if (!mounted) return;
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(content: Text('Expiry date selected. Tap Save to persist.')),
                              );
                            }
                          },
                          child: Text(expiry == null ? 'Pick' : 'Change'),
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
                              'category': _cleanOptional(category),
                              'subcategory': _cleanOptional(subcategory),
                              'cuisine': _cleanOptional(cuisine),
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
    final rootContext = context;
    final nameController = TextEditingController();
    final quantityController = TextEditingController();
    final unitController = TextEditingController();
    String selectedStorage = 'fridge';
    String selectedState = 'raw';
    String? category;
    String? subcategory;
    String? cuisine;
    bool cuisineTouched = false;

    showDialog(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              title: const Text('Add Item'),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    TextField(
                      controller: nameController,
                      decoration: const InputDecoration(labelText: 'Name'),
                      onChanged: (_) {
                        if (!cuisineTouched && (cuisine?.trim().isEmpty ?? true)) {
                          final suggested = _suggestCuisineFromName(nameController.text);
                          if (suggested != null) {
                            setDialogState(() {
                              cuisine = suggested;
                            });
                          }
                        }
                      },
                    ),
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String>(
                      value: category,
                      decoration: const InputDecoration(
                        labelText: 'Category (optional)',
                        border: OutlineInputBorder(),
                      ),
                      items: _categoryOptionsForStorage(selectedStorage, includeValue: category)
                          .map((c) => DropdownMenuItem(value: c, child: Text(_prettyName(c))))
                          .toList(),
                      onChanged: (value) {
                        setDialogState(() {
                          category = value;
                          subcategory = null;
                        });
                      },
                    ),
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String>(
                      value: subcategory,
                      decoration: const InputDecoration(
                        labelText: 'Subcategory (optional)',
                        border: OutlineInputBorder(),
                      ),
                      items: (category == null)
                          ? const <DropdownMenuItem<String>>[]
                          : _subcategoryOptionsFor(selectedStorage, category!, includeValue: subcategory)
                              .map((sc) => DropdownMenuItem(value: sc, child: Text(_prettyName(sc))))
                              .toList(),
                      onChanged: (category == null)
                          ? null
                          : (value) {
                              setDialogState(() {
                                subcategory = value;
                              });
                            },
                    ),
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String>(
                      value: cuisine,
                      decoration: const InputDecoration(
                        labelText: 'Cuisine (optional)',
                        border: OutlineInputBorder(),
                      ),
                      items: [
                        const DropdownMenuItem<String>(value: null, child: Text('None')),
                        ..._cuisineOptions.map((c) => DropdownMenuItem(value: c, child: Text(_prettyName(c)))),
                      ],
                      onChanged: (value) {
                        setDialogState(() {
                          cuisine = value;
                          cuisineTouched = true;
                        });
                      },
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: quantityController,
                      decoration: const InputDecoration(labelText: 'Quantity'),
                      keyboardType: TextInputType.number,
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: unitController,
                      decoration: const InputDecoration(labelText: 'Unit'),
                    ),
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String>(
                      value: selectedStorage,
                      decoration: const InputDecoration(labelText: 'Storage'),
                      items: _storageOptions.map((s) => DropdownMenuItem(value: s, child: Text(s))).toList(),
                      onChanged: (value) {
                        setDialogState(() {
                          selectedStorage = value ?? 'fridge';
                          final validCategories = _categoryOptionsForStorage(selectedStorage);
                          if (category != null && !validCategories.contains(category)) {
                            category = null;
                            subcategory = null;
                          }
                          if (category != null) {
                            final validSubcategories = _subcategoryOptionsFor(selectedStorage, category!);
                            if (subcategory != null && !validSubcategories.contains(subcategory)) {
                              subcategory = null;
                            }
                          }
                        });
                      },
                    ),
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String>(
                      value: selectedState,
                      decoration: const InputDecoration(labelText: 'State'),
                      items: const ['raw', 'cooked', 'prepared', 'leftover', 'frozen']
                          .map((s) => DropdownMenuItem(value: s, child: Text(s)))
                          .toList(),
                      onChanged: (value) {
                        setDialogState(() {
                          selectedState = value ?? 'raw';
                        });
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
                    final display = nameController.text.trim();
                    if (display.isEmpty) {
                      if (!context.mounted) return;
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Name cannot be empty.')),
                      );
                      return;
                    }

                    // Manual add is allowed without an image, but we should nudge the user.
                    if (rootContext.mounted) {
                      ScaffoldMessenger.of(rootContext).showSnackBar(
                        const SnackBar(
                          content: Text('Tip: Add an image for better recognition (you can add it later from Pantry).'),
                        ),
                      );
                    }

                    final item = {
                      'canonical_name': _canonicalizeName(display),
                      'display_name': display,
                      'category': _cleanOptional(category),
                      'subcategory': _cleanOptional(subcategory),
                      'cuisine': _cleanOptional(cuisine),
                      'quantity': double.tryParse(quantityController.text) ?? 1.0,
                      'unit': unitController.text,
                      'storage_location': selectedStorage, // Match database field name
                      'item_state': selectedState, // Match database field name
                    };

                    try {
                      final apiClient = Provider.of<ApiClient>(context, listen: false);
                      await apiClient.post('/inventory-db/items', item);
                      if (!context.mounted) return;
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
            );
          },
        );
      },
    );
  }

  Future<void> _showImagePreview(String imageUrl) async {
    final url = imageUrl.trim();
    if (url.isEmpty) return;
    await showDialog<void>(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: const Text('Item image'),
          content: ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: Image.network(
              url,
              fit: BoxFit.cover,
              errorBuilder: (_, __, ___) {
                return Container(
                  height: 200,
                  width: 300,
                  color: Colors.grey.shade100,
                  alignment: Alignment.center,
                  child: const Text('Image unavailable'),
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
        );
      },
    );
  }

  Future<void> _captureAndAttachImage(InventoryItem item) async {
    if (_uploadingImageIds.contains(item.inventoryId)) return;

    if (kIsWeb) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Adding images is best done on mobile (camera upload not available on web).')),
      );
      return;
    }

    setState(() => _uploadingImageIds.add(item.inventoryId));
    try {
      final picker = ImagePicker();
      final XFile? photo = await picker.pickImage(
        source: ImageSource.camera,
        maxWidth: 1920,
        maxHeight: 1080,
        imageQuality: 85,
      );
      if (photo == null) return;

      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final uploadRes = await apiClient.postMultipart(
        '/inventory-db/upload-image',
        file: photo,
        fieldName: 'image',
      );
      final url = (uploadRes['image_url'] ?? '').toString().trim();
      if (url.isEmpty) {
        throw Exception('Upload succeeded but image_url missing');
      }

      await apiClient.patch('/inventory-db/items/${item.inventoryId}', {
        'image_url': url,
      });

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Image saved.')),
      );
      await _loadInventory();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to save image: $e')),
      );
    } finally {
      if (mounted) {
        setState(() => _uploadingImageIds.remove(item.inventoryId));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    if (kDebugMode || kProfileMode) {
      // v1: maxChoices=3. Inventory scan entry exposes <= 3 scan modes.
      // (Realtime + barcode are hidden on web.)
      SavoUiGuards.warnIfTooManyChoices(
        screen: 'InventoryScreen',
        surface: 'Scan menu',
        choices: kIsWeb ? 1 : 3,
      );

      // v1: mandatory AI confirmation. Realtime scan always normalizes and
      // shows an explicit review dialog before any inventory write.
      SavoUiGuards.warnIfAiConfirmationNotExplicit(
        flow: 'SnapPantry',
        surface: 'Review before save (realtime/photo/barcode)',
        hasExplicitReviewStep: true,
      );
    }

    final filteredItems = (_selectedCuisine == null)
      ? _items
      : _items.where((i) => (i.cuisine ?? '').trim() == _selectedCuisine).toList();

    final duplicateGroups = _findDuplicateGroups(filteredItems);
    final expiring = filteredItems.where((i) => i.isExpiringSoon).toList();
    final notExpiring = filteredItems.where((i) => !i.isExpiringSoon).toList();
    notExpiring.sort((a, b) => a.displayLabel.toLowerCase().compareTo(b.displayLabel.toLowerCase()));

    final cuisineOptions = filteredItems.isEmpty
      ? _cuisineOptions
      : (() {
        final present = filteredItems
          .map((i) => (i.cuisine ?? '').trim())
          .where((c) => c.isNotEmpty)
          .toSet()
          .toList();
        present.sort((a, b) => a.toLowerCase().compareTo(b.toLowerCase()));
        return present;
        })();

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
                // Use new continuous camera scanning
                result = await Navigator.push<List<Map<String, dynamic>>>(
                  context,
                  MaterialPageRoute(
                    builder: (_) => const ContinuousCameraScanScreen(),
                  ),
                );
                if (result != null && result is List) {
                  // Items are already saved to backend by continuous scanner
                  // Just reload inventory
                  if (!context.mounted) return;
                  await _loadInventory();
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('Added ${result.length} items to inventory')),
                  );
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
              } else if (value == 'video30' && !kIsWeb) {
                final added = await Navigator.push<bool>(
                  context,
                  MaterialPageRoute(
                    builder: (_) => const ScanIngredientsScreen(autoStartVideoScan: true),
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
                  value: 'video30',
                  child: Row(
                    children: [
                      Icon(Icons.video_camera_back_outlined),
                      SizedBox(width: 8),
                      Text('Video Scan (30s)'),
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

                          // Persist so it doesn't reset on refresh/navigation.
                          try {
                            final prefs = await SharedPreferences.getInstance();
                            await prefs.setBool(_prefsShowInactiveKey, value);
                          } catch (_) {
                            // Best-effort only
                          }

                          await _loadInventory();
                        },
                      ),
                    ),
                    const SizedBox(height: 12),
                    Card(
                      elevation: 0,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                        side: BorderSide(color: Colors.grey.shade200),
                      ),
                      child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: DropdownButtonFormField<String>(
                          value: _selectedCuisine,
                          decoration: const InputDecoration(
                            labelText: 'Cuisine filter',
                            border: OutlineInputBorder(),
                          ),
                          items: [
                            const DropdownMenuItem<String>(value: null, child: Text('All')),
                            ...cuisineOptions.map(
                              (c) => DropdownMenuItem<String>(value: c, child: Text(_prettyName(c))),
                            ),
                          ],
                          onChanged: (value) {
                            setState(() {
                              _selectedCuisine = value;
                            });
                          },
                        ),
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
                            uploadingImage: _uploadingImageIds.contains(item.inventoryId),
                            onViewImage: (url) => _showImagePreview(url),
                            onCaptureImage: () => _captureAndAttachImage(item),
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

                      // Category -> Subcategory -> Items
                      final Map<String, Map<String, List<InventoryItem>>> byCategory = {};
                      for (final item in items) {
                        final c = (item.category ?? '').trim();
                        final categoryKey = c.isEmpty ? 'uncategorized' : c;
                        final sc = (item.subcategory ?? '').trim();
                        final subKey = sc.isEmpty ? '' : sc;
                        byCategory.putIfAbsent(categoryKey, () => <String, List<InventoryItem>>{});
                        byCategory[categoryKey]!.putIfAbsent(subKey, () => <InventoryItem>[]).add(item);
                      }

                      final categories = byCategory.keys.toList();
                      categories.sort((a, b) {
                        if (a == 'uncategorized' && b != 'uncategorized') return 1;
                        if (b == 'uncategorized' && a != 'uncategorized') return -1;
                        return a.toLowerCase().compareTo(b.toLowerCase());
                      });

                      return <Widget>[
                        Padding(
                          padding: const EdgeInsets.only(top: 8, bottom: 8),
                          child: Text(
                            title,
                            style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.bold),
                          ),
                        ),
                        ...categories.expand((categoryKey) {
                          final bySubcategory = byCategory[categoryKey] ?? const <String, List<InventoryItem>>{};
                          final noSubItems = (bySubcategory[''] ?? const <InventoryItem>[]).toList();
                          noSubItems.sort((a, b) => a.displayLabel.toLowerCase().compareTo(b.displayLabel.toLowerCase()));

                          final subcats = bySubcategory.keys.where((k) => k.trim().isNotEmpty).toList();
                          subcats.sort((a, b) => a.toLowerCase().compareTo(b.toLowerCase()));

                          final widgets = <Widget>[
                            Padding(
                              padding: const EdgeInsets.only(top: 6, bottom: 6, left: 8),
                              child: Text(
                                _prettyName(categoryKey),
                                style: Theme.of(context)
                                    .textTheme
                                    .titleSmall
                                    ?.copyWith(fontWeight: FontWeight.w600),
                              ),
                            ),
                            ...noSubItems.map((item) => _InventoryCard(
                                  item: item,
                                  prettyName: _prettyName,
                                  onEdit: () => _showEditItemSheet(item),
                                  onDelete: () => _deleteItem(item.inventoryId),
                                  onUse: item.isCurrent ? null : () => _setItemCurrent(item, true),
                                  uploadingImage: _uploadingImageIds.contains(item.inventoryId),
                                  onViewImage: (url) => _showImagePreview(url),
                                  onCaptureImage: () => _captureAndAttachImage(item),
                                )),
                          ];

                          for (final subKey in subcats) {
                            final subItems = (bySubcategory[subKey] ?? const <InventoryItem>[]).toList();
                            subItems.sort((a, b) => a.displayLabel.toLowerCase().compareTo(b.displayLabel.toLowerCase()));
                            widgets.add(
                              Padding(
                                padding: const EdgeInsets.only(top: 4, bottom: 4, left: 16),
                                child: Text(
                                  _prettyName(subKey),
                                  style: Theme.of(context)
                                      .textTheme
                                      .bodySmall
                                      ?.copyWith(fontWeight: FontWeight.w500, color: Colors.grey.shade700),
                                ),
                              ),
                            );
                            widgets.addAll(
                              subItems.map((item) => _InventoryCard(
                                    item: item,
                                    prettyName: _prettyName,
                                    onEdit: () => _showEditItemSheet(item),
                                    onDelete: () => _deleteItem(item.inventoryId),
                                    onUse: item.isCurrent ? null : () => _setItemCurrent(item, true),
                                uploadingImage: _uploadingImageIds.contains(item.inventoryId),
                                onViewImage: (url) => _showImagePreview(url),
                                onCaptureImage: () => _captureAndAttachImage(item),
                                  )),
                            );
                          }

                          return widgets;
                        }),
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
  final bool uploadingImage;
  final void Function(String imageUrl)? onViewImage;
  final VoidCallback? onCaptureImage;

  const _InventoryCard({
    required this.item,
    required this.prettyName,
    required this.onEdit,
    required this.onDelete,
    this.onUse,
    this.uploadingImage = false,
    this.onViewImage,
    this.onCaptureImage,
  });

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
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final freshness = item.freshnessDaysRemaining;
    final showExpiryChip = freshness != null;

    final category = (item.category ?? '').trim();
    final subcategory = (item.subcategory ?? '').trim();
    final cuisine = (item.cuisine ?? '').trim();
    final expiry = item.expiryDate;

    final taxonomyLabel = () {
      if (category.isEmpty && subcategory.isEmpty) return 'Category: Uncategorized';
      if (category.isNotEmpty && subcategory.isNotEmpty) {
        return 'Category: ${prettyName(category)} / ${prettyName(subcategory)}';
      }
      if (category.isNotEmpty) return 'Category: ${prettyName(category)}';
      return 'Category: ${prettyName(subcategory)}';
    }();

    final metaParts = <String>[
      taxonomyLabel,
      'Expiry: ${expiry == null ? '—' : _formatDate(expiry)}',
      if (cuisine.isNotEmpty) 'Cuisine: ${prettyName(cuisine)}',
    ];

    final hasImage = (item.imageUrl ?? '').trim().isNotEmpty;

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      color: item.isExpiringSoon ? Colors.orange[50] : null,
      child: ListTile(
        onTap: onEdit,
        leading: InkWell(
          onTap: hasImage
              ? () => onViewImage?.call(item.imageUrl!.trim())
              : (onCaptureImage == null || uploadingImage)
                  ? null
                  : onCaptureImage,
          child: hasImage
              ? _InventoryThumb(imageUrl: item.imageUrl)
              : CircleAvatar(
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
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('${_formatQty(item.quantity)} ${item.unit} • ${item.storage} • ${prettyName(item.state)}'),
            const SizedBox(height: 2),
            Text(metaParts.join(' • '), style: theme.textTheme.bodySmall),
            if (!hasImage) ...[
              const SizedBox(height: 4),
              Text(
                'Image required',
                style: theme.textTheme.bodySmall?.copyWith(color: Colors.red.shade700),
              ),
            ],
          ],
        ),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (onUse != null)
              TextButton(
                onPressed: onUse,
                child: const Text('Use'),
              ),
            IconButton(
              tooltip: hasImage ? 'View image' : 'Add image',
              onPressed: uploadingImage
                  ? null
                  : hasImage
                      ? (onViewImage == null ? null : () => onViewImage!.call(item.imageUrl!.trim()))
                      : onCaptureImage,
              icon: uploadingImage
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : Icon(hasImage ? Icons.image_outlined : Icons.photo_camera_outlined),
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
