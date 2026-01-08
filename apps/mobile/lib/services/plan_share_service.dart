import 'package:share_plus/share_plus.dart';

import 'api_client.dart';

class PlanShareService {
  Future<String> createShare(ApiClient apiClient, Map<String, dynamic> plan, {int expiresHours = 168}) async {
    final res = await apiClient.post(
      '/plan/share',
      {
        'plan': plan,
        'expires_hours': expiresHours,
      },
    );

    final shareId = (res['share_id'] ?? '').toString().trim();
    if (shareId.isEmpty) {
      throw Exception('Share failed: missing share id');
    }

    // Prefer the server-provided path.
    final sharePath = (res['share_path'] ?? '').toString().trim();
    if (sharePath.isNotEmpty) return sharePath;

    return '/plan/shared/$shareId';
  }

  Future<void> shareLink({required String title, required String sharePath}) async {
    final origin = Uri.base.origin;
    final url = origin.isNotEmpty ? '$origin$sharePath' : sharePath;
    await Share.share('$title\n$url');
  }
}
