# Referencia: EZ Screen Translator

Revisión de la ficha pública de Google Play, 22 de octubre de 2026. No se ha accedido al código ni se ha instalado la app de referencia.

La ficha de [Tap To Translate Screen, de EZ Screen Translator](https://play.google.com/store/apps/details?id=com.tap_to_translate.snap_translate) describe traducción de pantalla completa con un toque y resultados sobre otras aplicaciones. También anuncia cámara, voz, imágenes y un modo de chat con accesibilidad. El requisito de este proyecto es la traducción de pantalla con una barra movible, por lo que esas funciones adicionales no forman parte de la implementación.

| Necesidad | Windows | Android |
|---|---|---|
| Control pequeño sobre otras apps | Barra Win32 `WS_EX_TOPMOST`, icono único animado, arrastrable por Luma | `TYPE_APPLICATION_OVERLAY`, icono único animado, arrastrable por Luma |
| Captura de pantalla | GDI del escritorio virtual | MediaProjection y un ImageReader |
| Texto y posiciones reales | Windows.Media.Ocr y segunda lectura inglesa PP-OCRv4 | ML Kit Text Recognition y segunda lectura inglesa PP-OCRv4 |
| Traducción | OPUS EN→ES incluido; MyMemory y LibreTranslate opcionales con consentimiento | Mismo OPUS EN→ES incluido; ML Kit local para otros pares |
| Sustituir texto en su posición | Ventana transparente, fondo muestreado y opacidad inicial del 100 % | Canvas nativo, máscara calculada con la captura para compensar las letras originales bajo alfa 0,8 |
| Seguir interactuando debajo | `WS_EX_TRANSPARENT` y `WS_EX_NOACTIVATE` | `FLAG_NOT_TOUCHABLE`, `FLAG_NOT_FOCUSABLE` y alfa limitado |
| Evitar traducir la propia capa | Excluir de captura; ocultar si no está disponible | Ocultar la capa; excluir del OCR el rectángulo de la barra, que permanece visible |
| Volver al texto original | Retirar resultado al pulsar fuera, detectar movimiento o cambiar pantalla; descartar tareas antiguas | Retirar resultado ante toque exterior, movimiento u orientación; descartar tareas antiguas |
| Traducción con un toque | Icono de traducción y atajo; OCR y traducción se ejecutan una vez | Icono de traducción; OCR y traducción se ejecutan una vez |
| Idiomas | Se eligen en la app, fuera de la barra | Se eligen en la app, fuera de la barra |
| Finalizar | ×, cierre de la app | ×, notificación, cancelación de MediaProjection o cierre del proceso |

El parecido aplicado es de comportamiento. El reconocimiento y las traducciones sustituyen la anterior demo con textos predefinidos. El modo local incluido traduce inglés a español; el resto de pares y los proveedores opcionales tienen otro alcance. Se respetan las restricciones de captura y de toques del sistema. El [informe de los seis capítulos](comic-quality.md) separa cobertura de ejecución y errores de calidad aún observados.

## Documentación primaria utilizada

- [Android MediaProjection](https://developer.android.com/media/grow/media-projection): consentimiento nuevo por sesión, servicio foreground, callback de parada y resize sin reutilizar el token.
- [WindowManager.LayoutParams](https://developer.android.com/reference/android/view/WindowManager.LayoutParams): permiso de superposición y límite de opacidad para permitir toques a ventanas inferiores.
- [ML Kit Text Recognition](https://developers.google.com/ml-kit/vision/text-recognition/v2/android): OCR con posiciones.
- [ML Kit Translation](https://developers.google.com/ml-kit/language/translation/android): modelos locales y descarga previa al uso.
- [Windows OcrEngine](https://learn.microsoft.com/en-us/uwp/api/windows.media.ocr.ocrengine): palabras, líneas y coordenadas.
- [Modelo OPUS EN→ES](https://huggingface.co/Helsinki-NLP/opus-mt-tc-big-en-es) y [RapidOCR](https://github.com/RapidAI/RapidOCR): modelos ya entrenados utilizados localmente.
- [SetWindowDisplayAffinity](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowdisplayaffinity): exclusión de las traducciones de su propia captura, disponible desde Windows 10 versión 2004.
- [MyMemory API](https://mymemory.translated.net/doc/spec.php) y [cuotas](https://mymemory.translated.net/doc/usagelimits.php): límite de 500 bytes por segmento y 5.000 caracteres diarios anónimos.
