class MarketConfig {
  final String region;
  final Map<String, bool> flags;
  final Map<String, dynamic> payloads;
  final List<Map<String, dynamic>> retailers;
  final bool isSuperAdmin;

  const MarketConfig({
    required this.region,
    required this.flags,
    this.payloads = const {},
    this.retailers = const [],
    required this.isSuperAdmin,
  });

  bool isEnabled(String key, {bool defaultValue = false}) {
    return flags[key] ?? defaultValue;
  }

  dynamic payload(String key) {
    return payloads[key];
  }

  factory MarketConfig.fromJson(Map<String, dynamic> json) {
    final flagsRaw = json['flags'];
    final flags = <String, bool>{};
    if (flagsRaw is Map) {
      for (final entry in flagsRaw.entries) {
        flags[entry.key.toString()] = entry.value == true;
      }
    }

    final payloadsRaw = json['payloads'];
    final payloads = <String, dynamic>{};
    if (payloadsRaw is Map) {
      for (final entry in payloadsRaw.entries) {
        payloads[entry.key.toString()] = entry.value;
      }
    }

    final retailers = <Map<String, dynamic>>[];
    final retailersRaw = json['retailers'];
    if (retailersRaw is List) {
      for (final row in retailersRaw) {
        if (row is Map) {
          retailers.add(Map<String, dynamic>.from(row));
        }
      }
    }

    return MarketConfig(
      region: (json['region'] ?? 'US').toString(),
      flags: flags,
      payloads: payloads,
      retailers: retailers,
      isSuperAdmin: json['is_super_admin'] == true,
    );
  }
}
