# Adaptación local de pesos: ensayos 8031–8033

Se adaptó el modelo preentrenado OPUS-MT mediante LoRA. Son actualizaciones
reales de 294.912 parámetros por adaptador, separadas de los pesos instalados.
Los tres ensayos terminaron; ninguno se incorpora a producción porque conserva
o añade errores de significado. El objetivo de menos del 5 % de fallos por uso
completo sigue sin acreditarse.

## Datos y separación

El archivo nuevo del usuario contiene 434 enlaces: 217 parejas bilingües.
La asignación determinista por capítulo reserva 136 para entrenamiento, 38
para validación y 43 para prueba. Se conservan 252 imágenes acotadas de siete
parejas, con un máximo de 18 páginas por idioma en cada selección. No son
siete capítulos completos revisados, ni 217 capítulos entrenados.

Se inspeccionaron visualmente 184 propuestas, se aceptaron 129 etiquetas y
se excluyeron 55. Las aceptadas se distribuyen así:

| Uso | Etiquetas originales | Papel |
| --- | ---: | --- |
| Entrenamiento | 86 | Cuatro selecciones de capítulos asignados a entrenamiento |
| Validación | 14 | Control conocido para seleccionar el método; sin gradientes |
| Primera prueba | 13 | Ya inspeccionada; no se vuelve a llamar prueba ciega |
| Segunda prueba | 16 | Referencias congeladas antes de generar con el segundo adaptador; control conocido para el tercero |

Quedan 41 capítulos asignados a prueba sin inspeccionar. El corpus histórico
anterior permanece exclusivamente como evaluación: sus fuentes y referencias
no se usan para entrenar, tampoco mediante regularización o destilación.

Las etiquetas fueron cotejadas por el asistente contra las imágenes inglesas
y españolas; no tienen certificación humana final. Las diferencias de
portadas, desplazamientos de páginas y agrupaciones OCR se verifican en cada
etiqueta aceptada. Las correcciones explícitas a traducciones publicadas
conservan modificadores, negaciones y relaciones del inglés. No se deduce
inglés ilegible a partir del español ni se usan salidas de otros traductores
como respuestas esperadas.

Los dos ensayos ampliados añaden 130 secuencias que concatenan dos o tres
diálogos de entrenamiento ya cotejados. Son ampliación de secuencia, no 130
parejas independientes nuevas ni conversaciones atribuidas al mismo
personaje. Se conserva el orden fuente/traducción, se excluyen cláusulas
inacabadas y se rechazan secuencias que exceden el presupuesto de tokens,
sin truncarlas silenciosamente.

## Entrenamiento y resultados

Base: `Helsinki-NLP/opus-mt-tc-big-en-es`, revisión
`8f4d4924189681076e9c642b2fd85278d793fd4d`. Se verificaron los hashes
publicados de los pesos originales y la identidad de todos los tensores
base antes y después de entrenar. No se entrenan los ONNX cuantizados de
producción. Se usa un entorno Python/CUDA separado y cada adaptador se
guarda en otro directorio.

| Ensayo | Datos de entrenamiento | Actualizaciones | Validación: errores confirmados | Control antiguo: correcciones / regresiones nuevas |
| --- | --- | ---: | --- | --- |
| 8031 | 35 diálogos | 40 | 5 → 5 | 5 / 2 |
| 8032 | 86 diálogos + 130 concatenaciones | 160 | 5 → 3 | 12 / 3 |
| 8033 | Los mismos datos, con penalización respecto al modelo base | 160 | 5 → 3 | 9 / 2 |

La validación contiene 14 diálogos y mantiene además tres casos de contexto
sin resolver. La reducción relativa del 40 % afecta solo a los cinco errores
confirmados iniciales de esa muestra pequeña. No estima el fallo de la app.

El primer ensayo no corrigió completamente ningún diálogo del lote reservado
y añadió una omisión. El segundo recuperó una traducción completa y parte de
otra en la nueva prueba de 16 diálogos, sin nuevas pérdidas de contenido;
la recuperación parcial aún tiene redacción defectuosa y no se aprueba como
corrección completa. Las salidas sin aprobar pasan de cuatro a tres y dos
casos permanecen pendientes de contexto. El tercero conserva esos resultados
en el mismo conjunto, que ya es conocido, sin abrir otra prueba ciega.

Las onomatopeyas, vacilaciones y sufijos de habla no inflan las correcciones
de contenido. Una afirmación, pregunta, acción o modificador significativo
omitido sí se registra. Se admiten paráfrasis que preservan significado y
se separan la incertidumbre de género, los defectos de redacción, los artefactos
y los errores de significado. Las referencias no se comparan solo por igualdad
literal de palabras.

El tercer ensayo optimiza entropía cruzada y `0,5 × KL(base || adaptado)`
únicamente sobre tokens no vacíos de los ejemplos de entrenamiento. La
distribución base se obtiene con el adaptador desactivado y sin gradientes.
Se desactiva también el dropout para hacer comparables ambas distribuciones;
por tanto, no es una comparación causal que aísle solo el efecto de KL.
La divergencia inicial es cero. No se cargan fuentes ni referencias de
evaluación para formar esa penalización.

En el control antiguo se ejecuta únicamente el núcleo flotante sobre 229
fuentes OCR conservadas de 124 vistas. No se repite la captura ni el OCR y no
se aplican el glosario, reparaciones ni recuperaciones de producción. Algunas
fuentes están cortadas: una corrección del fragmento capturado no aprueba
toda la vista. Se revisaron los 81 cambios del segundo adaptador; el tercero
cambia 59 salidas respecto a la base y 34 respecto al segundo. Se reutilizan
48 dictámenes por identidad exacta de fuente y traducción, y se revisan
expresamente las otras 11 salidas modificadas. Las reversiones a la base
también quedan registradas.

El segundo ensayo añade dos pérdidas parciales de significado, además de sus
tres regresiones; el tercero añade una, además de sus dos regresiones. Ambos
copian un artefacto de la fuente. La penalización evita una regresión, pero
pierde otras correcciones; no justifica instalar el candidato. Tampoco
entrena los pesos de reconocimiento OCR ni acredita que se hayan detectado
todas las palabras visibles.

## Comprobación y reproducción

Pasaron 15 guardas del primer piloto, 16 del segundo y 10 del tercero. Las
nuevas verifican separación de capítulos y fuentes, procedencia de etiquetas,
concatenación exacta, ausencia de referencias en las peticiones de generación,
gradientes solo de entrenamiento, matemática y máscara de KL, píxeles,
adaptadores finitos y realmente actualizados, hashes y recarga con traducciones
idénticas. Son comprobaciones de integridad; no certifican calidad semántica.

Los protocolos, datos y programas ejecutados quedan fijados por SHA-256. No
se deben editar retrospectivamente: cualquier ensayo nuevo requiere otra
versión. Las revisiones de significado están separadas de las salidas brutas.

- `benchmarks/finetune8031/pilot-review.json`: piloto inicial y prueba rechazada.
- `benchmarks/finetune8032/pilot-review.json`: datos ampliados y prueba reservada.
- `benchmarks/finetune8033/pilot-review.json`: ensayo con penalización y evidencia.
- `build/finetune8031/lora-pilot/adapter`: primer adaptador conservado.
- `build/finetune8032/lora-pilot/adapter`: segundo adaptador conservado.
- `build/finetune8033/lora-pilot/adapter`: tercer adaptador conservado.
- `build/full-comics/finetune803*-tests.log`: comprobaciones ejecutadas.

El informe local está en `http://127.0.0.1:8765/finetune8033/index.html`.
El control de la app instalada conserva 56 vistas sin aprobar sobre 124 y la
reducción histórica del 9,68 %. No se suman los tres conjuntos para fabricar
una tasa global. La revisión de todas las palabras de los capítulos y la
probabilidad de fallo por uso completo permanecen pendientes.

El siguiente paso es ampliar ejemplos reales cotejados y diversidad de
lenguaje, manteniendo reservadas las pruebas. Estos ensayos no justifican
seguir cambiando hiperparámetros sin ampliar datos ni reemplazar el modelo
instalado. No se genera otro APK ni se necesita el teléfono para este trabajo.
