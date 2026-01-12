import 'dart:async';

import 'package:camera/camera.dart';

/// Caches the result of `availableCameras()`.
///
/// On iOS this call can be noticeably slow; caching improves perceived
/// camera startup time across scan screens.
class CameraCache {
  static Future<List<CameraDescription>>? _camerasFuture;

  static Future<List<CameraDescription>> getCameras() {
    _camerasFuture ??= availableCameras();
    return _camerasFuture!;
  }

  static Future<CameraDescription?> getPreferredBackCamera() async {
    final cams = await getCameras();
    if (cams.isEmpty) return null;

    final back = cams.where((c) => c.lensDirection == CameraLensDirection.back).toList();
    if (back.isNotEmpty) return back.first;

    return cams.first;
  }

  static void reset() {
    _camerasFuture = null;
  }
}
