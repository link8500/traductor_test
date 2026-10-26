enum OverlayPlatform { windows, android, unsupported }

enum TranslationProvider {
  local('local'),
  myMemory('mymemory'),
  libreTranslate('libre');

  const TranslationProvider(this.id);
  final String id;
}

/// Settings for one capture session, independent of Flutter and native channels.
class OverlaySettings {
  const OverlaySettings({
    this.source = 'en',
    this.target = 'es',
    this.opacity = 1,
    this.provider = TranslationProvider.local,
    this.endpoint = 'http://127.0.0.1:5000/translate',
    this.apiKey = '',
  });

  factory OverlaySettings.defaultsFor(OverlayPlatform platform) =>
      OverlaySettings(opacity: platform == OverlayPlatform.android ? .8 : 1);

  final String source;
  final String target;
  final double opacity;
  final TranslationProvider provider;
  final String endpoint;
  final String apiKey;

  bool get isLocalPair => source == 'en' && target == 'es';

  bool usesOnlineProvider(OverlayPlatform platform) =>
      platform != OverlayPlatform.android &&
      provider != TranslationProvider.local;

  String? startError({
    required OverlayPlatform platform,
    required bool onlineConsent,
  }) {
    if (source == target) return 'Elige dos idiomas distintos.';
    if (platform != OverlayPlatform.android &&
        provider == TranslationProvider.local &&
        !isLocalPair) {
      return 'El modelo local incluido requiere English → Español.';
    }
    if (usesOnlineProvider(platform) && !onlineConsent) {
      return 'Permite el envío del texto al proveedor seleccionado.';
    }
    final maximum = platform == OverlayPlatform.android ? .8 : 1;
    if (!opacity.isFinite || opacity < .4 || opacity > maximum) {
      return 'La opacidad está fuera del intervalo permitido.';
    }
    return null;
  }

  OverlaySettings copyWith({
    String? source,
    String? target,
    double? opacity,
    TranslationProvider? provider,
    String? endpoint,
    String? apiKey,
  }) => OverlaySettings(
    source: source ?? this.source,
    target: target ?? this.target,
    opacity: opacity ?? this.opacity,
    provider: provider ?? this.provider,
    endpoint: endpoint ?? this.endpoint,
    apiKey: apiKey ?? this.apiKey,
  );
}
