import 'package:flutter/material.dart';

class CookContextSelection {
  final String dayType; // weekday|weekend|holiday
  final String mealType; // breakfast|lunch|dinner

  const CookContextSelection({
    required this.dayType,
    required this.mealType,
  });
}

String formatCookContextTitle({required String dayType, required String mealType}) {
  String cap(String s) {
    final t = s.trim();
    if (t.isEmpty) return '';
    return t[0].toUpperCase() + t.substring(1);
  }

  final dt = dayType.trim().toLowerCase();
  final mt = mealType.trim().toLowerCase();
  final meal = cap(mt.isNotEmpty ? mt : 'meals');

  switch (dt) {
    case 'holiday':
      return 'Holiday $meal ideas';
    case 'weekend':
      return 'Weekend $meal ideas';
    default:
      return '$meal ideas you can cook';
  }
}

String inferDayType() {
  final wd = DateTime.now().weekday;
  // DateTime: Mon=1 ... Sun=7
  if (wd == DateTime.saturday || wd == DateTime.sunday) return 'weekend';
  return 'weekday';
}

String inferMealType() {
  final hour = DateTime.now().hour;
  if (hour < 11) return 'breakfast';
  if (hour < 16) return 'lunch';
  return 'dinner';
}

Future<CookContextSelection?> showCookContextPickerSheet(
  BuildContext context, {
  String? initialDayType,
  String? initialMealType,
  String title = 'When are you cooking?',
  bool includeHoliday = true,
}) async {
  final theme = Theme.of(context);

  final initialDay = (initialDayType ?? inferDayType()).trim().toLowerCase();
  final initialMeal = (initialMealType ?? inferMealType()).trim().toLowerCase();

  final safeDay = {'weekday', 'weekend', 'holiday'}.contains(initialDay) ? initialDay : inferDayType();
  final safeMeal = {'breakfast', 'lunch', 'dinner'}.contains(initialMeal) ? initialMeal : inferMealType();

  return showModalBottomSheet<CookContextSelection>(
    context: context,
    isScrollControlled: false,
    showDragHandle: true,
    builder: (ctx) {
      String dayType = safeDay;
      String mealType = safeMeal;

      return StatefulBuilder(
        builder: (ctx, setLocalState) {
          final dayChoices = <Map<String, String>>[
            {'key': 'weekday', 'label': 'Weekday'},
            {'key': 'weekend', 'label': 'Weekend'},
            if (includeHoliday) {'key': 'holiday', 'label': 'Holiday'},
          ];

          final mealChoices = <Map<String, String>>[
            {'key': 'breakfast', 'label': 'Breakfast'},
            {'key': 'lunch', 'label': 'Lunch'},
            {'key': 'dinner', 'label': 'Dinner'},
          ];

          return Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  title,
                  style: theme.textTheme.titleMedium,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 10,
                  runSpacing: 8,
                  alignment: WrapAlignment.center,
                  children: [
                    for (final c in dayChoices)
                      ChoiceChip(
                        label: Text(c['label']!),
                        selected: dayType == c['key']!,
                        onSelected: (v) {
                          if (!v) return;
                          setLocalState(() => dayType = c['key']!);
                        },
                      ),
                  ],
                ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 10,
                  runSpacing: 8,
                  alignment: WrapAlignment.center,
                  children: [
                    for (final c in mealChoices)
                      ChoiceChip(
                        label: Text(c['label']!),
                        selected: mealType == c['key']!,
                        onSelected: (v) {
                          if (!v) return;
                          setLocalState(() => mealType = c['key']!);
                        },
                      ),
                  ],
                ),
                const SizedBox(height: 16),
                Row(
                  children: [
                    Expanded(
                      child: TextButton(
                        onPressed: () => Navigator.of(ctx).pop(null),
                        child: const Text('Skip'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: FilledButton(
                        onPressed: () => Navigator.of(ctx).pop(
                          CookContextSelection(dayType: dayType, mealType: mealType),
                        ),
                        child: const Text('Continue'),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          );
        },
      );
    },
  );
}
