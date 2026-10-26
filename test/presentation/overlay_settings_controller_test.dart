import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:traductor/application/overlay/overlay_session.dart';
import 'package:traductor/domain/overlay/overlay_settings.dart';
import 'package:traductor/presentation/overlay/overlay_settings_controller.dart';

import '../support/fake_overlay_gateway.dart';

void main() {
  test(
    'Changing provider resets consent and running sessions freeze their settings',
    () async {
      final gateway = FakeOverlayGateway();
      final session = OverlaySession(gateway);
      final controller = OverlaySettingsController(
        session,
        platform: OverlayPlatform.windows,
      );
      addTearDown(session.dispose);
      addTearDown(controller.dispose);
      expect(controller.canStart, isTrue);
      controller.setProvider(TranslationProvider.myMemory);
      expect(controller.canStart, isFalse);
      controller.setOnlineConsent(true);
      expect(controller.canStart, isTrue);
      controller.setProvider(TranslationProvider.libreTranslate);
      expect(controller.onlineConsent, isFalse);
      controller.setOnlineConsent(true);
      gateway.pendingStart = Completer<void>();
      final pending = controller.start();
      controller.setTarget('fr');
      expect(controller.settings.target, 'es');
      expect(controller.editable, isFalse);
      gateway.pendingStart!.complete();
      await pending;
      controller.setOpacity(.5);
      expect(controller.settings.opacity, 1);
      await controller.stop();
      controller.setOpacity(.5);
      expect(controller.settings.opacity, .5);
    },
  );

  test(
    'Android defaults stay local and support the platform language fallback',
    () async {
      final session = OverlaySession(FakeOverlayGateway());
      final controller = OverlaySettingsController(
        session,
        platform: OverlayPlatform.android,
      );
      addTearDown(session.dispose);
      addTearDown(controller.dispose);
      expect(controller.settings.opacity, .8);
      controller.setProvider(TranslationProvider.myMemory);
      expect(controller.online, isFalse);
      expect(controller.settings.provider, TranslationProvider.local);
      controller.setTarget('pt');
      expect(controller.canStart, isTrue);
    },
  );
}
