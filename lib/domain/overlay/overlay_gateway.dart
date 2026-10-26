import 'overlay_settings.dart';
import 'overlay_status.dart';

enum OverlayFailureKind { unavailable, native }

class OverlayFailure implements Exception {
  const OverlayFailure(this.kind, [this.message]);

  final OverlayFailureKind kind;
  final String? message;
}

/// Port implemented by the platform adapter. It does not schedule translations.
abstract interface class OverlayGateway {
  Stream<OverlayStatus> get statusChanges;
  Future<OverlayStatus> readStatus();
  Future<void> start(OverlaySettings settings);
  Future<void> translate();
  Future<void> stop();
  Future<void> dispose();
}
