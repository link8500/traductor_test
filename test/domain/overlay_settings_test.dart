import 'package:flutter_test/flutter_test.dart';
import 'package:traductor/domain/overlay/overlay_settings.dart';

void main() {
  test('Offline defaults respect the Android touch-through limit', () {
    for (final platform in OverlayPlatform.values) {
      final settings = OverlaySettings.defaultsFor(platform);
      expect(settings.provider, TranslationProvider.local);
      expect(
        settings.startError(platform: platform, onlineConsent: false),
        isNull,
      );
      expect(settings.opacity, platform == OverlayPlatform.android ? .8 : 1);
    }
  });

  test(
    'The bundled Windows pair and Android fallback have different limits',
    () {
      const settings = OverlaySettings(target: 'fr', opacity: .8);
      expect(
        settings.startError(
          platform: OverlayPlatform.windows,
          onlineConsent: false,
        ),
        isNotNull,
      );
      expect(
        settings.startError(
          platform: OverlayPlatform.android,
          onlineConsent: false,
        ),
        isNull,
      );
      expect(
        settings
            .copyWith(source: 'fr')
            .startError(
              platform: OverlayPlatform.android,
              onlineConsent: false,
            ),
        isNotNull,
      );
    },
  );

  test('Online consent applies to the selected Windows provider', () {
    const settings = OverlaySettings(
      provider: TranslationProvider.myMemory,
      opacity: .8,
    );
    expect(
      settings.startError(
        platform: OverlayPlatform.windows,
        onlineConsent: false,
      ),
      isNotNull,
    );
    expect(
      settings.startError(
        platform: OverlayPlatform.windows,
        onlineConsent: true,
      ),
      isNull,
    );
    expect(settings.usesOnlineProvider(OverlayPlatform.android), isFalse);
  });

  test('Invalid opacity never reaches the native service', () {
    for (final opacity in [double.nan, double.infinity, .39, .81, 1.1]) {
      expect(
        OverlaySettings(
          opacity: opacity,
        ).startError(platform: OverlayPlatform.android, onlineConsent: false),
        isNotNull,
      );
    }
  });
}
