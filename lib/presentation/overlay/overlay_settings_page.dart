import 'package:flutter/material.dart';
import '../theme/luma_colors.dart';
import '../widgets/small_label.dart';
import 'overlay_settings_controller.dart';
import 'widgets/appearance_card.dart';
import 'widgets/overlay_preview_card.dart';
import 'widgets/overlay_session_controls.dart';
import 'widgets/translation_provider_card.dart';

class OverlaySettingsPage extends StatefulWidget {
  const OverlaySettingsPage({super.key, required this.controller});
  final OverlaySettingsController controller;

  @override
  State<OverlaySettingsPage> createState() => _OverlaySettingsPageState();
}

class _OverlaySettingsPageState extends State<OverlaySettingsPage>
    with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) widget.controller.refresh();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: widget.controller,
    builder: (context, child) => Scaffold(
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
                const OverlayPreviewCard(),
                const SizedBox(height: 18),
                AppearanceCard(controller: widget.controller),
                const SizedBox(height: 18),
                TranslationProviderCard(controller: widget.controller),
                const SizedBox(height: 22),
                OverlaySessionControls(controller: widget.controller),
              ],
            ),
          ),
        ),
      ),
    ),
  );
}
