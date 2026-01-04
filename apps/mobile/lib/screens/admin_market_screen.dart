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

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final market = Provider.of<MarketConfigState>(context);
    _region = market.region;
    _shoppingList = market.isEnabled('shopping_list', defaultValue: true);
    _shoppingCart = market.isEnabled('shopping_cart', defaultValue: false);
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

      await upsert('shopping_list', _shoppingList);
      await upsert('shopping_cart', _shoppingCart);

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
