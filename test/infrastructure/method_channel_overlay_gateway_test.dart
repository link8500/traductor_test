import 'dart:async';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:traductor/domain/overlay/overlay_gateway.dart';
import 'package:traductor/domain/overlay/overlay_settings.dart';
import 'package:traductor/domain/overlay/overlay_status.dart';
import 'package:traductor/infrastructure/overlay/method_channel_overlay_gateway.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const channel = MethodChannel('luma/screen_translator');
  final messenger =
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
  late MethodChannelOverlayGateway gateway;
  late List<MethodCall> calls;

  setUp(() {
    calls = [];
    messenger.setMockMethodCallHandler(channel, (call) async {
      calls.add(call);
      if (call.method == 'status') {
        return {'running': true, 'original': false, 'message': 'Barra activa'};
      }
      return null;
    });
    gateway = MethodChannelOverlayGateway(channel: channel);
  });
  tearDown(() async {
    await gateway.dispose();
    messenger.setMockMethodCallHandler(channel, null);
  });

  Future<void> sendStatus(Object? arguments) async {
    final reply = Completer<void>();
    await messenger.handlePlatformMessage(
      channel.name,
      const StandardMethodCodec().encodeMethodCall(
        MethodCall('status', arguments),
      ),
      (_) => reply.complete(),
    );
    await reply.future;
  }

  test('The existing Windows and Android wire protocol is preserved', () async {
    await gateway.start(
      const OverlaySettings(
        opacity: .8,
        provider: TranslationProvider.libreTranslate,
        endpoint: ' http://127.0.0.1:5000/translate ',
        apiKey: ' key ',
      ),
    );
    expect(calls.single.arguments, {
      'source': 'en',
      'target': 'es',
      'opacity': .8,
      'provider': 'libre',
      'endpoint': 'http://127.0.0.1:5000/translate',
      'apiKey': 'key',
    });
    expect((await gateway.readStatus()).running, isTrue);
    await gateway.translate();
    await gateway.stop();
    expect(calls.map((call) => call.method), [
      'start',
      'status',
      'translate',
      'stop',
    ]);
  });

  test(
    'Native push events and partial status maps preserve the current message',
    () async {
      final statuses = <OverlayStatus>[];
      final subscription = gateway.statusChanges.listen(statuses.add);
      addTearDown(subscription.cancel);
      await gateway.readStatus();
      await sendStatus({'running': true, 'original': true});
      expect(statuses.single.original, isTrue);
      expect(statuses.single.message, 'Barra activa');
      await sendStatus('invalid status');
      expect(statuses, hasLength(1));
    },
  );

  test('Framework exceptions are translated into domain failures', () async {
    messenger.setMockMethodCallHandler(channel, (_) async {
      throw PlatformException(code: 'permission', message: 'Captura cancelada');
    });
    await expectLater(
      gateway.start(const OverlaySettings()),
      throwsA(
        isA<OverlayFailure>()
            .having(
              (failure) => failure.kind,
              'kind',
              OverlayFailureKind.native,
            )
            .having(
              (failure) => failure.message,
              'message',
              'Captura cancelada',
            ),
      ),
    );
    messenger.setMockMethodCallHandler(channel, null);
    await expectLater(
      gateway.readStatus(),
      throwsA(
        isA<OverlayFailure>().having(
          (failure) => failure.kind,
          'kind',
          OverlayFailureKind.unavailable,
        ),
      ),
    );
  });
}
