import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:traductor/application/overlay/overlay_session.dart';
import 'package:traductor/domain/overlay/overlay_gateway.dart';
import 'package:traductor/domain/overlay/overlay_settings.dart';
import 'package:traductor/domain/overlay/overlay_status.dart';

import '../support/fake_overlay_gateway.dart';

void main() {
  late FakeOverlayGateway gateway;
  late OverlaySession session;

  setUp(() {
    gateway = FakeOverlayGateway();
    session = OverlaySession(gateway);
  });
  tearDown(() => session.dispose());

  Future<void> start([OverlaySettings settings = const OverlaySettings()]) =>
      session.start(
        settings,
        platform: OverlayPlatform.windows,
        onlineConsent: false,
      );

  test(
    'A session only translates on explicit request and follows native events',
    () async {
      await start();
      expect(session.state.status.running, isTrue);
      expect(gateway.translations, 0);
      await session.translate();
      expect(gateway.translations, 1);
      gateway.emit(
        const OverlayStatus(
          running: true,
          original: true,
          message: 'Movimiento detectado',
        ),
      );
      expect(session.state.status.original, isTrue);
      await session.stop();
      expect(session.state.status.running, isFalse);
      await session.translate();
      expect(gateway.translations, 1);
    },
  );

  test(
    'Invalid settings cannot bypass validation through another presenter',
    () async {
      await start(const OverlaySettings(target: 'fr'));
      expect(gateway.starts, 0);
      expect(session.state.status.error, isNotNull);
      await start(
        const OverlaySettings(provider: TranslationProvider.myMemory),
      );
      expect(gateway.starts, 0);
    },
  );

  test('Duplicate starts do not open a second capture session', () async {
    gateway.pendingStart = Completer<void>();
    final pending = start();
    expect(session.state.starting, isTrue);
    await start();
    expect(gateway.starts, 1);
    gateway.pendingStart!.complete();
    await pending;
    expect(session.state.starting, isFalse);
    await start();
    expect(gateway.starts, 1);
  });

  test('Denied capture remains stopped and can be retried', () async {
    gateway.startFailure = const OverlayFailure(
      OverlayFailureKind.native,
      'Captura cancelada',
    );
    await start();
    expect(session.state.status.running, isFalse);
    expect(session.state.starting, isFalse);
    expect(session.state.status.error, 'Captura cancelada');
    gateway.startFailure = null;
    await start();
    expect(session.state.status.running, isTrue);
    expect(session.state.status.error, isNull);
  });

  test(
    'Status failures are reported without an unhandled platform exception',
    () async {
      gateway.statusFailure = const OverlayFailure(
        OverlayFailureKind.native,
        'Servicio detenido',
      );
      await session.refresh();
      expect(session.state.status.error, 'Servicio detenido');
      gateway.statusFailure = const OverlayFailure(
        OverlayFailureKind.unavailable,
      );
      await session.refresh();
      expect(session.state.status.error, isNull);
      expect(session.state.status.message, contains('Windows y Android'));
    },
  );

  test(
    'Closing the app ignores a late start completion and releases the port',
    () async {
      gateway.pendingStart = Completer<void>();
      final pending = start();
      await session.dispose();
      gateway.pendingStart!.complete();
      await pending;
      expect(gateway.reads, 0);
      expect(gateway.disposed, isTrue);
      await session.refresh();
      expect(gateway.reads, 0);
    },
  );
}
