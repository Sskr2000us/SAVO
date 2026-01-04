import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../models/planning.dart';
import '../models/profile_state.dart';
import '../services/api_client.dart';
import 'recipe_detail_screen.dart';

enum _ImportMode { url, text, photo }

class RecipeImportScreen extends StatefulWidget {
  const RecipeImportScreen({super.key});

  @override
  State<RecipeImportScreen> createState() => _RecipeImportScreenState();
}

class _RecipeImportScreenState extends State<RecipeImportScreen> {
  _ImportMode _mode = _ImportMode.url;
  final _urlCtrl = TextEditingController();
  final _textCtrl = TextEditingController();

  bool _loading = false;
  String? _error;

  @override
  void dispose() {
    _urlCtrl.dispose();
    _textCtrl.dispose();
    super.dispose();
  }

  String? _secondaryLanguage(BuildContext context) {
    final profile = Provider.of<ProfileState>(context, listen: false);
    final lang = (profile.preferredLanguage?.trim().isNotEmpty == true)
        ? profile.preferredLanguage!.trim()
        : (profile.primaryLanguage?.trim().isNotEmpty == true)
            ? profile.primaryLanguage!.trim()
            : null;
    if (lang == null || lang.isEmpty) return null;
    if (lang.toLowerCase() == 'en') return null;
    return lang;
  }

  Future<void> _importFromUrl() async {
    final url = _urlCtrl.text.trim();
    if (url.isEmpty) {
      setState(() => _error = 'Please paste a recipe URL');
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final secondary = _secondaryLanguage(context);
      final resp = await apiClient.post('/recipes/import', {
        'source_url': url,
        'output_language': 'en',
        if (secondary != null) 'secondary_language': secondary,
      });

      final recipe = Recipe.fromJson(resp['recipe'] as Map<String, dynamic>);
      if (!mounted) return;
      Navigator.push(
        context,
        MaterialPageRoute(builder: (_) => RecipeDetailScreen(recipe: recipe)),
      );
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _importFromText() async {
    final text = _textCtrl.text.trim();
    if (text.isEmpty) {
      setState(() => _error = 'Please paste recipe text');
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final secondary = _secondaryLanguage(context);
      final resp = await apiClient.post('/recipes/import', {
        'source_text': text,
        'output_language': 'en',
        if (secondary != null) 'secondary_language': secondary,
      });

      final recipe = Recipe.fromJson(resp['recipe'] as Map<String, dynamic>);
      if (!mounted) return;
      Navigator.push(
        context,
        MaterialPageRoute(builder: (_) => RecipeDetailScreen(recipe: recipe)),
      );
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _importFromPhoto() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final picker = ImagePicker();
      final file = await picker.pickImage(source: ImageSource.gallery);
      if (!mounted) return;
      if (file == null) {
        setState(() => _loading = false);
        return;
      }

      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final secondary = _secondaryLanguage(context);
      final resp = await apiClient.postMultipart(
        '/recipes/import/image',
        file: file,
        fields: {
          'output_language': 'en',
          if (secondary != null) 'secondary_language': secondary,
        },
      );

      final recipe = Recipe.fromJson(resp['recipe'] as Map<String, dynamic>);
      if (!mounted) return;
      Navigator.push(
        context,
        MaterialPageRoute(builder: (_) => RecipeDetailScreen(recipe: recipe)),
      );
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Import Recipe')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          SegmentedButton<_ImportMode>(
            segments: const [
              ButtonSegment(value: _ImportMode.url, label: Text('URL'), icon: Icon(Icons.link)),
              ButtonSegment(value: _ImportMode.text, label: Text('Text'), icon: Icon(Icons.text_snippet)),
              ButtonSegment(value: _ImportMode.photo, label: Text('Photo'), icon: Icon(Icons.photo)),
            ],
            selected: <_ImportMode>{_mode},
            onSelectionChanged: (v) {
              setState(() {
                _mode = v.first;
                _error = null;
              });
            },
          ),
          const SizedBox(height: 16),

          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Text(
                _error!,
                style: const TextStyle(color: Colors.red),
              ),
            ),

          if (_mode == _ImportMode.url) ...[
            TextField(
              controller: _urlCtrl,
              decoration: const InputDecoration(
                labelText: 'Recipe URL',
                hintText: 'https://…',
                border: OutlineInputBorder(),
              ),
              keyboardType: TextInputType.url,
            ),
            const SizedBox(height: 12),
            ElevatedButton.icon(
              onPressed: _loading ? null : _importFromUrl,
              icon: _loading
                  ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.download),
              label: Text(_loading ? 'Importing…' : 'Import'),
            ),
          ],

          if (_mode == _ImportMode.text) ...[
            TextField(
              controller: _textCtrl,
              decoration: const InputDecoration(
                labelText: 'Recipe text',
                hintText: 'Paste ingredients + instructions…',
                border: OutlineInputBorder(),
              ),
              minLines: 8,
              maxLines: 16,
            ),
            const SizedBox(height: 12),
            ElevatedButton.icon(
              onPressed: _loading ? null : _importFromText,
              icon: _loading
                  ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.download),
              label: Text(_loading ? 'Importing…' : 'Import'),
            ),
          ],

          if (_mode == _ImportMode.photo) ...[
            Text(
              'Pick a photo of a recipe (cookbook page, screenshot, etc.).',
              style: TextStyle(color: Colors.grey.shade600),
            ),
            const SizedBox(height: 12),
            ElevatedButton.icon(
              onPressed: _loading ? null : _importFromPhoto,
              icon: _loading
                  ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.photo_library),
              label: Text(_loading ? 'Importing…' : 'Choose Photo & Import'),
            ),
          ],
        ],
      ),
    );
  }
}
