class MarketConfig {
  final String region;
  final Map<String, bool> flags;
  final bool isSuperAdmin;

  const MarketConfig({
    required this.region,
    required this.flags,
    required this.isSuperAdmin,
  });

  bool isEnabled(String key, {bool defaultValue = false}) {
    return flags[key] ?? defaultValue;
  }

  factory MarketConfig.fromJson(Map<String, dynamic> json) {
    final flagsRaw = json['flags'];
    final flags = <String, bool>{};
    if (flagsRaw is Map) {
      for (final entry in flagsRaw.entries) {
        flags[entry.key.toString()] = entry.value == true;
      }
    }

    return MarketConfig(
      region: (json['region'] ?? 'US').toString(),
      flags: flags,
      isSuperAdmin: json['is_super_admin'] == true,
    );
  }
}
