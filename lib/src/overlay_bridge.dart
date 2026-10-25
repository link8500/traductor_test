import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

/// The Flutter window configures the tool. Capture and overlays live natively,
/// so they continue working while this window is minimized or backgrounded.
class OverlayBridge extends ChangeNotifier {
  OverlayBridge({MethodChannel? channel})
    : _channel = channel ?? const MethodChannel('luma/screen_translator') {
    _channel.setMethodCallHandler((call) async {
      if (call.method == 'status') _update(call.arguments);
    });
  }

  final MethodChannel _channel;
  bool running = false;
  bool original = false;
  String message = 'Listo para activar la barra flotante';
  String? error;

  void _update(dynamic data) {
    if (data is! Map) return;
    running = data['running'] == true;
    original = data['original'] == true;
    message = data['message'] as String? ?? message;
    error = data['error'] as String?;
    notifyListeners();
  }

  Future<void> refresh() async {
    try {
      _update(await _channel.invokeMethod<Object?>('status'));
    } on MissingPluginException {
      message = 'La superposición está disponible en Windows y Android.';
      notifyListeners();
    }
  }

  Future<void> start({
    required String source,
    required String target,
    required double opacity,
    required String provider,
    required String endpoint,
    required String apiKey,
  }) async {
    error = null;
    message = 'Preparando la barra flotante…';
    notifyListeners();
    try {
      await _channel.invokeMethod<void>('start', {
        'source': source,
        'target': target,
        'opacity': opacity,
        'provider': provider,
        'endpoint': endpoint,
        'apiKey': apiKey,
      });
      await refresh();
    } on PlatformException catch (e) {
      error = e.message ?? 'No se pudo iniciar la captura.';
      message = error!;
      notifyListeners();
    } on MissingPluginException {
      error = 'Ejecuta la versión nativa para Windows o Android.';
      notifyListeners();
    }
  }

  Future<void> command(String method) async {
    try {
      await _channel.invokeMethod<void>(method);
      await refresh();
    } on PlatformException catch (e) {
      error = e.message;
      notifyListeners();
    }
  }

  @override
  void dispose() {
    _channel.setMethodCallHandler(null);
    super.dispose();
  }
}
