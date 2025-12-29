import 'dart:async';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_client.dart';
import '../models/planning.dart';

class CookModeScreen extends StatefulWidget {
  final Recipe recipe;

  const CookModeScreen({super.key, required this.recipe});

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

  @override
  void initState() {
    super.initState();
    _startRecipeTimer();
  }

  @override
  void dispose() {
    _stepTimer?.cancel();
    _recipeTimer?.cancel();
    super.dispose();
  }

  void _startRecipeTimer() {
    _recipeTimer?.cancel();
    _recipeTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      setState(() {
        _recipeTotalSeconds++;
      });
    });
  }

  void _startStepTimer() {
    final step = widget.recipe.steps[_currentStepIndex];
    if (step.timeMinutes <= 0) return;

    setState(() {
      _stepSecondsRemaining = step.timeMinutes * 60;
      _isStepTimerRunning = true;
    });

    _stepTimer?.cancel();
    _stepTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      setState(() {
        if (_stepSecondsRemaining > 0) {
          _stepSecondsRemaining--;
        } else {
          _isStepTimerRunning = false;
          _stepTimer?.cancel();
          _showStepCompleteDialog();
        }
      });
    });
  }

  void _addOneMinute() {
    setState(() {
      _stepSecondsRemaining += 60;
    });
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
        _stepSecondsRemaining = 0;
      });
    }
  }

  void _previousStep() {
    if (_currentStepIndex > 0) {
      setState(() {
        _currentStepIndex--;
        _stepTimer?.cancel();
        _isStepTimerRunning = false;
        _stepSecondsRemaining = 0;
      });
    }
  }

  Future<void> _completeRecipe() async {
    _stepTimer?.cancel();
    _recipeTimer?.cancel();

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      await apiClient.post('/history/recipes', {
        'recipe_id': widget.recipe.recipeId,
        'recipe_name': widget.recipe.recipeName['en'] ?? 'Unknown Recipe',
        'cuisine': widget.recipe.cuisine,
        'cooking_method': widget.recipe.cookingMethod,
        'servings_made': 4,
        'notes': 'Completed in ${(_recipeTotalSeconds / 60).toStringAsFixed(1)} minutes',
      });

      if (mounted) {
        showDialog(
          context: context,
          builder: (_) => AlertDialog(
            title: const Text('Recipe Complete!'),
            content: const Text('Great job! This recipe has been added to your history.'),
            actions: [
              TextButton(
                onPressed: () {
                  Navigator.pop(context); // Close dialog
                  Navigator.pop(context); // Close cook mode
                  Navigator.pop(context); // Close recipe detail
                },
                child: const Text('Done'),
              ),
            ],
          ),
        );
      }
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

    return Scaffold(
      appBar: AppBar(
        title: const Text('Cook Mode'),
        actions: [
          Center(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16.0),
              child: Chip(
                avatar: const Icon(Icons.timer, size: 16),
                label: Text(_formatTime(_recipeTotalSeconds)),
                backgroundColor: Colors.blue[100],
              ),
            ),
          ),
        ],
      ),
      body: Column(
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
                                currentStep.getLocalizedInstruction('en'),
                                style: Theme.of(context).textTheme.titleLarge,
                              ),
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
                                        Icon(Icons.lightbulb_outline,
                                            size: 16, color: Colors.amber[700]),
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
                      color: _isStepTimerRunning ? Colors.blue[50] : Colors.grey[100],
                      child: Padding(
                        padding: const EdgeInsets.all(16.0),
                        child: Column(
                          children: [
                            Text(
                              _isStepTimerRunning
                                  ? _formatTime(_stepSecondsRemaining)
                                  : '${currentStep.timeMinutes} minutes',
                              style: Theme.of(context).textTheme.displaySmall?.copyWith(
                                    color: _isStepTimerRunning
                                        ? Colors.blue[900]
                                        : Colors.grey[700],
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
                                if (_isStepTimerRunning)
                                  OutlinedButton.icon(
                                    onPressed: _addOneMinute,
                                    icon: const Icon(Icons.add),
                                    label: const Text('+1 Min'),
                                  ),
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
    );
  }
}
