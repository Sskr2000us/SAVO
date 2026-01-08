import 'package:flutter/material.dart';

import '../services/entitlements_service.dart';

Future<bool> showProPaywallSheet(
  BuildContext context, {
  required String title,
  required String ctaLabel,
  required String reason,
}) async {
  final res = await showModalBottomSheet<bool>(
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
              Text(title, style: Theme.of(ctx).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
              const SizedBox(height: 8),
              Text(
                reason,
                style: Theme.of(ctx).textTheme.bodyMedium,
              ),
              const SizedBox(height: 12),
              Text(
                'Pro helps you:',
                style: Theme.of(ctx).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 8),
              _Bullet(text: 'Save time with auto weekly plans + shopping lists.'),
              _Bullet(text: 'Waste less with expiry reminders and smarter planning.'),
              _Bullet(text: 'Plan for the whole household (family profiles).'),
              _Bullet(text: 'Regenerate/swap without limits.'),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: FilledButton(
                      onPressed: () async {
                        // Placeholder upgrade flow: locally unlock.
                        await EntitlementsService.instance.setPro(true);
                        if (ctx.mounted) Navigator.pop(ctx, true);
                      },
                      child: Text(ctaLabel),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              SizedBox(
                width: double.infinity,
                child: TextButton(
                  onPressed: () => Navigator.pop(ctx, false),
                  child: const Text('Not now'),
                ),
              ),
            ],
          ),
        ),
      );
    },
  );

  return res == true;
}

class _Bullet extends StatelessWidget {
  final String text;

  const _Bullet({required this.text});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Icon(Icons.circle, size: 6, color: cs.primary),
          ),
          const SizedBox(width: 10),
          Expanded(child: Text(text)),
        ],
      ),
    );
  }
}
