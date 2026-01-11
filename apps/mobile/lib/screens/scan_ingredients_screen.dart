import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../ui/ui_principles.dart';
import '../services/api_client.dart';
import '../services/barcode_lookup_service.dart';
import '../services/metrics_service.dart';
import 'scanning/guided_scan_screen.dart';
import 'scanning/barcode_scan_screen.dart';
import 'scanning/video_capture_screen.dart';

class ScanIngredientsScreen extends StatefulWidget {
  const ScanIngredientsScreen({super.key, this.autoStartVideoScan = false});

  final bool autoStartVideoScan;

  @override
  State<ScanIngredientsScreen> createState() => _ScanIngredientsScreenState();
}

class _ScanIngredientsScreenState extends State<ScanIngredientsScreen> {
  final ImagePicker _picker = ImagePicker();
  final FocusNode _quantityFocus = FocusNode();
  final BarcodeLookupService _barcodeLookup = BarcodeLookupService();

  static const double _lowQuantityConfidenceThreshold = 0.70;

  bool _loading = false;
  XFile? _image;
  List<_Candidate> _candidates = [];
  String? _scanId;
  Map<String, dynamic>? _deltaSummary;

  String? _barcode;
  String? _barcodeNameHint;
  double? _barcodeQuantityHint;
  String? _barcodeUnitHint;

  int _currentIndex = 0;
  int _savedCount = 0;
  int _skippedCount = 0;
  bool _autoVideoStarted = false;

  String? _videoProcessingText;
  double? _videoProgressValue;
  bool _loadingIsVideo = false;

  Future<Map<String, dynamic>> _pollVideoScanStatus(String scanId) async {
    final apiClient = Provider.of<ApiClient>(context, listen: false);
    final deadline = DateTime.now().add(const Duration(minutes: 6));

    while (DateTime.now().isBefore(deadline)) {
      final res = await apiClient.get('/api/scanning/video/status/$scanId');
      if (res is Map) {
        final map = res.cast<String, dynamic>();
        final status = map['status']?.toString() ?? 'processing';

        final meta = map['metadata'];
        if (meta is Map) {
          final md = meta.cast<String, dynamic>();
          final done = md['frames_done'];
          final total = md['frames_total'];

          int? doneI;
          int? totalI;
          if (done is num) doneI = done.toInt();
          if (total is num) totalI = total.toInt();

          if (mounted) {
            setState(() {
              if (doneI != null && totalI != null && totalI > 0) {
                _videoProcessingText = 'AI is analyzing your video… ($doneI/$totalI frames)';
                _videoProgressValue = (doneI / totalI).clamp(0.0, 1.0);
              } else {
                _videoProcessingText = 'AI is analyzing your video…';
                _videoProgressValue = null;
              }
            });
          }
        }

        if (status == 'completed' || status == 'failed') {
          return map;
        }
      }
      await Future<void>.delayed(const Duration(seconds: 2));
    }

    throw Exception('Analysis is taking longer than expected. Please keep this screen open. Tap “Scan Video” to retry.');
  }

  @override
  void initState() {
    super.initState();
    if (widget.autoStartVideoScan && !kIsWeb) {
      WidgetsBinding.instance.addPostFrameCallback((_) async {
        // Presenting the native camera picker during a route transition can crash on iOS.
        // Delay slightly and ensure this route is current before opening the picker.
        await Future<void>.delayed(const Duration(milliseconds: 350));
        if (!mounted || _autoVideoStarted) return;
        final route = ModalRoute.of(context);
        if (route != null && route.isCurrent != true) return;
        _autoVideoStarted = true;
        await _videoScan();
      });
    }
  }

  bool _quantityNeedsConfirmation(_Candidate c) {
    final hasSuggestion = (c.quantityController.text.trim().isNotEmpty);
    if (!hasSuggestion) return false;

    // If quantity confidence is missing, treat as low confidence to be safe.
    final qc = c.quantityConfidence;
    return qc == null || qc < _lowQuantityConfidenceThreshold;
  }

  Future<void> _editQuantityDialog(_Candidate c) async {
    final initial = c.quantityController.text.trim();
    final controller = TextEditingController(text: initial);

    final res = await showDialog<String>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Edit quantity'),
        content: TextField(
          controller: controller,
          autofocus: true,
          decoration: const InputDecoration(
            labelText: 'e.g., 500 g, 2 kg, 3 pieces',
            border: OutlineInputBorder(),
          ),
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, controller.text.trim()),
            child: const Text('Save'),
          ),
        ],
      ),
    );

    if (!mounted) return;
    if (res == null) return;

    setState(() {
      c.quantityController.text = res;
      c.quantityEstimate = res;
      c.quantityConfirmed = true;
    });
  }

  int? _nextPendingIndex({int startAt = 0}) {
    if (_candidates.isEmpty) return null;
    for (int i = startAt; i < _candidates.length; i++) {
      if (!_candidates[i].processed) return i;
    }
    for (int i = 0; i < startAt && i < _candidates.length; i++) {
      if (!_candidates[i].processed) return i;
    }
    return null;
  }

  void _jumpToNextPending() {
    final next = _nextPendingIndex(startAt: _currentIndex);
    if (next == null) return;
    setState(() => _currentIndex = next);
  }

  Future<void> _clearAllPending() async {
    if (_loading || _candidates.isEmpty) return;

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Clear all items?'),
        content: const Text('This removes the current scan results.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Clear'),
          ),
        ],
      ),
    );

    if (confirmed != true || !mounted) return;

    setState(() {
      _candidates = [];
      _image = null;
      _scanId = null;
      _deltaSummary = null;
      _currentIndex = 0;
      _savedCount = 0;
      _skippedCount = 0;
    });
  }

  Future<void> _pickAndScan({required ImageSource source}) async {
    setState(() {
      _loading = true;
      _candidates = [];
      _image = null;
      _scanId = null;
      _deltaSummary = null;

      _currentIndex = 0;
      _savedCount = 0;
      _skippedCount = 0;
    });

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);

      final image = await _picker.pickImage(
        source: source,
        imageQuality: 85,
        maxWidth: 1600,
      );
      if (image == null) {
        setState(() => _loading = false);
        return;
      }

      setState(() => _image = image);
      final fields = <String, String>{
        'scan_type': 'pantry',
        if (_barcode != null && _barcode!.trim().isNotEmpty) 'barcode': _barcode!.trim(),
        if (_barcodeNameHint != null && _barcodeNameHint!.trim().isNotEmpty) 'barcode_name_hint': _barcodeNameHint!.trim(),
        if (_barcodeQuantityHint != null && _barcodeQuantityHint! > 0) 'barcode_quantity_hint': _barcodeQuantityHint!.toString(),
        if (_barcodeUnitHint != null && _barcodeUnitHint!.trim().isNotEmpty) 'barcode_unit_hint': _barcodeUnitHint!.trim(),
      };
      final response = await apiClient.postMultipart(
        '/api/scanning/analyze-image',
        file: image,
        fields: fields,
      );

      if (!mounted) return;

      final success = response['success'] == true;
      if (!success) {
        String msg = 'Scan failed';
        final detail = response['detail'];
        if (detail is Map) {
          final m = detail['message']?.toString();
          if (m != null && m.trim().isNotEmpty) {
            msg = m.trim();
          } else {
            msg = detail.toString();
          }
        } else {
          msg = response['detail']?.toString() ?? response['error']?.toString() ?? 'Scan failed';
        }

        final lower = msg.toLowerCase();
        if (lower.contains('too dark') || lower.contains('too blurry') || lower.contains('glare')) {
          fireAndForget(MetricsService.instance.recordEvent('pantry_scan_retake'));
        }

        _showError(msg);
        setState(() => _loading = false);
        return;
      }

      final scanId = response['scan_id']?.toString();
      final meta = response['metadata'];
      Map<String, dynamic>? delta;
      if (meta is Map) {
        final d = meta['delta'];
        if (d is Map<String, dynamic>) {
          delta = d;
        } else if (d is Map) {
          delta = d.cast<String, dynamic>();
        }
      }
      final items = response['ingredients'];
      final parsed = <_Candidate>[];
      if (items is List) {
        for (final item in items) {
          if (item is Map<String, dynamic>) {
            parsed.add(_Candidate.fromDetectedJson(item));
          } else if (item is Map) {
            parsed.add(_Candidate.fromDetectedJson(item.cast<String, dynamic>()));
          }
        }
      }

      final message = response['message']?.toString();
      if (message != null && message.trim().isNotEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(message.trim())),
        );
      }

      setState(() {
        _scanId = (scanId != null && scanId.trim().isNotEmpty) ? scanId.trim() : null;
        _candidates = parsed;
        _deltaSummary = delta;
        _loading = false;

        _currentIndex = 0;
        _savedCount = 0;
        _skippedCount = 0;
      });

      _jumpToNextPending();
    } catch (e) {
      if (!mounted) return;
      _showError(e.toString());
      setState(() => _loading = false);
    }
  }

  Future<void> _videoScan() async {
    if (_loading) return;

    final messenger = ScaffoldMessenger.of(context);

    setState(() {
      _loading = true;
      _loadingIsVideo = true;
      _candidates = [];
      _image = null;
      _scanId = null;
      _deltaSummary = null;

      _videoProcessingText = 'Uploading video…';
      _videoProgressValue = null;

      _currentIndex = 0;
      _savedCount = 0;
      _skippedCount = 0;
    });

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);

      final res = await Navigator.of(context).push<VideoCaptureResult>(
        MaterialPageRoute(
          builder: (_) => const VideoCaptureScreen(initialDurationSeconds: 30),
        ),
      );
      if (res == null) {
        setState(() {
          _loading = false;
          _loadingIsVideo = false;
          _videoProcessingText = null;
          _videoProgressValue = null;
        });
        return;
      }

      final video = res.video;
      final durationSeconds = res.durationSeconds;

      final fields = <String, String>{
        'scan_type': 'pantry',
        'max_frames': '12',
        'duration_seconds': durationSeconds.toString(),
        'async_mode': 'true',
        if (_barcode != null && _barcode!.trim().isNotEmpty) 'barcode': _barcode!.trim(),
        if (_barcodeNameHint != null && _barcodeNameHint!.trim().isNotEmpty) 'barcode_name_hint': _barcodeNameHint!.trim(),
        if (_barcodeQuantityHint != null && _barcodeQuantityHint! > 0) 'barcode_quantity_hint': _barcodeQuantityHint!.toString(),
        if (_barcodeUnitHint != null && _barcodeUnitHint!.trim().isNotEmpty) 'barcode_unit_hint': _barcodeUnitHint!.trim(),
      };

      final response = await apiClient.postMultipart(
        '/api/scanning/video/analyze',
        file: video,
        fieldName: 'video',
        fields: fields,
        timeoutSeconds: 600,
      );

      if (!mounted) return;

      final success = response['success'] == true;
      if (!success) {
        final msg = response['detail']?.toString() ?? response['error']?.toString() ?? 'Video scan failed';
        _showError(msg);
        setState(() {
          _loading = false;
          _loadingIsVideo = false;
          _videoProcessingText = null;
          _videoProgressValue = null;
        });
        return;
      }

      final scanId = response['scan_id']?.toString();
      dynamic items = response['detections'];

      // New async flow: /video/analyze returns quickly with scan_id; poll for detections.
      if ((items == null || (items is List && items.isEmpty)) && scanId != null && scanId.trim().isNotEmpty) {
        if (mounted) {
          setState(() {
            _videoProcessingText = 'AI is analyzing your video…';
            _videoProgressValue = null;
          });
        }
        final status = await _pollVideoScanStatus(scanId.trim());
        final st = status['status']?.toString();
        if (st == 'failed') {
          String msg = 'Video scan failed';
          final meta = status['metadata'];
          if (meta is Map) {
            final err = meta['error']?.toString();
            if (err != null && err.trim().isNotEmpty) msg = err.trim();
          }
          throw Exception(msg);
        }
        items = status['detections'];
      }
      final parsed = <_Candidate>[];
      if (items is List) {
        for (final item in items) {
          if (item is Map<String, dynamic>) {
            parsed.add(_Candidate.fromDetectedJson(item));
          } else if (item is Map) {
            parsed.add(_Candidate.fromDetectedJson(item.cast<String, dynamic>()));
          }
        }
      }

      final message = response['message']?.toString();
      if (mounted && message != null && message.trim().isNotEmpty) {
        messenger.showSnackBar(SnackBar(content: Text(message.trim())));
      }

      setState(() {
        _scanId = (scanId != null && scanId.trim().isNotEmpty) ? scanId.trim() : null;
        _candidates = parsed;
        _deltaSummary = null;
        _loading = false;

        _loadingIsVideo = false;

        _videoProcessingText = null;
        _videoProgressValue = null;

        _currentIndex = 0;
        _savedCount = 0;
        _skippedCount = 0;
      });

      _jumpToNextPending();
    } catch (e) {
      if (!mounted) return;
      _showError(e.toString());
      setState(() {
        _loading = false;
        _loadingIsVideo = false;
        _videoProcessingText = null;
        _videoProgressValue = null;
      });
    }
  }

  Future<void> _saveAllDetections() async {
    if (_loading) return;
    if (_scanId == null || _scanId!.trim().isEmpty) {
      _showError('Missing scan id. Please rescan.');
      return;
    }
    if (_candidates.isEmpty) return;

    setState(() {
      _loading = true;
      _loadingIsVideo = false;
      _videoProcessingText = 'Preparing to save…';
      _videoProgressValue = null;
    });

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);

      final pending = _candidates.where((c) => !c.processed && c.selected).toList();
      if (pending.isEmpty) {
        setState(() {
          _loading = false;
          _videoProcessingText = null;
          _videoProgressValue = null;
        });
        _showError('No pending items to save.');
        return;
      }

      final total = pending.length;
      var savedSoFar = 0;

      for (final c in pending) {
        final detectedId = c.detectedId.trim();
        if (detectedId.isEmpty) {
          setState(() {
            c.processed = true;
            _skippedCount += 1;
          });
          continue;
        }

        if (mounted) {
          setState(() {
            _videoProcessingText = 'Saving ${savedSoFar + 1}/$total…';
            _videoProgressValue = total <= 0 ? null : (savedSoFar / total).clamp(0.0, 1.0);
          });
        }

        final name = c.ingredientController.text.trim();
        final parsed = _parseQtyUnit(c.quantityController.text);

        final conf = <String, dynamic>{
          'detected_id': detectedId,
          'action': 'confirmed',
        };

        final original = c.originalIngredient.trim().toLowerCase();
        final edited = name.toLowerCase();
        if (name.isNotEmpty && edited != original) {
          conf['action'] = 'modified';
          conf['confirmed_name'] = name;

          // If the user scanned a barcode during this scan session,
          // attach it to the correction so the backend can learn pantry vocabulary.
          if (_barcode != null && _barcode!.trim().isNotEmpty) {
            conf['barcode'] = _barcode!.trim();
          }
          if (_barcodeNameHint != null && _barcodeNameHint!.trim().isNotEmpty) {
            conf['barcode_name_hint'] = _barcodeNameHint!.trim();
          }
          if (_barcodeQuantityHint != null && _barcodeQuantityHint! > 0) {
            conf['barcode_quantity_hint'] = _barcodeQuantityHint;
          }
          if (_barcodeUnitHint != null && _barcodeUnitHint!.trim().isNotEmpty) {
            conf['barcode_unit_hint'] = _barcodeUnitHint!.trim();
          }
        }

        // Only include quantity if it isn't flagged as needing confirmation,
        // unless the user explicitly confirmed/edited it.
        final wantsQty = (parsed.qty != null);
        final qtyOk = !_quantityNeedsConfirmation(c) || c.quantityConfirmed;
        if (wantsQty && qtyOk) {
          conf['quantity'] = parsed.qty;
          if (parsed.unit != null && parsed.unit!.trim().isNotEmpty) {
            conf['unit'] = parsed.unit!.trim();
          }
        }

        await apiClient.post('/api/scanning/confirm-ingredients', {
          'scan_id': _scanId,
          'confirmations': [conf],
        });

        if (!mounted) return;

        setState(() {
          c.processed = true;
          _savedCount += 1;
        });

        savedSoFar += 1;
      }

      setState(() {
        _loading = false;
        _videoProcessingText = null;
        _videoProgressValue = null;
      });

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Saved $savedSoFar/$total items to inventory')),
      );

      Navigator.pop(context, savedSoFar > 0);
    } catch (e) {
      if (!mounted) return;
      _showError(e.toString());
      setState(() {
        _loading = false;
        _videoProcessingText = null;
        _videoProgressValue = null;
      });
    }
  }

  Future<void> _scanBarcode() async {
    if (_loading) return;
    final code = await Navigator.of(context).push<String>(
      MaterialPageRoute(builder: (_) => const BarcodeScanScreen()),
    );
    if (!mounted) return;
    if (code == null || code.trim().isEmpty) return;

    setState(() {
      _barcode = code.trim();
      _barcodeNameHint = null;
      _barcodeQuantityHint = null;
      _barcodeUnitHint = null;
    });

    try {
      final product = await _barcodeLookup.lookupProduct(_barcode!);
      if (!mounted) return;
      if (product != null) {
        setState(() {
          _barcodeNameHint = product['name']?.toString();
          final q = product['quantity'];
          _barcodeQuantityHint = (q is num) ? q.toDouble() : double.tryParse(q?.toString() ?? '');
          _barcodeUnitHint = product['unit']?.toString();
        });
      }
    } catch (_) {
      // best-effort
    }

    final name = (_barcodeNameHint ?? '').trim();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(name.isNotEmpty ? 'Barcode: $name' : 'Barcode scanned')),
    );
  }

  Future<void> _guidedScan() async {
    setState(() {
      _loading = true;
      _candidates = [];
      _image = null;
      _scanId = null;
      _deltaSummary = null;

      _currentIndex = 0;
      _savedCount = 0;
      _skippedCount = 0;
    });

    try {
      final res = await Navigator.of(context).push<GuidedScanResult>(
        MaterialPageRoute(
          builder: (_) => GuidedScanScreen(
            scanType: 'pantry',
            barcode: _barcode,
            barcodeNameHint: _barcodeNameHint,
            barcodeQuantityHint: _barcodeQuantityHint,
            barcodeUnitHint: _barcodeUnitHint,
          ),
        ),
      );

      if (!mounted) return;
      if (res == null) {
        setState(() => _loading = false);
        return;
      }

      final response = res.response;

      final success = response['success'] == true;
      if (!success) {
        final detail = response['detail'];
        final msg = (detail is Map)
            ? (detail['message']?.toString() ?? detail.toString())
            : (response['detail']?.toString() ?? response['error']?.toString() ?? 'Scan failed');
        _showError(msg);
        setState(() => _loading = false);
        return;
      }

      final scanId = response['scan_id']?.toString();
      final meta = response['metadata'];
      Map<String, dynamic>? delta;
      if (meta is Map) {
        final d = meta['delta'];
        if (d is Map<String, dynamic>) {
          delta = d;
        } else if (d is Map) {
          delta = d.cast<String, dynamic>();
        }
      }
      final items = response['ingredients'];
      final parsed = <_Candidate>[];
      if (items is List) {
        for (final item in items) {
          if (item is Map<String, dynamic>) {
            parsed.add(_Candidate.fromDetectedJson(item));
          } else if (item is Map) {
            parsed.add(_Candidate.fromDetectedJson(item.cast<String, dynamic>()));
          }
        }
      }

      final message = response['message']?.toString();
      if (message != null && message.trim().isNotEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(message.trim())),
        );
      }

      setState(() {
        _scanId = (scanId != null && scanId.trim().isNotEmpty) ? scanId.trim() : null;
        _candidates = parsed;
        _deltaSummary = delta;
        _loading = false;

        _currentIndex = 0;
        _savedCount = 0;
        _skippedCount = 0;
      });

      _jumpToNextPending();
    } catch (e) {
      if (!mounted) return;
      _showError(e.toString());
      setState(() => _loading = false);
    }
  }

  ({double? qty, String? unit}) _parseQtyUnit(String? input) {
    final raw = (input ?? '').trim();
    if (raw.isEmpty) return (qty: null, unit: null);

    final match = RegExp(r'^(\d+(?:\.\d+)?)\s*([a-zA-Z]+)?').firstMatch(raw);
    if (match == null) return (qty: null, unit: null);
    final qty = double.tryParse(match.group(1) ?? '');
    final unit = match.group(2);
    return (qty: qty, unit: unit);
  }

  Future<void> _confirmCurrentAndAdvance({required bool save}) async {
    if (_scanId == null || _scanId!.trim().isEmpty) {
      _showError('Missing scan id. Please rescan.');
      return;
    }
    if (_candidates.isEmpty) return;

    final pendingIndex = _nextPendingIndex(startAt: _currentIndex);
    if (pendingIndex == null) {
      if (mounted) Navigator.pop(context, _savedCount > 0);
      return;
    }

    final c = _candidates[pendingIndex];
    if (c.detectedId.trim().isEmpty) {
      setState(() {
        c.processed = true;
        _skippedCount += 1;
      });
      _jumpToNextPending();
      return;
    }

    setState(() {
      _loading = true;
      _currentIndex = pendingIndex;

      _loadingIsVideo = false;
      final total = _candidates.length;
      final done = (_savedCount + _skippedCount).clamp(0, total);
      _videoProcessingText = save ? 'Saving ${done + 1}/$total…' : 'Skipping ${done + 1}/$total…';
      _videoProgressValue = total <= 0 ? null : (done / total).clamp(0.0, 1.0);
    });

    try {
      if (save && _quantityNeedsConfirmation(c) && !c.quantityConfirmed) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Confirm or edit the quantity first.')),
          );
        }
        setState(() => _loading = false);
        return;
      }

      final apiClient = Provider.of<ApiClient>(context, listen: false);

      final name = c.ingredientController.text.trim();
      final parsed = _parseQtyUnit(c.quantityController.text);

      final Map<String, dynamic> confirmation = {
        'detected_id': c.detectedId,
        'action': 'rejected',
      };

      if (save && name.isNotEmpty) {
        final original = c.originalIngredient.trim().toLowerCase();
        final edited = name.toLowerCase();
        if (edited != original) {
          confirmation['action'] = 'modified';
          confirmation['confirmed_name'] = name;

          // If the user scanned a barcode during this scan session,
          // attach it to the correction so the backend can learn pantry vocabulary.
          if (_barcode != null && _barcode!.trim().isNotEmpty) {
            confirmation['barcode'] = _barcode!.trim();
          }
          if (_barcodeNameHint != null && _barcodeNameHint!.trim().isNotEmpty) {
            confirmation['barcode_name_hint'] = _barcodeNameHint!.trim();
          }
          if (_barcodeQuantityHint != null && _barcodeQuantityHint! > 0) {
            confirmation['barcode_quantity_hint'] = _barcodeQuantityHint;
          }
          if (_barcodeUnitHint != null && _barcodeUnitHint!.trim().isNotEmpty) {
            confirmation['barcode_unit_hint'] = _barcodeUnitHint!.trim();
          }
        } else {
          confirmation['action'] = 'confirmed';
        }

        if (parsed.qty != null) {
          confirmation['quantity'] = parsed.qty;
          if (parsed.unit != null && parsed.unit!.trim().isNotEmpty) {
            confirmation['unit'] = parsed.unit!.trim();
          }
        }
      }

      final res = await apiClient.post('/api/scanning/confirm-ingredients', {
        'scan_id': _scanId,
        'confirmations': [confirmation],
      });

      if (!mounted) return;

      final msg = res['message']?.toString();

      setState(() {
        c.processed = true;
        if (save && name.isNotEmpty) {
          _savedCount += 1;
        } else {
          _skippedCount += 1;
        }

        _loading = false;
        _videoProcessingText = null;
        _videoProgressValue = null;
      });

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            (msg != null && msg.trim().isNotEmpty)
                ? msg.trim()
                : (save ? 'Saved' : 'Rejected'),
          ),
        ),
      );

      final next = _nextPendingIndex(startAt: _currentIndex + 1);
      if (next == null) {
        Navigator.pop(context, _savedCount > 0);
        return;
      }

      setState(() {
        _currentIndex = next;
      });
    } catch (e) {
      if (!mounted) return;
      _showError(e.toString());
      setState(() {
        _loading = false;
        _videoProcessingText = null;
        _videoProgressValue = null;
      });
    }
  }

  void _finish() {
    Navigator.pop(context, _savedCount > 0);
  }

  @override
  void dispose() {
    _quantityFocus.dispose();
    super.dispose();
  }

  void _showError(String message) {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Error'),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  Widget _buildConfidenceChip(double confidence) {
    final percentage = (confidence * 100).round();
    final Color color;
    final IconData icon;
    
    if (percentage >= 75) {
      color = Colors.green;
      icon = Icons.check_circle;
    } else if (percentage >= 50) {
      color = Colors.orange;
      icon = Icons.warning_amber_rounded;
    } else {
      color = Colors.red;
      icon = Icons.help_outline;
    }

    return Chip(
      avatar: Icon(icon, size: 18, color: color),
      label: Text(
        '$percentage%',
        style: TextStyle(
          color: color,
          fontWeight: FontWeight.bold,
          fontSize: 13,
        ),
      ),
      backgroundColor: color.withAlpha(26),
      side: BorderSide(color: color.withAlpha(77)),
      padding: const EdgeInsets.symmetric(horizontal: 4),
      visualDensity: VisualDensity.compact,
    );
  }

  Widget _buildFormChip(String? itemForm) {
    final raw = (itemForm ?? '').trim().toLowerCase();
    if (raw.isEmpty || raw == 'unknown') return const SizedBox.shrink();

    final label = raw == 'packaged' ? 'Packaged' : (raw == 'loose' ? 'Loose' : raw);
    return Chip(
      label: Text(label, style: const TextStyle(fontSize: 13)),
      visualDensity: VisualDensity.compact,
    );
  }

  Widget _buildDeltaSummary() {
    final delta = _deltaSummary;
    if (delta == null) return const SizedBox.shrink();

    final newCount = (delta['new_count'] is num) ? (delta['new_count'] as num).toInt() : 0;
    final removedCount = (delta['removed_count'] is num) ? (delta['removed_count'] as num).toInt() : 0;
    final changedCount = (delta['changed_count'] is num) ? (delta['changed_count'] as num).toInt() : 0;

    if (newCount == 0 && removedCount == 0 && changedCount == 0) {
      return const SizedBox.shrink();
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            Expanded(child: Text('New: $newCount')),
            Expanded(child: Text('Removed: $removedCount')),
            Expanded(child: Text('Changed: $changedCount')),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (kDebugMode || kProfileMode) {
      // v1: maxChoices=3. Scan entry presents up to 2 capture choices.
      SavoUiGuards.warnIfTooManyChoices(
        screen: 'ScanIngredientsScreen',
        surface: 'Capture method',
        choices: 2,
      );

      // v1: mandatory AI confirmation. This screen always requires user review
      // (select items) before any inventory write.
      SavoUiGuards.warnIfAiConfirmationNotExplicit(
        flow: 'SnapPantry',
        surface: 'Review candidates before save',
        hasExplicitReviewStep: true,
      );
    }

    final canScan = !_loading;

    final hasResults = _scanId != null && _candidates.isNotEmpty;
    final int? pendingIndex = hasResults ? _nextPendingIndex(startAt: _currentIndex) : null;
    final _Candidate? current = (pendingIndex != null) ? _candidates[pendingIndex] : null;

    final Widget scanContent;
    if (!hasResults) {
      scanContent = Center(
        child: Text(
          _image == null ? 'Select a photo to scan.' : 'No ingredients detected.',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
      );
    } else if (pendingIndex == null || current == null) {
      scanContent = Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'All items reviewed.',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            FilledButton(
              onPressed: _loading ? null : _finish,
              child: const Text('Back to inventory'),
            ),
          ],
        ),
      );
    } else {
      scanContent = Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      'Item ${pendingIndex + 1} of ${_candidates.length}',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                  ),
                  if ((current.changeStatus ?? '').toLowerCase() == 'new') ...[
                    const Chip(label: Text('NEW'), visualDensity: VisualDensity.compact),
                    const SizedBox(width: 8),
                  ] else if ((current.changeStatus ?? '').toLowerCase() == 'changed') ...[
                    const Chip(label: Text('CHANGED'), visualDensity: VisualDensity.compact),
                    const SizedBox(width: 8),
                  ],
                  _buildFormChip(current.itemForm),
                  const SizedBox(width: 8),
                  _buildConfidenceChip(current.confidence),
                ],
              ),
              const SizedBox(height: 12),
              TextField(
                controller: current.ingredientController,
                enabled: !_loading,
                decoration: const InputDecoration(
                  labelText: 'Ingredient',
                  border: OutlineInputBorder(),
                ),
                onChanged: (v) => current.ingredient = v,
              ),
              const SizedBox(height: 10),
              if (current.quantityController.text.trim().isNotEmpty) ...[
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        _quantityNeedsConfirmation(current) && !current.quantityConfirmed
                            ? 'Looks like ${current.quantityController.text.trim()} — correct?'
                            : 'Looks like ${current.quantityController.text.trim()}',
                        style: Theme.of(context).textTheme.bodyMedium,
                      ),
                    ),
                    if (_quantityNeedsConfirmation(current) && !current.quantityConfirmed) ...[
                      TextButton(
                        onPressed: _loading
                            ? null
                            : () => setState(() {
                                  current.quantityConfirmed = true;
                                }),
                        child: const Text('Correct'),
                      ),
                      TextButton(
                        onPressed: _loading ? null : () => _editQuantityDialog(current),
                        child: const Text('Edit'),
                      ),
                    ] else ...[
                      TextButton(
                        onPressed: _loading ? null : () => _editQuantityDialog(current),
                        child: const Text('Edit'),
                      ),
                    ],
                  ],
                ),
                if ((current.changeStatus ?? '').toLowerCase() == 'changed' && current.previousQuantity != null) ...[
                  const SizedBox(height: 6),
                  Text(
                    'Was ${current.previousQuantity}${(current.previousUnit != null && current.previousUnit!.trim().isNotEmpty) ? ' ${current.previousUnit}' : ''}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
                const SizedBox(height: 10),
              ],
              TextField(
                controller: current.quantityController,
                focusNode: _quantityFocus,
                enabled: !_loading,
                decoration: InputDecoration(
                  labelText: _quantityNeedsConfirmation(current)
                      ? 'Quantity (required review)'
                      : 'Quantity (optional, e.g., 2 kg)',
                  border: const OutlineInputBorder(),
                ),
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                onChanged: (v) {
                  current.quantityEstimate = v;
                  // Any edit counts as confirmation for low-confidence quantities.
                  if (_quantityNeedsConfirmation(current)) {
                    current.quantityConfirmed = true;
                  }
                },
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: _loading ? null : () => _confirmCurrentAndAdvance(save: false),
                      child: const Text('Reject'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: FilledButton(
                      onPressed: (_loading || (_quantityNeedsConfirmation(current) && !current.quantityConfirmed))
                          ? null
                          : () => _confirmCurrentAndAdvance(save: true),
                      child: const Text('Save & next'),
                    ),
                  ),
                ],
              ),
              if (_quantityNeedsConfirmation(current) && !current.quantityConfirmed) ...[
                const SizedBox(height: 8),
                Text(
                  'Please confirm or edit the quantity before saving.',
                  style: Theme.of(context).textTheme.bodySmall,
                  textAlign: TextAlign.center,
                ),
              ],
              const SizedBox(height: 8),
              Text(
                'Saved: $_savedCount  Skipped: $_skippedCount',
                style: Theme.of(context).textTheme.bodySmall,
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Scan Ingredients'),
        actions: [
          IconButton(
            tooltip: 'Scan barcode (optional)',
            onPressed: _loading ? null : _scanBarcode,
            icon: const Icon(Icons.qr_code_scanner),
          ),
          if (hasResults)
            TextButton(
              onPressed: _loading ? null : _clearAllPending,
              child: const Text('Clear'),
            ),
          if (hasResults)
            TextButton(
              onPressed: _loading ? null : _saveAllDetections,
              child: const Text('Save all'),
            ),
          if (hasResults)
            TextButton(
              onPressed: _loading ? null : _finish,
              child: const Text('Done'),
            ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (hasResults) ...[
              _buildDeltaSummary(),
              const SizedBox(height: 12),
            ],
            Wrap(
              spacing: 12,
              runSpacing: 12,
              children: [
                FilledButton.icon(
                  onPressed: canScan
                      ? () => (kIsWeb ? _pickAndScan(source: ImageSource.gallery) : _guidedScan())
                      : null,
                  icon: Icon(kIsWeb ? Icons.upload_file : Icons.photo_camera),
                  label: Text(kIsWeb ? 'Upload Photo' : 'Guided Scan'),
                ),
                if (!kIsWeb)
                  OutlinedButton.icon(
                    onPressed: canScan ? _videoScan : null,
                    icon: const Icon(Icons.videocam),
                    label: const Text('Video Scan (30s)'),
                  ),
                OutlinedButton.icon(
                  onPressed: canScan ? () => _pickAndScan(source: ImageSource.gallery) : null,
                  icon: const Icon(Icons.photo_library),
                  label: const Text('Pick From Gallery'),
                ),
              ],
            ),
            const SizedBox(height: 16),
            if (_loading) LinearProgressIndicator(value: _videoProgressValue),
            if (_loading) ...[
              const SizedBox(height: 12),
              Text(
                (_videoProcessingText ?? 'Working…'),
                style: Theme.of(context).textTheme.titleSmall,
                textAlign: TextAlign.center,
              ),
              if (_loadingIsVideo) ...[
                const SizedBox(height: 6),
                Text(
                  'Keep this screen open while processing. This can take a minute. For the best speed and clarity, photos (Guided Scan) are usually faster than video.',
                  style: Theme.of(context).textTheme.bodySmall,
                  textAlign: TextAlign.center,
                ),
              ],
            ],
            const SizedBox(height: 16),
            Expanded(
              child: scanContent,
            ),
          ],
        ),
      ),
    );
  }
}

class _Candidate {
  final String detectedId;
  String ingredient;
  final String originalIngredient;
  String? quantityEstimate;
  final String? originalQuantityEstimate;
  double confidence;
  double? quantityConfidence;
  String? quantitySource;
  String? itemForm;
  String? changeStatus;
  double? previousQuantity;
  String? previousUnit;
  String? storageHint;
  bool selected;

  bool processed;
  bool quantityConfirmed;

  final TextEditingController ingredientController;
  final TextEditingController quantityController;

  _Candidate({
    required this.detectedId,
    required this.ingredient,
    required this.originalIngredient,
    required this.quantityEstimate,
    required this.originalQuantityEstimate,
    required this.confidence,
    required this.quantityConfidence,
    required this.quantitySource,
    required this.itemForm,
    required this.changeStatus,
    required this.previousQuantity,
    required this.previousUnit,
    required this.storageHint,
    required this.selected,
    required this.processed,
    required this.quantityConfirmed,
  })  : ingredientController = TextEditingController(text: ingredient),
        quantityController = TextEditingController(text: quantityEstimate ?? '');

  factory _Candidate.fromDetectedJson(Map<String, dynamic> json) {
    final detectedId = (json['id'] ?? '').toString();
    final detectedName = (json['detected_name'] ?? '').toString();

    final quantity = json['quantity'];
    final unit = json['unit']?.toString();
    final quantityEstimate = (quantity is num)
        ? '${quantity.toDouble()}${(unit != null && unit.trim().isNotEmpty) ? ' $unit' : ''}'
        : null;

    final confidenceRaw = json['confidence'];
    final confidence = (confidenceRaw is num) ? confidenceRaw.toDouble() : 0.0;

    final qcRaw = json['quantity_confidence'];
    final quantityConfidence = (qcRaw is num) ? qcRaw.toDouble().clamp(0.0, 1.0) : null;
    final quantitySource = json['quantity_source']?.toString();
    final itemForm = json['item_form']?.toString();

    final changeStatus = json['change_status']?.toString();
    final prevQtyRaw = json['previous_quantity'];
    final previousQuantity = (prevQtyRaw is num) ? prevQtyRaw.toDouble() : double.tryParse(prevQtyRaw?.toString() ?? '');
    final previousUnit = json['previous_unit']?.toString();

    // Low-confidence quantities must be explicitly confirmed/edited.
    final quantityConfirmed = (quantityEstimate == null || quantityEstimate.trim().isEmpty)
        ? true
        : (quantityConfidence != null && quantityConfidence >= _ScanIngredientsScreenState._lowQuantityConfidenceThreshold);

    final storageHint = null;

    return _Candidate(
      detectedId: detectedId,
      ingredient: detectedName,
      originalIngredient: detectedName,
      quantityEstimate: quantityEstimate,
      originalQuantityEstimate: quantityEstimate,
      confidence: confidence.clamp(0.0, 1.0),
      quantityConfidence: quantityConfidence,
      quantitySource: quantitySource,
      itemForm: itemForm,
      changeStatus: changeStatus,
      previousQuantity: previousQuantity,
      previousUnit: previousUnit,
      storageHint: storageHint,
      selected: true,
      processed: false,
      quantityConfirmed: quantityConfirmed,
    );
  }
}
