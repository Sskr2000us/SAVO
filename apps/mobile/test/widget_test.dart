// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'package:flutter_test/flutter_test.dart';

import 'package:flutter/material.dart';
import 'package:savo/screens/landing_screen.dart';

void main() {
  testWidgets('Renders landing screen', (WidgetTester tester) async {
    // Give the landing screen enough vertical space to avoid RenderFlex overflow
    // in the hero section during widget tests.
    tester.binding.window.physicalSizeTestValue = const Size(1200, 2400);
    tester.binding.window.devicePixelRatioTestValue = 1.0;
    addTearDown(() {
      tester.binding.window.clearPhysicalSizeTestValue();
      tester.binding.window.clearDevicePixelRatioTestValue();
    });

    await tester.pumpWidget(
      const MaterialApp(
        home: LandingScreen(),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('SAVO'), findsOneWidget);
    expect(find.text('Scan Ingredients'), findsOneWidget);
    expect(find.text('Smart meal plans'), findsOneWidget);
  });
}
