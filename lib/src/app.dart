import 'package:flutter/material.dart';
import 'overlay_home.dart';
import 'theme.dart';

class LumaApp extends StatelessWidget {
  const LumaApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Luma · Traductor flotante',
    debugShowCheckedModeBanner: false,
    theme: buildLumaTheme(),
    home: const OverlayHome(),
  );
}
