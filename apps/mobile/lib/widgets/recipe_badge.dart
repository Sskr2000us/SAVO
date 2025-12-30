import 'package:flutter/material.dart';

/// Badge types for recipe classification
enum BadgeType {
  nutrition,
  skill,
  time,
}

/// Recipe badge data model
class RecipeBadge {
  final BadgeType type;
  final String label;
  final int priority;
  final String? explanation;

  const RecipeBadge({
    required this.type,
    required this.label,
    required this.priority,
    this.explanation,
  });

  factory RecipeBadge.fromJson(Map<String, dynamic> json) {
    BadgeType type;
    switch (json['type'] as String?) {
      case 'skill':
        type = BadgeType.skill;
        break;
      case 'time':
        type = BadgeType.time;
        break;
      case 'nutrition':
      default:
        type = BadgeType.nutrition;
    }

    return RecipeBadge(
      type: type,
      label: json['label'] as String? ?? '',
      priority: json['priority'] as int? ?? 0,
      explanation: json['explanation'] as String?,
    );
  }
}

/// Recipe badge widget - displays max 3 badges with proper styling
class RecipeBadgeWidget extends StatelessWidget {
  final RecipeBadge badge;
  final bool showTooltip;

  const RecipeBadgeWidget({
    Key? key,
    required this.badge,
    this.showTooltip = true,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final badgeStyle = _getBadgeStyle(badge.type, context);
    
    Widget badgeChip = Container(
      height: 24,
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: badgeStyle.backgroundColor,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            badgeStyle.icon,
            style: const TextStyle(fontSize: 14),
          ),
          const SizedBox(width: 4),
          Text(
            badge.label,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w500,
              color: badgeStyle.textColor,
              height: 1.0,
            ),
          ),
        ],
      ),
    );

    // Wrap with tooltip if explanation is available
    if (showTooltip && badge.explanation != null && badge.explanation!.isNotEmpty) {
      badgeChip = Tooltip(
        message: badge.explanation!,
        preferBelow: false,
        verticalOffset: 20,
        child: badgeChip,
      );
    }

    return badgeChip;
  }

  _BadgeStyle _getBadgeStyle(BadgeType type, BuildContext context) {
    switch (type) {
      case BadgeType.nutrition:
        return _BadgeStyle(
          icon: '🟢',
          backgroundColor: const Color(0xFFE8F5E9), // Light green
          textColor: const Color(0xFF2E7D32), // Dark green
        );
      case BadgeType.skill:
        return _BadgeStyle(
          icon: '⭐',
          backgroundColor: const Color(0xFFFFF3E0), // Light orange
          textColor: const Color(0xFFE65100), // Dark orange
        );
      case BadgeType.time:
        return _BadgeStyle(
          icon: '⏱',
          backgroundColor: const Color(0xFFE3F2FD), // Light blue
          textColor: const Color(0xFF1565C0), // Dark blue
        );
    }
  }
}

class _BadgeStyle {
  final String icon;
  final Color backgroundColor;
  final Color textColor;

  _BadgeStyle({
    required this.icon,
    required this.backgroundColor,
    required this.textColor,
  });
}

/// Widget that displays a list of recipe badges (max 3)
class RecipeBadgeList extends StatelessWidget {
  final List<RecipeBadge> badges;

  const RecipeBadgeList({
    Key? key,
    required this.badges,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    // Sort by priority and take max 3
    final sortedBadges = List<RecipeBadge>.from(badges)
      ..sort((a, b) => b.priority.compareTo(a.priority));
    final displayBadges = sortedBadges.take(3).toList();

    if (displayBadges.isEmpty) {
      return const SizedBox.shrink();
    }

    return Wrap(
      spacing: 8,
      runSpacing: 4,
      children: displayBadges
          .map((badge) => RecipeBadgeWidget(badge: badge))
          .toList(),
    );
  }
}

/// Helper to parse badges from API response
List<RecipeBadge> parseBadges(dynamic badgesJson) {
  if (badgesJson == null) return [];
  
  if (badgesJson is! List) return [];
  
  return badgesJson
      .map((json) {
        try {
          return RecipeBadge.fromJson(json as Map<String, dynamic>);
        } catch (e) {
          print('Error parsing badge: $e');
          return null;
        }
      })
      .whereType<RecipeBadge>()
      .toList();
}
