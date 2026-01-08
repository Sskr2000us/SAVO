import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../screens/planning_results_screen.dart';
import '../screens/shopping_list_screen.dart';
import '../services/entitlements_service.dart';
import '../services/saved_recipes_local_service.dart';
import '../widgets/pro_paywall_sheet.dart';

class UpsellService {
  UpsellService._();

  static final UpsellService instance = UpsellService._();

  static const String _saveCountKey = 'savo.upsell.saved_recipes.count';
  static const String _save3ShownKey = 'savo.upsell.save3.shown';

  Future<void> recordRecipeSavedAndMaybeShow(BuildContext context) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final shown = prefs.getBool(_save3ShownKey) ?? false;

      final next = (prefs.getInt(_saveCountKey) ?? 0) + 1;
      await prefs.setInt(_saveCountKey, next);

      if (shown || next != 3) return;
      await prefs.setBool(_save3ShownKey, true);

      if (!context.mounted) return;
      await _showSave3Upsell(context);
    } catch (_) {
      // Best-effort only.
    }
  }

  Future<void> _showSave3Upsell(BuildContext context) async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (ctx) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Nice — you saved 3 recipes',
                  style: Theme.of(ctx).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 8),
                Text(
                  'Want SAVO to auto-build a weekly plan + shopping list from your saved recipes?',
                  style: Theme.of(ctx).textTheme.bodyMedium,
                ),
                const SizedBox(height: 16),
                Row(
                  children: [
                    Expanded(
                      child: FilledButton(
                        onPressed: () async {
                          Navigator.pop(ctx);
                          await _handleAutoPlanCTA(context);
                        },
                        child: const Text('Auto weekly plan + shopping list'),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                SizedBox(
                  width: double.infinity,
                  child: TextButton(
                    onPressed: () => Navigator.pop(ctx),
                    child: const Text('Not now'),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Future<void> _handleAutoPlanCTA(BuildContext context) async {
    final isPro = await EntitlementsService.instance.isPro();
    if (!isPro && context.mounted) {
      final upgraded = await showProPaywallSheet(
        context,
        title: 'Upgrade to SAVO Pro',
        ctaLabel: 'Upgrade to auto-plan',
        reason: 'Auto weekly plans + shopping lists are a Pro feature. Upgrade to save time and reduce waste.',
        trigger: 'upsell_auto_plan',
      );
      if (!upgraded) return;
    }

    // Pro path: build plan from locally-cached saved recipes.
    if (!context.mounted) return;

    final saved = await SavedRecipesLocalService.instance.loadRecipesMostRecentFirst(maxItems: 20);
    if (saved.isEmpty) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No saved recipes found yet.')),
      );
      return;
    }

    final plan = SavedRecipesLocalService.instance.buildWeeklyPlanFromSaved(recipes: saved, numDays: 3);

    // Persist a shopping list immediately (so user sees instant value).
    final items = SavedRecipesLocalService.instance.buildShoppingListFromRecipes(saved.take(3).toList());
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('savo.shopping_list.latest', jsonEncode(items));
    } catch (_) {
      // ignore
    }

    if (!context.mounted) return;
    Navigator.of(context).push(
      MaterialPageRoute(
        settings: const RouteSettings(name: '/planning_results'),
        builder: (_) => PlanningResultsScreen(menuPlan: plan, planType: 'weekly'),
      ),
    );

    // Non-blocking: jump user straight to the list as the immediate payoff.
    await Future.delayed(const Duration(milliseconds: 250));
    if (!context.mounted) return;
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const ShoppingListScreen()),
    );
  }
}
