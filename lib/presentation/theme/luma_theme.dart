import 'package:flutter/material.dart';
import 'luma_colors.dart';

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
