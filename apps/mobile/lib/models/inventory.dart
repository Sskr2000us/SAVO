class InventoryItem {
  final String inventoryId;
  final String canonicalName;
  final String? displayName;
  final String? category;
  final double quantity;
  final String unit;
  final String state; // raw, cooked, leftover, frozen
  final String storage; // pantry, refrigerator, freezer
  final int? freshnessDaysRemaining;
  final DateTime? expiryDate;
  final String? notes;

  // Planning semantics
  final bool isCurrent;
  final String? source;

  // Optional packaged-good metadata
  final String? barcode;
  final String? productName;
  final String? brand;
  final String? imageUrl;
  final String? packageSizeText;

  InventoryItem({
    required this.inventoryId,
    required this.canonicalName,
    this.displayName,
    this.category,
    required this.quantity,
    required this.unit,
    this.state = 'raw',
    this.storage = 'pantry',
    this.freshnessDaysRemaining,
    this.expiryDate,
    this.notes,
    this.isCurrent = true,
    this.source,
    this.barcode,
    this.productName,
    this.brand,
    this.imageUrl,
    this.packageSizeText,
  });

  static DateTime? _tryParseDate(dynamic value) {
    if (value == null) return null;
    if (value is DateTime) return value;
    if (value is String) {
      final trimmed = value.trim();
      if (trimmed.isEmpty) return null;
      // Accept either YYYY-MM-DD or full ISO timestamps.
      try {
        return DateTime.parse(trimmed);
      } catch (_) {
        return null;
      }
    }
    return null;
  }

  static int? _computeFreshnessDaysRemaining(DateTime? expiry) {
    if (expiry == null) return null;
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final expDay = DateTime(expiry.year, expiry.month, expiry.day);
    return expDay.difference(today).inDays;
  }

  static String _normalizeStorage(String raw) {
    final s = raw.trim().toLowerCase();
    if (s == 'refrigerator') return 'fridge';
    if (s == 'refrigerator/freezer') return 'fridge';
    return s.isEmpty ? 'pantry' : s;
  }

  static String _normalizeState(String raw) {
    final s = raw.trim().toLowerCase();
    if (s.isEmpty) return 'raw';
    return s;
  }

  factory InventoryItem.fromJson(Map<String, dynamic> json) {
    final expiry = _tryParseDate(json['expiry_date']);
    final freshness = json['freshness_days_remaining'] ?? json['freshnessDaysRemaining'];
    final int? freshnessDays = freshness is int
        ? freshness
        : (freshness is num ? freshness.toInt() : _computeFreshnessDaysRemaining(expiry));

    return InventoryItem(
      // inventory-db uses `id` while legacy endpoints use `inventory_id`
      inventoryId: (json['inventory_id'] ?? json['id'] ?? '').toString(),
      canonicalName: json['canonical_name'] ?? '',
      displayName: json['display_name'],
      category: json['category']?.toString(),
      quantity: (json['quantity'] ?? 0).toDouble(),
      unit: json['unit'] ?? '',
      // inventory-db uses `item_state` and `storage_location`
      state: _normalizeState((json['state'] ?? json['item_state'] ?? 'raw').toString()),
      storage: _normalizeStorage((json['storage'] ?? json['storage_location'] ?? 'pantry').toString()),
      freshnessDaysRemaining: freshnessDays,
      expiryDate: expiry,
      notes: json['notes'],

      isCurrent: json['is_current'] == null ? true : (json['is_current'] == true),
      source: json['source']?.toString(),

      barcode: json['barcode']?.toString(),
      productName: json['product_name']?.toString(),
      brand: json['brand']?.toString(),
      imageUrl: json['image_url']?.toString(),
      packageSizeText: json['package_size_text']?.toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'inventory_id': inventoryId,
      'canonical_name': canonicalName,
      'display_name': displayName,
      'category': category,
      'quantity': quantity,
      'unit': unit,
      'state': state,
      'storage': storage,
      'freshness_days_remaining': freshnessDaysRemaining,
      'expiry_date': expiryDate?.toIso8601String().split('T').first,
      'notes': notes,

      'is_current': isCurrent,
      'source': source,

      'barcode': barcode,
      'product_name': productName,
      'brand': brand,
      'image_url': imageUrl,
      'package_size_text': packageSizeText,
    };
  }

  String get displayLabel => (displayName != null && displayName!.trim().isNotEmpty)
      ? displayName!.trim()
      : canonicalName;

  bool get isExpiringSoon => freshnessDaysRemaining != null && freshnessDaysRemaining! <= 3;
  bool get isLeftover => state == 'leftover';
}
