/// YouTube ranking models
class YouTubeVideoCandidate {
  final String videoId;
  final String title;
  final String channel;
  final String language;
  final String? transcript;
  final Map<String, dynamic> metadata;

  YouTubeVideoCandidate({
    required this.videoId,
    required this.title,
    required this.channel,
    this.language = 'en',
    this.transcript,
    this.metadata = const {},
  });

  Map<String, dynamic> toJson() => {
        'video_id': videoId,
        'title': title,
        'channel': channel,
        'language': language,
        'transcript': transcript,
        'metadata': metadata,
      };
}

class RankedVideo {
  final String videoId;
  final String title;
  final String channel;
  final double trustScore;
  final double matchScore;
  final List<String> reasons;

  RankedVideo({
    required this.videoId,
    required this.title,
    required this.channel,
    required this.trustScore,
    required this.matchScore,
    this.reasons = const [],
  });

  factory RankedVideo.fromJson(Map<String, dynamic> json) {
    return RankedVideo(
      videoId: json['video_id'] ?? '',
      title: json['title'] ?? '',
      channel: json['channel'] ?? '',
      trustScore: (json['trust_score'] ?? 0.0).toDouble(),
      matchScore: (json['match_score'] ?? 0.0).toDouble(),
      reasons: List<String>.from(json['reasons'] ?? []),
    );
  }

  String get youtubeUrl => 'https://www.youtube.com/watch?v=$videoId';
  String get embedUrl => 'https://www.youtube.com/embed/$videoId';
  String get thumbnailUrl =>
      'https://img.youtube.com/vi/$videoId/hqdefault.jpg';
}

class YouTubeRankRequest {
  final String recipeName;
  final String? recipeCuisine;
  final List<String> recipeTechniques;
  final List<YouTubeVideoCandidate> candidates;
  final String outputLanguage;

  YouTubeRankRequest({
    required this.recipeName,
    this.recipeCuisine,
    this.recipeTechniques = const [],
    required this.candidates,
    this.outputLanguage = 'en',
  });

  Map<String, dynamic> toJson() => {
        'recipe_name': recipeName,
        'recipe_cuisine': recipeCuisine,
        'recipe_techniques': recipeTechniques,
        'candidates': candidates.map((c) => c.toJson()).toList(),
        'output_language': outputLanguage,
      };
}

class YouTubeRankResponse {
  final List<RankedVideo> rankedVideos;

  YouTubeRankResponse({required this.rankedVideos});

  factory YouTubeRankResponse.fromJson(Map<String, dynamic> json) {
    return YouTubeRankResponse(
      rankedVideos: (json['ranked_videos'] as List?)
              ?.map((v) => RankedVideo.fromJson(v))
              .toList() ??
          [],
    );
  }
}
