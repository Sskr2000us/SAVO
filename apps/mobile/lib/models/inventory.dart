class InventoryItem {
  final String inventoryId;
  final String canonicalName;
  final String? displayName;
  final double quantity;
  final String unit;
  final String state; // raw, cooked, leftover, frozen
  final String storage; // pantry, refrigerator, freezer
  final int? freshnessDaysRemaining;
  final String? notes;

  InventoryItem({
    required this.inventoryId,
    required this.canonicalName,
    this.displayName,
    required this.quantity,
    required this.unit,
    this.state = 'raw',
    this.storage = 'pantry',
    this.freshnessDaysRemaining,
    this.notes,
  });

  factory InventoryItem.fromJson(Map<String, dynamic> json) {
    return InventoryItem(
      inventoryId: json['inventory_id'] ?? '',
      canonicalName: json['canonical_name'] ?? '',
      displayName: json['display_name'],
      quantity: (json['quantity'] ?? 0).toDouble(),
      unit: json['unit'] ?? '',
      state: json['state'] ?? 'raw',
      storage: json['storage'] ?? 'pantry',
      freshnessDaysRemaining: json['freshness_days_remaining'],
      notes: json['notes'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'inventory_id': inventoryId,
      'canonical_name': canonicalName,
      'display_name': displayName,
      'quantity': quantity,
      'unit': unit,
      'state': state,
      'storage': storage,
      'freshness_days_remaining': freshnessDaysRemaining,
      'notes': notes,
    };
  }

  bool get isExpiringSoon => freshnessDaysRemaining != null && freshnessDaysRemaining! <= 3;
  bool get isLeftover => state == 'leftover';
}
