import 'dart:typed_data';

import 'package:eventmonitor_voice/src/app_state.dart';
import 'package:eventmonitor_voice/src/domain/measurement.dart';
import 'package:eventmonitor_voice/src/services/api_client.dart';
import 'package:eventmonitor_voice/src/services/measurement_service.dart';
import 'package:eventmonitor_voice/src/ui/login_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('ready measurements never pretend zero is valid', () {
    const snapshot = MeasurementSnapshot.ready();

    expect(snapshot.currentDb, isNull);
    expect(snapshot.minimumDb, isNull);
    expect(snapshot.maximumDb, isNull);
    expect(snapshot.averageDb, isNull);
    expect(snapshot.status, SessionStatus.ready);
  });

  test('digital microphone silence is detectable and never a decibel value', () {
    final samples = MeasurementService.pcm16Samples(Uint8List(320));

    expect(samples, isNotEmpty);
    expect(MeasurementService.rmsOf(samples), 0);
  });

  test(
    'api rejects unencrypted server connections before sending credentials',
    () async {
      final client = ApiClient();

      await expectLater(
        client.login('http://example.test', 'user', 'secret'),
        throwsA(isA<ApiException>()),
      );
      client.close();
    },
  );

  testWidgets('login explains secure tenant access', (tester) async {
    final state = AppState();
    await tester.pumpWidget(MaterialApp(home: LoginScreen(state: state)));

    expect(find.text('EventMonitor Voice'), findsOneWidget);
    expect(find.text('Server-URL'), findsOneWidget);
    expect(find.textContaining('verschlüsselt'), findsOneWidget);
    expect(find.textContaining('HTTPS'), findsOneWidget);
  });
}
