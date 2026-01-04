import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/planning.dart';
import '../services/api_client.dart';
import '../services/cook_session_storage.dart';
import '../services/metrics_service.dart';
import '../ui/ui_principles.dart';

class PostCookFeedbackScreen extends StatefulWidget {
  final Recipe recipe;
  final int servingsMade;
  final double completionMinutes;

  const PostCookFeedbackScreen({
    super.key,
    required this.recipe,
    required this.servingsMade,
    required this.completionMinutes,
  });

  @override
  State<PostCookFeedbackScreen> createState() => _PostCookFeedbackScreenState();
}

class _PostCookFeedbackScreenState extends State<PostCookFeedbackScreen> {
  final TextEditingController _notesController = TextEditingController();
  bool _saving = false;
  String? _error;

  @override
  void dispose() {
    _notesController.dispose();
    super.dispose();
  }

  Future<void> _submit({required int rating}) async {
    if (_saving) return;

    setState(() {
      _saving = true;
      _error = null;
    });

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final userNotes = _notesController.text.trim();
      final completion = 'Completed in ${widget.completionMinutes.toStringAsFixed(1)} minutes';
      final notes = userNotes.isEmpty ? completion : '$userNotes\n\n$completion';

      await apiClient.post('/history/recipes', {
        'recipe_id': widget.recipe.recipeId,
        'recipe_name': widget.recipe.recipeName['en'] ?? widget.recipe.getLocalizedName('en'),
        'cuisine': widget.recipe.cuisine,
        'cooking_method': widget.recipe.cookingMethod,
        'servings_made': widget.servingsMade,
        'user_rating': rating,
        'notes': notes,
      });

      fireAndForget(MetricsService.instance.recordWorkflowStep('CookNow', 'Learn'));
      fireAndForget(MetricsService.instance.recordEvent('recipe_cooked'));

      // Clear any resume state.
      try {
        await ActiveCookSession.clear();
      } catch (_) {
        // Best-effort only.
      }

      if (!mounted) return;
      Navigator.of(context).popUntil((route) => route.isFirst);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = e.toString();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (kDebugMode || kProfileMode) {
      SavoUiGuards.warnIfTooManyChoices(
        screen: 'PostCookFeedbackScreen',
        surface: 'Feedback options',
        choices: 3,
      );
    }

    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('How was it?'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            widget.recipe.getLocalizedName('en'),
            style: theme.textTheme.titleMedium,
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _notesController,
            maxLines: 4,
            decoration: const InputDecoration(
              labelText: 'Notes (optional)',
              alignLabelWithHint: true,
            ),
            enabled: !_saving,
          ),
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(
              _error!,
              style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.error),
            ),
          ],
          const SizedBox(height: 20),
          Row(
            children: [
              Expanded(
                child: FilledButton(
                  onPressed: _saving ? null : () => _submit(rating: 5),
                  child: Text(_saving ? 'Saving…' : 'Loved it'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: OutlinedButton(
                  onPressed: _saving ? null : () => _submit(rating: 3),
                  child: const Text('Okay'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: OutlinedButton(
                  onPressed: _saving ? null : () => _submit(rating: 1),
                  child: const Text('Skip next time'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
