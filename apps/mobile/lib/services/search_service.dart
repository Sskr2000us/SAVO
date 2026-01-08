/// Search Service for Flutter Mobile App
/// Provides multi-language, semantic, fuzzy, and voice search

import 'dart:convert';
import 'package:http/http.dart' as http;

class SearchService {
  final String baseUrl;
  
  SearchService({required this.baseUrl});
  
  /// Multi-language search across all ingredient names and aliases
  Future<SearchResponse> multiLanguageSearch({
    required String query,
    int limit = 20,
    String? language,
    String? category,
  }) async {
    final queryParams = {
      'query': query,
      'limit': limit.toString(),
      if (language != null) 'language': language,
      if (category != null) 'category': category,
    };
    
    final uri = Uri.parse('$baseUrl/api/search/multi-language')
        .replace(queryParameters: queryParams);
    
    final response = await http.get(uri);
    
    if (response.statusCode == 200) {
      return SearchResponse.fromJson(json.decode(response.body));
    } else {
      throw Exception('Multi-language search failed: ${response.statusCode}');
    }
  }
  
  /// Semantic search using vector embeddings
  Future<SearchResponse> semanticSearch({
    required String query,
    int limit = 20,
    double minSimilarity = 0.5,
    String? language,
    String? category,
  }) async {
    final uri = Uri.parse('$baseUrl/api/search/semantic');
    
    final response = await http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: json.encode({
        'query': query,
        'limit': limit,
        'min_similarity': minSimilarity,
        if (language != null) 'language': language,
        if (category != null) 'category': category,
      }),
    );
    
    if (response.statusCode == 200) {
      return SearchResponse.fromJson(json.decode(response.body));
    } else if (response.statusCode == 503) {
      throw Exception('Semantic search unavailable. Embeddings not generated.');
    } else {
      throw Exception('Semantic search failed: ${response.statusCode}');
    }
  }
  
  /// Fuzzy search with typo tolerance
  Future<SearchResponse> fuzzySearch({
    required String query,
    int limit = 20,
    int threshold = 70,
    String? language,
  }) async {
    final uri = Uri.parse('$baseUrl/api/search/fuzzy');
    
    final response = await http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: json.encode({
        'query': query,
        'limit': limit,
        'threshold': threshold,
        if (language != null) 'language': language,
      }),
    );
    
    if (response.statusCode == 200) {
      return SearchResponse.fromJson(json.decode(response.body));
    } else {
      throw Exception('Fuzzy search failed: ${response.statusCode}');
    }
  }
  
  /// Hybrid search combining multiple strategies (RECOMMENDED)
  Future<SearchResponse> hybridSearch({
    required String query,
    int limit = 20,
    String? language,
    String? category,
    bool useSemantic = true,
    bool useFuzzy = true,
  }) async {
    final uri = Uri.parse('$baseUrl/api/search/hybrid');
    
    final response = await http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: json.encode({
        'query': query,
        'limit': limit,
        'use_semantic': useSemantic,
        'use_fuzzy': useFuzzy,
        if (language != null) 'language': language,
        if (category != null) 'category': category,
      }),
    );
    
    if (response.statusCode == 200) {
      return SearchResponse.fromJson(json.decode(response.body));
    } else {
      throw Exception('Hybrid search failed: ${response.statusCode}');
    }
  }
  
  /// Voice search optimized for speech-to-text input
  Future<SearchResponse> voiceSearch({
    required String audioText,
    int limit = 20,
    String? language,
  }) async {
    final uri = Uri.parse('$baseUrl/api/search/voice');
    
    final response = await http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: json.encode({
        'audio_text': audioText,
        'limit': limit,
        if (language != null) 'language': language,
      }),
    );
    
    if (response.statusCode == 200) {
      return SearchResponse.fromJson(json.decode(response.body));
    } else {
      throw Exception('Voice search failed: ${response.statusCode}');
    }
  }
  
  /// Autocomplete suggestions
  Future<AutocompleteResponse> autocomplete({
    required String prefix,
    int limit = 10,
    String? language,
  }) async {
    final queryParams = {
      'prefix': prefix,
      'limit': limit.toString(),
      if (language != null) 'language': language,
    };
    
    final uri = Uri.parse('$baseUrl/api/search/autocomplete')
        .replace(queryParameters: queryParams);
    
    final response = await http.get(uri);
    
    if (response.statusCode == 200) {
      return AutocompleteResponse.fromJson(json.decode(response.body));
    } else {
      throw Exception('Autocomplete failed: ${response.statusCode}');
    }
  }
  
  /// Health check
  Future<bool> checkHealth() async {
    try {
      final uri = Uri.parse('$baseUrl/api/search/health');
      final response = await http.get(uri);
      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }
}

// ============================================================================
// DATA MODELS
// ============================================================================

class SearchResponse {
  final String query;
  final String? language;
  final String? category;
  final List<SearchResult> results;
  final int count;
  
  SearchResponse({
    required this.query,
    this.language,
    this.category,
    required this.results,
    required this.count,
  });
  
  factory SearchResponse.fromJson(Map<String, dynamic> json) {
    return SearchResponse(
      query: json['query'] ?? json['transcribed_text'] ?? '',
      language: json['language'],
      category: json['category'],
      results: (json['results'] as List)
          .map((r) => SearchResult.fromJson(r))
          .toList(),
      count: json['count'],
    );
  }
}

class SearchResult {
  final String id;
  final String canonicalName;
  final String category;
  final String? subcategory;
  final Map<String, dynamic> names;
  final List<String>? commonUses;
  final String matchType;
  final double? finalScore;
  final List<String>? searchMethods;
  final String? matchedAlias;
  final String? matchedLanguage;
  final int? relevanceScore;
  final int? fuzzyScore;
  final double? similarity;
  
  SearchResult({
    required this.id,
    required this.canonicalName,
    required this.category,
    this.subcategory,
    required this.names,
    this.commonUses,
    required this.matchType,
    this.finalScore,
    this.searchMethods,
    this.matchedAlias,
    this.matchedLanguage,
    this.relevanceScore,
    this.fuzzyScore,
    this.similarity,
  });
  
  factory SearchResult.fromJson(Map<String, dynamic> json) {
    return SearchResult(
      id: json['id'],
      canonicalName: json['canonical_name'],
      category: json['category'],
      subcategory: json['subcategory'],
      names: Map<String, dynamic>.from(json['names'] ?? {}),
      commonUses: json['common_uses'] != null 
          ? List<String>.from(json['common_uses'])
          : null,
      matchType: json['match_type'],
      finalScore: json['final_score']?.toDouble(),
      searchMethods: json['search_methods'] != null
          ? List<String>.from(json['search_methods'])
          : null,
      matchedAlias: json['matched_alias'],
      matchedLanguage: json['matched_language'],
      relevanceScore: json['relevance_score'],
      fuzzyScore: json['fuzzy_score'],
      similarity: json['similarity']?.toDouble(),
    );
  }
  
  /// Get display name in preferred language
  String getDisplayName(String languageCode) {
    return names[languageCode] ?? canonicalName;
  }
  
  /// Get match quality indicator
  String getMatchQuality() {
    if (finalScore != null) {
      if (finalScore! >= 90) return 'Excellent';
      if (finalScore! >= 75) return 'Good';
      if (finalScore! >= 60) return 'Fair';
      return 'Low';
    }
    
    if (relevanceScore != null) {
      if (relevanceScore! >= 90) return 'Exact';
      if (relevanceScore! >= 70) return 'Partial';
      return 'Low';
    }
    
    return 'Unknown';
  }
  
  /// Check if found by multiple search methods
  bool get isMultiMethodMatch {
    return searchMethods != null && searchMethods!.length > 1;
  }
}

class AutocompleteResponse {
  final String prefix;
  final String? language;
  final List<AutocompleteSuggestion> suggestions;
  final int count;
  
  AutocompleteResponse({
    required this.prefix,
    this.language,
    required this.suggestions,
    required this.count,
  });
  
  factory AutocompleteResponse.fromJson(Map<String, dynamic> json) {
    return AutocompleteResponse(
      prefix: json['prefix'],
      language: json['language'],
      suggestions: (json['suggestions'] as List)
          .map((s) => AutocompleteSuggestion.fromJson(s))
          .toList(),
      count: json['count'],
    );
  }
}

class AutocompleteSuggestion {
  final String suggestion;
  final String language;
  final String canonicalName;
  final String category;
  
  AutocompleteSuggestion({
    required this.suggestion,
    required this.language,
    required this.canonicalName,
    required this.category,
  });
  
  factory AutocompleteSuggestion.fromJson(Map<String, dynamic> json) {
    return AutocompleteSuggestion(
      suggestion: json['suggestion'],
      language: json['language'],
      canonicalName: json['canonical_name'],
      category: json['category'],
    );
  }
}
