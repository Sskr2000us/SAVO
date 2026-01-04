import 'package:flutter/foundation.dart';

/// SAVO v1 — Global UI Principles
///
/// Source of truth: `SAVO_COMPREHENSIVE_UI_JSON_USER_STORIES_V1.md`.
///
/// Note: These are *principles*; enforcement should be conservative and
/// non-breaking. Use [SavoUiGuards] for debug-time warnings.
class SavoUiPrinciples {
  static const bool primaryActionPerScreen = true;
  static const int maxChoices = 3;
  static const bool mandatoryAiConfirmation = true;

  static const String designTone = 'calm_food_first_trust_driven';
}

/// Debug-only guardrails that help keep the app aligned with v1 principles.
///
/// These intentionally do not throw; they only warn in debug/profile
/// to avoid breaking existing UX while the app is being migrated.
class SavoUiGuards {
  static void warnIfTooManyChoices({
    required String screen,
    required String surface,
    required int choices,
  }) {
    if (choices <= SavoUiPrinciples.maxChoices) return;

    _warn(
      '$screen: "$surface" offers $choices choices; '
      'v1 maxChoices=${SavoUiPrinciples.maxChoices}.',
    );
  }

  static void warnIfMultiplePrimaryActions({
    required String screen,
    required String surface,
    required int primaryActions,
  }) {
    if (!SavoUiPrinciples.primaryActionPerScreen) return;
    if (primaryActions <= 1) return;

    _warn(
      '$screen: "$surface" has $primaryActions primary actions; '
      'v1 requires a single primary action per screen.',
    );
  }

  static void warnIfAiConfirmationNotExplicit({
    required String flow,
    required String surface,
    required bool hasExplicitReviewStep,
  }) {
    if (!SavoUiPrinciples.mandatoryAiConfirmation) return;
    if (hasExplicitReviewStep) return;

    _warn(
      'Flow "$flow": "$surface" appears to save AI output without an explicit '
      'review/confirm step; v1 requires mandatory AI confirmation.',
    );
  }

  static void _warn(String message) {
    // Keep this noisy in debug, but still visible in profile.
    if (kDebugMode || kProfileMode) {
      debugPrint('SAVO_UI_PRINCIPLES: $message');
    }
  }
}
