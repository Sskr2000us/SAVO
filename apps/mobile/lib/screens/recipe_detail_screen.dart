import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_client.dart';
import '../models/planning.dart';
import '../models/youtube.dart';
import 'cook_mode_screen.dart';
import 'package:url_launcher/url_launcher.dart';

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

  @override
  void initState() {
    super.initState();
    _loadYouTubeVideos();
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

      // Search YouTube for real videos using our API
      final searchResponse = await apiClient.post('/youtube/search', {
        'recipe_name': widget.recipe.getLocalizedName('en'),
        'cuisine': widget.recipe.cuisine,
        'max_results': 5,
      });

      final candidates = (searchResponse['candidates'] as List?)
          ?.map((c) => YouTubeVideoCandidate.fromJson(c as Map<String, dynamic>))
          .toList() ?? [];

      // If no results from YouTube API, skip video section
      if (candidates.isEmpty) {
        setState(() {
          _rankedVideos = [];
          _loadingVideos = false;
        });
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

      final response = await apiClient.post('/youtube/rank', request.toJson());
      final rankResponse = YouTubeRankResponse.fromJson(response);

      setState(() {
        _rankedVideos = rankResponse.rankedVideos;
        _loadingVideos = false;
      });
    } catch (e) {
      setState(() {
        _videoError = e.toString();
        _loadingVideos = false;
      });
    }
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.recipe.getLocalizedName('en')),
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

          // YouTube Videos Section
          if (_loadingVideos)
            const Center(
              child: Padding(
                padding: EdgeInsets.symmetric(vertical: 24.0),
                child: Column(
                  children: [
                    CircularProgressIndicator(),
                    SizedBox(height: 12),
                    Text('Finding YouTube tutorials...'),
                  ],
                ),
              ),
            )
          else if (_videoError != null)
            Card(
              color: Colors.orange[50],
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Row(
                  children: [
                    const Icon(Icons.warning, color: Colors.orange),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text('Could not load videos: $_videoError'),
                    ),
                  ],
                ),
              ),
            )
          else if (_rankedVideos != null && _rankedVideos!.isNotEmpty) ...[
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
            ...(_rankedVideos!.take(3).map((video) => _buildVideoCard(video))),
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
                builder: (_) => CookModeScreen(recipe: widget.recipe),
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
}
