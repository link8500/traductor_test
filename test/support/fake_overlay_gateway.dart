import 'dart:async';

import 'package:traductor/domain/overlay/overlay_gateway.dart';
import 'package:traductor/domain/overlay/overlay_settings.dart';
import 'package:traductor/domain/overlay/overlay_status.dart';

class FakeOverlayGateway implements OverlayGateway {
  final events = StreamController<OverlayStatus>.broadcast(sync: true);
  OverlayStatus status = const OverlayStatus();
  OverlaySettings? lastSettings;
  OverlayFailure? startFailure;
  OverlayFailure? statusFailure;
  Completer<void>? pendingStart;
  int starts = 0;
  int reads = 0;
  int translations = 0;
  bool disposed = false;

  @override
  Stream<OverlayStatus> get statusChanges => events.stream;

  void emit(OverlayStatus value) {
    status = value;
    events.add(value);
  }

  @override
  Future<OverlayStatus> readStatus() async {
    reads++;
    if (statusFailure case final failure?) throw failure;
    return status;
  }

  @override
  Future<void> start(OverlaySettings settings) async {
    starts++;
    lastSettings = settings;
    if (startFailure case final failure?) throw failure;
    if (pendingStart case final pending?) await pending.future;
    status = const OverlayStatus(running: true, message: 'Barra activa');
  }

  @override
  Future<void> translate() async => translations++;

  @override
  Future<void> stop() async =>
      status = const OverlayStatus(message: 'Captura detenida');

  @override
  Future<void> dispose() async {
    disposed = true;
    await events.close();
  }
}
