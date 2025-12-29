import 'package:flutter/material.dart';

class CookScreen extends StatelessWidget {
  const CookScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Cook Mode'),
      ),
      body: const Center(
        child: Text('Start cooking from a recipe to begin'),
      ),
    );
  }
}
