import 'package:flutter/material.dart';
import '../../theme/luma_colors.dart';
import '../../widgets/surface_card.dart';

class OverlayPreviewCard extends StatelessWidget {
  const OverlayPreviewCard({super.key});

  @override
  Widget build(BuildContext context) => SurfaceCard(
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
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
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
                const Icon(Icons.close, size: 18, color: Colors.white70),
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
  );
}
