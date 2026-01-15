import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/planning.dart';
import '../services/api_client.dart';
import '../theme/app_theme.dart';
import '../widgets/savo_network_image.dart';
import '../widgets/savo_widgets.dart';
import '../ui/ui_principles.dart';
import 'recipe_detail_screen.dart';

class RecipeCatalogScreen extends StatefulWidget {
  const RecipeCatalogScreen({super.key});

  @override
  State<RecipeCatalogScreen> createState() => _RecipeCatalogScreenState();
}

class _RecipeCatalogScreenState extends State<RecipeCatalogScreen> {
  final _searchController = TextEditingController();
  final _scrollController = ScrollController();

  Timer? _debounce;
  bool _loading = true;
  bool _loadingMore = false;
  String? _error;

  List<Recipe> _items = const [];
  int _offset = 0;
  final int _limit = 30;
  bool _hasMore = true;

  List<String> _cuisines = const [];
  String? _selectedCuisine;

  String get _query => _searchController.text.trim();

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadCuisines();
      _refresh();
    });
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _searchController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (!_hasMore || _loadingMore || _loading) return;
    if (!_scrollController.hasClients) return;

    final pos = _scrollController.position;
    if (pos.pixels >= (pos.maxScrollExtent - 240)) {
      _loadMore();
    }
  }

  void _onQueryChanged() {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 350), () {
      _refresh();
    });
  }

  Future<dynamic> _getWithFallback(ApiClient apiClient, String endpoint) async {
    try {
      return await apiClient.get(endpoint);
    } catch (e) {
      // Some services in this repo use an /api prefix. Try it if the direct route fails.
      if (endpoint.startsWith('/api/')) rethrow;
      final alt = '/api$endpoint';
      return await apiClient.get(alt);
    }
  }

  Future<void> _loadCuisines() async {
    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final res = await _getWithFallback(apiClient, '/recipes/catalog/cuisines');
      if (res is Map && res['cuisines'] is List) {
        final list = (res['cuisines'] as List)
            .map((x) => x.toString().trim())
            .where((s) => s.isNotEmpty)
            .toSet()
            .toList()
          ..sort((a, b) => a.toLowerCase().compareTo(b.toLowerCase()));
        if (!mounted) return;
        setState(() {
          _cuisines = list;
        });
      }
    } catch (_) {
      // Best-effort only; the screen still works without cuisine filter.
    }
  }

  Future<void> _refresh() async {
    if (!mounted) return;
    setState(() {
      _loading = true;
      _loadingMore = false;
      _error = null;
      _offset = 0;
      _hasMore = true;
      _items = const [];
    });

    await _fetchPage(reset: true);
  }

  Future<void> _loadMore() async {
    if (!_hasMore || _loadingMore || _loading) return;
    setState(() {
      _loadingMore = true;
      _error = null;
    });
    await _fetchPage(reset: false);
  }

  Future<void> _fetchPage({required bool reset}) async {
    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      final params = <String, String>{
        'limit': _limit.toString(),
        'offset': _offset.toString(),
      };

      final q = _query;
      if (q.isNotEmpty) params['q'] = q;
      final cuisine = (_selectedCuisine ?? '').trim();
      if (cuisine.isNotEmpty) params['cuisine'] = cuisine;

      final uri = Uri(path: '/recipes/catalog', queryParameters: params);
      final res = await _getWithFallback(apiClient, uri.toString());

      if (res is! Map) throw Exception('Unexpected response');

      final rawItems = res['items'];
      final rawHasMore = res['has_more'];

      final next = <Recipe>[];
      if (rawItems is List) {
        for (final row in rawItems) {
          if (row is Map) {
            try {
              next.add(Recipe.fromJson(Map<String, dynamic>.from(row)));
            } catch (_) {
              // Skip invalid catalog rows.
            }
          }
        }
      }

      final hasMore = (rawHasMore == true) || (next.length == _limit);

      if (!mounted) return;
      setState(() {
        final combined = <Recipe>[..._items, ...next];
        _items = combined;
        _offset = combined.length;
        _hasMore = hasMore;
        _loading = false;
        _loadingMore = false;
      });
    } catch (e) {
      if (!mounted) return;
      final msg = e.toString().replaceFirst(RegExp(r'^Exception:\s*'), '');
      setState(() {
        _error = msg;
        _loading = false;
        _loadingMore = false;
      });
    }
  }

  String _titleFor(Recipe r) {
    final t = r.getLocalizedName('en').trim();
    if (t.isNotEmpty) return t;
    final fallback = r.recipeName.values.where((s) => s.trim().isNotEmpty).toList();
    if (fallback.isNotEmpty) return fallback.first;
    return 'Recipe';
  }

  String? _thumbFor(Recipe r) {
    if (r.imageUrls.isNotEmpty) return r.imageUrls.first;
    if ((r.imageUrl ?? '').trim().isNotEmpty) return r.imageUrl;
    return null;
  }

  @override
  Widget build(BuildContext context) {
    if (Theme.of(context).platform == TargetPlatform.android ||
        Theme.of(context).platform == TargetPlatform.iOS) {
      // no-op
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Recipe Catalog'),
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(AppSpacing.md, AppSpacing.md, AppSpacing.md, AppSpacing.sm),
            child: Column(
              children: [
                TextField(
                  controller: _searchController,
                  onChanged: (_) => _onQueryChanged(),
                  decoration: InputDecoration(
                    hintText: 'Search recipes…',
                    prefixIcon: const Icon(Icons.search),
                    suffixIcon: _query.isEmpty
                        ? null
                        : IconButton(
                            tooltip: 'Clear',
                            icon: const Icon(Icons.close),
                            onPressed: () {
                              _searchController.clear();
                              _onQueryChanged();
                            },
                          ),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(AppRadius.md),
                    ),
                  ),
                ),
                if (_cuisines.isNotEmpty) ...[
                  const SizedBox(height: AppSpacing.sm),
                  Row(
                    children: [
                      const Icon(Icons.public, size: 18),
                      const SizedBox(width: AppSpacing.sm),
                      Expanded(
                        child: DropdownButtonFormField<String>(
                          value: _selectedCuisine,
                          isExpanded: true,
                          decoration: InputDecoration(
                            hintText: 'All cuisines',
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(AppRadius.md),
                            ),
                          ),
                          items: [
                            const DropdownMenuItem<String>(
                              value: null,
                              child: Text('All cuisines'),
                            ),
                            ..._cuisines.map(
                              (c) => DropdownMenuItem<String>(
                                value: c,
                                child: Text(c),
                              ),
                            ),
                          ],
                          onChanged: (v) {
                            setState(() {
                              _selectedCuisine = v;
                            });
                            _refresh();
                          },
                        ),
                      ),
                    ],
                  ),
                ],
              ],
            ),
          ),
          Expanded(
            child: _buildBody(context),
          ),
        ],
      ),
    );
  }

  Widget _buildBody(BuildContext context) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_error != null && _items.isEmpty) {
      return Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              'Could not load recipes',
              style: Theme.of(context).textTheme.titleMedium,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(
              _error!,
              style: Theme.of(context).textTheme.bodyMedium,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AppSpacing.md),
            FilledButton.icon(
              onPressed: _refresh,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      );
    }

    if (_items.isEmpty) {
      return Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              'No recipes found',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: AppSpacing.sm),
            OutlinedButton(
              onPressed: () {
                _searchController.clear();
                setState(() {
                  _selectedCuisine = null;
                });
                _refresh();
              },
              child: const Text('Clear filters'),
            ),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _refresh,
      child: ListView.separated(
        controller: _scrollController,
        padding: const EdgeInsets.fromLTRB(AppSpacing.md, 0, AppSpacing.md, AppSpacing.lg),
        itemCount: _items.length + 1,
        separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
        itemBuilder: (context, i) {
          if (i >= _items.length) {
            if (_loadingMore) {
              return const Padding(
                padding: EdgeInsets.symmetric(vertical: AppSpacing.md),
                child: Center(child: CircularProgressIndicator()),
              );
            }
            if (!_hasMore) {
              return const Padding(
                padding: EdgeInsets.symmetric(vertical: AppSpacing.md),
                child: Center(child: Text('End of catalog')),
              );
            }
            return const SizedBox.shrink();
          }

          final r = _items[i];
          final title = _titleFor(r);
          final subtitleParts = <String>[];
          if (r.cuisine.trim().isNotEmpty) subtitleParts.add(r.cuisine.trim());
          final t = r.estimatedTimes.totalMinutes;
          if (t > 0) subtitleParts.add('${t} min');
          if (r.videoUrl != null && r.videoUrl!.trim().isNotEmpty) subtitleParts.add('Video');
          final subtitle = subtitleParts.join(' • ');

          return SavoCard(
            elevated: true,
            padding: const EdgeInsets.all(AppSpacing.sm),
            onTap: () {
              Navigator.push(
                context,
                AppMotion.createRoute(RecipeDetailScreen(recipe: r)),
              );
            },
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SavoNetworkImageThumb.roundedRect(
                  url: _thumbFor(r),
                  size: 64,
                  borderRadius: BorderRadius.circular(AppRadius.md),
                ),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: Theme.of(context).textTheme.titleMedium,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                      if (subtitle.isNotEmpty) ...[
                        const SizedBox(height: 4),
                        Text(
                          subtitle,
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                color: Theme.of(context).colorScheme.onSurfaceVariant,
                              ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ],
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                const Icon(Icons.chevron_right),
              ],
            ),
          );
        },
      ),
    );
  }
}
