# Cierre nativo al preparar el modelo en Android ARM64

El registro del teléfono POCO 2412DPC0AG, Android 16/API 36, mostró un
`SIGSEGV` por acceso a un puntero nulo en `libonnxruntime.so` 1.23.2. El
decodificador fallaba al crear su sesión, antes de traducir. Al morir el proceso
nativo, Flutter perdía la conexión sin recibir una excepción de Dart.

## Causa y corrección

El decodificador combina dos ramas `If` que comparten inicializadores del grafo
principal. El empaquetado previo ARM64 de `MatMulNBits` necesita resolver las
escalas constantes dentro de la rama. Un modelo mínimo con condición dinámica
reproduce el cierre cuando sus escalas están en el grafo padre.

`tools/localize_decoder_scales.py` coloca 110 escalas dentro de sus ramas y
elimina las copias del padre que quedan sin uso. La preparación Int4 sigue
activada. El conversor `tools/compare_int4_model.py` aplica esta transformación
también al regenerar el modelo. El manifiesto registra el nuevo SHA-256.

La comparación del modelo anterior y el corregido verificó los bytes de los
410 argumentos constantes resueltos por ámbito y la identidad de operadores,
atributos, entradas y salidas. Cambia la ubicación de las constantes; sus
valores son idénticos. El decodificador ocupa 153.146.563 bytes.

Desactivar todo el empaquetado previo permitió cargar y traducir, pero produjo
una latencia excesiva. Esa configuración se usó únicamente para el diagnóstico.

## Reproducción aislada

Los modelos de `androidTest/assets/arm-int4-*.onnx` se regeneran con:

```powershell
python tools/create_arm_int4_probes.py
python tools/localize_decoder_scales.py assets/models/opus-en-es/decoder.onnx --check
python tools/check_model_assets.py
```

La prueba numérica usa entradas conocidas y exige que los 1024 resultados sean
64.0. El teléfono pasó los casos locales `level0`, `level4`,
`subgraph-local-scales` y `subgraph-level0`. El caso `subgraph` reproduce el
cierre con el runtime afectado; debe ejecutarse solo como diagnóstico aislado.

Para verificar el modelo real, se usa el APK de instrumentación separado:

```powershell
.\android\gradlew.bat -p android -PlumaBenchmark=true -PlumaTestBuildType=release -Ptarget-platform=android-arm64 -Psplit-per-abi=true :app:assembleRelease :app:assembleReleaseAndroidTest
# Instalar ambos APK con adb -s SERIAL install -r antes de ejecutar:
python tools/run_android_quality.py model --serial SERIAL --output-directory build/phone-crash/local-scales --import-fixtures
```

`lumaBenchmark=true` conserva las clases que necesita la instrumentación. La
versión distribuida se compila después con la optimización habitual de R8.
Las pruebas usan textos e imágenes de prueba, sin capturar contenido personal.

## Resultado en el teléfono (23 de octubre de 2026)

- 7 casos de tokenización y 29 casos de traducción procesados sin cierres.
- OCR local, geometría de párrafos, máscara de opacidad, preservación de
  fragmentos incompletos, cancelación y recuperación: correctos.
- Suite completa: 14.880 ms. Mediana por texto: 360 ms; máximo: 633 ms.
- APK final optimizado instalado como actualización, versión 1.0.0, código
  6003. El usuario confirmó traducción desde la barra y retirada del resultado
  al deslizar sobre la página local de prueba.
- Los toques por ADB estaban bloqueados por `INJECT_EVENTS`; la comprobación
  del gesto la realizó el usuario en el teléfono.
- Windows pasó la prueba nativa de OCR y traducción: `Hello world` →
  `Hola mundo`. Se verificaron los hashes de los modelos dentro del APK final
  y del paquete Windows.

Informes: `build/phone-crash/local-scales/android-model-summary.json`,
`android-translations.jsonl`, `build/phone-crash/decoder-equivalence.json` y
`build/phone-crash/windows-model-smoke.json`.

APK final: `build/app/outputs/flutter-apk/app-release.apk`.
SHA-256: `57181334e969e9fc392305616724ce18e7bcd8b02923eaaa4f878166ad74f087`.

Al terminar se detuvo la captura, se retiró el APK temporal de instrumentación
y se cerró el servidor local de pruebas. Luma quedó instalada y abierta.
