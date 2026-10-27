# Herramientas y experimentos

Estas herramientas se ejecutan fuera de la aplicación. No son dependencias del
APK ni del ejecutable de Windows. La lógica de sesión en producción está en
`lib/`; el motor de inferencia está en `native/`.

## Puntos de entrada

| Objetivo | Herramientas |
|---|---|
| Verificar los modelos distribuidos | `check_model_assets.py` |
| Auditar cobertura del corpus | `audit_corpus_quality.py`, `verify_corpus_quality.py`, `test_corpus_quality.py` |
| Preparar y revisar comparaciones | `prepare_bilingual_quality.py`, `create_full_comic_review.py`, `review_comic_quality.py` |
| Pruebas del flujo Android | `run_android_quality.py`, `test_android_background_standalone.py` |
| Revisar espacio de snapshots | `optimize_quality_storage.py` (sin `--apply`, solo calcula) |
| Recursos de los procesos de evaluación | `quality_resources.py` |

## Familias experimentales

- `*801*`, `*802*`, `*8030*`: evaluaciones y mejoras de OCR, cobertura,
  disposición y recuperación. Sus conclusiones están en
  [el informe del corpus](../docs/full-comic-quality.md).
- `*8031*`, `*8032*`, `*8033*`, `*8034*`: adaptación LoRA de OPUS y controles
  de integridad y significado. [Resultados y límites](../docs/local-model-adaptation.md).

Las piezas del ensayo **8034**, todavía experimental, se
encuentran agrupadas lógicamente así:

| Etapa | Archivos |
|---|---|
| Preparación y validación de datos | `prepare_finetune8034.py`, `finetune8034_data.py` |
| Entrenamiento preregistrado | `train_opus_lora8034.py` |
| Evaluación y diagnóstico | `evaluate_opus_lora8034.py`, `audit_generation8034.py`, `diagnose_precision8034.py` |
| Controles y publicación del informe | `finetune8034_gates.py`, `test_finetune8034.py`, `publish_finetune8034.py` |

No es una secuencia para repetir sin preparación: los scripts consumen
protocolos congelados, checkpoints y decisiones revisadas. Publicar un informe
local no instala un candidato en la app.

La continuación se organiza como paquetes en `tools/experiments/`:

- `stability8035/`: evaluación de dos intensidades, selección y comparación de
  salidas. No entrena otros pesos.
- `onpolicy8036/`: entrenamiento con prefijos generados exclusivamente desde
  datos de entrenamiento, selección de punto, evaluación y publicación local.

Ambos quedaron descartados. Consulta
[sus resultados y límites](../docs/model-stability.md). Para comprobar la
integridad se ejecutan como módulos desde la raíz del proyecto; no hace falta
repetir el entrenamiento ni descargar otros modelos.

La continuación más reciente mantiene paquetes separados:

- `decoder8037/`: variantes de decodificación y protección del primer token.
- `qe8038/`: base nativa reproducida, conjunto fijo de candidatos y COMET local.
- `roundtrip8039/`: puntuación inversa con el inglés original como objetivo;
  evalúa alternativas sin entrenar con las respuestas de prueba.
- `temporal8040/`: veto morfológico general, controles, revisión y HTML independiente.

Los cuatro ensayos quedaron descartados para producción. Consulta
[resultados y reproducción](../docs/translation-selection.md). Los entornos
COMET y de morfología son exclusivamente de investigación; no forman parte
de la aplicación. Los scripts de publicación crean evidencia local y no
levantan un servidor.

## Rutas y reproducibilidad

Los scripts históricos permanecen en su ubicación original. Varios calculan la
raíz a partir de su ruta, importan helpers vecinos y verifican el SHA-256 del
script que produjo el experimento. Moverlos o introducir wrappers en su lugar
cambiaría esa evidencia. Este índice permite encontrarlos por responsabilidad
sin alterar experimentos terminados.

Para nuevos experimentos, mantener separados datos, entrenamiento, evaluación
y publicación, con un identificador propio. No reescribir herramientas de un
ensayo ya ejecutado para hacer pasar sus controles. Las nuevas herramientas
que no tengan restricciones históricas pueden usar subdirectorios por función;
sus rutas e imports deben quedar fijados antes de ejecutar el ensayo.

## Entornos y datos

Usar el intérprete que corresponda: las tareas de entrenamiento requieren el
entorno local con PyTorch, Transformers y PEFT; las de imágenes y ONNX emplean
el entorno de calidad. No se necesita reinstalarlos para organizar el código.

Los metadatos revisables están en `benchmarks/`; imágenes, informes generados,
entornos y checkpoints están en `build/`. No ejecutar una limpieza general de
`build/` para liberar cachés: también contiene evidencia de las evaluaciones.
