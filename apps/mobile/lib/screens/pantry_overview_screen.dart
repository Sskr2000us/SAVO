import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../models/inventory.dart';
import '../services/api_client.dart';
import '../services/waste_analytics_service.dart';
import '../theme/app_theme.dart';
import '../ui/ui_principles.dart';

String _prettyPantryToken(String raw) {
  final s = raw.trim().replaceAll('_', ' ');
  if (s.isEmpty) return s;
  return s.split(RegExp(r'\s+')).map((w) {
    if (w.isEmpty) return w;
    return w[0].toUpperCase() + w.substring(1);
  }).join(' ');
}

String _formatPantryQty(double qty) {
  if (qty == qty.roundToDouble()) return qty.toInt().toString();
  return qty
      .toStringAsFixed(2)
      .replaceAll(RegExp(r'0+$'), '')
      .replaceAll(RegExp(r'\.$'), '');
}

String _formatPantryDate(DateTime d) {
  return '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
}

class _PantryThumb extends StatelessWidget {
  const _PantryThumb({required this.imageUrl, required this.missingRequired});

  final String? imageUrl;
  final bool missingRequired;

  @override
  Widget build(BuildContext context) {
    final url = (imageUrl ?? '').trim();
    if (url.isEmpty) {
      return Container(
        width: 44,
        height: 44,
        decoration: BoxDecoration(
          color: Colors.grey.shade100,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: missingRequired ? Colors.red.shade400 : Colors.grey.shade300),
        ),
        alignment: Alignment.center,
        child: const Icon(Icons.photo_outlined, size: 18, color: Colors.grey),
      );
    }

    return ClipRRect(
      borderRadius: BorderRadius.circular(10),
      child: Image.network(
        url,
        width: 44,
        height: 44,
        fit: BoxFit.cover,
        errorBuilder: (_, __, ___) {
          return Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: Colors.grey.shade100,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: Colors.grey.shade300),
            ),
            alignment: Alignment.center,
            child: const Icon(Icons.broken_image_outlined, size: 18, color: Colors.grey),
          );
        },
      ),
    );
  }
}

class PantryOverviewScreen extends StatefulWidget {
  const PantryOverviewScreen({super.key});

  @override
  State<PantryOverviewScreen> createState() => _PantryOverviewScreenState();
}

class _PantryOverviewScreenState extends State<PantryOverviewScreen> {
  bool _loading = true;
  List<InventoryItem> _items = const [];
  bool _cleaning = false;
  final Set<String> _uploadingImageIds = <String>{};

  static const List<String> _categoryOptions = [
    'vegetables',
    'fruits',
    'dairy',
    'proteins',
    'condiments',
    'beverages',
    'leftovers',
    'grains',
    'pulses',
    'flours',
    'spices',
    'powders',
    'oils',
    'snacks',
    'canned',
    'baking',
    'frozen_vegetables',
    'frozen_fruits',
    'meat_seafood',
    'prepared_meals',
    'desserts',
    'produce',
    'breads',
    'other',
  ];

  bool _loadingWaste = true;
  WasteAnalyticsSummary? _waste;

  @override
  void initState() {
    super.initState();
    _load();
    _loadWaste();
  }

  Future<void> _loadWaste() async {
    if (mounted) {
      setState(() => _loadingWaste = true);
    }

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final service = WasteAnalyticsService();
      final summary = await service.fetchMonthly(apiClient);
      if (!mounted) return;
      setState(() {
        _waste = summary;
        _loadingWaste = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _waste = null;
        _loadingWaste = false;
      });
    }
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

  Future<void> _captureAndAttachImage(InventoryItem item) async {
    if (kIsWeb) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Capturing a package photo is not supported on web.')),
      );
      return;
    }

    if (_uploadingImageIds.contains(item.inventoryId)) return;

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
      await _load();
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

  static String? _cleanOptional(String? raw) {
    final trimmed = raw?.trim();
    if (trimmed == null || trimmed.isEmpty) return null;
    return trimmed;
  }

  Future<void> _showCategorySheet(InventoryItem item) async {
    String? category = _cleanOptional(item.category);
    final subcategoryController = TextEditingController(text: (item.subcategory ?? '').trim());

    await showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (context) {
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
              Text('Assign category', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 12),
              Text(
                item.displayLabel,
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              const SizedBox(height: 12),
              Builder(
                builder: (context) {
                  final options = <String>{..._categoryOptions, if (category != null) category!}.toList()..sort();
                  return DropdownButtonFormField<String?>(
                    initialValue: category,
                    decoration: const InputDecoration(
                      labelText: 'Category',
                      border: OutlineInputBorder(),
                    ),
                    items: [
                      const DropdownMenuItem<String?>(value: null, child: Text('Uncategorized')),
                      ...options.map((c) => DropdownMenuItem<String?>(value: c, child: Text(_prettyPantryToken(c)))),
                    ],
                    onChanged: (value) {
                      category = value;
                    },
                  );
                },
              ),
              const SizedBox(height: 12),
              TextField(
                controller: subcategoryController,
                textInputAction: TextInputAction.done,
                decoration: const InputDecoration(
                  labelText: 'Subcategory (optional)',
                  hintText: 'e.g. cheese, leafy, rice',
                  border: OutlineInputBorder(),
                ),
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
                        final cleanCategory = _cleanOptional(category);
                        final subcategory = _cleanOptional(subcategoryController.text);

                        // Allow clearing both values.
                        final updates = <String, dynamic>{
                          'category': cleanCategory,
                          'subcategory': subcategory,
                        };

                        try {
                          final apiClient = Provider.of<ApiClient>(context, listen: false);
                          await apiClient.patch('/inventory-db/items/${item.inventoryId}', updates);
                          if (!context.mounted) return;
                          Navigator.pop(context);
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('Category updated.')),
                          );
                          await _load();
                        } catch (e) {
                          if (!context.mounted) return;
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text('Failed to update category: $e')),
                          );
                        }
                      },
                      child: const Text('Save'),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
            ],
          ),
        );
      },
    );
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
                    _PantryList(
                      items: _useSoon,
                      onEditCategory: _showCategorySheet,
                      onCaptureImage: _captureAndAttachImage,
                      uploadingImageIds: _uploadingImageIds,
                      header: _WasteHeader(
                        loading: _loadingWaste,
                        summary: _waste,
                      ),
                    ),
                    _PantryList(
                      items: _available,
                      onEditCategory: _showCategorySheet,
                      onCaptureImage: _captureAndAttachImage,
                      uploadingImageIds: _uploadingImageIds,
                    ),
                    _PantryList(
                      items: _missing,
                      onEditCategory: _showCategorySheet,
                      onCaptureImage: _captureAndAttachImage,
                      uploadingImageIds: _uploadingImageIds,
                    ),
                  ],
                ),
              ),
      ),
    );
  }
}

class _PantryList extends StatelessWidget {
  final List<InventoryItem> items;
  final Widget? header;
  final Future<void> Function(InventoryItem item)? onEditCategory;
  final Future<void> Function(InventoryItem item)? onCaptureImage;
  final Set<String> uploadingImageIds;

  const _PantryList({
    required this.items,
    this.header,
    this.onEditCategory,
    this.onCaptureImage,
    this.uploadingImageIds = const <String>{},
  });

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty && header == null) {
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
      itemCount: items.length + (header != null ? 1 : 0),
      separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
      itemBuilder: (context, index) {
        if (header != null && index == 0) {
          return header!;
        }

        final realIndex = header != null ? index - 1 : index;
        if (realIndex < 0 || realIndex >= items.length) {
          return const SizedBox.shrink();
        }

        final item = items[realIndex];
        final categoryIsEmpty = (item.category ?? '').trim().isEmpty;
        final imageMissing = (item.imageUrl ?? '').trim().isEmpty;
        final uploading = uploadingImageIds.contains(item.inventoryId);
        return Card(
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: Row(
              children: [
                _FreshnessIndicator(item: item),
                const SizedBox(width: AppSpacing.md),
                InkWell(
                  borderRadius: BorderRadius.circular(10),
                  onTap: (imageMissing && onCaptureImage != null && !uploading)
                      ? () => onCaptureImage!(item)
                      : null,
                  child: _PantryThumb(imageUrl: item.imageUrl, missingRequired: imageMissing),
                ),
                const SizedBox(width: AppSpacing.md),
                _StorageIcon(item: item),
                const SizedBox(width: AppSpacing.md),
                Expanded(
                  child: Builder(
                    builder: (context) {
                      final theme = Theme.of(context);
                      final category = (item.category ?? '').trim();
                      final subcategory = (item.subcategory ?? '').trim();
                      final cuisine = (item.cuisine ?? '').trim();
                      final expiry = item.expiryDate;

                      final taxonomyLabel = () {
                        if (category.isEmpty && subcategory.isEmpty) return 'Category: Uncategorized';
                        if (category.isNotEmpty && subcategory.isNotEmpty) {
                          return 'Category: ${_prettyPantryToken(category)} / ${_prettyPantryToken(subcategory)}';
                        }
                        if (category.isNotEmpty) return 'Category: ${_prettyPantryToken(category)}';
                        return 'Category: ${_prettyPantryToken(subcategory)}';
                      }();

                      final metaParts = <String>[
                        taxonomyLabel,
                        'Expiry: ${expiry == null ? '—' : _formatPantryDate(expiry)}',
                        if (cuisine.isNotEmpty) 'Cuisine: ${_prettyPantryToken(cuisine)}',
                      ];

                      return Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(item.displayLabel, style: theme.textTheme.titleMedium),
                          const SizedBox(height: 2),
                          Text(
                            '${_formatPantryQty(item.quantity)} ${item.unit} • ${_prettyPantryToken(item.state)}',
                            style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            metaParts.join(' • '),
                            style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                          ),
                          if (imageMissing) ...[
                            const SizedBox(height: 4),
                            Text(
                              'Image required',
                              style: theme.textTheme.bodySmall?.copyWith(color: Colors.red.shade700),
                            ),
                          ],
                        ],
                      );
                    },
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                if (imageMissing)
                  IconButton(
                    tooltip: 'Capture image',
                    onPressed: (onCaptureImage == null || uploading) ? null : () => onCaptureImage!(item),
                    icon: uploading
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.photo_camera_outlined),
                  ),
                IconButton(
                  tooltip: categoryIsEmpty ? 'Assign category' : 'Edit category',
                  onPressed: onEditCategory == null ? null : () => onEditCategory!(item),
                  icon: Icon(categoryIsEmpty ? Icons.label_outline : Icons.edit_outlined),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _WasteHeader extends StatelessWidget {
  final bool loading;
  final WasteAnalyticsSummary? summary;

  const _WasteHeader({required this.loading, required this.summary});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;

    if (loading) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Row(
            children: [
              const SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
              const SizedBox(width: AppSpacing.sm),
              Text(
                'Calculating waste score…',
                style: theme.textTheme.bodyMedium,
              ),
            ],
          ),
        ),
      );
    }

    if (summary == null) {
      return const SizedBox.shrink();
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Waste score: ${summary!.score}/100',
              style: theme.textTheme.titleMedium,
            ),
            const SizedBox(height: AppSpacing.xs),
            Text(
              summary!.message,
              style: theme.textTheme.bodySmall?.copyWith(color: cs.onSurfaceVariant),
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(
              'Expiring soon: ${summary!.expiringSoonCount} • Expired: ${summary!.expiredCount} • Risk: ${summary!.wasteRiskPercentage.toStringAsFixed(1)}%',
              style: theme.textTheme.bodySmall?.copyWith(color: cs.onSurfaceVariant),
            ),
          ],
        ),
      ),
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
