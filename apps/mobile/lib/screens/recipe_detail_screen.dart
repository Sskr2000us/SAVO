import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/api_client.dart';
import '../services/scanning_service.dart';
import '../models/planning.dart';
import '../models/profile_state.dart';
import '../models/market_config_state.dart';
import '../models/youtube.dart';
import 'cook_mode_screen.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:share_plus/share_plus.dart';
import '../services/recipe_share_service.dart';

enum _RecipeLanguageMode { english, bilingual }

class RecipeDetailScreen extends StatefulWidget {
  final Recipe recipe;

  const RecipeDetailScreen({super.key, required this.recipe});

  @override
  State<RecipeDetailScreen> createState() => _RecipeDetailScreenState();
}

class _RecipeDetailScreenState extends State<RecipeDetailScreen> {
  List<RankedVideo>? _rankedVideos;
  bool _loadingVideos = false;
  String? _videoError;
  final Map<String, YouTubeSummary?> _videoSummaries = {};
  final Set<String> _loadingSummaries = {};
  
  // Serving calculator state
  int _targetServings = 4;
  bool _checkingSufficiency = false;
  Map<String, dynamic>? _sufficiencyResult;

  // Recipe language / presentation state
  bool _languageInitialized = false;
  String _recipeLanguageCode = 'en';
  bool _showBilingual = false;

  bool _sharing = false;

  @override
  void initState() {
    super.initState();
    _loadYouTubeVideos();
    _targetServings = 4; // Default to 4 servings
  }

  Future<void> _shareRecipe() async {
    if (_sharing) return;

    setState(() {
      _sharing = true;
    });

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final shareService = RecipeShareService();
      final shareId = await shareService.createShare(apiClient, widget.recipe);

      final origin = Uri.base.origin;
      final link = origin.isNotEmpty ? '$origin/r/$shareId' : '/r/$shareId';
      final title = widget.recipe.getLocalizedName('en');
      await Share.share('$title\n$link');
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Could not create share link: ${e.toString()}'),
            backgroundColor: Colors.red,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _sharing = false;
        });
      }
    }
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_languageInitialized) return;

    final profileState = Provider.of<ProfileState>(context, listen: false);
    final preferred = (profileState.preferredLanguage?.trim().isNotEmpty == true)
        ? profileState.preferredLanguage!.trim()
        : (profileState.primaryLanguage?.trim().isNotEmpty == true)
            ? profileState.primaryLanguage!.trim()
            : Localizations.localeOf(context).languageCode;

    final available = _availableRecipeLanguageCodes(widget.recipe);
    final nonEnglish = available.where((c) => c != 'en').toList()..sort();

    final chosen = available.contains(preferred)
        ? preferred
        : (nonEnglish.isNotEmpty ? nonEnglish.first : 'en');

    _recipeLanguageCode = chosen;
    _showBilingual = chosen != 'en' && available.contains(chosen);
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

  String? _secondaryLanguageCode(Recipe recipe) {
    final available = _availableRecipeLanguageCodes(recipe);
    if (_recipeLanguageCode != 'en' && available.contains(_recipeLanguageCode)) {
      return _recipeLanguageCode;
    }
    final nonEnglish = available.where((c) => c != 'en').toList()..sort();
    return nonEnglish.isNotEmpty ? nonEnglish.first : null;
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
      case 'de':
        return 'German';
      case 'it':
        return 'Italian';
      case 'pt':
        return 'Portuguese';
      case 'el':
        return 'Greek';
      case 'ar':
        return 'Arabic';
      default:
        return code.toUpperCase();
    }
  }

  String _titleCaseWords(String input) {
    final normalized = input
        .replaceAll('_', ' ')
        .replaceAll('-', ' ')
        .trim();
    if (normalized.isEmpty) return input;
    final parts = normalized.split(RegExp(r'\s+'));
    return parts
        .map((p) => p.isEmpty
            ? p
            : p[0].toUpperCase() + (p.length > 1 ? p.substring(1) : ''))
        .join(' ');
  }

  String _formatAmount(double amount) {
    final rounded = amount.roundToDouble();
    if ((amount - rounded).abs() < 1e-9) {
      return rounded.toInt().toString();
    }
    return amount
        .toStringAsFixed(2)
        .replaceAll(RegExp(r'0+$'), '')
        .replaceAll(RegExp(r'\.$'), '');
  }

  String _prettyNutritionKey(String key) {
    return _titleCaseWords(key);
  }

  String _buildRecipeMarkdown() {
    final recipe = widget.recipe;
    final secondaryCode = _secondaryLanguageCode(recipe);
    final showSecondary = _showBilingual && secondaryCode != null && secondaryCode != 'en';

    final nameEn = recipe.getLocalizedName('en').trim();
    final nameSecondary = showSecondary ? recipe.getLocalizedName(secondaryCode!).trim() : '';

    final buffer = StringBuffer();
    buffer.writeln('## ${nameEn.isEmpty ? recipe.recipeId : nameEn}');
    if (showSecondary && nameSecondary.isNotEmpty && nameSecondary != nameEn) {
      buffer.writeln('### $nameSecondary');
    }

    buffer.writeln('**Cuisine:** ${recipe.cuisine}');
    buffer.writeln('**Language:** ${showSecondary ? '${_languageLabel(secondaryCode!)} + English' : 'English'}');
    buffer.writeln('**Difficulty:** ${_titleCaseWords(recipe.difficulty)}');

    final t = recipe.estimatedTimes;
    if (t.totalMinutes > 0 || t.prepMinutes > 0 || t.cookMinutes > 0) {
      buffer.writeln(
        '**Time:** ${t.totalMinutes} minutes (Prep: ${t.prepMinutes}min, Cook: ${t.cookMinutes}min)',
      );
    }

    buffer.writeln('**Servings:** $_targetServings');
    buffer.writeln('');

    buffer.writeln('### Ingredients');
    for (final ing in recipe.ingredientsUsed) {
      final name = _titleCaseWords(ing.canonicalName);
      final unit = ing.unit.trim();
      final amount = _formatAmount(ing.amount);
      final qty = [amount, unit].where((x) => x.isNotEmpty).join(' ');
      buffer.writeln('- **$name:** $qty');
    }
    buffer.writeln('');

    buffer.writeln('### Instructions (English)');
    for (var i = 0; i < recipe.steps.length; i++) {
      final stepText = recipe.steps[i].getLocalizedInstruction('en').trim();
      if (stepText.isEmpty) continue;
      buffer.writeln('${i + 1}. $stepText');
    }
    buffer.writeln('');

    if (showSecondary) {
      buffer.writeln('### Instructions (${_languageLabel(secondaryCode!)})');
      for (var i = 0; i < recipe.steps.length; i++) {
        final stepText = recipe.steps[i].getLocalizedInstruction(secondaryCode!).trim();
        if (stepText.isEmpty) continue;
        buffer.writeln('${i + 1}. $stepText');
      }
      buffer.writeln('');
    }

    if (recipe.nutritionPerServing.isNotEmpty) {
      buffer.writeln('### Nutrition (Per Serving)');
      final keys = recipe.nutritionPerServing.keys.toList()..sort();
      for (final key in keys) {
        final value = recipe.nutritionPerServing[key];
        if (value == null) continue;
        buffer.writeln('- **${_prettyNutritionKey(key)}:** $value');
      }
      buffer.writeln('');
    }

    if (recipe.healthBenefits != null && recipe.healthBenefits!.isNotEmpty) {
      buffer.writeln('### Health Benefits');
      for (final b in recipe.healthBenefits!) {
        final title = (b['title'] ?? b['ingredient'] ?? '').trim();
        final desc = (b['description'] ?? b['benefit'] ?? '').trim();
        if (title.isEmpty && desc.isEmpty) continue;
        if (title.isNotEmpty && desc.isNotEmpty) {
          buffer.writeln('- **$title:** $desc');
        } else {
          buffer.writeln('- ${title.isNotEmpty ? title : desc}');
        }
      }
      buffer.writeln('');
    }

    final tips = <String>{};
    for (final s in recipe.steps) {
      for (final tip in s.tips) {
        final cleaned = tip.trim();
        if (cleaned.isNotEmpty) tips.add(cleaned);
      }
    }
    if (tips.isNotEmpty) {
      buffer.writeln("### Chef's Tips");
      final list = tips.toList()..sort();
      for (final tip in list) {
        buffer.writeln('- $tip');
      }
      buffer.writeln('');
    }

    return buffer.toString();
  }

  Future<void> _loadYouTubeVideos() async {
    setState(() {
      _loadingVideos = true;
      _videoError = null;
    });

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);

      // Extract techniques from recipe steps
      final techniques = _extractTechniques(widget.recipe.steps);

      print('🎥 Searching YouTube for: ${widget.recipe.getLocalizedName('en')}');

      // Search YouTube for real videos using our API
      final searchResponse = await apiClient.post('/youtube/search', {
        'recipe_name': widget.recipe.getLocalizedName('en'),
        'cuisine': widget.recipe.cuisine,
        'max_results': 5,
      });

      print('🎥 Search response: $searchResponse');

      final candidates = (searchResponse['candidates'] as List?)
          ?.map((c) => YouTubeVideoCandidate.fromJson(c as Map<String, dynamic>))
          .toList() ?? [];

      print('🎥 Found ${candidates.length} video candidates');

      // If no results from YouTube API, skip video section
      if (candidates.isEmpty) {
        setState(() {
          _rankedVideos = [];
          _loadingVideos = false;
          _videoError = 'No YouTube videos found for "${widget.recipe.getLocalizedName('en')}"';
        });
        print('🎥 No videos found');
        return;
      }

      // Rank candidates using /youtube/rank
      final request = YouTubeRankRequest(
        recipeName: widget.recipe.getLocalizedName('en'),
        recipeCuisine: widget.recipe.cuisine,
        recipeTechniques: techniques,
        candidates: candidates,
        outputLanguage: 'en',
      );

      print('🎥 Ranking ${candidates.length} videos...');
      try {
        final response = await apiClient.post('/youtube/rank', request.toJson());
        final rankResponse = YouTubeRankResponse.fromJson(response);

        print('🎥 Successfully ranked ${rankResponse.rankedVideos.length} videos');

        setState(() {
          _rankedVideos = rankResponse.rankedVideos;
          _loadingVideos = false;
        });
      } catch (e) {
        print('🎥 Ranking failed, falling back to keyword match: $e');
        setState(() {
          _rankedVideos = _fallbackRankFromCandidates(
            candidates,
            widget.recipe.getLocalizedName('en'),
          );
          _videoError = 'Showing YouTube results (ranking unavailable)';
          _loadingVideos = false;
        });
      }
    } catch (e, stackTrace) {
      print('🎥 ERROR loading YouTube videos: $e');
      print('🎥 Stack trace: $stackTrace');
      setState(() {
        _videoError = e.toString();
        _loadingVideos = false;
      });
    }
  }

  List<RankedVideo> _fallbackRankFromCandidates(
    List<YouTubeVideoCandidate> candidates,
    String recipeName,
  ) {
    String normalize(String v) {
      return v
          .toLowerCase()
          .replaceAll(RegExp(r'[^a-z0-9\s]'), ' ')
          .replaceAll(RegExp(r'\s+'), ' ')
          .trim();
    }

    Set<String> tokens(String v) {
      final n = normalize(v);
      return n
          .split(' ')
          .where((t) => t.length > 1)
          .toSet();
    }

    final q = tokens(recipeName);
    double matchScore(String title) {
      final t = tokens(title);
      if (q.isEmpty || t.isEmpty) return 0.0;
      return q.intersection(t).length / q.length;
    }

    double trustScore(String channel, String title) {
      final text = (channel + ' ' + title).toLowerCase();
      var score = 0.5;
      if (text.contains('official') || text.contains('kitchen') || text.contains('chef')) {
        score += 0.15;
      }
      if (text.contains('shorts') || text.contains('asmr') || text.contains('mukbang')) {
        score -= 0.15;
      }
      if (score < 0) score = 0;
      if (score > 1) score = 1;
      return score;
    }

    final ranked = candidates
        .map(
          (c) => RankedVideo(
            videoId: c.videoId,
            title: c.title,
            channel: c.channel,
            trustScore: trustScore(c.channel, c.title),
            matchScore: matchScore(c.title),
            reasons: const ['Fallback ranking (keyword match)'],
          ),
        )
        .toList();

    ranked.sort((a, b) {
      final ms = b.matchScore.compareTo(a.matchScore);
      if (ms != 0) return ms;
      return b.trustScore.compareTo(a.trustScore);
    });

    return ranked;
  }

  List<String> _extractTechniques(List<RecipeStep> steps) {
    final techniques = <String>{};
    for (final step in steps) {
      final instruction =
          step.instruction['en']?.toLowerCase() ?? '';
      
      // Extract common cooking techniques
      if (instruction.contains('sauté') || instruction.contains('saute')) {
        techniques.add('sautéing');
      }
      if (instruction.contains('chop') || instruction.contains('dice')) {
        techniques.add('knife skills');
      }
      if (instruction.contains('boil')) techniques.add('boiling');
      if (instruction.contains('simmer')) techniques.add('simmering');
      if (instruction.contains('roast') || instruction.contains('bake')) {
        techniques.add('roasting');
      }
      if (instruction.contains('stir')) techniques.add('stirring');
      if (instruction.contains('fold')) techniques.add('folding');
      if (instruction.contains('whisk')) techniques.add('whisking');
      if (instruction.contains('grill')) techniques.add('grilling');
      if (instruction.contains('fry')) techniques.add('frying');
    }
    return techniques.toList();
  }

  List<YouTubeVideoCandidate> _createMockCandidates(
      String recipeName, String cuisine) {
    // Mock candidates - in production, replace with YouTube API search
    // Search query: "$recipeName $cuisine recipe"
    return [
      YouTubeVideoCandidate(
        videoId: 'mock_${recipeName.hashCode}_1',
        title: 'How to Make $recipeName - $cuisine Chef',
        channel: '$cuisine Cooking Academy',
        language: 'en',
        transcript: 'Today we make authentic $recipeName...',
        metadata: {'duration': '12:00', 'views': 500000},
      ),
      YouTubeVideoCandidate(
        videoId: 'mock_${recipeName.hashCode}_2',
        title: '$recipeName Recipe - Step by Step',
        channel: 'Culinary Institute',
        language: 'en',
        transcript: 'Welcome to our $recipeName tutorial...',
        metadata: {'duration': '15:00', 'views': 1000000},
      ),
      YouTubeVideoCandidate(
        videoId: 'mock_${recipeName.hashCode}_3',
        title: 'Quick $recipeName Recipe',
        channel: 'Fast Cooking Channel',
        language: 'en',
        transcript: 'This is a quick $recipeName dish...',
        metadata: {'duration': '8:00', 'views': 200000},
      ),
    ];
  }

  Future<void> _launchYouTubeUrl(String url) async {
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not open YouTube: $url')),
        );
      }
    }
  }

  Future<void> _loadVideoSummary(String videoId) async {
    if (_loadingSummaries.contains(videoId) || _videoSummaries.containsKey(videoId)) {
      return;
    }

    setState(() {
      _loadingSummaries.add(videoId);
    });

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final request = YouTubeSummaryRequest(
        videoId: videoId,
        recipeName: widget.recipe.getLocalizedName('en'),
        outputLanguage: 'en',
      );

      final response = await apiClient.post('/youtube/summary', request.toJson());
      final summary = YouTubeSummary.fromJson(response);

      setState(() {
        _videoSummaries[videoId] = summary;
        _loadingSummaries.remove(videoId);
      });
    } catch (e) {
      setState(() {
        _videoSummaries[videoId] = null;
        _loadingSummaries.remove(videoId);
      });
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not load summary: ${e.toString()}')),
        );
      }
    }
  }

  Future<void> _checkSufficiency() async {
    setState(() {
      _checkingSufficiency = true;
      _sufficiencyResult = null;
    });

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final scanningService = ScanningService();
      final result = await scanningService.checkSufficiency(
        recipeId: widget.recipe.recipeId,
        servings: _targetServings,
        apiClient: apiClient,
      );

      setState(() {
        _sufficiencyResult = result;
        _checkingSufficiency = false;
      });

      // Persist latest shopping list for the Shopping List screen
      try {
        if (result['success'] == true) {
          final prefs = await SharedPreferences.getInstance();
          final list = result['shopping_list'] ?? [];
          await prefs.setString('savo.shopping_list.latest', jsonEncode(list));
        }
      } catch (_) {
        // Best-effort only
      }
    } catch (e) {
      setState(() {
        _checkingSufficiency = false;
      });
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Could not check sufficiency: ${e.toString()}'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final market = Provider.of<MarketConfigState>(context, listen: true);
    final canShare = market.isEnabled('shareable_recipes');

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.recipe.getLocalizedName('en')),
        actions: [
          if (canShare)
            IconButton(
              tooltip: 'Share recipe',
              onPressed: _sharing ? null : _shareRecipe,
              icon: _sharing
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.share),
            ),
          PopupMenuButton<_RecipeLanguageMode>(
            tooltip: 'Recipe language',
            initialValue:
                _showBilingual ? _RecipeLanguageMode.bilingual : _RecipeLanguageMode.english,
            onSelected: (mode) {
              setState(() {
                _showBilingual = mode == _RecipeLanguageMode.bilingual;
              });
            },
            itemBuilder: (context) => const [
              PopupMenuItem(
                value: _RecipeLanguageMode.english,
                child: Text('English'),
              ),
              PopupMenuItem(
                value: _RecipeLanguageMode.bilingual,
                child: Text('Bilingual'),
              ),
            ],
            icon: const Icon(Icons.translate),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Header with badges
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              Chip(
                avatar: const Icon(Icons.timer, size: 16),
                label: Text('${widget.recipe.estimatedTimes.totalMinutes} min'),
              ),
              Chip(
                avatar: const Icon(Icons.signal_cellular_alt, size: 16),
                label: Text(widget.recipe.difficulty),
              ),
              Chip(
                avatar: const Icon(Icons.restaurant, size: 16),
                label: Text(widget.recipe.cuisine),
              ),
              Chip(
                avatar: const Icon(Icons.whatshot, size: 16),
                label: Text(widget.recipe.cookingMethod),
              ),
            ],
          ),
          const SizedBox(height: 24),

            // Recipe (Markdown) Section
            Text(
              'Recipe',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 12),
            Card(
              elevation: 2,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: MarkdownBody(
                  data: _buildRecipeMarkdown(),
                  selectable: true,
                  styleSheet: MarkdownStyleSheet.fromTheme(Theme.of(context)).copyWith(
                    h2: Theme.of(context).textTheme.headlineSmall,
                    h3: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 24),

          // YouTube Videos Section
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'YouTube Tutorials',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              Icon(Icons.ondemand_video, color: Colors.red[600]),
            ],
          ),
          const SizedBox(height: 12),
          
          if (_loadingVideos)
            const Center(
              child: Padding(
                padding: EdgeInsets.all(16.0),
                child: CircularProgressIndicator(),
              ),
            )
          else if (_rankedVideos != null && _rankedVideos!.isNotEmpty)
            ...(_rankedVideos!.take(3).map((video) => _buildVideoCard(video)))
          else
            Padding(
              padding: const EdgeInsets.all(16.0),
              child: Text(
                _videoError?.trim().isNotEmpty == true
                    ? _videoError!.trim()
                    : 'No YouTube videos available for this recipe',
                style: TextStyle(
                  color: Colors.grey[600],
                  fontStyle: FontStyle.italic,
                ),
              ),
            ),
          const SizedBox(height: 24),

          // Serving Calculator Section
          Card(
            elevation: 2,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.restaurant_menu, color: Color(0xFF4CAF50)),
                      const SizedBox(width: 8),
                      Text(
                        'Serving Calculator',
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  
                  // Serving size selector
                  Row(
                    children: [
                      const Text(
                        'How many people?',
                        style: TextStyle(fontSize: 14),
                      ),
                      const Spacer(),
                      IconButton(
                        icon: const Icon(Icons.remove_circle_outline),
                        onPressed: _targetServings > 1
                            ? () {
                                setState(() {
                                  _targetServings--;
                                  _sufficiencyResult = null;
                                });
                              }
                            : null,
                        color: const Color(0xFF4CAF50),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                        decoration: BoxDecoration(
                          border: Border.all(color: Colors.grey.shade300),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(
                          _targetServings.toString(),
                          style: const TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                      IconButton(
                        icon: const Icon(Icons.add_circle_outline),
                        onPressed: () {
                          setState(() {
                            _targetServings++;
                            _sufficiencyResult = null;
                          });
                        },
                        color: const Color(0xFF4CAF50),
                      ),
                    ],
                  ),
                  
                  const SizedBox(height: 12),
                  
                  // Check button
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      icon: _checkingSufficiency
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                              ),
                            )
                          : const Icon(Icons.check_circle_outline),
                      label: Text(_checkingSufficiency
                          ? 'Checking...'
                          : 'Check if I have enough'),
                      onPressed: _checkingSufficiency ? null : _checkSufficiency,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF4CAF50),
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                    ),
                  ),
                  
                  // Results
                  if (_sufficiencyResult != null) ...[
                    const SizedBox(height: 16),
                    const Divider(),
                    const SizedBox(height: 12),
                    
                    if (_sufficiencyResult!['success'] == true) ...[
                      // Sufficient or not
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: _sufficiencyResult!['sufficient'] == true
                              ? Colors.green.shade50
                              : Colors.orange.shade50,
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(
                            color: _sufficiencyResult!['sufficient'] == true
                                ? Colors.green
                                : Colors.orange,
                          ),
                        ),
                        child: Row(
                          children: [
                            Icon(
                              _sufficiencyResult!['sufficient'] == true
                                  ? Icons.check_circle
                                  : Icons.warning,
                              color: _sufficiencyResult!['sufficient'] == true
                                  ? Colors.green
                                  : Colors.orange,
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Text(
                                _sufficiencyResult!['message'] ?? '',
                                style: TextStyle(
                                  color: _sufficiencyResult!['sufficient'] == true
                                      ? Colors.green.shade900
                                      : Colors.orange.shade900,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                      
                      // Missing ingredients
                      if (_sufficiencyResult!['missing'] != null &&
                          (_sufficiencyResult!['missing'] as List).isNotEmpty) ...[
                        const SizedBox(height: 16),
                        const Text(
                          'Missing Ingredients:',
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 14,
                          ),
                        ),
                        const SizedBox(height: 8),
                        ...(_sufficiencyResult!['missing'] as List).map((item) {
                          return Padding(
                            padding: const EdgeInsets.symmetric(vertical: 4),
                            child: Row(
                              children: [
                                const Icon(Icons.close, color: Colors.red, size: 18),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    '${item['ingredient']}: Need ${item['needed']} ${item['unit']}',
                                    style: const TextStyle(fontSize: 13),
                                  ),
                                ),
                              ],
                            ),
                          );
                        }),
                      ],
                      
                      // Shopping list
                      if (_sufficiencyResult!['shopping_list'] != null &&
                          (_sufficiencyResult!['shopping_list'] as List).isNotEmpty) ...[
                        const SizedBox(height: 16),
                        const Divider(),
                        const SizedBox(height: 12),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            const Text(
                              'Shopping List:',
                              style: TextStyle(
                                fontWeight: FontWeight.bold,
                                fontSize: 14,
                              ),
                            ),
                            TextButton.icon(
                              icon: const Icon(Icons.copy, size: 16),
                              label: const Text('Copy'),
                              onPressed: () {
                                // Copy shopping list to clipboard
                                final shoppingList = (_sufficiencyResult!['shopping_list'] as List)
                                    .map((item) => '${item['quantity']} ${item['unit']} ${item['ingredient']}')
                                    .join('\n');
                                
                                Clipboard.setData(ClipboardData(text: shoppingList)).then((_) {
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    const SnackBar(
                                      content: Text('Shopping list copied to clipboard!'),
                                      duration: Duration(seconds: 2),
                                      backgroundColor: Colors.green,
                                    ),
                                  );
                                });
                              },
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        ...(_sufficiencyResult!['shopping_list'] as List).map((item) {
                          return Container(
                            margin: const EdgeInsets.symmetric(vertical: 4),
                            padding: const EdgeInsets.all(8),
                            decoration: BoxDecoration(
                              color: Colors.grey.shade100,
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: Row(
                              children: [
                                const Icon(Icons.shopping_cart, size: 18),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    '${item['quantity']} ${item['unit']} ${item['ingredient']}',
                                    style: const TextStyle(fontSize: 13),
                                  ),
                                ),
                              ],
                            ),
                          );
                        }),
                      ],
                    ],
                    // Silently handle errors - don't show error banner
                  ],
                ],
              ),
            ),
          ),
          
          const SizedBox(height: 24),

          // Nutrition Information Section
          if (widget.recipe.nutritionPerServing.isNotEmpty) ...[
            Card(
              elevation: 2,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.pie_chart, color: Color(0xFF2196F3)),
                        const SizedBox(width: 8),
                        Text(
                          'Nutrition Per Serving',
                          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    Wrap(
                      spacing: 12,
                      runSpacing: 12,
                      children: [
                        if (widget.recipe.nutritionPerServing['calories_kcal'] != null)
                          _buildNutrientChip(
                            icon: Icons.local_fire_department,
                            label: 'Calories',
                            value: '${widget.recipe.nutritionPerServing['calories_kcal']} kcal',
                            color: Colors.orange,
                          ),
                        if (widget.recipe.nutritionPerServing['protein_g'] != null)
                          _buildNutrientChip(
                            icon: Icons.fitness_center,
                            label: 'Protein',
                            value: '${widget.recipe.nutritionPerServing['protein_g']}g',
                            color: Colors.red,
                          ),
                        if (widget.recipe.nutritionPerServing['carbohydrates_g'] != null)
                          _buildNutrientChip(
                            icon: Icons.bakery_dining,
                            label: 'Carbs',
                            value: '${widget.recipe.nutritionPerServing['carbohydrates_g']}g',
                            color: Colors.amber,
                          ),
                        if (widget.recipe.nutritionPerServing['fat_g'] != null)
                          _buildNutrientChip(
                            icon: Icons.water_drop,
                            label: 'Fat',
                            value: '${widget.recipe.nutritionPerServing['fat_g']}g',
                            color: Colors.yellow[700]!,
                          ),
                        if (widget.recipe.nutritionPerServing['fiber_g'] != null)
                          _buildNutrientChip(
                            icon: Icons.grass,
                            label: 'Fiber',
                            value: '${widget.recipe.nutritionPerServing['fiber_g']}g',
                            color: Colors.green,
                          ),
                        if (widget.recipe.nutritionPerServing['calcium_mg'] != null)
                          _buildNutrientChip(
                            icon: Icons.medical_services,
                            label: 'Calcium',
                            value: '${widget.recipe.nutritionPerServing['calcium_mg']}mg',
                            color: Colors.grey,
                          ),
                      ],
                    ),
                    
                    // Additional micronutrients in expandable section
                    if (_hasAdditionalMicronutrients()) ...[
                      const SizedBox(height: 12),
                      ExpansionTile(
                        title: const Text('More Details', style: TextStyle(fontSize: 14)),
                        tilePadding: EdgeInsets.zero,
                        childrenPadding: const EdgeInsets.only(top: 8),
                        children: [
                          Wrap(
                            spacing: 12,
                            runSpacing: 12,
                            children: _buildAdditionalMicronutrients(),
                          ),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),
          ],

          // Health Benefits Section
          if (widget.recipe.healthBenefits != null && widget.recipe.healthBenefits!.isNotEmpty) ...[
            Card(
              elevation: 2,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.favorite, color: Color(0xFFE91E63)),
                        const SizedBox(width: 8),
                        Text(
                          'Health Benefits',
                          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    ...widget.recipe.healthBenefits!.map((benefit) {
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Container(
                              margin: const EdgeInsets.only(top: 2),
                              padding: const EdgeInsets.all(6),
                              decoration: BoxDecoration(
                                color: Colors.green[50],
                                borderRadius: BorderRadius.circular(6),
                              ),
                              child: Icon(
                                Icons.eco,
                                size: 16,
                                color: Colors.green[700],
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    benefit['ingredient'] ?? '',
                                    style: TextStyle(
                                      fontWeight: FontWeight.bold,
                                      fontSize: 14,
                                      color: Colors.green[900],
                                    ),
                                  ),
                                  const SizedBox(height: 2),
                                  Text(
                                    benefit['benefit'] ?? '',
                                    style: TextStyle(
                                      fontSize: 13,
                                      color: Colors.grey[700],
                                      height: 1.4,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      );
                    }),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),
          ],

          // Ingredients
          Text(
            'Ingredients',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 12),
          ...widget.recipe.ingredientsUsed.map((ingredient) => Padding(
                padding: const EdgeInsets.symmetric(vertical: 4.0),
                child: Row(
                  children: [
                    const Icon(Icons.check_circle_outline, size: 20),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        '${ingredient.amount} ${ingredient.unit} ${ingredient.canonicalName}',
                      ),
                    ),
                  ],
                ),
              )),
          const SizedBox(height: 24),

          // Steps preview
          Text(
            'Steps',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 12),
          ...widget.recipe.steps.take(3).map((step) => Card(
                margin: const EdgeInsets.only(bottom: 8),
                child: ListTile(
                  leading: CircleAvatar(
                    child: Text('${step.step}'),
                  ),
                  title: Text(
                    step.getLocalizedInstruction('en'),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  trailing: step.timeMinutes > 0
                      ? Chip(
                          label: Text('${step.timeMinutes}m'),
                          backgroundColor: Colors.blue[100],
                        )
                      : null,
                ),
              )),
          if (widget.recipe.steps.length > 3)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8.0),
              child: Text(
                '+ ${widget.recipe.steps.length - 3} more steps',
                style: Theme.of(context).textTheme.bodySmall,
                textAlign: TextAlign.center,
              ),
            ),
        ],
      ),
      bottomNavigationBar: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surface,
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.1),
              blurRadius: 8,
              offset: const Offset(0, -2),
            ),
          ],
        ),
        child: FilledButton.icon(
          onPressed: () {
            Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => CookModeScreen(
                  recipe: widget.recipe,
                  servings: _targetServings,
                  preferredLanguageCode: _recipeLanguageCode,
                  startBilingual: _showBilingual,
                ),
              ),
            );
          },
          icon: const Icon(Icons.play_arrow),
          label: const Text('Start Cook Mode'),
        ),
      ),
    );
  }

  Widget _buildVideoCard(RankedVideo video) {
    final summary = _videoSummaries[video.videoId];
    final isLoadingSummary = _loadingSummaries.contains(video.videoId);
    final showSummary = _videoSummaries.containsKey(video.videoId);

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Column(
        children: [
          InkWell(
            onTap: () => _launchYouTubeUrl(video.youtubeUrl),
            borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
            child: Padding(
              padding: const EdgeInsets.all(12.0),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Thumbnail
                  ClipRRect(
                    borderRadius: BorderRadius.circular(8),
                    child: Container(
                      width: 120,
                      height: 68,
                      color: Colors.grey[300],
                      child: Stack(
                        fit: StackFit.expand,
                        children: [
                          Image.network(
                            video.thumbnailUrl,
                            fit: BoxFit.cover,
                            errorBuilder: (_, __, ___) => Container(
                              color: Colors.grey[300],
                              child: const Icon(Icons.play_circle_outline, size: 40),
                            ),
                          ),
                          Center(
                            child: Container(
                              padding: const EdgeInsets.all(8),
                              decoration: BoxDecoration(
                                color: Colors.black.withOpacity(0.7),
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: const Icon(
                                Icons.play_arrow,
                                color: Colors.white,
                                size: 24,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  // Video info
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          video.title,
                          style: const TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 14,
                          ),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 4),
                        Text(
                          video.channel,
                          style: TextStyle(
                            fontSize: 12,
                            color: Colors.grey[600],
                          ),
                        ),
                        const SizedBox(height: 8),
                        // Scores
                        Wrap(
                          spacing: 6,
                          runSpacing: 6,
                          children: [
                            _buildScoreChip(
                              'Trust',
                              video.trustScore,
                              Colors.blue,
                            ),
                            _buildScoreChip(
                              'Match',
                              video.matchScore,
                              Colors.green,
                            ),
                          ],
                        ),
                        if (video.reasons.isNotEmpty) ...[
                          const SizedBox(height: 8),
                          Text(
                            video.reasons.first,
                            style: TextStyle(
                              fontSize: 11,
                              color: Colors.grey[700],
                              fontStyle: FontStyle.italic,
                            ),
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          // AI Summary button
          if (!showSummary)
            TextButton.icon(
              onPressed: isLoadingSummary ? null : () => _loadVideoSummary(video.videoId),
              icon: isLoadingSummary
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.auto_awesome, size: 16),
              label: Text(isLoadingSummary ? 'Loading AI Summary...' : 'Show AI Summary'),
              style: TextButton.styleFrom(
                foregroundColor: Colors.purple[700],
              ),
            ),
          // AI Summary content
          if (showSummary && summary != null) ...[
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.purple[50],
                border: Border(top: BorderSide(color: Colors.purple[100]!)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(Icons.auto_awesome, size: 18, color: Colors.purple[700]),
                      const SizedBox(width: 8),
                      Text(
                        'AI Summary',
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          color: Colors.purple[900],
                        ),
                      ),
                      const Spacer(),
                      Chip(
                        label: Text(
                          summary.watchTimeEstimate,
                          style: const TextStyle(fontSize: 11),
                        ),
                        materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                        visualDensity: VisualDensity.compact,
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    summary.summary,
                    style: TextStyle(color: Colors.grey[800]),
                  ),
                  if (summary.keyTechniques.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    Text(
                      'Key Techniques:',
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 12,
                        color: Colors.purple[900],
                      ),
                    ),
                    const SizedBox(height: 4),
                    Wrap(
                      spacing: 6,
                      runSpacing: 6,
                      children: summary.keyTechniques
                          .map((tech) => Chip(
                                label: Text(tech, style: const TextStyle(fontSize: 11)),
                                backgroundColor: Colors.purple[100],
                                materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                                visualDensity: VisualDensity.compact,
                              ))
                          .toList(),
                    ),
                  ],
                  if (summary.timestampHighlights.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    Text(
                      'Key Moments:',
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 12,
                        color: Colors.purple[900],
                      ),
                    ),
                    const SizedBox(height: 6),
                    ...summary.timestampHighlights.map((highlight) => Padding(
                          padding: const EdgeInsets.only(top: 4),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 6,
                                  vertical: 2,
                                ),
                                decoration: BoxDecoration(
                                  color: Colors.purple[200],
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: Text(
                                  highlight.time,
                                  style: const TextStyle(
                                    fontSize: 11,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  highlight.description,
                                  style: const TextStyle(fontSize: 12),
                                ),
                              ),
                            ],
                          ),
                        )),
                  ],
                  const SizedBox(height: 8),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      TextButton(
                        onPressed: () {
                          setState(() {
                            _videoSummaries.remove(video.videoId);
                          });
                        },
                        child: const Text('Hide'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildScoreChip(String label, double score, Color color) {
    final percentage = (score * 100).round();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            label,
            style: TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w600,
              color: color.withOpacity(0.9),
            ),
          ),
          const SizedBox(width: 4),
          Text(
            '$percentage%',
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildNutrientChip({
    required IconData icon,
    required String label,
    required String value,
    required Color color,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 18, color: color),
          const SizedBox(width: 6),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                style: TextStyle(
                  fontSize: 10,
                  color: Colors.grey[700],
                ),
              ),
              Text(
                value,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.bold,
                  color: color,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  bool _hasAdditionalMicronutrients() {
    final nutrition = widget.recipe.nutritionPerServing;
    return nutrition['iron_mg'] != null ||
        nutrition['vitamin_c_mg'] != null ||
        nutrition['vitamin_a_iu'] != null ||
        nutrition['potassium_mg'] != null ||
        nutrition['sodium_mg'] != null;
  }

  List<Widget> _buildAdditionalMicronutrients() {
    final List<Widget> widgets = [];
    final nutrition = widget.recipe.nutritionPerServing;

    if (nutrition['iron_mg'] != null) {
      widgets.add(_buildNutrientChip(
        icon: Icons.bloodtype,
        label: 'Iron',
        value: '${nutrition['iron_mg']}mg',
        color: Colors.brown,
      ));
    }

    if (nutrition['vitamin_c_mg'] != null) {
      widgets.add(_buildNutrientChip(
        icon: Icons.lightbulb,
        label: 'Vitamin C',
        value: '${nutrition['vitamin_c_mg']}mg',
        color: Colors.orange[300]!,
      ));
    }

    if (nutrition['vitamin_a_iu'] != null) {
      widgets.add(_buildNutrientChip(
        icon: Icons.visibility,
        label: 'Vitamin A',
        value: '${nutrition['vitamin_a_iu']} IU',
        color: Colors.deepOrange,
      ));
    }

    if (nutrition['potassium_mg'] != null) {
      widgets.add(_buildNutrientChip(
        icon: Icons.favorite,
        label: 'Potassium',
        value: '${nutrition['potassium_mg']}mg',
        color: Colors.pink,
      ));
    }

    if (nutrition['sodium_mg'] != null) {
      widgets.add(_buildNutrientChip(
        icon: Icons.grain,
        label: 'Sodium',
        value: '${nutrition['sodium_mg']}mg',
        color: Colors.blueGrey,
      ));
    }

    return widgets;
  }
}
