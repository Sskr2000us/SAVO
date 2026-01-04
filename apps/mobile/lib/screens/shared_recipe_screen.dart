import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/planning.dart';
import '../services/api_client.dart';
import '../services/recipe_share_service.dart';
import 'recipe_detail_screen.dart';

class SharedRecipeScreen extends StatefulWidget {
  final String shareId;

  const SharedRecipeScreen({super.key, required this.shareId});

  @override
  State<SharedRecipeScreen> createState() => _SharedRecipeScreenState();
}

class _SharedRecipeScreenState extends State<SharedRecipeScreen> {
  Recipe? _recipe;
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final service = RecipeShareService();
      final data = await service.fetchShared(apiClient, widget.shareId);
      final recipeJson = (data['recipe'] as Map?)?.cast<String, dynamic>() ?? <String, dynamic>{};
      final recipe = Recipe.fromJson(recipeJson);

      setState(() {
        _recipe = recipe;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }

    if (_error != null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Shared Recipe')),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  'Could not load recipe',
                  style: Theme.of(context).textTheme.titleLarge,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                Text(
                  _error!,
                  style: Theme.of(context).textTheme.bodyMedium,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: _load,
                  child: const Text('Retry'),
                ),
              ],
            ),
          ),
        ),
      );
    }

    if (_recipe == null) {
      return const Scaffold(
        body: Center(child: Text('Recipe not found')),
      );
    }

    return RecipeDetailScreen(recipe: _recipe!);
  }
}
