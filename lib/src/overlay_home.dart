import 'package:flutter/material.dart';
import 'overlay_bridge.dart';
import 'theme.dart';

class OverlayHome extends StatefulWidget {
  const OverlayHome({super.key, this.bridge});
  final OverlayBridge? bridge;
  @override
  State<OverlayHome> createState() => _OverlayHomeState();
}

class _OverlayHomeState extends State<OverlayHome> with WidgetsBindingObserver {
  late final OverlayBridge _bridge;
  final _endpoint = TextEditingController(
    text: 'http://127.0.0.1:5000/translate',
  );
  final _apiKey = TextEditingController();
  String _source = 'en';
  String _target = 'es';
  String _provider = 'local';
  bool _onlineConsent = false;
  bool _starting = false;
  double _opacity = .8;
  bool _appearanceInitialized = false;
  bool get _android => Theme.of(context).platform == TargetPlatform.android;
  bool get _online => !_android && _provider != 'local';
  bool get _localPair => _source == 'en' && _target == 'es';
  static const _languages = {
    'en': 'English',
    'es': 'Español',
    'pt': 'Português',
    'fr': 'Français',
    'de': 'Deutsch',
    'it': 'Italiano',
  };

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _bridge = widget.bridge ?? OverlayBridge();
    _bridge.addListener(_changed);
    _bridge.refresh();
  }

  void _changed() {
    if (mounted) setState(() {});
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_appearanceInitialized) {
      _opacity = _android ? .8 : 1;
      _appearanceInitialized = true;
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) _bridge.refresh();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _bridge.removeListener(_changed);
    if (widget.bridge == null) _bridge.dispose();
    _endpoint.dispose();
    _apiKey.dispose();
    super.dispose();
  }

  Future<void> _start() async {
    setState(() => _starting = true);
    await _bridge.start(
      source: _source,
      target: _target,
      opacity: _opacity,
      provider: _provider,
      endpoint: _endpoint.text.trim(),
      apiKey: _apiKey.text.trim(),
    );
    if (mounted) setState(() => _starting = false);
  }

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
        onChanged: _bridge.running
            ? null
            : (v) {
                if (v != null) onChanged(v);
              },
      ),
    ],
  );

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 760),
          child: ListView(
            padding: const EdgeInsets.all(28),
            children: [
              const Row(
                children: [
                  Icon(
                    Icons.translate_rounded,
                    color: LumaColors.green,
                    size: 29,
                  ),
                  SizedBox(width: 10),
                  Text(
                    'luma',
                    style: TextStyle(
                      fontSize: 29,
                      fontWeight: FontWeight.w700,
                      letterSpacing: -1,
                    ),
                  ),
                  SizedBox(width: 20),
                  Expanded(
                    child: Align(
                      alignment: Alignment.centerRight,
                      child: SmallLabel('TRADUCTOR DE PANTALLA'),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 30),
              const Text(
                'Una barra. Toda tu pantalla.',
                style: TextStyle(
                  fontSize: 30,
                  fontWeight: FontWeight.w600,
                  letterSpacing: -1,
                ),
              ),
              const SizedBox(height: 10),
              const Text(
                'Elige los idiomas aquí, activa la barra y toca el icono de traducción. El texto se reconoce y se traduce en su posición con un solo toque.',
                style: TextStyle(color: LumaColors.muted, height: 1.7),
              ),
              const SizedBox(height: 26),
              SurfaceCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Así se verá sobre tus aplicaciones',
                      style: TextStyle(fontWeight: FontWeight.w600),
                    ),
                    const SizedBox(height: 17),
                    FittedBox(
                      fit: BoxFit.scaleDown,
                      alignment: Alignment.centerLeft,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 14,
                          vertical: 13,
                        ),
                        decoration: BoxDecoration(
                          color: LumaColors.ink,
                          borderRadius: BorderRadius.circular(15),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Icon(
                              Icons.drag_indicator,
                              size: 18,
                              color: Colors.white54,
                            ),
                            const SizedBox(width: 10),
                            const Text(
                              'Luma',
                              style: TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            const SizedBox(width: 18),
                            Container(
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                color: LumaColors.lime,
                                shape: BoxShape.circle,
                              ),
                              child: const Icon(
                                Icons.translate,
                                size: 23,
                                color: LumaColors.ink,
                              ),
                            ),
                            const SizedBox(width: 16),
                            const Icon(
                              Icons.close,
                              size: 18,
                              color: Colors.white70,
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 14),
                    const Text(
                      'Toca el icono para traducir. El anillo gira mientras trabaja y se detiene al terminar. Al desplazar la pantalla, vuelve el texto original. Arrastra Luma para mover la barra; × la cierra.',
                      style: TextStyle(fontSize: 12, color: LumaColors.muted),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 18),
              SurfaceCard(
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
                          child: _language(
                            'ORIGINAL',
                            _source,
                            (v) => setState(() => _source = v),
                          ),
                        ),
                        const SizedBox(width: 16),
                        Expanded(
                          child: _language(
                            'TRADUCIR A',
                            _target,
                            (v) => setState(() => _target = v),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    if (_bridge.running)
                      const Padding(
                        padding: EdgeInsets.only(bottom: 12),
                        child: Text(
                          'Para cambiar idiomas, detén la barra y vuelve a activarla con los nuevos idiomas.',
                          style: TextStyle(
                            fontSize: 12,
                            color: LumaColors.muted,
                          ),
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
                      onChanged: _bridge.running
                          ? null
                          : (v) => setState(() => _opacity = v),
                    ),
                    Text(
                      _android
                          ? 'El límite de 80 % permite seguir tocando las aplicaciones debajo.'
                          : 'Las traducciones dejan pasar los clics a las aplicaciones debajo.',
                      style: const TextStyle(
                        fontSize: 11,
                        color: LumaColors.muted,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 18),
              SurfaceCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _android
                          ? 'Traducción en el dispositivo'
                          : 'Motor de traducción',
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
                      DropdownButtonFormField<String>(
                        key: const Key('translation-provider'),
                        isExpanded: true,
                        initialValue: _provider,
                        decoration: const InputDecoration(
                          labelText: 'Proveedor',
                          border: OutlineInputBorder(),
                        ),
                        items: const [
                          DropdownMenuItem(
                            value: 'local',
                            child: Text(
                              'OPUS · sin conexión · inglés → español',
                            ),
                          ),
                          DropdownMenuItem(
                            value: 'mymemory',
                            child: Text('MyMemory · sin clave'),
                          ),
                          DropdownMenuItem(
                            value: 'libre',
                            child: Text('LibreTranslate · servidor propio'),
                          ),
                        ],
                        onChanged: _bridge.running
                            ? null
                            : (v) => setState(() {
                                _provider = v!;
                                _onlineConsent = false;
                              }),
                      ),
                      const SizedBox(height: 12),
                      if (_provider == 'local')
                        const Text(
                          'Modelo inglés → español incluido. El texto se procesa en este equipo, con contexto de párrafo y terminología de cómics. No necesita cuenta ni conexión.',
                          style: TextStyle(
                            fontSize: 12,
                            color: LumaColors.muted,
                            height: 1.7,
                          ),
                        ),
                      if (_provider == 'mymemory')
                        const Text(
                          'El OCR se ejecuta en Windows. Solo el texto reconocido se envía a MyMemory; las capturas permanecen en memoria. El servicio gratuito limita el uso a 5.000 caracteres al día.',
                          style: TextStyle(
                            fontSize: 12,
                            color: LumaColors.muted,
                            height: 1.7,
                          ),
                        ),
                      if (_provider == 'libre') ...[
                        TextField(
                          controller: _endpoint,
                          enabled: !_bridge.running,
                          decoration: const InputDecoration(
                            labelText: 'URL de /translate',
                            hintText: 'http://127.0.0.1:5000/translate',
                          ),
                        ),
                        const SizedBox(height: 10),
                        TextField(
                          controller: _apiKey,
                          enabled: !_bridge.running,
                          obscureText: true,
                          decoration: const InputDecoration(
                            labelText: 'API key (opcional)',
                          ),
                        ),
                        const SizedBox(height: 10),
                        const Text(
                          'El texto se envía al servidor indicado. Con un servidor local puedes mantener el procesamiento en tu equipo.',
                          style: TextStyle(
                            fontSize: 12,
                            color: LumaColors.muted,
                          ),
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
                          onChanged: _bridge.running
                              ? null
                              : (v) =>
                                    setState(() => _onlineConsent = v ?? false),
                        ),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: 22),
              if (_source == _target)
                const Padding(
                  padding: EdgeInsets.only(bottom: 12),
                  child: Text(
                    'Elige dos idiomas distintos.',
                    style: TextStyle(color: Colors.deepOrange),
                  ),
                ),
              if (!_android && _provider == 'local' && !_localPair)
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
                  color: _bridge.error == null
                      ? LumaColors.pale
                      : const Color(0xFFFFF0E8),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(
                      _bridge.error == null
                          ? Icons.info_outline
                          : Icons.error_outline,
                      size: 18,
                      color: _bridge.error == null
                          ? LumaColors.green
                          : Colors.deepOrange,
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        _bridge.error ?? _bridge.message,
                        style: const TextStyle(fontSize: 12),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              if (_bridge.running)
                Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: [
                    FilledButton.icon(
                      onPressed: () => _bridge.command('translate'),
                      icon: const Icon(Icons.translate),
                      label: const Text('Traducir ahora'),
                    ),
                    OutlinedButton(
                      onPressed: () => _bridge.command('stop'),
                      child: const Text('Detener y cerrar la barra'),
                    ),
                  ],
                )
              else
                FilledButton.icon(
                  key: const Key('start-overlay'),
                  onPressed:
                      _starting ||
                          _source == _target ||
                          (_online && !_onlineConsent) ||
                          (!_android && _provider == 'local' && !_localPair)
                      ? null
                      : _start,
                  icon: Icon(
                    _starting ? Icons.hourglass_top : Icons.open_in_new,
                  ),
                  label: Text(
                    _starting ? 'Preparando…' : 'Activar barra flotante',
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
          ),
        ),
      ),
    ),
  );
}
