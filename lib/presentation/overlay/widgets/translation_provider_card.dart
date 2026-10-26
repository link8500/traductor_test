import 'package:flutter/material.dart';
import '../../../domain/overlay/overlay_settings.dart';
import '../../theme/luma_colors.dart';
import '../../widgets/surface_card.dart';
import '../overlay_settings_controller.dart';

class TranslationProviderCard extends StatefulWidget {
  const TranslationProviderCard({super.key, required this.controller});
  final OverlaySettingsController controller;

  @override
  State<TranslationProviderCard> createState() =>
      _TranslationProviderCardState();
}

class _TranslationProviderCardState extends State<TranslationProviderCard> {
  OverlaySettingsController get controller => widget.controller;
  late final TextEditingController _endpoint;
  late final TextEditingController _apiKey;
  bool get _android => controller.isAndroid;
  bool get _localPair => controller.settings.isLocalPair;
  TranslationProvider get _provider => controller.settings.provider;
  bool get _online => controller.online;
  bool get _onlineConsent => controller.onlineConsent;

  @override
  void initState() {
    super.initState();
    _endpoint = TextEditingController(text: controller.settings.endpoint);
    _apiKey = TextEditingController(text: controller.settings.apiKey);
  }

  @override
  void dispose() {
    _endpoint.dispose();
    _apiKey.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => SurfaceCard(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          _android ? 'Traducción en el dispositivo' : 'Motor de traducción',
          style: const TextStyle(fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 12),
        if (_android)
          Text(
            _localPair
                ? 'Modelo OPUS inglés → español incluido en la app, con contexto de párrafo y terminología de cómics. OCR y traducción sin conexión. La primera carga puede tardar unos segundos.'
                : 'Para estos idiomas se utiliza ML Kit sin conexión. La primera vez necesita descargar los modelos de idioma; después, el texto se procesa en el teléfono.',
            style: TextStyle(
              fontSize: 12,
              color: LumaColors.muted,
              height: 1.7,
            ),
          )
        else ...[
          DropdownButtonFormField<TranslationProvider>(
            key: const Key('translation-provider'),
            isExpanded: true,
            initialValue: _provider,
            decoration: const InputDecoration(
              labelText: 'Proveedor',
              border: OutlineInputBorder(),
            ),
            items: const [
              DropdownMenuItem(
                value: TranslationProvider.local,
                child: Text('OPUS · sin conexión · inglés → español'),
              ),
              DropdownMenuItem(
                value: TranslationProvider.myMemory,
                child: Text('MyMemory · sin clave'),
              ),
              DropdownMenuItem(
                value: TranslationProvider.libreTranslate,
                child: Text('LibreTranslate · servidor propio'),
              ),
            ],
            onChanged: !controller.editable
                ? null
                : (value) {
                    if (value != null) controller.setProvider(value);
                  },
          ),
          const SizedBox(height: 12),
          if (_provider == TranslationProvider.local)
            const Text(
              'Modelo inglés → español incluido. El texto se procesa en este equipo, con contexto de párrafo y terminología de cómics. No necesita cuenta ni conexión.',
              style: TextStyle(
                fontSize: 12,
                color: LumaColors.muted,
                height: 1.7,
              ),
            ),
          if (_provider == TranslationProvider.myMemory)
            const Text(
              'El OCR se ejecuta en Windows. Solo el texto reconocido se envía a MyMemory; las capturas permanecen en memoria. El servicio gratuito limita el uso a 5.000 caracteres al día.',
              style: TextStyle(
                fontSize: 12,
                color: LumaColors.muted,
                height: 1.7,
              ),
            ),
          if (_provider == TranslationProvider.libreTranslate) ...[
            TextField(
              controller: _endpoint,
              onChanged: controller.setEndpoint,
              enabled: controller.editable,
              decoration: const InputDecoration(
                labelText: 'URL de /translate',
                hintText: 'http://127.0.0.1:5000/translate',
              ),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: _apiKey,
              onChanged: controller.setApiKey,
              enabled: controller.editable,
              obscureText: true,
              decoration: const InputDecoration(
                labelText: 'API key (opcional)',
              ),
            ),
            const SizedBox(height: 10),
            const Text(
              'El texto se envía al servidor indicado. Con un servidor local puedes mantener el procesamiento en tu equipo.',
              style: TextStyle(fontSize: 12, color: LumaColors.muted),
            ),
          ],
          if (_online)
            CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              controlAffinity: ListTileControlAffinity.leading,
              title: const Text(
                'Permitir el envío del texto visible al proveedor seleccionado mientras la herramienta esté activa.',
                style: TextStyle(fontSize: 12),
              ),
              value: _onlineConsent,
              onChanged: !controller.editable
                  ? null
                  : (value) => controller.setOnlineConsent(value ?? false),
            ),
        ],
      ],
    ),
  );
}
