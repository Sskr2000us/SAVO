import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';

import '../theme/app_theme.dart';
import '../ui/ui_principles.dart';
import '../widgets/savo_widgets.dart';
import 'daily_plan_screen.dart';
import 'party_setup_screen.dart';

class PlanScreen extends StatefulWidget {
  const PlanScreen({super.key});

  @override
  State<PlanScreen> createState() => _PlanScreenState();
}

class _PlanScreenState extends State<PlanScreen> {
  @override
  Widget build(BuildContext context) {
    if (kDebugMode || kProfileMode) {
      SavoUiGuards.warnIfTooManyChoices(
        screen: 'PlanScreen',
        surface: 'Entry options',
        choices: 3,
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Plan'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Choose what you want to plan',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: AppSpacing.md),
            SavoCard(
              elevated: true,
              onTap: () {
                Navigator.push(
                  context,
                  AppMotion.createRoute(const DailyPlanScreen()),
                );
              },
              child: const Row(
                children: [
                  Icon(Icons.today_outlined),
                  SizedBox(width: AppSpacing.md),
                  Expanded(child: Text('Daily meal')),
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            SavoCard(
              elevated: true,
              onTap: () {
                Navigator.push(
                  context,
                  AppMotion.createRoute(
                    const PartySetupScreen(mode: PartyPlanningMode.dinnerParty),
                  ),
                );
              },
              child: const Row(
                children: [
                  Icon(Icons.celebration_outlined),
                  SizedBox(width: AppSpacing.md),
                  Expanded(child: Text('Dinner party')),
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            SavoCard(
              onTap: () {
                Navigator.push(
                  context,
                  AppMotion.createRoute(
                    const PartySetupScreen(mode: PartyPlanningMode.festival),
                  ),
                );
              },
              child: const Row(
                children: [
                  const SizedBox(width: AppSpacing.md),
                  Icon(Icons.festival_outlined),
                  SizedBox(width: AppSpacing.md),
                  Expanded(child: Text('Festival')),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
