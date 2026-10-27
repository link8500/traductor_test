# Selección de traducciones: ensayos 8037–8040

El criterio inverso recupera contenido que otros selectores omiten, pero todavía
introduce empeoramientos parciales. **Ninguno de estos cuatro ensayos se incorpora
a producción.** El objetivo de menos del 5 % de fallos por pantalla sigue pendiente.

## Comparación con el motor que usa la app

En esta continuación se recuperó la salida del motor nativo **803001**, incluidas
sus recuperaciones y glosario. Se verificó el ejecutable congelado por SHA-256,
se reutilizaron sus 229 salidas conservadas y se repitió la traducción de otras
54 fuentes con ese mismo ejecutable. No hubo captura ni OCR nuevos.

Este punto cambia la interpretación de las cuentas anteriores: la base flotante
sin las recuperaciones nativas no equivale al traductor de producción. Sus cifras
históricas siguen conservadas, pero no se mezclan con la nueva comparación.
No cambió el modelo instalado al establecer esta base de comparación.

Se fijó un conjunto de tres alternativas por fuente: salida nativa, OPUS flotante
sin adaptar y adaptador completo 8034. Los selectores solo pueden elegir una de
esas cadenas. No escriben frases nuevas ni reciben la referencia española, el
dictamen de revisión o reglas que identifiquen capítulos.

Antes de puntuar los candidatos se revisaron las 25 salidas nativas de validación
y las 258 de control. En los controles se reutilizaron 97 dictámenes por identidad
exacta de fuente y salida y se revisaron los otros 161 registros. Es una revisión
del asistente frente al inglés capturado, pendiente de certificación humana final.
Las fuentes con OCR ilegible siguen separadas de los errores de traducción.

## Qué se probó y qué se descartó

| Ensayo | Método | Resultado y decisión |
|---|---|---|
| 8037 | Búsqueda de decodificación con parada canónica y protección del primer token léxico | Se revisaron 100 salidas de cuatro variantes sobre 25 fuentes. Aparecieron contenido añadido y bucles después de comenzar la frase. Rechazado antes de controles. |
| 8038 | Evaluador de calidad COMET sin referencia, con márgenes fijados de 0 y 0,02 unidades | Ambos recuperaron 2 diálogos de validación y empeoraron 2. El margen no representa un porcentaje. Rechazados antes de controles. |
| 8039 | Verosimilitud inversa; variante adicional que exige acuerdo con COMET | El criterio inverso recuperó 7 diálogos, pero introdujo una duda temporal; el acuerdo con COMET solo recuperó 3 y conservó esa duda. Ambos fallaron el criterio previo de cero dudas nuevas. |
| 8040 | Criterio inverso con veto morfológico si se pierde una categoría temporal de la salida nativa | Conservó las 7 correcciones sin dudas nuevas en validación. Pasó a controles y allí aparecieron 2 empeoramientos parciales y 2 dudas nuevas. Rechazado para producción. |

8039 y 8040 emplean **OPUS español→inglés** para medir cuánto respalda cada
traducción española el inglés original. Se calcula la media del logaritmo de
probabilidad de los mismos tokens ingleses para todas las alternativas, incluido
EOS y excluido el relleno. No se generan traducciones inversas libres ni se entrena
con las respuestas de evaluación. **La puntuación no es la probabilidad de que
una traducción sea correcta.**

8040 utiliza un analizador español preentrenado para conservar las categorías
pasado, presente, futuro y condicional que identifica en la salida nativa. Reconoce
el perfecto compuesto con «haber». Es un veto conservador por oración, sin alinear
cláusulas ni certificar significado. Puede bloquear paráfrasis válidas y no detecta
todos los cambios de sentido. Se diseñó después de observar la validación de 8039;
por tanto, esa validación es desarrollo conocido, no una prueba independiente.
Los criterios de aceptación de los controles quedaron fijados antes de puntuarlos.

## Resultados de 8040

| Recuento de significado capturado | Validación conocida, 25 | Controles, 258 |
|---|---:|---:|
| Errores confirmados del motor nativo | 10 | 39 |
| Errores confirmados tras seleccionar | 3 | 28 |
| Correcciones completas | 7 | 10 |
| Regresiones completas nuevas | 0 | 0 |
| Empeoramientos parciales adicionales | 0 | 2 |
| Incertidumbres nuevas | 0 | 2 |
| Entradas inciertas o con fuente no fiable, antes → después | 4 → 4 | 24 → 24 |
| Traducciones modificadas | 12 | 64 |

La caída de 39 a 28 errores confirmados **no significa 11 correcciones completas**:
una salida pasa de error confirmado a incierta, con una pérdida parcial nueva.
Las diez correcciones completas se cuentan por separado. Tampoco se suman las
dos columnas para fabricar una tasa global ni se incluyen onomatopeyas como
correcciones de contenido.

Se revisaron las 64 salidas de control modificadas: 53 dictámenes se reutilizaron
por identidad exacta y 11 requirieron revisión nueva. Las otras 194 conservan
exactamente el texto nativo ya revisado. La comparación relativa también detectó
pérdidas parciales en salidas que ya tenían errores; no se ocultaron por conservar
la misma categoría general de fallo.

La primera cuenta normalizaba el estado antiguo `unreadable_source` solo después
de seleccionar y atribuía una duda nueva a una salida intacta. Se conservaron
los archivos originales y se añadió una enmienda explícita en
`control-meaning-review-v2.json` y `result-v2.json`. No cambió ningún dictamen
semántico, traducción o decisión de selección.

## Modelos, licencias y espacio

Se descargaron modelos **ya entrenados**, con revisiones y hashes fijados:

| Componente de investigación | Procedencia | Licencia | Peso aproximado |
|---|---|---|---:|
| Evaluador de calidad | [Unbabel/wmt20-comet-qe-da](https://huggingface.co/Unbabel/wmt20-comet-qe-da) | Apache-2.0 | 2,28 GB de checkpoint |
| Traducción inversa | [Helsinki-NLP/opus-mt-es-en](https://huggingface.co/Helsinki-NLP/opus-mt-es-en) | Apache-2.0 | 312 MB de pesos |
| Morfología española | [es_core_news_sm 3.8.0](https://github.com/explosion/spacy-models/releases/tag/es_core_news_sm-3.8.0) | GNU GPL 3.0 | 12,9 MB de rueda comprimida |

El analizador GPL se usa exclusivamente en el entorno de investigación; no se
incluyó en la aplicación ni se sustituyó la licencia del proyecto. Tampoco se
incluyó COMET, cuyo tamaño y resultado no justifican usarlo como selector único.

COMET se contrastó con su cargador oficial: solo se retiró un búfer posicional
obsoleto tras verificar sus valores, con carga estricta de los parámetros
aprendidos. Hubo igualdad exacta de puntuaciones en la comprobación sintética.
No se modificó el checkpoint ni se descargó otra copia de su codificador completo.

Los entornos nuevos comparten las bibliotecas grandes de entrenamiento sin
modificar ese entorno. Los archivos de esta continuación ocupan aproximadamente
2,88 GiB, incluidos modelos, entornos y resultados; quedan unos 11,83 GiB libres
en la instantánea final. No se borraron datos personales, modelos anteriores,
historial Git ni resultados fallidos. No se generó APK.

## Evidencia y continuación

- Protocolos, hashes, decisiones y resultados: `benchmarks/decoder8037/`,
  `benchmarks/qe8038/`, `benchmarks/roundtrip8039/`, `benchmarks/temporal8040/`.
- Código separado por responsabilidad: `tools/experiments/` con esas mismas familias.
- Comparación completa, con búsqueda y filtro de cambios: `build/temporal8040/index.html`.
  Es un HTML independiente, sin servidor ni peticiones externas.
- Resumen local vigente: `build/full-comics/continuation8040.json`.

Los 41 capítulos reservados permanecen sin abrir. Estos 283 textos no son 283
pantallas independientes ni equivalen a revisar cada palabra de 124 capítulos.
El último control de la aplicación conserva **56 de 124 vistas sin aprobar** y
su reducción histórica del 9,68 %; esta continuación no actualiza esa tasa.

La señal útil para continuar es la recuperación de contenido con el criterio
inverso. Antes de plantear su integración se necesita contrastar alineación de
cláusulas y cambios de participantes sobre un bloque de desarrollo más amplio,
sin añadir sustituciones particulares de los relatos. Después deberán pasar
los controles congelados y una evaluación independiente del flujo completo.
