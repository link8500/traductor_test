import 'dart:async';

import 'package:flutter/services.dart';

import '../../domain/overlay/overlay_gateway.dart';
import '../../domain/overlay/overlay_settings.dart';
import '../../domain/overlay/overlay_status.dart';

/// The native protocol is confined to this adapter.
class MethodChannelOverlayGateway implements OverlayGateway {
  MethodChannelOverlayGateway({MethodChannel? channel})
    : _channel = channel ?? const MethodChannel('luma/screen_translator') {
    _channel.setMethodCallHandler((call) async {
      if (call.method == 'status' && !_disposed) {
        final status = _decode(call.arguments);
        if (status != null) _changes.add(status);
      }
    });
  }

  final MethodChannel _channel;
  final _changes = StreamController<OverlayStatus>.broadcast(sync: true);
  var _status = const OverlayStatus();
  var _disposed = false;

  @override
  Stream<OverlayStatus> get statusChanges => _changes.stream;

  OverlayStatus? _decode(Object? data) {
    if (data is! Map) return null;
    _status = OverlayStatus(
      running: data['running'] == true,
      original: data['original'] == true,
      message: data['message'] is String
          ? data['message'] as String
          : _status.message,
      error: data['error'] is String ? data['error'] as String : null,
    );
    return _status;
  }

  Future<T?> _invoke<T>(String method, [Object? arguments]) async {
    try {
      return await _channel.invokeMethod<T>(method, arguments);
    } on MissingPluginException {
      throw const OverlayFailure(OverlayFailureKind.unavailable);
    } on PlatformException catch (error) {
      throw OverlayFailure(OverlayFailureKind.native, error.message);
    }
  }

  @override
  Future<OverlayStatus> readStatus() async =>
      _decode(await _invoke<Object?>('status')) ?? _status;

  @override
  Future<void> start(OverlaySettings settings) => _invoke<void>('start', {
    'source': settings.source,
    'target': settings.target,
    'opacity': settings.opacity,
    'provider': settings.provider.id,
    'endpoint': settings.endpoint.trim(),
    'apiKey': settings.apiKey.trim(),
  });

  @override
  Future<void> translate() => _invoke<void>('translate');

  @override
  Future<void> stop() => _invoke<void>('stop');

  @override
  Future<void> dispose() async {
    if (_disposed) return;
    _disposed = true;
    _channel.setMethodCallHandler(null);
    await _changes.close();
  }
}
