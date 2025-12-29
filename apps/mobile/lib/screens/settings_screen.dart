import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_client.dart';
import '../models/config.dart';
import 'inventory_screen.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  AppConfiguration? _config;
  bool _loading = true;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _loadConfig();
  }

  Future<void> _loadConfig() async {
    setState(() => _loading = true);

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final response = await apiClient.get('/config');

      setState(() {
        _config = AppConfiguration.fromJson(response);
        _loading = false;
      });
    } catch (e) {
      setState(() => _loading = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error loading config: $e')),
        );
      }
    }
  }

  Future<void> _saveConfig() async {
    if (_config == null) return;

    setState(() => _saving = true);

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      await apiClient.put('/config', _config!.toJson());

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Settings saved')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error saving: $e')),
        );
      }
    } finally {
      setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings'),
        actions: [
          if (_config != null)
            TextButton(
              onPressed: _saving ? null : _saveConfig,
              child: _saving
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Save'),
            ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _config == null
              ? const Center(child: Text('Failed to load configuration'))
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    ListTile(
                      leading: const Icon(Icons.inventory_2),
                      title: const Text('Manage Inventory'),
                      trailing: const Icon(Icons.arrow_forward_ios, size: 16),
                      onTap: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => const InventoryScreen(),
                          ),
                        );
                      },
                    ),
                    const Divider(),
                    const SizedBox(height: 16),
                    Text(
                      'Household Profile',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 8),
                    ListTile(
                      title: const Text('Family Size'),
                      trailing: Text(
                        '${_config!.householdProfile.members.length} members',
                      ),
                    ),
                    const SizedBox(height: 16),
                    Text(
                      'Preferences',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 8),
                    SwitchListTile(
                      title: const Text('Metric Units'),
                      subtitle: const Text('Use grams/liters instead of cups/oz'),
                      value: _config!.globalSettings.measurementSystem == 'metric',
                      onChanged: (value) {
                        setState(() {
                          _config = AppConfiguration(
                            householdProfile: _config!.householdProfile,
                            globalSettings: GlobalSettings(
                              measurementSystem: value ? 'metric' : 'imperial',
                              timezone: _config!.globalSettings.timezone,
                              primaryLanguage: _config!.globalSettings.primaryLanguage,
                              availableEquipment: _config!.globalSettings.availableEquipment,
                            ),
                            behaviorSettings: _config!.behaviorSettings,
                          );
                        });
                      },
                    ),
                    ListTile(
                      title: const Text('Timezone'),
                      trailing: Text(_config!.globalSettings.timezone),
                    ),
                    const SizedBox(height: 16),
                    Text(
                      'Behavior',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 8),
                    ListTile(
                      title: const Text('Avoid Repetition'),
                      trailing: Text(
                        '${_config!.behaviorSettings.avoidRepetitionDays} days',
                      ),
                    ),
                    SwitchListTile(
                      title: const Text('Prioritize Expiring Items'),
                      value: _config!.behaviorSettings.preferExpiringIngredients,
                      onChanged: (value) {
                        setState(() {
                          _config = AppConfiguration(
                            householdProfile: _config!.householdProfile,
                            globalSettings: _config!.globalSettings,
                            behaviorSettings: BehaviorSettings(
                              avoidRepetitionDays:
                                  _config!.behaviorSettings.avoidRepetitionDays,
                              preferExpiringIngredients: value,
                              rotateCuisines: _config!.behaviorSettings.rotateCuisines,
                              rotateMethods: _config!.behaviorSettings.rotateMethods,
                              maxRepeatCuisinePerWeek: _config!.behaviorSettings.maxRepeatCuisinePerWeek,
                            ),
                          );
                        });
                      },
                    ),
                    const SizedBox(height: 16),
                    if (_config!.householdProfile.members.isNotEmpty) ...[
                      Text(
                        'Dietary Restrictions',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      const SizedBox(height: 8),
                      ..._config!.householdProfile.members.map(
                        (member) => ListTile(
                          title: Text(member.name),
                          subtitle: member.dietaryRestrictions.isEmpty
                              ? const Text('No restrictions')
                              : Text(member.dietaryRestrictions.join(', ')),
                        ),
                      ),
                    ],
                  ],
                ),
    );
  }
}
