import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/profile_state.dart';
import '../services/api_client.dart';
import '../services/cook_now_service.dart';
import '../services/metrics_service.dart';
import '../ui/ui_principles.dart';
import 'recipe_options_screen.dart';

class CookNowEntryScreen extends StatefulWidget {
  const CookNowEntryScreen({super.key});

  @override
  State<CookNowEntryScreen> createState() => _CookNowEntryScreenState();
}

class _CookNowEntryScreenState extends State<CookNowEntryScreen> {
  bool _generating = false;
  String? _error;

  Future<void> _generate() async {
    if (_generating) return;
    setState(() {
      _generating = true;
      _error = null;
    });

    try {
      fireAndForget(MetricsService.instance.recordWorkflowStep('CookNow', 'CheckInventory'));
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final profileState = Provider.of<ProfileState>(context, listen: false);
      final service = CookNowService();

      final options = await service.generateRecipeOptions(
        apiClient: apiClient,
        profileState: profileState,
        maxOptions: 5,
        avoidRecentRecipes: 3,
      );

      if (!mounted) return;

      if (options.isEmpty) {
        setState(() {
          _generating = false;
          _error = 'No recipe options right now. Try again after updating your pantry.';
        });
        return;
      }

      fireAndForget(MetricsService.instance.recordWorkflowStep('CookNow', 'Generate'));

      await Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => RecipeOptionsScreen(recipes: options),
        ),
      );

      if (!mounted) return;
      setState(() {
        _generating = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _generating = false;
        _error = e.toString();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (kDebugMode || kProfileMode) {
      SavoUiGuards.warnIfTooManyChoices(
        screen: 'CookNowEntryScreen',
        surface: 'Primary actions',
        choices: 1,
      );
    }

    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Cook'),
      ),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 520),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  'Cook now',
                  style: theme.textTheme.headlineSmall,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                Text(
                  'Generate recipes based on what\'s in your pantry.',
                  style: theme.textTheme.bodyMedium,
                  textAlign: TextAlign.center,
                ),
                if (_error != null) ...[
                  const SizedBox(height: 16),
                  Text(
                    _error!,
                    style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.error),
                    textAlign: TextAlign.center,
                  ),
                ],
                const SizedBox(height: 24),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton(
                    onPressed: _generating ? null : _generate,
                    child: Text(_generating ? 'Generating…' : 'Generate recipes'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
