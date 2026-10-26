class OverlayStatus {
  const OverlayStatus({
    this.running = false,
    this.original = false,
    this.message = 'Listo para activar la barra flotante',
    this.error,
  });

  final bool running;
  final bool original;
  final String message;
  final String? error;

  OverlayStatus copyWith({
    bool? running,
    bool? original,
    String? message,
    String? error,
    bool clearError = false,
  }) => OverlayStatus(
    running: running ?? this.running,
    original: original ?? this.original,
    message: message ?? this.message,
    error: clearError ? null : error ?? this.error,
  );
}
