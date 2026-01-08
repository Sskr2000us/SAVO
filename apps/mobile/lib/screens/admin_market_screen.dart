import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/market_config_state.dart';
import '../services/api_client.dart';

class AdminMarketScreen extends StatefulWidget {
  const AdminMarketScreen({super.key});

  @override
  State<AdminMarketScreen> createState() => _AdminMarketScreenState();
}

class _AdminMarketScreenState extends State<AdminMarketScreen> {
  bool _saving = false;
  String _region = 'US';

  bool _shoppingList = true;
  bool _shoppingCart = false;
  bool _shareableRecipes = false;
  bool _shareablePlans = false;
  bool _coachDashboard = false;

  final TextEditingController _availableRegionsCsv = TextEditingController();
  final TextEditingController _enabledCuisinesCsv = TextEditingController();

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final market = Provider.of<MarketConfigState>(context);
    _region = market.region;
    _shoppingList = market.isEnabled('shopping_list', defaultValue: true);
    _shoppingCart = market.isEnabled('shopping_cart', defaultValue: false);
    _shareableRecipes = market.isEnabled('shareable_recipes', defaultValue: false);
    _shareablePlans = market.isEnabled('shareable_plans', defaultValue: false);
    _coachDashboard = market.isEnabled('coach_dashboard', defaultValue: false);

    final regionsPayload = market.config?.payload('available_regions');
    if (regionsPayload is Map && regionsPayload['regions'] is List) {
      final regions = (regionsPayload['regions'] as List)
          .map((e) => e.toString().trim())
          .where((s) => s.isNotEmpty)
          .toList();
      _availableRegionsCsv.text = regions.join(', ');
    }

    final cuisinesPayload = market.config?.payload('enabled_cuisines');
    if (cuisinesPayload is Map && cuisinesPayload['cuisines'] is List) {
      final cuisines = (cuisinesPayload['cuisines'] as List)
          .map((e) => e.toString().trim())
          .where((s) => s.isNotEmpty)
          .toList();
      _enabledCuisinesCsv.text = cuisines.join(', ');
    }
  }

  Future<void> _save() async {
    if (_saving) return;
    setState(() => _saving = true);

    try {
      final api = Provider.of<ApiClient>(context, listen: false);

      Future<void> upsert(String key, bool enabled) async {
        await api.put('/admin/market/feature-flags', {
          'region': _region,
          'feature_key': key,
          'enabled': enabled,
          'payload': null,
        });
      }

      Future<void> upsertWithPayload(String key, bool enabled, Object? payload) async {
        await api.put('/admin/market/feature-flags', {
          'region': _region,
          'feature_key': key,
          'enabled': enabled,
          'payload': payload,
        });
      }

      await upsert('shopping_list', _shoppingList);
      await upsert('shopping_cart', _shoppingCart);
      await upsert('shareable_recipes', _shareableRecipes);
      await upsert('shareable_plans', _shareablePlans);
      await upsert('coach_dashboard', _coachDashboard);

      final regions = _availableRegionsCsv.text
          .split(',')
          .map((s) => s.trim())
          .where((s) => s.isNotEmpty)
          .toList();
      await upsertWithPayload(
        'available_regions',
        regions.isNotEmpty,
        regions.isNotEmpty ? {'regions': regions} : null,
      );

      final cuisines = _enabledCuisinesCsv.text
          .split(',')
          .map((s) => s.trim())
          .where((s) => s.isNotEmpty)
          .toList();
      await upsertWithPayload(
        'enabled_cuisines',
        cuisines.isNotEmpty,
        cuisines.isNotEmpty ? {'cuisines': cuisines} : null,
      );

      final market = Provider.of<MarketConfigState>(context, listen: false);
      await market.refresh(api);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Saved market flags')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to save: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final market = Provider.of<MarketConfigState>(context);
    if (!market.isSuperAdmin) {
      return const Scaffold(
        body: Center(child: Text('Admin access required')),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Admin: Market Features'),
        actions: [
          TextButton(
            onPressed: _saving ? null : _save,
            child: _saving ? const Text('Saving...') : const Text('Save'),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Region', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          DropdownButtonFormField<String>(
            value: _region,
            items: const [
              DropdownMenuItem(value: 'US', child: Text('US')),
              DropdownMenuItem(value: 'CA', child: Text('Canada')),
              DropdownMenuItem(value: 'IN', child: Text('India')),
              DropdownMenuItem(value: 'GB', child: Text('UK (GB)')),
            ],
            onChanged: _saving
                ? null
                : (v) {
                    if (v == null) return;
                    setState(() => _region = v);
                  },
          ),
          const SizedBox(height: 24),
          SwitchListTile(
            value: _shoppingList,
            onChanged: _saving ? null : (v) => setState(() => _shoppingList = v),
            title: const Text('Shopping List'),
            subtitle: const Text('Show/hide Shopping List UI'),
          ),
          SwitchListTile(
            value: _shoppingCart,
            onChanged: _saving ? null : (v) => setState(() => _shoppingCart = v),
            title: const Text('Shopping Cart'),
            subtitle: const Text('Enable retailer-based cart features (future)'),
          ),
          SwitchListTile(
            value: _shareableRecipes,
            onChanged: _saving ? null : (v) => setState(() => _shareableRecipes = v),
            title: const Text('Shareable Recipes'),
            subtitle: const Text('Enable share links (/r/...) and public recipe pages'),
          ),
          SwitchListTile(
            value: _shareablePlans,
            onChanged: _saving ? null : (v) => setState(() => _shareablePlans = v),
            title: const Text('Shareable Plans'),
            subtitle: const Text('Enable share links for meal plans'),
          ),
          SwitchListTile(
            value: _coachDashboard,
            onChanged: _saving ? null : (v) => setState(() => _coachDashboard = v),
            title: const Text('Coach Dashboard'),
            subtitle: const Text('Enable Coach dashboard in-app'),
          ),
          const SizedBox(height: 24),
          Text('Available regions (CSV)', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          TextField(
            controller: _availableRegionsCsv,
            enabled: !_saving,
            decoration: const InputDecoration(
              hintText: 'US, CA, IN, GB',
            ),
          ),
          const SizedBox(height: 16),
          Text('Enabled cuisines (CSV)', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          TextField(
            controller: _enabledCuisinesCsv,
            enabled: !_saving,
            decoration: const InputDecoration(
              hintText: 'Italian, Indian, Mexican',
            ),
          ),
          const SizedBox(height: 12),
          Text(
            'Note: Admin access is determined by backend (SUPER_ADMIN_EMAILS or users.is_super_admin).',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}
