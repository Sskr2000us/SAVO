import 'dart:async';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_client.dart';
import '../services/cook_session_storage.dart';
import '../services/scanning_service.dart';
import '../models/profile_state.dart';
import '../models/planning.dart';
import 'post_cook_feedback_screen.dart';

enum _CookLanguageMode { english, bilingual }

class CookModeScreen extends StatefulWidget {
  final Recipe recipe;
  final int servings;
  final int? baseServings;
  final String? preferredLanguageCode;
  final bool? startBilingual;
  final bool enablePostCookFeedback;

  // Optional restore state (used for Resume Cooking)
  final int? initialStepIndex;
  final int? initialStepSecondsRemaining;
  final int? initialRecipeTotalSeconds;
  final bool? initialIsStepTimerRunning;
  final bool? initialIsStepTimerPaused;
  final String? initialSecondaryLanguageCode;
  final bool? initialStartBilingual;

  const CookModeScreen({
    super.key,
    required this.recipe,
    this.servings = 4,
    this.baseServings,
    this.preferredLanguageCode,
    this.startBilingual,
    this.enablePostCookFeedback = false,
    this.initialStepIndex,
    this.initialStepSecondsRemaining,
    this.initialRecipeTotalSeconds,
    this.initialIsStepTimerRunning,
    this.initialIsStepTimerPaused,
    this.initialSecondaryLanguageCode,
    this.initialStartBilingual,
  });

  @override
  State<CookModeScreen> createState() => _CookModeScreenState();
}

class _CookModeScreenState extends State<CookModeScreen> {
  int _currentStepIndex = 0;
  Timer? _stepTimer;
  int _stepSecondsRemaining = 0;
  Timer? _recipeTimer;
  int _recipeTotalSeconds = 0;
  bool _isStepTimerRunning = false;
  bool _isStepTimerPaused = false;

  int _lastPersistMillis = 0;

  // Language / presentation
  bool _languageInitialized = false;
  String _secondaryLanguageCode = 'en';
  _CookLanguageMode _languageMode = _CookLanguageMode.english;

  // Pantry / substitutions
  bool _checkingSufficiency = false;
  List<Map<String, dynamic>> _missingItems = const [];

  double get _scalingFactor {
    final base = (widget.baseServings != null && widget.baseServings! > 0)
        ? widget.baseServings!
        : (widget.servings > 0 ? widget.servings : 1);
    return base > 0 ? (widget.servings / base) : 1.0;
  }

  List<Map<String, dynamic>> _ingredientsForSufficiencyPayload() {
    return widget.recipe.ingredientsUsed
        .where((i) => i.canonicalName.trim().isNotEmpty)
        .map(
          (i) => {
            'name': i.canonicalName.trim(),
            'quantity': i.amount,
            'unit': i.unit,
          },
        )
        .toList();
  }

  List<Map<String, dynamic>> _ingredientsForDeductPayload() {
    final factor = _scalingFactor;
    return widget.recipe.ingredientsUsed
        .where((i) => i.canonicalName.trim().isNotEmpty)
        .map(
          (i) => {
            'name': i.canonicalName.trim(),
            'quantity': i.amount * factor,
            'unit': i.unit,
          },
        )
        .toList();
  }

  @override
  void initState() {
    super.initState();
    _restoreInitialStateIfProvided();
    _startRecipeTimer();
    // Ensure a session exists even if user immediately leaves.
    Future.microtask(() => _persistSession(force: true));
  }

  void _restoreInitialStateIfProvided() {
    final stepIndex = widget.initialStepIndex;
    if (stepIndex != null && stepIndex >= 0 && stepIndex < widget.recipe.steps.length) {
      _currentStepIndex = stepIndex;
    }

    final recipeSeconds = widget.initialRecipeTotalSeconds;
    if (recipeSeconds != null && recipeSeconds >= 0) {
      _recipeTotalSeconds = recipeSeconds;
    }

    final stepSeconds = widget.initialStepSecondsRemaining;
    if (stepSeconds != null && stepSeconds > 0) {
      _stepSecondsRemaining = stepSeconds;
    }

    final running = widget.initialIsStepTimerRunning;
    final paused = widget.initialIsStepTimerPaused;
    if ((running == true) || _stepSecondsRemaining > 0) {
      _isStepTimerRunning = true;
      _isStepTimerPaused = paused ?? true;
      _startStepTimerFromExistingRemaining();
    }

    final secLang = widget.initialSecondaryLanguageCode;
    if (secLang != null && secLang.trim().isNotEmpty) {
      _secondaryLanguageCode = secLang.trim();
    }
    if (widget.initialStartBilingual != null) {
      _languageMode = widget.initialStartBilingual == true
          ? _CookLanguageMode.bilingual
          : _CookLanguageMode.english;
      _languageInitialized = true;
    }
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_languageInitialized) return;

    final profileState = Provider.of<ProfileState>(context, listen: false);
    final preferred = (widget.preferredLanguageCode?.trim().isNotEmpty == true)
        ? widget.preferredLanguageCode!.trim()
        : (profileState.preferredLanguage?.trim().isNotEmpty == true)
            ? profileState.preferredLanguage!.trim()
            : (profileState.primaryLanguage?.trim().isNotEmpty == true)
                ? profileState.primaryLanguage!.trim()
                : Localizations.localeOf(context).languageCode;

    final available = _availableRecipeLanguageCodes(widget.recipe);
    final nonEnglish = available.where((c) => c != 'en').toList()..sort();

    final chosen = available.contains(preferred)
        ? preferred
        : (nonEnglish.isNotEmpty ? nonEnglish.first : 'en');

    _secondaryLanguageCode = chosen;
    final canBilingual = chosen != 'en' && available.contains(chosen);
    final wantBilingual = widget.startBilingual ?? canBilingual;
    _languageMode = (canBilingual && wantBilingual)
        ? _CookLanguageMode.bilingual
        : _CookLanguageMode.english;
    _languageInitialized = true;
  }

  Set<String> _availableRecipeLanguageCodes(Recipe recipe) {
    final codes = <String>{};
    codes.addAll(recipe.recipeName.keys);
    for (final step in recipe.steps) {
      codes.addAll(step.instruction.keys);
    }
    return codes
        .map((c) => c.trim().toLowerCase())
        .where((c) => c.isNotEmpty)
        .toSet();
  }

  String _languageLabel(String code) {
    switch (code) {
      case 'hi':
        return 'Hindi';
      case 'mr':
        return 'Marathi';
      case 'ta':
        return 'Tamil';
      case 'te':
        return 'Telugu';
      case 'kn':
        return 'Kannada';
      case 'ml':
        return 'Malayalam';
      case 'gu':
        return 'Gujarati';
      case 'bn':
        return 'Bengali';
      case 'pa':
        return 'Punjabi';
      case 'ur':
        return 'Urdu';
      case 'es':
        return 'Spanish';
      case 'fr':
        return 'French';
      default:
        return code.toUpperCase();
    }
  }

  @override
  void dispose() {
    _persistSession(force: true);
    _stepTimer?.cancel();
    _recipeTimer?.cancel();
    super.dispose();
  }

  Future<void> _persistSession({bool force = false}) async {
    final now = DateTime.now().millisecondsSinceEpoch;
    if (!force && (now - _lastPersistMillis) < 1500) return;
    _lastPersistMillis = now;

    final session = ActiveCookSession(
      recipe: widget.recipe,
      servings: widget.servings,
      baseServings: widget.baseServings,
      currentStepIndex: _currentStepIndex,
      stepSecondsRemaining: _stepSecondsRemaining,
      recipeTotalSeconds: _recipeTotalSeconds,
      isStepTimerRunning: _isStepTimerRunning,
      isStepTimerPaused: _isStepTimerPaused,
      secondaryLanguageCode: _secondaryLanguageCode,
      languageMode: _languageMode == _CookLanguageMode.bilingual ? 'bilingual' : 'english',
      savedAtMillis: now,
    );

    try {
      await session.save();
    } catch (_) {
      // Best-effort only.
    }
  }

  String _uuidV4() {
    final rng = Random.secure();
    final bytes = List<int>.generate(16, (_) => rng.nextInt(256));
    // Per RFC 4122 section 4.4
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;

    String two(int n) => n.toRadixString(16).padLeft(2, '0');
    final hex = bytes.map(two).join();
    return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
  }

  Future<void> _deductInventory(ApiClient apiClient) async {
    final ingredients = _ingredientsForDeductPayload();

    if (ingredients.isEmpty) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No ingredients available to deduct.')),
      );
      return;
    }

    final response = await apiClient.post('/inventory-db/deduct', {
      // Endpoint expects a UUID-like string; generate a synthetic one for cook completion.
      'meal_plan_id': _uuidV4(),
      'ingredients': ingredients,
    });

    if (!mounted) return;
    final success = response['success'] == true;
    if (success) {
      final message = (response['message'] is String)
          ? (response['message'] as String)
          : 'Inventory updated';
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(message)),
      );
      return;
    }

    final msg = (response['message'] is String)
      ? (response['message'] as String)
        : 'Could not update inventory';

    final insufficient = (response['insufficient_items'] is List)
        ? (response['insufficient_items'] as List)
        : const [];

    await showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Inventory not updated'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(msg),
            if (insufficient.isNotEmpty) ...[
              const SizedBox(height: 12),
              const Text('Missing items:'),
              const SizedBox(height: 8),
              ...insufficient.take(6).map((i) => Text('• ${i.toString()}')),
              if (insufficient.length > 6) Text('• +${insufficient.length - 6} more'),
            ],
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  void _startRecipeTimer() {
    _recipeTimer?.cancel();
    _recipeTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      setState(() {
        _recipeTotalSeconds++;
      });
      _persistSession();
    });
  }

  void _startStepTimerFromExistingRemaining() {
    if (_stepSecondsRemaining <= 0) {
      setState(() {
        _isStepTimerRunning = false;
        _isStepTimerPaused = false;
      });
      return;
    }

    _stepTimer?.cancel();
    _stepTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      setState(() {
        if (_isStepTimerPaused) return;
        if (_stepSecondsRemaining > 0) {
          _stepSecondsRemaining--;
          _persistSession();
          return;
        }

        _isStepTimerRunning = false;
        _isStepTimerPaused = false;
        _stepTimer?.cancel();
        _persistSession(force: true);
        _showStepCompleteDialog();
      });
    });
  }

  void _startStepTimer() {
    final step = widget.recipe.steps[_currentStepIndex];
    if (step.timeMinutes <= 0) return;

    setState(() {
      _stepSecondsRemaining = step.timeMinutes * 60;
      _isStepTimerRunning = true;
      _isStepTimerPaused = false;
    });

    _persistSession(force: true);

    _stepTimer?.cancel();
    _stepTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      setState(() {
        if (_isStepTimerPaused) return;
        if (_stepSecondsRemaining > 0) {
          _stepSecondsRemaining--;
          _persistSession();
          return;
        }

        _isStepTimerRunning = false;
        _isStepTimerPaused = false;
        _stepTimer?.cancel();
        _persistSession(force: true);
        _showStepCompleteDialog();
      });
    });
  }

  void _togglePause() {
    if (!_isStepTimerRunning) return;
    setState(() {
      _isStepTimerPaused = !_isStepTimerPaused;
    });
    _persistSession(force: true);
  }

  void _resetStepTimer() {
    setState(() {
      _stepTimer?.cancel();
      _isStepTimerRunning = false;
      _isStepTimerPaused = false;
      _stepSecondsRemaining = 0;
    });
    _persistSession(force: true);
  }

  void _addOneMinute() {
    setState(() {
      _stepSecondsRemaining += 60;
    });
    _persistSession(force: true);
  }

  void _showStepCompleteDialog() {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Step Complete'),
        content: Text('Step ${_currentStepIndex + 1} timer finished!'),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              if (_currentStepIndex < widget.recipe.steps.length - 1) {
                _nextStep();
              }
            },
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  void _nextStep() {
    if (_currentStepIndex < widget.recipe.steps.length - 1) {
      setState(() {
        _currentStepIndex++;
        _stepTimer?.cancel();
        _isStepTimerRunning = false;
        _isStepTimerPaused = false;
        _stepSecondsRemaining = 0;
      });
      _persistSession(force: true);
    }
  }

  void _previousStep() {
    if (_currentStepIndex > 0) {
      setState(() {
        _currentStepIndex--;
        _stepTimer?.cancel();
        _isStepTimerRunning = false;
        _isStepTimerPaused = false;
        _stepSecondsRemaining = 0;
      });
      _persistSession(force: true);
    }
  }

  Future<void> _checkMissing() async {
    if (_checkingSufficiency) return;
    setState(() {
      _checkingSufficiency = true;
    });

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final service = ScanningService();
      final result = await service.checkSufficiency(
        recipeId: widget.recipe.recipeId,
        servings: widget.servings,
        recipeServings: (widget.baseServings != null && widget.baseServings! > 0)
            ? widget.baseServings!
            : widget.servings,
        recipeIngredients: _ingredientsForSufficiencyPayload(),
        apiClient: apiClient,
      );
      if (!mounted) return;

      final missing = result['missing'];
      if (result['success'] == true && missing is List) {
        setState(() {
          _missingItems = missing
              .whereType<Map>()
              .map((m) => Map<String, dynamic>.from(m))
              .toList();
        });
      }
    } catch (_) {
      // Ignore; substitutions can still be shown from static mapping.
    } finally {
      if (mounted) {
        setState(() {
          _checkingSufficiency = false;
        });
      }
    }
  }

  List<String> _substitutionIdeas(String ingredientName) {
    final name = ingredientName.toLowerCase();

    if (name.contains('milk')) return const ['Oat milk', 'Almond milk', 'Coconut milk'];
    if (name.contains('butter')) return const ['Ghee', 'Olive oil', 'Coconut oil'];
    if (name.contains('yogurt')) return const ['Sour cream', 'Greek yogurt', 'Buttermilk'];
    if (name.contains('egg')) return const ['Flax egg (vegan)', 'Chia egg (vegan)', 'Silken tofu'];
    if (name.contains('cream')) return const ['Coconut cream', 'Evaporated milk', 'Cashew cream'];
    if (name.contains('rice')) return const ['Quinoa', 'Couscous', 'Cauliflower rice'];
    if (name.contains('flour')) return const ['All-purpose flour', 'Whole wheat flour', 'Gluten-free flour blend'];
    if (name.contains('sugar')) return const ['Honey', 'Maple syrup', 'Coconut sugar'];
    if (name.contains('lemon')) return const ['Lime', 'Vinegar (small amount)', 'Tamarind'];
    if (name.contains('garlic')) return const ['Garlic powder', 'Shallot', 'Asafoetida (hing)'];
    if (name.contains('onion')) return const ['Shallot', 'Leek', 'Onion powder'];
    if (name.contains('tomato')) return const ['Canned tomatoes', 'Tomato paste + water', 'Roasted red pepper'];

    return const ['Use what you have (similar ingredient)', 'Adjust seasoning to taste'];
  }

  Future<void> _showSubstitutions() async {
    // Best-effort: fetch missing items once so we can prioritize substitutions.
    if (_missingItems.isEmpty) {
      await _checkMissing();
    }

    if (!mounted) return;
    final theme = Theme.of(context);
    final cs = theme.colorScheme;

    final prioritized = <String>[];
    if (_missingItems.isNotEmpty) {
      for (final m in _missingItems) {
        final name = (m['ingredient'] ?? m['canonical_name'] ?? m['name'] ?? '').toString().trim();
        if (name.isNotEmpty) prioritized.add(name);
      }
    }

    if (prioritized.isEmpty) {
      for (final ing in widget.recipe.ingredientsUsed) {
        prioritized.add(ing.canonicalName);
      }
    }

    await showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (context) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    Icon(Icons.swap_horiz, color: cs.primary),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text('Substitutions', style: theme.textTheme.titleLarge),
                    ),
                    if (_checkingSufficiency)
                      const SizedBox(
                        height: 18,
                        width: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  _missingItems.isNotEmpty
                      ? 'Suggestions prioritized for missing items.'
                      : 'Suggestions based on recipe ingredients.',
                  style: theme.textTheme.bodyMedium,
                ),
                const SizedBox(height: 12),
                Flexible(
                  child: ListView.separated(
                    shrinkWrap: true,
                    itemCount: prioritized.length,
                    separatorBuilder: (_, __) => const Divider(height: 1),
                    itemBuilder: (context, index) {
                      final name = prioritized[index];
                      final ideas = _substitutionIdeas(name);
                      return ListTile(
                        title: Text(name),
                        subtitle: Text(ideas.take(3).join(' • ')),
                      );
                    },
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Future<void> _completeRecipe() async {
    _stepTimer?.cancel();
    _recipeTimer?.cancel();

    if (widget.enablePostCookFeedback) {
      // Completed: clear resume state.
      try {
        await ActiveCookSession.clear();
      } catch (_) {
        // Best-effort only.
      }

      if (!mounted) return;
      final completionMinutes = _recipeTotalSeconds / 60.0;

      await Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => PostCookFeedbackScreen(
            recipe: widget.recipe,
            servingsMade: widget.servings,
            completionMinutes: completionMinutes,
          ),
        ),
      );
      return;
    }

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      await apiClient.post('/history/recipes', {
        'recipe_id': widget.recipe.recipeId,
        'recipe_name': widget.recipe.recipeName['en'] ?? 'Unknown Recipe',
        'cuisine': widget.recipe.cuisine,
        'cooking_method': widget.recipe.cookingMethod,
        'servings_made': widget.servings,
        'notes': 'Completed in ${(_recipeTotalSeconds / 60).toStringAsFixed(1)} minutes',
      });

      if (!mounted) return;

      final doDeduct = await showDialog<bool>(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text('Recipe Complete!'),
          content: Text(
            'Added to your history.\n\nUpdate inventory by deducting ingredients used (${widget.recipe.ingredientsUsed.length})?',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Skip'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Deduct'),
            ),
          ],
        ),
      );

      if (doDeduct == true) {
        try {
          await _deductInventory(apiClient);
        } catch (e) {
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text('Inventory update failed: $e')),
            );
          }
        }
      }

      if (!mounted) return;
      final nav = Navigator.of(context);

      // Completed: clear resume state.
      try {
        await ActiveCookSession.clear();
      } catch (_) {
        // Best-effort only.
      }

      nav.pop();
      if (nav.canPop()) nav.pop();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error saving to history: $e')),
        );
      }
    }
  }

  String _formatTime(int seconds) {
    final minutes = seconds ~/ 60;
    final secs = seconds % 60;
    return '${minutes.toString().padLeft(2, '0')}:${secs.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    final currentStep = widget.recipe.steps[_currentStepIndex];
    final theme = Theme.of(context);
    final cs = theme.colorScheme;

    final canBilingual = _secondaryLanguageCode != 'en' &&
        _availableRecipeLanguageCodes(widget.recipe).contains(_secondaryLanguageCode);

    final primaryInstruction = currentStep.getLocalizedInstruction('en').trim();
    final secondaryInstruction = canBilingual
        ? currentStep.getLocalizedInstruction(_secondaryLanguageCode).trim()
        : '';
    final showSecondary = _languageMode == _CookLanguageMode.bilingual &&
        canBilingual &&
        secondaryInstruction.isNotEmpty &&
        secondaryInstruction != primaryInstruction;

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.recipe.recipeName['en']?.isNotEmpty == true
            ? widget.recipe.recipeName['en']!
            : 'Cook Mode'),
        actions: [
          if (canBilingual)
            PopupMenuButton<_CookLanguageMode>(
              tooltip: 'Language',
              initialValue: _languageMode,
              onSelected: (m) {
                setState(() {
                  _languageMode = m;
                });
                _persistSession(force: true);
              },
              itemBuilder: (_) => [
                const PopupMenuItem(
                  value: _CookLanguageMode.english,
                  child: Text('English'),
                ),
                PopupMenuItem(
                  value: _CookLanguageMode.bilingual,
                  child: Text('${_languageLabel(_secondaryLanguageCode)} + English'),
                ),
              ],
              icon: const Icon(Icons.translate),
            ),
          Center(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16.0),
              child: Chip(
                avatar: const Icon(Icons.timer, size: 16),
                label: Text(_formatTime(_recipeTotalSeconds)),
                backgroundColor: cs.surfaceContainerHighest,
              ),
            ),
          ),
        ],
      ),
      body: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onHorizontalDragEnd: (details) {
          final vx = details.primaryVelocity ?? 0;
          if (vx.abs() < 250) return;
          if (vx < 0) {
            // swipe left -> next
            _nextStep();
          } else {
            // swipe right -> previous
            _previousStep();
          }
        },
        child: Column(
          children: [
            // Progress indicator
            LinearProgressIndicator(
              value: (_currentStepIndex + 1) / widget.recipe.steps.length,
            ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                  // Step counter
                  Text(
                    'Step ${_currentStepIndex + 1} of ${widget.recipe.steps.length}',
                    style: Theme.of(context).textTheme.titleSmall,
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    alignment: WrapAlignment.center,
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      FilledButton.tonalIcon(
                        onPressed: _showSubstitutions,
                        icon: const Icon(Icons.swap_horiz),
                        label: const Text('Substitutions'),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),

                  // Step instruction
                  Expanded(
                    child: Card(
                      child: Padding(
                        padding: const EdgeInsets.all(24.0),
                        child: SingleChildScrollView(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                primaryInstruction,
                                style: theme.textTheme.titleLarge,
                              ),
                              if (showSecondary) ...[
                                const SizedBox(height: 12),
                                Divider(color: theme.dividerColor),
                                const SizedBox(height: 12),
                                Text(
                                  secondaryInstruction,
                                  style: theme.textTheme.titleMedium,
                                ),
                              ],
                              if (currentStep.tips.isNotEmpty) ...[
                                const SizedBox(height: 16),
                                const Divider(),
                                const SizedBox(height: 8),
                                ...currentStep.tips.map(
                                  (tip) => Padding(
                                    padding: const EdgeInsets.symmetric(vertical: 4.0),
                                    child: Row(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Icon(
                                          Icons.lightbulb_outline,
                                          size: 16,
                                          color: cs.secondary,
                                        ),
                                        const SizedBox(width: 8),
                                        Expanded(child: Text(tip)),
                                      ],
                                    ),
                                  ),
                                ),
                              ],
                            ],
                          ),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Step timer
                  if (currentStep.timeMinutes > 0) ...[
                    Card(
                      color: _isStepTimerRunning ? cs.primaryContainer : cs.surfaceContainerHighest,
                      child: Padding(
                        padding: const EdgeInsets.all(16.0),
                        child: Column(
                          children: [
                            Text(
                              _isStepTimerRunning
                                  ? _formatTime(_stepSecondsRemaining)
                                  : '${currentStep.timeMinutes} minutes',
                              style: Theme.of(context).textTheme.displaySmall?.copyWith(
                                    color: _isStepTimerRunning ? cs.onPrimaryContainer : cs.onSurface,
                                    fontWeight: FontWeight.bold,
                                  ),
                            ),
                            const SizedBox(height: 12),
                            Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                if (!_isStepTimerRunning)
                                  FilledButton.icon(
                                    onPressed: _startStepTimer,
                                    icon: const Icon(Icons.play_arrow),
                                    label: const Text('Start Timer'),
                                  ),
                                if (_isStepTimerRunning) ...[
                                  OutlinedButton.icon(
                                    onPressed: _togglePause,
                                    icon: Icon(_isStepTimerPaused ? Icons.play_arrow : Icons.pause),
                                    label: Text(_isStepTimerPaused ? 'Resume' : 'Pause'),
                                  ),
                                  const SizedBox(width: 8),
                                  OutlinedButton.icon(
                                    onPressed: _addOneMinute,
                                    icon: const Icon(Icons.add),
                                    label: const Text('+1 Min'),
                                  ),
                                  const SizedBox(width: 8),
                                  OutlinedButton.icon(
                                    onPressed: _resetStepTimer,
                                    icon: const Icon(Icons.restart_alt),
                                    label: const Text('Reset'),
                                  ),
                                ],
                              ],
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),
                  ],

                  // Navigation buttons
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton(
                          onPressed: _currentStepIndex > 0 ? _previousStep : null,
                          child: const Text('Previous'),
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        flex: 2,
                        child: FilledButton(
                          onPressed: _currentStepIndex < widget.recipe.steps.length - 1
                              ? _nextStep
                              : _completeRecipe,
                          child: Text(
                            _currentStepIndex < widget.recipe.steps.length - 1
                                ? 'Next Step'
                                : 'Complete Recipe',
                          ),
                        ),
                      ),
                    ],
                  ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
