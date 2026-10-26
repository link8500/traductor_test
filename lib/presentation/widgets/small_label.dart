import 'package:flutter/material.dart';
import '../theme/luma_colors.dart';

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
