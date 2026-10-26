# Motor nativo

Este directorio contiene el motor C++ compartido por Windows y Android. La API
pública está en `local_translation.h`; la implementación de inferencia, OCR y
tokenización está en `local_translation.cpp`. El motor carga ONNX Runtime en
tiempo de ejecución. No depende de Flutter, JNI ni de clases de interfaz gráfica.
En Windows usa además las funciones de normalización Unicode del sistema.

| Grupo | Archivos / ubicación |
|---|---|
| API y ejecución | `local_translation.h`, `local_translation.cpp` |
| Recuperación de traducción | `translation_*.h` |
| Recuperación y selección de OCR | `ocr_*.h`, `short_dialogue*.h` |
| Fondo de la superposición | `overlay_background.h` |
| Conversión y evaluación por consola | `*_cli.cpp`, `*_plan.cpp` |
| Comprobaciones nativas | `coverage_test.cpp`, `background_test.cpp`, `coverage_candidate_test.cpp` |
| Biblioteca compartida entre consumidores | `cmake/translation_core.cmake` |
| Ejecutables de evaluación y CTest | `cmake/benchmark_targets.cmake` |
| Dependencias incluidas | `third_party/` |

`luma::translation_core` es una biblioteca estática, con código independiente de
posición para enlazar JNI. Publica la cabecera del motor y mantiene privadas las
cabeceras ONNX. `luma::json` es un target de interfaz separado. El ejecutable de
Windows y la biblioteca JNI se encargan de los detalles de cada plataforma.

Con CMake disponible en PATH, para compilar las utilidades por separado:

```powershell
cmake -S native -B build/architecture/native -DLUMA_BUILD_TOOLS=ON
cmake --build build/architecture/native --config Release --parallel 2
ctest --test-dir build/architecture/native -C Release --output-on-failure
```

Los nombres de los ejecutables históricos se conservan. Las fuentes y sus rutas
también se mantienen porque forman parte de los controles de procedencia de las
evaluaciones. Los pesos no se copian a este directorio: proceden de
`assets/models/opus-en-es/` y se verifican con el manifiesto existente.

Más contexto en [la arquitectura general](../docs/architecture.md).
