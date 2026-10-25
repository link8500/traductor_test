import 'package:flutter/material.dart';

abstract final class LumaColors {
  static const ink = Color(0xFF26352F);
  static const muted = Color(0xFF829087);
  static const green = Color(0xFF456B50);
  static const lime = Color(0xFFD5EF9D);
  static const canvas = Color(0xFFF7F9F6);
  static const line = Color(0xFFE7ECE6);
  static const pale = Color(0xFFF0F5EB);
}

ThemeData buildLumaTheme() {
  final scheme = ColorScheme.fromSeed(
    seedColor: LumaColors.green,
    brightness: Brightness.light,
    surface: Colors.white,
  );
  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: LumaColors.canvas,
    fontFamily: 'Segoe UI',
    textTheme: const TextTheme(
      bodyMedium: TextStyle(fontSize: 13, height: 1.5, color: LumaColors.ink),
      bodySmall: TextStyle(fontSize: 11, height: 1.5, color: LumaColors.muted),
      titleMedium: TextStyle(
        fontSize: 15,
        fontWeight: FontWeight.w600,
        color: LumaColors.ink,
      ),
    ),
    iconTheme: const IconThemeData(color: LumaColors.ink, size: 20),
    dividerColor: LumaColors.line,
    tooltipTheme: TooltipThemeData(
      decoration: BoxDecoration(
        color: LumaColors.ink,
        borderRadius: BorderRadius.circular(8),
      ),
      textStyle: const TextStyle(color: Colors.white, fontSize: 12),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        foregroundColor: LumaColors.ink,
        backgroundColor: LumaColors.lime,
        padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 20),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        textStyle: const TextStyle(
          fontSize: 13,
          fontWeight: FontWeight.w600,
          fontFamily: 'Segoe UI',
        ),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: LumaColors.ink,
        side: const BorderSide(color: LumaColors.line),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      ),
    ),
    switchTheme: SwitchThemeData(
      thumbColor: const WidgetStatePropertyAll(Colors.white),
      trackColor: WidgetStateProperty.resolveWith(
        (states) => states.contains(WidgetState.selected)
            ? LumaColors.green
            : const Color(0xFFCFD8CF),
      ),
      trackOutlineColor: const WidgetStatePropertyAll(Colors.transparent),
    ),
    sliderTheme: const SliderThemeData(
      activeTrackColor: LumaColors.green,
      inactiveTrackColor: LumaColors.line,
      thumbColor: LumaColors.green,
      trackHeight: 3,
      thumbShape: RoundSliderThumbShape(enabledThumbRadius: 6),
      overlayShape: RoundSliderOverlayShape(overlayRadius: 14),
    ),
  );
}

class SurfaceCard extends StatelessWidget {
  const SurfaceCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(22),
  });
  final Widget child;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) => Material(
    color: Colors.white,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(18),
      side: const BorderSide(color: LumaColors.line),
    ),
    child: Padding(padding: padding, child: child),
  );
}

class SmallLabel extends StatelessWidget {
  const SmallLabel(this.text, {super.key, this.color = LumaColors.muted});
  final String text;
  final Color color;

  @override
  Widget build(BuildContext context) => Text(
    text,
    style: TextStyle(
      fontSize: 10,
      color: color,
      letterSpacing: 1.7,
      fontWeight: FontWeight.w600,
    ),
  );
}

class StatusDot extends StatelessWidget {
  const StatusDot({super.key, this.color = LumaColors.green});
  final Color color;

  @override
  Widget build(BuildContext context) => Container(
    width: 6,
    height: 6,
    decoration: BoxDecoration(color: color, shape: BoxShape.circle),
  );
}
