import 'dart:async';

import 'package:flutter/foundation.dart';

import '../../application/overlay/overlay_session.dart';
import '../../domain/overlay/overlay_settings.dart';

class OverlaySettingsController extends ChangeNotifier {
  OverlaySettingsController(this._session, {required this.platform})
    : _settings = OverlaySettings.defaultsFor(platform) {
    _subscription = _session.changes.listen((_) {
      if (!_disposed) notifyListeners();
    });
  }

  final OverlaySession _session;
  final OverlayPlatform platform;
  late final StreamSubscription<OverlaySessionState> _subscription;
  OverlaySettings _settings;
  bool _onlineConsent = false;
  bool _disposed = false;

  OverlaySettings get settings => _settings;
  bool get isAndroid => platform == OverlayPlatform.android;
  bool get online => _settings.usesOnlineProvider(platform);
  bool get onlineConsent => _onlineConsent;
  bool get running => _session.state.status.running;
  bool get starting => _session.state.starting;
  bool get editable => !running && !starting;
  String get message => _session.state.status.message;
  String? get error => _session.state.status.error;
  bool get canStart =>
      editable &&
      _settings.startError(platform: platform, onlineConsent: _onlineConsent) ==
          null;

  void _update(OverlaySettings settings) {
    if (_disposed || !editable) return;
    _settings = settings;
    notifyListeners();
  }

  void setSource(String value) => _update(_settings.copyWith(source: value));
  void setTarget(String value) => _update(_settings.copyWith(target: value));
  void setOpacity(double value) => _update(_settings.copyWith(opacity: value));
  void setEndpoint(String value) =>
      _update(_settings.copyWith(endpoint: value));
  void setApiKey(String value) => _update(_settings.copyWith(apiKey: value));

  void setProvider(TranslationProvider provider) {
    if (!editable || _disposed || isAndroid) return;
    _onlineConsent = false;
    _update(_settings.copyWith(provider: provider));
  }

  void setOnlineConsent(bool value) {
    if (!editable || _disposed) return;
    _onlineConsent = value;
    notifyListeners();
  }

  Future<void> refresh() => _session.refresh();
  Future<void> start() => _session.start(
    _settings,
    platform: platform,
    onlineConsent: _onlineConsent,
  );
  Future<void> translate() => _session.translate();
  Future<void> stop() => _session.stop();

  @override
  void dispose() {
    _disposed = true;
    unawaited(_subscription.cancel());
    super.dispose();
  }
}
