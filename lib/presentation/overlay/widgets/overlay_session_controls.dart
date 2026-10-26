import 'package:flutter/material.dart';
import '../../../domain/overlay/overlay_settings.dart';
import '../../theme/luma_colors.dart';
import '../overlay_settings_controller.dart';

class OverlaySessionControls extends StatelessWidget {
  const OverlaySessionControls({super.key, required this.controller});
  final OverlaySettingsController controller;
  bool get _android => controller.isAndroid;
  String get _source => controller.settings.source;
  String get _target => controller.settings.target;
  bool get _localPair => controller.settings.isLocalPair;
  TranslationProvider get _provider => controller.settings.provider;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      if (_source == _target)
        const Padding(
          padding: EdgeInsets.only(bottom: 12),
          child: Text(
            'Elige dos idiomas distintos.',
            style: TextStyle(color: Colors.deepOrange),
          ),
        ),
      if (!_android && _provider == TranslationProvider.local && !_localPair)
        const Padding(
          padding: EdgeInsets.only(bottom: 12),
          child: Text(
            'El modelo local incluido requiere English → Español.',
            style: TextStyle(color: Colors.deepOrange),
          ),
        ),
      Container(
        padding: const EdgeInsets.all(15),
        decoration: BoxDecoration(
          color: controller.error == null
              ? LumaColors.pale
              : const Color(0xFFFFF0E8),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(
              controller.error == null
                  ? Icons.info_outline
                  : Icons.error_outline,
              size: 18,
              color: controller.error == null
                  ? LumaColors.green
                  : Colors.deepOrange,
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                controller.error ?? controller.message,
                style: const TextStyle(fontSize: 12),
              ),
            ),
          ],
        ),
      ),
      const SizedBox(height: 16),
      if (controller.running)
        Wrap(
          spacing: 10,
          runSpacing: 10,
          children: [
            FilledButton.icon(
              onPressed: controller.translate,
              icon: const Icon(Icons.translate),
              label: const Text('Traducir ahora'),
            ),
            OutlinedButton(
              onPressed: controller.stop,
              child: const Text('Detener y cerrar la barra'),
            ),
          ],
        )
      else
        FilledButton.icon(
          key: const Key('start-overlay'),
          onPressed: controller.canStart ? controller.start : null,
          icon: Icon(
            controller.starting ? Icons.hourglass_top : Icons.open_in_new,
          ),
          label: Text(
            controller.starting ? 'Preparando…' : 'Activar barra flotante',
          ),
        ),
      const SizedBox(height: 15),
      Text(
        _android
            ? 'Android pedirá permiso para aparecer sobre otras apps y compartir la pantalla completa. Puedes detenerlo desde la barra o la notificación.'
            : 'La ventana de ajustes se minimizará. La barra permanecerá sobre tus otras aplicaciones. Ctrl + Shift + L traduce la pantalla.',
        style: const TextStyle(
          fontSize: 11,
          color: LumaColors.muted,
          height: 1.7,
        ),
      ),
      const SizedBox(height: 12),
      const Text(
        'Las pantallas protegidas por el sistema o por otra aplicación pueden impedir la captura.',
        style: TextStyle(fontSize: 11, color: LumaColors.muted),
      ),
    ],
  );
}
