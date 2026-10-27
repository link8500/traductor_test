# Adaptación local de pesos: ensayos 8031–8034

Se adaptó el modelo preentrenado OPUS-MT mediante LoRA. Son actualizaciones
reales de 294.912 parámetros por adaptador, separadas de los pesos instalados.
Los cuatro ensayos terminaron; ninguno se incorpora a producción porque conserva
o añade errores de significado. El objetivo de menos del 5 % de fallos por uso
completo sigue sin acreditarse.

La continuación posterior conserva estos resultados históricos y estudia
intensidad del adaptador y estabilidad durante generación:
[ensayos 8035–8036](model-stability.md). Tampoco se aprobaron para producción.

## Datos y separación

El archivo nuevo del usuario contiene 434 enlaces: 217 parejas bilingües.
La asignación determinista por capítulo reserva 136 para entrenamiento, 38
para validación y 43 para prueba. Se conservan 419 imágenes acotadas de doce
parejas, con un máximo de 18 páginas por idioma en cada selección. No son
doce capítulos completos revisados, ni 217 capítulos entrenados.

Se inspeccionaron visualmente 295 propuestas, se aceptaron 217 etiquetas y
se excluyeron 78. Las 217 etiquetas no equivalen a 217 capítulos. Se
distribuyen así:

| Uso | Etiquetas originales | Papel |
| --- | ---: | --- |
| Entrenamiento | 163 | Ocho selecciones de capítulos asignados a entrenamiento |
| Validación | 25 | 14 conocidas y 11 nuevas de otra selección reservada; sin gradientes |
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

Los ensayos 8032 y 8033 añaden 130 secuencias que concatenan dos o tres
diálogos de entrenamiento ya cotejados. Son ampliación de secuencia, no 130
parejas independientes nuevas ni conversaciones atribuidas al mismo
personaje. Se conserva el orden fuente/traducción, se excluyen cláusulas
inacabadas y se rechazan secuencias que exceden el presupuesto de tokens,
sin truncarlas silenciosamente.

El cuarto amplía el mismo método a 163 diálogos y 254 concatenaciones.
Los 77 diálogos nuevos de entrenamiento y las 11 referencias nuevas de
validación se cotejaron antes de entrenar o generar traducciones candidatas.
No se consultaron salidas de modelos para escribir las etiquetas. Las
actualizaciones se fijaron mediante una regla de exposición proporcional,
sin una búsqueda de hiperparámetros: 312 pasos para 417 ejemplos que incluyen
las concatenaciones. Los 417 no son diálogos originales independientes.

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
| 8034 | 163 diálogos + 254 concatenaciones, mismo método regularizado | 312 | 5 → 2 | 11 / 0 |

La validación fija contiene 14 diálogos y mantiene además tres casos de contexto
sin resolver. La reducción relativa actual del 60 % frente a la base y del
33,3 % frente al candidato anterior se refiere únicamente a ese conjunto
pequeño. No estima el fallo de la app. El cero de la última columna del cuarto
ensayo se limita a regresiones completas confirmadas de regiones capturadas;
no elimina las pérdidas parciales, artefactos ni errores de otros conjuntos.

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

El cuarto ensayo mantiene ese método y no entrena con los errores de los
controles. En sus 11 diálogos de validación nueva recupera tres unidades de
contenido, pero introduce una regresión confirmada y un cambio de tiempo
verbal que requiere contexto. Los dictámenes de la base se registraron antes
de revisar la salida candidata. El 8034 no supera el criterio previamente
fijado de cero regresiones nuevas en ese conjunto.

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

El cuarto cambia 79 regiones del control; se cotejaron sus 44 variantes nuevas
y se reutilizaron 35 dictámenes por identidad exacta de fuente y salida.
Conserva una pérdida parcial adicional de significado y un artefacto copiado.
Dos cambios de relación quedan pendientes de contexto. No se recalifica el
significado de las otras 150 salidas ni se aprueban por estar sin cambios.

En la prueba conocida de 16 diálogos recupera dos traducciones completas y
otra parcialmente, con una nueva duda de contexto y un artefacto de sufijo.
En la primera prueba conocida de 13 diálogos corrige una omisión, pero genera
una salida formada solo por signos y pierde contenido adicional dentro de
otro diálogo ya fallido. El fallo se reproduce usando el mismo lote con
bfloat16 y float32; el diagnóstico no reemplaza los resultados oficiales ni
identifica por sí solo toda la causa. No basta cambiar la precisión.

La auditoría de formato recorrió 566 salidas de base y candidato y marcó un
caso. Son 283 entradas con dos salidas cada una, no 566 muestras independientes
ni una revisión semántica automática. La ausencia de alertas no aprueba una
traducción. Las mejoras del 8034 no justifican instalarlo y no se abre otro
capítulo de prueba ciega.

## Comprobación y reproducción

Pasaron 15 guardas del primer piloto, 16 del segundo, 10 del tercero y 18 del
cuarto. Son comprobaciones de integridad; los criterios de calidad del cuarto
modelo no se superaron. Las
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
- `benchmarks/finetune8034/pilot-review.json`: ampliación, nueva validación y fallos conservados.
- `build/finetune8031/lora-pilot/adapter`: primer adaptador conservado.
- `build/finetune8032/lora-pilot/adapter`: segundo adaptador conservado.
- `build/finetune8033/lora-pilot/adapter`: tercer adaptador conservado.
- `build/finetune8034/lora-pilot/adapter`: cuarto adaptador conservado.
- `build/full-comics/finetune803*-tests.log`: comprobaciones ejecutadas.

El informe local actual está en `http://127.0.0.1:8765/finetune8034/index.html`,
con todas las comparaciones de validación, los controles conocidos y las
propuestas fotográficas. Incluye las salidas fallidas, no solo las mejoras.
El control de la app instalada conserva 56 vistas sin aprobar sobre 124 y la
reducción histórica del 9,68 %. No se suman los tres conjuntos para fabricar
una tasa global. La revisión de todas las palabras de los capítulos y la
probabilidad de fallo por uso completo permanecen pendientes.

El siguiente paso es estudiar la estabilidad autoregresiva al seleccionar
candidatos y seguir ampliando ejemplos reales y diversidad de lenguaje,
manteniendo reservadas las pruebas. Las pérdidas sobre tokens correctos
durante el entrenamiento no garantizan que la generación libre sea estable.
No se reutiliza el fallo observado como respuesta de entrenamiento ni se
rebaja el criterio para incorporarlo. No se genera otro APK ni se necesita
el teléfono para este trabajo.

Ese estudio continuó en los ensayos 8035–8040. La intensidad del adaptador y
otro entrenamiento no superaron los controles. La selección inversa de
traducciones recuperó contenido adicional, pero mantuvo empeoramientos parciales.
Consulta [estabilidad](model-stability.md) y
[selección de traducciones](translation-selection.md) para las comparaciones
con la base flotante y, después, con el motor nativo real. Ningún candidato
reemplazó al motor instalado.
