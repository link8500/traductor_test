import 'package:flutter/material.dart';
import '../../theme/luma_colors.dart';
import '../../widgets/surface_card.dart';
import '../../widgets/small_label.dart';
import '../overlay_settings_controller.dart';

class AppearanceCard extends StatelessWidget {
  const AppearanceCard({super.key, required this.controller});
  final OverlaySettingsController controller;
  bool get _android => controller.isAndroid;
  String get _source => controller.settings.source;
  String get _target => controller.settings.target;
  double get _opacity => controller.settings.opacity;
  static const _languages = {
    'en': 'English',
    'es': 'Español',
    'pt': 'Português',
    'fr': 'Français',
    'de': 'Deutsch',
    'it': 'Italiano',
  };

  Widget _language(
    String label,
    String value,
    ValueChanged<String> onChanged,
  ) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      SmallLabel(label),
      const SizedBox(height: 8),
      DropdownButtonFormField<String>(
        isExpanded: true,
        initialValue: value,
        decoration: InputDecoration(
          filled: true,
          fillColor: LumaColors.canvas,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(10),
            borderSide: const BorderSide(color: LumaColors.line),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(10),
            borderSide: const BorderSide(color: LumaColors.line),
          ),
          contentPadding: const EdgeInsets.symmetric(
            horizontal: 14,
            vertical: 14,
          ),
        ),
        items: _languages.entries
            .map(
              (e) => DropdownMenuItem(
                value: e.key,
                child: Text(e.value, style: const TextStyle(fontSize: 13)),
              ),
            )
            .toList(),
        onChanged: !controller.editable
            ? null
            : (v) {
                if (v != null) onChanged(v);
              },
      ),
    ],
  );

  @override
  Widget build(BuildContext context) => SurfaceCard(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Idiomas y apariencia',
          style: TextStyle(fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 20),
        Row(
          children: [
            Expanded(
              child: _language('ORIGINAL', _source, controller.setSource),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: _language('TRADUCIR A', _target, controller.setTarget),
            ),
          ],
        ),
        const SizedBox(height: 16),
        if (controller.running)
          const Padding(
            padding: EdgeInsets.only(bottom: 12),
            child: Text(
              'Para cambiar idiomas, detén la barra y vuelve a activarla con los nuevos idiomas.',
              style: TextStyle(fontSize: 12, color: LumaColors.muted),
            ),
          ),
        const Text(
          'La traducción se inicia con el icono. Al desplazarte se retira el resultado; no se vuelve a traducir sin que lo pidas.',
          style: TextStyle(fontSize: 12, color: LumaColors.muted),
        ),
        const SizedBox(height: 18),
        Row(
          children: [
            const Expanded(
              child: Text(
                'Opacidad de la superposición',
                style: TextStyle(fontSize: 12),
              ),
            ),
            Text(
              '${(_opacity * 100).round()}%',
              style: const TextStyle(color: LumaColors.green),
            ),
          ],
        ),
        Slider(
          value: _opacity,
          min: .4,
          max: _android ? .8 : 1,
          onChanged: !controller.editable ? null : controller.setOpacity,
        ),
        Text(
          _android
              ? 'El límite de 80 % permite seguir tocando las aplicaciones debajo.'
              : 'Las traducciones dejan pasar los clics a las aplicaciones debajo.',
          style: const TextStyle(fontSize: 11, color: LumaColors.muted),
        ),
      ],
    ),
  );
}
