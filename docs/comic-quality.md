# Prueba de los seis capítulos de Asura

La evaluación posterior con los 60 capítulos bilingües está documentada en
[bilingual-comic-quality.md](bilingual-comic-quality.md).

Evaluación local del 22–23 de octubre de 2026. **La aplicación todavía no cumple el objetivo de no observar ningún error de traducción.** Se mejoró el flujo sin conexión y se ejecutó el corpus completo; persisten errores de reconocimiento y de significado.

## Cobertura real

Se descargaron 130 imágenes públicas de los seis enlaces indicados y se recorrieron en 966 recortes de hasta 2.000 píxeles de alto, con 700 píxeles de solapamiento. Se conservaron el texto nativo, la segunda lectura, las coordenadas y la traducción para comparar los fallos. Las imágenes y los resultados completos están en `build/comic-quality/`, excluidos de la distribución de Luma.

| Capítulo | Imágenes | Regiones Android | Regiones Windows |
|---|---:|---:|---:|
| academy-128 | 27 | 229 | 241 |
| cultivation-35 | 23 | 135 | 166 |
| cultivation-34 | 21 | 95 | 111 |
| cultivation-33 | 25 | 107 | 102 |
| cultivation-32 | 17 | 150 | 149 |
| cultivation-31 | 17 | 147 | 159 |

Android ejecutó OCR ML Kit, la segunda lectura PP-OCRv4 y el traductor nativo dentro del APK de pruebas: **863 regiones, cero excepciones de ejecución**. Windows ejecutó su flujo nativo sobre las mismas 130 imágenes: **928 regiones y una excepción** por un fragmento cortado que el decodificador no pudo completar.

Se corrigió ese caso para conservar el original y permitir que los demás bloques continúen. Después se volvieron a traducir las **928 regiones de Windows, 883 textos únicos**, con el núcleo final compartido: cero excepciones, un fragmento conservado por falta de resultado y un crédito conservado como nombre. Esta repetición usa las coordenadas y el OCR de la pasada completa anterior; no es otra pasada completa de captura/OCR. El informe JSON conserva esa diferencia.

Los recuentos incluyen nombres, sonidos y créditos. Un número menor de regiones puede deberse a unir líneas y eliminar duplicados; no demuestra una mejora del porcentaje de palabras detectadas. Recorrer todos los archivos tampoco demuestra que todos los bocadillos hayan sido encontrados.

Después del recorrido completo se amplió el margen de agrupación de párrafos Android para letras grandes. Ese cambio se verificó sobre pantallas de control; no se repitió el recorrido completo de 130 imágenes después de ese ajuste. Los recuentos anteriores corresponden a la pasada guardada, con el margen anterior.

## Comprobación visual del APK optimizado

En el Pixel_6a existente, Android 36 x86_64, se abrió una página de control en un lector temporal separado de Luma. Se comprobó que dos bocadillos se traducen como dos párrafos completos, incluida una última palabra que antes quedaba aislada. Dos capturas de la animación tienen píxeles distintos; al terminar, el recorte del icono coincide exactamente con el de reposo. Deslizar desplaza la página inferior, retira la traducción y deja el original sin volver a traducirlo automáticamente.

También se abrió un recorte real del capítulo 35 con el párrafo de regresión de la captura del usuario. Se movió la barra, se tradujo con un toque y se comprobó el retorno al original. El modelo todavía omite el adverbio inicial por la lectura de la puntuación; en letras inclinadas puede quedar un borde del original fuera del área detectada. El fondo de la máscara queda gris para respetar el paso de toques. No se presenta esta prueba como equivalente a Google ni como traducción perfecta.

Capturas locales: `build/comic-quality/android-translated-final.png`, `android-comic-translated.png`, `android-comic-after-swipe.png`. Resumen: `android-visual-summary.json`. Al cerrar ×, el gestor de MediaProjection informó `null`.

## Cambios probados

- OPUS `Helsinki-NLP/opus-mt-tc-big-en-es` incluido, cuantizado a Int4, con el mismo tokenizador y búsqueda en Windows y Android. No se envía texto a un proveedor externo en este modo.
- PP-OCRv4 inglés como segunda lectura de líneas, seleccionado por confianza y límites de longitud. La confianza del OCR no certifica que una frase sea correcta.
- Agrupación de líneas del mismo párrafo, ajuste del texto al rectángulo y glosario general para términos de cultivo/regresión.
- Corrección del vocabulario del tokenizador para cuatro variantes de guiones. Coincide con siete casos de referencia de SentencePiece, incluidos caracteres de compatibilidad y espacios.
- Cancelación del decodificador al cambiar la pantalla, recuperación posterior y conservación explícita de fragmentos que no terminan.
- Barra de un único icono con animación ligada al trabajo; sin traducción periódica. Windows pasó las comprobaciones de arrastre, paso de clics, movimiento, resultados antiguos y cierre.
- Máscara Android calculada con la captura para ocultar letras antiguas bajo la opacidad permitida. La prueba comprueba el contraste de la composición final, no solo el color del bitmap.

Se comparó también PP-OCRv5 inglés en 21 ejemplos de desarrollo: hubo mejoras en algunas letras y regresiones claras en otras. Esa comparación no proporciona una puntuación de exactitud y no justificó sustituir el reconocedor seleccionado.

## Errores que siguen presentes

En los capítulos hay palabras pegadas, pronombres confundidos con cifras, nombres propios deformados y letras decorativas que ninguno de los reconocedores lee bien. Traducir una lectura incorrecta produce un resultado incorrecto aunque el modelo funcione. También se observaron omisiones y frases poco naturales con el texto bien reconocido.

El ejemplo de regresión mejora al reconocer la oración completa y separar las palabras, pero la puntuación errónea puede hacer que el modelo omita el adverbio inicial. En otra viñeta, unir una conjunción y un pronombre hace que se interpreten como un nombre. Esos casos siguen abiertos; no están ocultos en un porcentaje artificial de “100 %”.

No hay traducciones de referencia revisadas de cada región para calcular una precisión semántica fiable. El corpus de seis capítulos es una prueba de desarrollo; no es un conjunto independiente de validación para un modelo ajustado con esos mismos textos.

## Entrenar un modelo

La corrección posterior del cierre nativo en teléfonos ARM64, con sus pruebas
en un dispositivo físico, está documentada en [android-arm64-crash.md](android-arm64-crash.md).

Esta versión adapta modelos ya entrenados y añade procesamiento; **no se entrenó una IA nueva**. Un ajuste especializado requeriría imágenes con transcripciones correctas para OCR y pares inglés/español revisados para traducción, con capítulos separados para validación. Memorizar las respuestas de estos seis capítulos no demostraría que la app traduce otros cómics correctamente.

El siguiente paso de calidad es construir esas referencias, medir errores de caracteres, palabras y significado, y comparar cualquier ajuste con el modelo actual sobre material que no haya visto durante el desarrollo.

## Reproducir

```sh
python tools/check_model_assets.py
python tools/prepare_windows_quality.py
python tools/evaluate_comic_quality.py --workers 2 --input build/comic-quality/windows-ctc-translations.jsonl --prefix windows-final-
python tools/summarize_comic_quality.py
python tools/create_comic_preview.py
python tools/verify_release_artifacts.py
```

La instrumentación de corpus es separada del APK distribuido:

```powershell
.\android\gradlew.bat -p android -PlumaBenchmark=true -PlumaTestBuildType=release -Ptarget-platform=android-x64 -Psplit-per-abi=true :app:assembleRelease :app:assembleReleaseAndroidTest
python tools/run_android_quality.py full --import-fixtures
python tools/run_android_quality.py model --import-fixtures
```

La prueba de corpus ejecuta los mismos componentes de OCR y traducción de producción sobre archivos de prueba. La captura de pantalla, los permisos y los gestos requieren además la comprobación visual de la superposición. El APK optimizado se compila por separado y sus modelos se verifican por SHA-256.

Los informes completos son `android-full.jsonl`, `windows-ctc-translations.jsonl`, `windows-final-translated-regions.jsonl` y `quality-summary.json`. Sus capturas y textos no se incluyen como datos de entrenamiento ni como respuestas predefinidas de la app.

## Fuentes y procedencia

Los enlaces de los seis capítulos y las imágenes utilizadas constan en `build/comic-quality/manifest.json`. La procedencia de los modelos, revisiones y SHA-256 están en `assets/models/opus-en-es/manifest.json`.

- [Modelo OPUS EN→ES](https://huggingface.co/Helsinki-NLP/opus-mt-tc-big-en-es).
- [Modelos de RapidOCR](https://github.com/RapidAI/RapidOCR/blob/main/python/rapidocr/default_models.yaml).
- [Cuantización de ONNX Runtime](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html).
- [Límite de opacidad y toques de Android](https://developer.android.com/about/versions/12/behavior-changes-all#untrusted-touch-events).
