# Luma · Traductor flotante

Traduce el texto visible sobre otras aplicaciones en Windows y Android. Flutter muestra los ajustes; la captura, la barra movible y el reemplazo del texto son nativos.

## Organización del proyecto

La configuración y las sesiones usan arquitectura limpia: `domain` define las
reglas y los contratos, `application` coordina las acciones, `infrastructure`
implementa el canal nativo y `presentation` contiene la interfaz. `app` conecta
las dependencias. Windows, Android y las utilidades enlazan un único target
para el motor C++ compartido.

Consulta [el mapa, las dependencias y la guía de cambios](docs/architecture.md),
[el índice de documentación](docs/README.md),
[las herramientas de evaluación](tools/README.md) y
[los datos de pruebas](benchmarks/README.md).

## Uso

1. Elige los idiomas en la aplicación. Inglés → español usa por defecto el modelo incluido y funciona sin conexión desde la instalación.
2. Activa la barra flotante. Android solicita aparecer sobre otras apps y compartir la pantalla completa durante esa sesión.
3. Arrastra **Luma** para mover la barra. Pulsa su único **icono de traducción** para capturar, reconocer y traducir una vez. El anillo gira mientras se procesa y vuelve al reposo al terminar o cancelar.
4. Deslizar o cambiar el contenido retira la traducción y descarta los resultados pendientes. Tocar un margen vacío o arrastrar la barra conserva el resultado. Pulsa de nuevo el icono para traducir otra pantalla. **×** cierra la barra y termina la captura.

Los idiomas se cambian desde la aplicación. No hay traducciones periódicas ni al activar la barra. La comprobación de movimiento solo compara muestras pequeñas de imagen mientras hay una tarea o un resultado; no ejecuta OCR. Las capturas se procesan en memoria y no se guardan en el uso normal. La superposición deja pasar los gestos a la aplicación inferior; no necesita un servicio de accesibilidad.

## Traducción y reconocimiento locales

El motor compartido C++ ejecuta **Helsinki-NLP/opus-mt-tc-big-en-es** con ONNX Runtime 1.23.2, búsqueda de cuatro candidatos, tokenización SentencePiece y pesos Int4. El modelo incluido se convirtió a ONNX y se cuantizó para ejecutarse localmente; no se entrenó desde cero. Los ajustes experimentales de pesos se describen por separado más abajo. El paquete incluye alrededor de 259 MB de modelos y metadatos, además de los componentes de la aplicación.

Windows OCR y Android ML Kit localizan los textos. La compilación 8007 usa el reconocedor latino **PP-OCRv5** y consulta el lector inglés **PP-OCRv4** cuando la primera lectura es incierta o discrepa del OCR del sistema. Los cambios pequeños se contrastan entre lectores; una confianza alta por sí sola puede corresponder a una palabra incorrecta. El detector DB móvil PP-OCRv4 localiza texto adicional. Se unen líneas del mismo párrafo, se normalizan las mayúsculas para traducir, y un glosario general mantiene términos de ficción y cultivo. El glosario no contiene respuestas completas de los capítulos de prueba.

La compilación 8010 también contrasta pequeños ajustes del margen vertical cuando los lectores discrepan. Solo acepta una lectura obtenida de los píxeles si coincide con el lector del sistema y supera el umbral de confianza. Esto corrige el caso observado de «LNDERWATER» sin sustituir palabras por las respuestas del cómic. Los pesos del traductor no cambiaron.

La 8011 reconstruye fragmentos de una misma línea antes de agrupar el diálogo: `THEN FOLLOW ME.` ya produce «Entonces sígueme» en las pruebas de Windows y Android. La evaluación de capítulos también selecciona la lectura más completa entre capturas solapadas, para conservar las continuaciones de frases que antes se perdían cerca del borde. El recorrido vigente usa el motor inmutable `frozen-windows801101` y los informes `*-en8011-context`; las imágenes indican qué pasada las produjo.

Antes de capturar se ocultan la barra y la traducción anterior. Después, la barra busca un espacio libre entre las regiones reconocidas. Los textos que cruzan el borde útil de la pantalla se conservan para evitar traducir palabras recortadas.

La posición, el centrado y el tamaño se ajustan al área reconocida. En Windows la opacidad inicial es del 100 %. Android limita la ventana al 80 % para permitir el paso de toques: una máscara calculada con la captura compensa las letras originales y suaviza los bordes. El fondo resultante puede verse ligeramente gris. Fondos en movimiento y letras artísticas siguen siendo casos difíciles.

**Alcance:** el modelo incluido traduce inglés → español. En Android, otros pares usan ML Kit local; su primera preparación necesita descargar los modelos de idioma. En Windows hay proveedores opcionales MyMemory y LibreTranslate: solo se usan al seleccionarlos y aceptar expresamente el envío del texto. El modo local no hace peticiones de traducción.

## Adaptación experimental del traductor

Se entrenaron adaptadores LoRA sobre OPUS-MT y se compararon con inglés
transcrito y con fuentes OCR conservadas. Son candidatos de traducción,
separados del modelo instalado; no se añadieron dos motores nuevos a la app.
Los ensayos recuperan contenido en conjuntos pequeños, pero también muestran
regresiones y salidas fallidas en otros controles. Ninguno se incorporó a
producción y no se acredita menos del 5 % de fallos por uso.

Continúa la ampliación de diálogos bilingües cotejados con sus imágenes,
manteniendo separados entrenamiento, validación y prueba. Consulta
[los resultados, los protocolos y sus límites](docs/local-model-adaptation.md).
Estos ajustes de traducción no entrenan los pesos del reconocimiento OCR.

La continuación [8035–8036 estudia intensidad, estabilidad y selección de
puntos de control](docs/model-stability.md). Incluye otro entrenamiento real,
pero conserva regresiones y tampoco se incorpora a producción. Las mejoras
parciales de validación no acreditan el objetivo del 5 %.

La continuación [8037–8040 compara decodificación, evaluación de calidad y
selección inversa](docs/translation-selection.md). La última variante recupera
7 diálogos de validación y 10 de control frente al motor nativo, pero introduce
dos empeoramientos parciales y dos dudas nuevas en los controles. Sigue
experimental; la aplicación conserva su motor actual.

## Plataformas

- **Windows:** Windows 10 2004 o posterior, x64; idioma de OCR instalado en Configuración. Captura del escritorio virtual y varios monitores. Atajo `Ctrl + Shift + L` mientras la barra está activa.
- **Android:** Android 8.0 o posterior; MediaProjection con consentimiento por sesión y servicio foreground. Se usa el Pixel_6a existente para las pruebas, sin crear otro emulador.

Las pantallas protegidas, DRM y ciertos juegos pueden bloquear la captura. El ajuste del texto puede reducir la letra cuando la traducción ocupa más espacio.

## Ejecutar y exportar

```sh
flutter run -d windows
flutter run -d emulator-5554 --release
flutter build windows --release
flutter build apk --release --split-per-abi
```

Windows: distribuye **toda** la carpeta `build/windows/x64/runner/Release/`, con `data/`, DLL y licencias; requiere el runtime de Visual C++. Android: `build/app/outputs/flutter-apk/`, elige `app-arm64-v8a-release.apk` para la mayoría de teléfonos actuales o `app-x86_64-release.apk` para este emulador. La firma actual es de desarrollo; publicar en una tienda requiere una firma propia.

Si Java falla por una ruta temporal demasiado larga en Windows:

```powershell
New-Item -ItemType Directory -Force build\java-tmp | Out-Null
$env:JAVA_HOME = 'C:\Program Files\Android\Android Studio\jbr'
$env:JAVA_TOOL_OPTIONS = '-Djdk.net.unixdomain.tmpdir="' + (Join-Path $PWD 'build\java-tmp') + '"'
```

## Verificación

```sh
flutter analyze --no-pub
flutter test --no-pub
python tools/check_model_assets.py
```

```powershell
.\android\gradlew.bat -p android :app:testDebugUnitTest
& .\build\windows\x64\runner\Release\traductor.exe --overlay-self-test "$PWD\build\overlay-self-test.json"
& .\build\windows\x64\runner\Release\traductor.exe --overlay-toolbar-test "$PWD\build\overlay-toolbar-test.json"
```

La prueba nativa Windows reconoce una imagen generada y comprueba «Hola mundo» con el motor local. La prueba de barra comprueba activación manual, animación, movimiento, cancelación, arrastre y cierre. Las pruebas JVM cubren detección de movimiento, regiones excluidas y agrupación de párrafos.

Los seis capítulos iniciales se conservan en `build/comic-quality/`. El corpus ampliado contiene 154 pares de capítulos y sus imágenes permanecen en `build/full-comics/`; no se incluyen en la aplicación. Consulta [el informe ampliado](docs/full-comic-quality.md) para cobertura, procedimiento y límites. Procesar todos los archivos sin excepciones no equivale a obtener una traducción semánticamente perfecta.

`tools/export_chapter_photos.py` crea el visor `build/full-comics/chapter-photos/index.html` con todas las imágenes inglesas de los 124 capítulos de Regresión Absoluta, el original al lado de las salidas guardadas de Luma y las imágenes españolas de referencia. Usa el pintor de Windows con posiciones guardadas y presentación reconstruida; estas imágenes no son capturas nuevas del teléfono. Cada capítulo identifica la pasada y conserva las huellas de sus archivos. `tools/audit_chapter_translations.py` señala símbolos sospechosos y palabras conservadas para revisar; sus alertas no certifican el significado.

El avance visual por palabras está en `build/full-comics/word-review/index.html`. Registra las parejas de diálogo realmente inspeccionadas, sus transcripciones y los errores observados, separados del simple recorrido automático. La comparación de cada palabra inglesa de esos casos está en `visual-evaluation8011-context`. Las casillas del visor se conservan por versión en el navegador; no aprueban automáticamente el significado. La revisión completa de los 124 capítulos todavía está pendiente.

## Modelos y licencias

- [Helsinki-NLP/opus-mt-tc-big-en-es](https://huggingface.co/Helsinki-NLP/opus-mt-tc-big-en-es): CC BY 4.0, incluye tarjeta y licencia. Conversión ONNX de VaishalBusiness/opus fijada por revisión; pesos cuantizados a Int4 para este proyecto.
- [PaddleOCR / RapidOCR](https://github.com/RapidAI/RapidOCR): reconocedor latino PP-OCRv5 y detector DB PP-OCRv4, Apache 2.0.
- [ONNX Runtime](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html): runtime y avisos de terceros incluidos.
- [ML Kit](https://developers.google.com/ml-kit/language/translation) y [reglas de toques de Android](https://developer.android.com/about/versions/12/behavior-changes-all#untrusted-touch-events).

`assets/models/opus-en-es/manifest.json` fija procedencia y SHA-256. Las compilaciones Android y Windows verifican los archivos. Para un cambio intencional del glosario, ejecuta `python tools/check_model_assets.py --refresh` antes de compilar.

Consulta también [el análisis de la aplicación de referencia](docs/ez-screen-translator-analysis.md).
