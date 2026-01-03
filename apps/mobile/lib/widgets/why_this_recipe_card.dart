import 'package:flutter/material.dart';

/// Section in "Why This Recipe?" explanation
class WhySection {
  final String icon;
  final String title;
  final String content;

  const WhySection({
    required this.icon,
    required this.title,
    required this.content,
  });

  factory WhySection.fromJson(Map<String, dynamic> json) {
    return WhySection(
      icon: json['icon'] as String? ?? 'info',
      title: json['title'] as String? ?? '',
      content: json['content'] as String? ?? '',
    );
  }
}

/// Expandable card that explains why a recipe was recommended
class WhyThisRecipeCard extends StatefulWidget {
  final List<WhySection> sections;
  final bool initiallyExpanded;

  const WhyThisRecipeCard({
    Key? key,
    required this.sections,
    this.initiallyExpanded = false,
  }) : super(key: key);

  @override
  State<WhyThisRecipeCard> createState() => _WhyThisRecipeCardState();
}

class _WhyThisRecipeCardState extends State<WhyThisRecipeCard>
    with SingleTickerProviderStateMixin {
  late bool _isExpanded;
  late AnimationController _animationController;
  late Animation<double> _iconRotationAnimation;

  @override
  void initState() {
    super.initState();
    _isExpanded = widget.initiallyExpanded;
    _animationController = AnimationController(
      duration: const Duration(milliseconds: 300),
      vsync: this,
    );
    _iconRotationAnimation = Tween<double>(
      begin: 0.0,
      end: 0.5,
    ).animate(CurvedAnimation(
      parent: _animationController,
      curve: Curves.easeInOut,
    ));

    if (_isExpanded) {
      _animationController.value = 1.0;
    }
  }

  @override
  void dispose() {
    _animationController.dispose();
    super.dispose();
  }

  void _toggleExpanded() {
    setState(() {
      _isExpanded = !_isExpanded;
      if (_isExpanded) {
        _animationController.forward();
      } else {
        _animationController.reverse();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    if (widget.sections.isEmpty) {
      return const SizedBox.shrink();
    }

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: const Color(0xFF37474F),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header (always visible)
          InkWell(
            onTap: _toggleExpanded,
            borderRadius: BorderRadius.circular(12),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Why this recipe?',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w500,
                          color: Colors.white,
                        ),
                  ),
                  RotationTransition(
                    turns: _iconRotationAnimation,
                    child: const Icon(
                      Icons.keyboard_arrow_down,
                      size: 24,
                      color: Colors.white,
                    ),
                  ),
                ],
              ),
            ),
          ),
          
          // Expandable content
          AnimatedCrossFade(
            firstChild: const SizedBox.shrink(),
            secondChild: _buildExpandedContent(context),
            crossFadeState: _isExpanded
                ? CrossFadeState.showSecond
                : CrossFadeState.showFirst,
            duration: const Duration(milliseconds: 300),
          ),
        ],
      ),
    );
  }

  Widget _buildExpandedContent(BuildContext context) {
    return Container(
      padding: const EdgeInsets.only(left: 16, right: 16, bottom: 16),
      decoration: const BoxDecoration(
        border: Border(
          top: BorderSide(color: Color(0xFFE0E0E0), width: 1),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 12),
          ...widget.sections.asMap().entries.map((entry) {
            final index = entry.key;
            final section = entry.value;
            return Column(
              children: [
                _buildSection(context, section),
                if (index < widget.sections.length - 1)
                  const SizedBox(height: 16),
              ],
            );
          }).toList(),
        ],
      ),
    );
  }

  Widget _buildSection(BuildContext context, WhySection section) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Icon
        Text(
          _getIconEmoji(section.icon),
          style: const TextStyle(fontSize: 16),
        ),
        const SizedBox(width: 8),
        
        // Content
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                section.title,
                style: Theme.of(context).textTheme.labelLarge?.copyWith(
                      fontWeight: FontWeight.w500,
                      color: Colors.white,
                    ),
              ),
              const SizedBox(height: 4),
              Text(
                section.content,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Colors.white70,
                    ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  String _getIconEmoji(String iconKey) {
    switch (iconKey.toLowerCase()) {
      case 'health':
        return '✅';
      case 'skill':
        return '🍳';
      case 'cuisine':
        return '🌍';
      case 'time':
        return '⏱';
      default:
        return 'ℹ️';
    }
  }
}

/// Helper to parse "Why This Recipe?" sections from API response
List<WhySection> parseWhySections(dynamic sectionsJson) {
  if (sectionsJson == null) return [];
  
  if (sectionsJson is! List) return [];
  
  return sectionsJson
      .map((json) {
        try {
          return WhySection.fromJson(json as Map<String, dynamic>);
        } catch (e) {
          print('Error parsing why section: $e');
          return null;
        }
      })
      .whereType<WhySection>()
      .toList();
}
