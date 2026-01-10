import 'dart:math';
import 'dart:typed_data';

import 'package:image/image.dart' as img;

class ScanQualityResult {
  final bool ok;
  final bool tooDark;
  final bool tooBright;
  final bool tooBlurry;
  final double brightnessMean; // 0..255
  final double blurScore; // higher is sharper (heuristic)

  const ScanQualityResult({
    required this.ok,
    required this.tooDark,
    required this.tooBright,
    required this.tooBlurry,
    required this.brightnessMean,
    required this.blurScore,
  });
}

/// Lightweight quality checks for on-device guidance.
///
/// This is intentionally approximate: fast + fixable guidance,
/// not perfect computer vision.
class ScanQuality {
  // Conservative thresholds tuned for typical phone captures.
  static const double _darkMeanThreshold = 55.0;
  static const double _brightMeanThreshold = 210.0;
  static const double _blurScoreThreshold = 18.0;

  static ScanQualityResult assessJpegOrPng(Uint8List bytes) {
    final decoded = img.decodeImage(bytes);
    if (decoded == null) {
      return const ScanQualityResult(
        ok: true,
        tooDark: false,
        tooBright: false,
        tooBlurry: false,
        brightnessMean: 128,
        blurScore: 0,
      );
    }

    // Downscale for speed.
    final small = img.copyResize(decoded, width: min(220, decoded.width));

    final w = small.width;
    final h = small.height;

    // Compute mean brightness (luma).
    double sum = 0;
    int count = 0;
    final luma = List<double>.filled(w * h, 0);

    for (int y = 0; y < h; y++) {
      for (int x = 0; x < w; x++) {
        final p = small.getPixel(x, y);
        final r = p.r.toDouble();
        final g = p.g.toDouble();
        final b = p.b.toDouble();
        final yv = 0.2126 * r + 0.7152 * g + 0.0722 * b;
        final idx = y * w + x;
        luma[idx] = yv;
        sum += yv;
        count += 1;
      }
    }

    final mean = count > 0 ? (sum / count) : 128.0;

    // Blur heuristic: average gradient magnitude.
    // Lower values tend to correlate with blur.
    double gradSum = 0;
    int gradCount = 0;
    for (int y = 1; y < h - 1; y++) {
      for (int x = 1; x < w - 1; x++) {
        final c = luma[y * w + x];
        final dx = (luma[y * w + (x + 1)] - luma[y * w + (x - 1)]).abs();
        final dy = (luma[(y + 1) * w + x] - luma[(y - 1) * w + x]).abs();
        // include center lightly to damp noise
        gradSum += (dx + dy) * 0.5 + (c * 0.0);
        gradCount += 1;
      }
    }

    final blurScore = gradCount > 0 ? (gradSum / gradCount) : 0.0;

    final tooDark = mean < _darkMeanThreshold;
    final tooBright = mean > _brightMeanThreshold;
    final tooBlurry = blurScore < _blurScoreThreshold;

    final ok = !(tooDark || tooBright || tooBlurry);

    return ScanQualityResult(
      ok: ok,
      tooDark: tooDark,
      tooBright: tooBright,
      tooBlurry: tooBlurry,
      brightnessMean: mean,
      blurScore: blurScore,
    );
  }
}
