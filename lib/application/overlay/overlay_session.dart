import 'dart:async';

import '../../domain/overlay/overlay_gateway.dart';
import '../../domain/overlay/overlay_settings.dart';
import '../../domain/overlay/overlay_status.dart';

class OverlaySessionState {
  const OverlaySessionState({
    this.status = const OverlayStatus(),
    this.starting = false,
  });

  final OverlayStatus status;
  final bool starting;
}

/// Session use cases. Owns its gateway and closes it when disposed.
class OverlaySession {
  OverlaySession(this._gateway) {
    _subscription = _gateway.statusChanges.listen(_receiveStatus);
  }

  final OverlayGateway _gateway;
  final _changes = StreamController<OverlaySessionState>.broadcast(sync: true);
  late final StreamSubscription<OverlayStatus> _subscription;
  var _state = const OverlaySessionState();
  var _disposed = false;

  OverlaySessionState get state => _state;
  Stream<OverlaySessionState> get changes => _changes.stream;

  void _receiveStatus(OverlayStatus status) =>
      _publish(status, starting: _state.starting);

  void _publish(OverlayStatus status, {bool starting = false}) {
    if (_disposed) return;
    _state = OverlaySessionState(status: status, starting: starting);
    _changes.add(_state);
  }

  Future<void> refresh() => _execute(() async {
    _receiveStatus(await _gateway.readStatus());
  }, refreshing: true);

  Future<void> start(
    OverlaySettings settings, {
    required OverlayPlatform platform,
    required bool onlineConsent,
  }) async {
    if (_disposed || _state.starting || _state.status.running) return;
    final error = settings.startError(
      platform: platform,
      onlineConsent: onlineConsent,
    );
    if (error != null) {
      _publish(_state.status.copyWith(error: error));
      return;
    }
    _publish(
      _state.status.copyWith(
        message: 'Preparando la barra flotante…',
        clearError: true,
      ),
      starting: true,
    );
    await _execute(() async {
      await _gateway.start(settings);
      if (!_disposed) _receiveStatus(await _gateway.readStatus());
    });
    _publish(_state.status);
  }

  Future<void> translate() => _execute(() async {
    if (!_state.status.running) return;
    await _gateway.translate();
    if (!_disposed) _receiveStatus(await _gateway.readStatus());
  });

  Future<void> stop() => _execute(() async {
    await _gateway.stop();
    if (!_disposed) _receiveStatus(await _gateway.readStatus());
  });

  Future<void> _execute(
    Future<void> Function() action, {
    bool refreshing = false,
  }) async {
    if (_disposed) return;
    try {
      await action();
    } on OverlayFailure catch (failure) {
      if (failure.kind == OverlayFailureKind.unavailable && refreshing) {
        _publish(
          _state.status.copyWith(
            message: 'La superposición está disponible en Windows y Android.',
            clearError: true,
          ),
          starting: _state.starting,
        );
      } else {
        final error = failure.kind == OverlayFailureKind.unavailable
            ? 'Ejecuta la versión nativa para Windows o Android.'
            : failure.message ?? 'No se pudo completar la captura.';
        _publish(
          _state.status.copyWith(error: error, message: error),
          starting: _state.starting,
        );
      }
    }
  }

  Future<void> dispose() async {
    if (_disposed) return;
    _disposed = true;
    await _subscription.cancel();
    await _gateway.dispose();
    await _changes.close();
  }
}
