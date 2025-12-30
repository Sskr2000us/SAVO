import 'package:flutter/material.dart';

// Stub for web platform - camera not supported
class RealtimeScanScreen extends StatelessWidget {
  const RealtimeScanScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Camera Not Supported'),
      ),
      body: const Center(
        child: Text('Camera scanning is not supported on web platform'),
      ),
    );
  }
}
