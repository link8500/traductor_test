import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../application/overlay/overlay_session.dart';
import '../domain/overlay/overlay_gateway.dart';
import '../domain/overlay/overlay_settings.dart';
import '../infrastructure/overlay/method_channel_overlay_gateway.dart';
import '../presentation/overlay/overlay_settings_controller.dart';
import '../presentation/overlay/overlay_settings_page.dart';
import '../presentation/theme/luma_theme.dart';

/// Composition root. Each app instance owns its gateway, session and controller.
class LumaApp extends StatefulWidget {
  const LumaApp({super.key, this.gateway, this.platform});

  final OverlayGateway? gateway;
  final TargetPlatform? platform;

  @override
  State<LumaApp> createState() => _LumaAppState();
}

class _LumaAppState extends State<LumaApp> {
  late final OverlaySession _session;
  late final OverlaySettingsController _controller;

  @override
  void initState() {
    super.initState();
    final platform = switch (widget.platform ?? defaultTargetPlatform) {
      TargetPlatform.android => OverlayPlatform.android,
      TargetPlatform.windows => OverlayPlatform.windows,
      _ => OverlayPlatform.unsupported,
    };
    _session = OverlaySession(widget.gateway ?? MethodChannelOverlayGateway());
    _controller = OverlaySettingsController(_session, platform: platform);
    unawaited(_controller.refresh());
  }

  @override
  void dispose() {
    _controller.dispose();
    unawaited(_session.dispose());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Luma · Traductor flotante',
    debugShowCheckedModeBanner: false,
    theme: buildLumaTheme().copyWith(platform: widget.platform),
    home: OverlaySettingsPage(controller: _controller),
  );
}
