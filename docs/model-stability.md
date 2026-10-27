# Estabilidad del traductor: continuación 8035–8036

Se completaron dos experimentos posteriores al 8034. Ninguno está aprobado
para exportarlo a la aplicación. Los pesos instalados siguen intactos y no
se ha acreditado menos del 5 % de fallos por traducción completa de pantalla.

## Qué se probó

**8035: intensidad del adaptador.** Se reutilizó el adaptador 8034 con factores
uniformes de 0,50 y 0,75, sin otro entrenamiento. Antes de generar se fijaron
las variantes y los criterios de selección. El factor 0,75 pasó los criterios
de los 25 diálogos de validación y quedó congelado antes de los controles.
No se cambiaron los parámetros de decodificación ni se añadieron sustituciones
de palabras, rutas por ID o respuestas de referencia al generador.

**8036: regularización con prefijos generados.** Se entrenó un nuevo adaptador
LoRA desde la misma base, con 294.912 parámetros actualizables. Se mantuvieron
los mismos 163 diálogos originales y las 254 concatenaciones del 8034.
Las concatenaciones no son 254 diálogos independientes nuevos.

La pérdida combina entropía cruzada sobre referencias de entrenamiento, KL
respecto a la base sobre esos prefijos y otro término KL sobre prefijos que
el estudiante genera por sí mismo. Solo se utilizan fuentes de entrenamiento
para estas generaciones; las fuentes y respuestas de evaluación quedan fuera
de los gradientes. La idea está inspirada en
[la destilación sobre generaciones propias](https://arxiv.org/abs/2306.13649),
pero este ensayo no reproduce GKD ni utiliza un profesor externo mayor.

Se fijaron de antemano 312 actualizaciones y puntos de control en 104, 208 y
312. Los tres adaptadores se conservan por separado. El entrenamiento tardó
229,7 segundos y el máximo registrado de memoria CUDA asignada fue de unos
1,64 GiB. Las pérdidas de entrenamiento no se presentan como tasas de fallo.

## Selección y resultados

Los 25 diálogos de validación ya eran conocidos: se usaron como desarrollo,
no como prueba independiente. Se revisaron todas las salidas de las variantes
y puntos de control. La reutilización de dictámenes exige identidad exacta
de fuente y traducción; las variantes nuevas se cotejaron por significado.
Las revisiones son del asistente y no tienen certificación humana final.

| Comparación con OPUS base | 8034 | 8035, factor 0,75 | 8036, paso 104 |
|---|---:|---:|---:|
| Errores confirmados en 14 diálogos conocidos; base: 5 | 2 | 3 | 3 |
| Correcciones completas en los 11 de validación nueva | 3 | 2 | 1 |
| Regresiones de contenido nuevas en esos 11 | 1 | 0 | 0 |
| Correcciones completas de regiones OCR, sobre 229 | 11 | 10 | 8 |
| Regresiones completas nuevas en ese control | 0 | 1 | 1 |
| Pérdidas parciales adicionales en ese control | 1 | 1 | 1 |
| Artefactos nuevos en ese control | 1 | 1 | 1 |
| Correcciones / regresiones nuevas en el control de 16 | 2 / 0 | 1 / 0 | 1 / 1 |
| Correcciones / regresiones nuevas en el control de 13 | 1 / 1 | 1 / 1 | 0 / 1 |

En la validación conocida permanecen tres casos de contexto. En la nueva,
el 8034 tiene además una incertidumbre de tiempo verbal que no aparece con
las variantes seleccionadas de 8035/8036. No se fabrica un porcentaje global
sumando conjuntos ni cambiando el denominador de los casos inciertos.

En el 8036, el paso 104 fue el único elegible según los criterios semánticos.
Los pasos 208 y 312 tuvieron cuatro errores conocidos en vez de tres y no
pasaron, aunque su chrF++ era mayor. El punto 104 se eligió antes de generar
los otros controles; no se cambió de punto tras ver sus resultados.

## Revisión completa de los cambios y descarte

El 8035 modificó 86 salidas en los controles: 69 dictámenes pudieron reutilizarse
por identidad exacta y se revisaron las otras 17. Conservó una salida formada
solo por signos e introdujo una omisión completa en una región OCR.

El 8036 seleccionado modificó 65 salidas: 55 dictámenes se reutilizaron y se
revisaron las otras 10. Conservó el fallo formado solo por signos, añadió una
pregunta omitida en el control limpio y empeoró una región OCR capturada.
Las otras 193 salidas de sus controles no se recalificaron por estar sin cambios.

Las recuperaciones parciales no se cuentan como correcciones completas. Las
onomatopeyas y vacilaciones tampoco inflan las mejoras de contenido.
Un error de OCR previo y una omisión introducida por el traductor se registran
por separado. La revisión de una región recortada no aprueba una pantalla.

Por estas razones ambos experimentos se descartan para producción. Reducir
la intensidad y añadir este término de regularización no bastaron para
resolver el problema. No se ocultaron los fallos con sustituciones de salida,
no se rebajaron los criterios y no se reentrenó con respuestas de evaluación.

## Alcance frente al objetivo del 5 %

Los controles repiten el núcleo flotante con texto conservado: 229 regiones
OCR procedentes de 124 vistas guardadas y 29 diálogos limpios conocidos.
No repiten captura, OCR, colocación o movimiento en Windows. No son una
revisión completa de las palabras de 124 capítulos ni una estimación de la
probabilidad de fallo de la aplicación. Los pesos OCR tampoco se entrenaron.

Quedan 41 capítulos de prueba reservados sin abrir. El control histórico de
la app instalada sigue con 56 vistas sin aprobar de 124; no ha disminuido
por estos experimentos. Un chrF++ mayor o menos errores en 14 diálogos no
demuestra el objetivo del 5 %.

El siguiente trabajo debe separar el comportamiento de la búsqueda del
decodificador de los cambios de pesos y ampliar la diversidad de lenguaje
revisado. Repetir variantes sobre los mismos pocos diálogos no ha mostrado
la mejora necesaria. Cualquier cambio posterior requiere su propio protocolo
y conservar los fallos anteriores como evaluación, sin convertirlos en
respuestas de entrenamiento.

## Evidencia y reproducción

- `benchmarks/stability8035/`: protocolo, selección, revisión y resultado.
- `benchmarks/onpolicy8036/`: protocolo, selección de punto, revisión y resultado.
- `build/stability8035/`: todas las salidas, paridad, pruebas y comparaciones HTML.
- `build/onpolicy8036/`: tres adaptadores, trazas de entrenamiento y generaciones,
  prueba de recarga exacta, todas las salidas y comparaciones HTML.

```powershell
.\build\training-venv8031\Scripts\python.exe -m unittest tools.experiments.stability8035.test_guards tools.experiments.onpolicy8036.test_losses tools.experiments.onpolicy8036.test_guards -v
```

Pasaron 18 comprobaciones de integridad y matemática. Los criterios de calidad
fallaron. Los programas de entrenamiento y generación, sus protocolos y
entradas están fijados por SHA-256; no se deben reescribir para reinterpretar
los resultados. No se descargaron otros modelos ni se construyó un APK.
