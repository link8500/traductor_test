# Evaluación ampliada de cómics

Trabajo en curso, iniciado el 23 de octubre de 2026. No se ha establecido
una precisión semántica ni se ha terminado la revisión visual de cada palabra.

## Material y cobertura

El inventario reúne 154 parejas de capítulos: Regresión Absoluta / Geom
Mugeuk 1–124 y The Greatest Estate Developer / Loco Frontera 1–30.
`benchmarks/full-comics/sources.json` conserva los 308 enlaces y la procedencia
de los archivos de entrada, incluidos los 94 capítulos añadidos en `texo.text`.

Se descargaron y verificaron 2.250 imágenes inglesas y 5.468 españolas.
Los manifiestos `build/full-comics/images-en.json` e `images-es.json`
registran sus dimensiones y SHA-256. El material incluye créditos, promoción
y marcas; contar esas imágenes o sus palabras no mide la cobertura de diálogo.
Las imágenes del corpus no se empaquetan en la aplicación.

`tools/run_full_comics.py` recorre cada imagen en ventanas de 2.000 píxeles,
con pasos de 1.300, usando OCR y traducción nativos de Windows. Conserva
progreso por imagen y capítulo. Los archivos `.done.json` distinguen el
recorrido de archivos de la revisión de palabras y significado. Un recorrido
terminado tampoco garantiza que el OCR haya descubierto todo el texto.

El recorrido inglés ya terminó: 154/154 capítulos, 2.250 archivos y 23.008
regiones, sin errores de ejecución. La repetición de la preparación final
también terminó: 5.902 inferencias nuevas y 17.106 reutilizaciones con entrada,
decodificador y pesos idénticos. La referencia española continúa por separado;
estos totales no son un porcentaje de precisión ni una aprobación visual.

## Cambios y pruebas concretas

Se añadió el detector DB móvil PP-OCRv4 para proponer líneas que el OCR del
sistema no encuentra. Se reutiliza un modelo previamente entrenado de
[PaddleOCR / RapidOCR](https://github.com/RapidAI/RapidOCR), con licencia
Apache 2.0 y hash fijado en el manifiesto. El reconocedor lee las propuestas
rectificadas y rechaza las que no alcanzan la confianza exigida. No se
entrenaron pesos nuevos ni se enviaron textos a un proveedor externo.

En Windows también se corrigieron las coordenadas cuando el resultado de OCR
informa una inclinación: las cajas de palabras se devuelven al espacio de la
captura antes de releer y colocar la traducción. La transformación sigue el
[ejemplo oficial de Microsoft](https://github.com/Microsoft/Windows-universal-samples/blob/main/Samples/OCR/cs/OcrFileImage.xaml.cs).

En los mismos píxeles de dos ventanas reales, el OCR anterior omitió
`FOR REVENGE`, `DEMON` y `SKIRMISH`; las tres se recuperan con el detector
añadido. Los registros están en `build/full-comics/styled-ab/`. La preparación
de etiquetas cortas en mayúsculas también se corrigió: las traducciones reales
guardadas pasan de «PARA INGRESOS» a «Por venganza» y de «HABILIDADES» a
«Escaramuza». Se protegen identificadores y siglas comunes. Los pesos del
traductor no cambiaron.

Nueve controles independientes de color, fondo e inclinación pasan por el
detector/reconocedor compartido. El OCR anterior ya leía esos controles;
demuestran funcionamiento y geometría, no una ganancia de cobertura sobre
cómics completos. Los 27 casos de preparación/protección también pasan.

## Comparación con Olympus

La referencia española se lee con OCR latino, separado del lector inglés de
la aplicación. Sus resultados necesitan revisión: no se consideran una
transcripción humana correcta. La alineación automática usa el dibujo para
proponer escenas equivalentes entre ediciones con cortes distintos.

`tools/compare_full_comics.py` genera un registro por token español leído,
con su caja, página, propuesta inglesa, traducción y estado. La ausencia de
una región cercana es un candidato a omisión; una redacción diferente puede
ser correcta y una coincidencia literal puede ser incorrecta. Las marcas y
promociones siguen en el registro aunque el visor permita ocultarlas.

El visor local está en `build/full-comics/review/index.html`. Incluye todas
las páginas y recortes de contexto. Ninguna palabra se marca automáticamente
como revisada o aprobada. La vista del capítulo 31 se verificó en el navegador:
el candidato «SNIF…» muestra el original inglés y el globo español correcto,
con su revisión manual pendiente.

Persisten errores reales. En ese globo, el detector localiza la palabra
inglesa «Sniff…», pero el lector obtiene «Smil» con confianza aproximada de
0,57 y la rechaza. No se sustituyó por una respuesta memorizada del capítulo.
Se probaron variantes de recorte y otro reconocedor; no dieron una lectura
fiable. Este caso impide afirmar que se reconoce toda letra decorativa.

## Procedencia de las ejecuciones

El recorrido largo usa un ejecutable congelado de Windows con el detector y
la geometría corregida. Su motor es
`2301a5d3f124a0b455a618aa58d1df56ea4028f77e48dff8a4d0f812b03b5780`.
`build/full-comics/windows-engine6005.json` fija el hash del ejecutable y del
manifiesto para reanudar sin mezclar motores.

La corrección posterior de mayúsculas se repite sobre el OCR guardado en
`translated-en-final`. Se reutiliza una inferencia solamente si la preparación
es idéntica y el código del decodificador y los pesos son los mismos. Los
cambios de preparación requieren una inferencia nueva. Esto no constituye
otro recorrido de captura/OCR. El comparador da preferencia a estos informes
finales y registra qué directorio utilizó.

La ejecución de Android se trasladó al emulador Pixel 6a x86_64 a petición
del usuario. Los resultados previos del POCO corresponden a otra compilación
y se conservan por separado. Los detalles de la comprobación del emulador
están en los registros `build/full-comics/emulator8003-*.log`.

En la compilación final 8003 pasaron 9 casos de preparación/protección,
29 textos, 9 controles de color/inclinación, supresión de duplicados, imagen
vacía, cancelación y recuperación. También pasó la captura real con letras
rojas: un reintento que reduce únicamente el margen vertical conserva el
ancho de la palabra y exige acuerdo con la primera lectura y confianza
superior a 0,90. No se redujo el umbral general de aceptación. La prueba
final tardó 57.197 ms con Wi-Fi y datos desactivados, sin red predeterminada.

La prueba manual de MediaProjection sobre el lector de prueba mostró cinco
regiones traducidas, incluidas «POR VENGANZA» y «DEMONIO». El segundo ya cabe
como palabra completa. El anillo aparece durante el trabajo y desaparece al
terminar. Al deslizar se retiraron los resultados, se conservaron los textos
ingleses y el proceso de Luma siguió vivo. El título que rozaba la barra fue
excluido por la protección contra capturar sus propios controles; este ensayo
no certifica que todo texto de la pantalla se traduzca. También quedó visible
un pequeño resto del original al borde de una región. Las máscaras sobre
dibujos detallados todavía necesitan mejora estética.

El APK del emulador está en
`build/app/outputs/flutter-apk/app-emulator-x86_64-release.apk`; el universal,
compatible también con ARM, en `app-release.apk` de esa misma carpeta. Se
verificaron sus modelos/licencias y que comparten el mismo DEX y las mismas
bibliotecas ejecutadas en x86_64. El empaquetado ahora alinea las bibliotecas
nativas con las arquitecturas solicitadas a Flutter; el verificador rechaza
un APK que anuncie una arquitectura sin su motor Flutter.

El POCO 2412DPC0AG se volvió a conectar y se actualizó a 8003 conservando los
datos. La misma suite pasó en ARM64 en 19.285 ms, incluida la captura roja
guardada. En una prueba de MediaProjection sobre el lector local se dibujaron
seis regiones traducidas y una conservada. Se verificaron los toques por USB,
el anillo durante el trabajo, el estado de reposo y la retirada al deslizar,
manteniendo el mismo proceso de Luma. El teléfono conservó su configuración
de red. Registro: `build/full-comics/poco8003-final.json`.

La prueba física confirmó problemas de presentación que la suite del motor
no detecta: partes de la I inicial y la D decorativa quedan fuera de la caja,
y algunos trazos originales siguen visibles a través del fondo. No se
considera solucionada la sustitución visual de todas las letras. El usuario
desconectó después el teléfono y pidió continuar autónomamente con el
emulador, sin esperar respuestas mientras está ausente. El APK auxiliar podría
seguir instalado en el teléfono; no se intentará limpiarlo mientras está
desconectado.

Se reprodujo otra causa de desaparición en el emulador 8003: tocar un margen
inerte retira los cuatro textos sin desplazar la página. Arrastrar la barra sí
los conserva y deslizar la página los retira, manteniendo el mismo proceso.
Secuencia: `build/full-comics/motion8003-baseline/report.json`. La corrección
8004 elimina la retirada por pulsación fuera de la barra y excluye del detector
de movimiento el tamaño real de la máscara difuminada. Su validación final
pasó sin conexión en `motion8004-final/report.json`: cuatro regiones, toque
inerte y arrastre conservados, desplazamiento que retira la traducción y mismo
proceso en toda la secuencia. No incluye los dos rótulos tapados por la barra.
En una segunda página, la traducción solo se inició al pulsar otra vez: se
comprobaron visualmente «DEMONIO», «ESCARAMUZA» y «LA BATALLA HA TERMINADO».
Persisten restos de trazos originales y máscaras demasiado planas sobre los
dibujos; no se considera terminada la edición visual.
En Windows también se pausa la vigilancia durante
el arrastre y se renueva la referencia al soltar la barra.

En 8004 pasaron el análisis de Flutter, sus ocho pruebas, cinco pruebas Android
de movimiento y las suites nativas de Windows. El modelo optimizado del
emulador pasó 29 textos, nueve casos de preparación, nueve controles de
color/inclinación, duplicados, imagen vacía, cancelación y recuperación en
44.523 ms, con Wi-Fi y datos apagados. El teléfono continúa desconectado y no
recibió esta actualización. Se verificaron los modelos de ambos APK y Windows;
el ZIP completo está en `build/releases/Luma-Windows-1.0.0+8004.zip`.

El primer intento con el emulador limitado a 2 GB terminó por `LOW_MEMORY`,
confirmado tanto por `ApplicationExitInfo` como por `lowmemorykiller`; no fue
una excepción capturada por Flutter. Se reanudó con 3 GB, limitando las otras
pruebas concurrentes. Se conserva el registro en `emulator-motion-logcat.txt`.
Una prueba de inclinación/cizalla adicional sobre «Sniff» tampoco obtuvo la
palabra completa de forma fiable. Algunas transformaciones produjeron «Sni»
con confianza alta, lo que demuestra que aumentar la confianza por sí solo
no demuestra una lectura correcta. No se incorporó ese reintento al producto.

La inspección del capítulo 1 encontró otro error: el inglés visible «YES.»
se lee como «Yes.» pero el modelo produce «En serio.»; la referencia muestra
«SÍ.». Además, el OCR automático de la referencia no detectó ese globo, por
lo que su ausencia no aparecía en el registro por tokens. Se conservó el
recorte emparejado en `build/full-comics/yes-en-es.png` y se añadió el caso
comprobado al inventario de revisión. Los dos casos puntuales aparecen en
el visor, separados de sus propuestas automáticas. No se añadió una respuesta
memorizada del capítulo ni se marcó una revisión completa.

La revisión completa requiere comprobar las lecturas españolas, las
correspondencias de escenas y el significado de cada segmento. La
comparación automática y el recorrido completo son pasos de esa revisión,
no una certificación de traducción perfecta.

## Validación 8006 y discrepancia encontrada en el POCO

El recorrido de las referencias españolas terminó: 154/154 capítulos, 5.468
archivos y 41.530 regiones, sin errores de ejecución. La comparación de la
línea base contiene 171.947 tokens leídos por OCR. Es una referencia automática;
también puede omitir letras, como ocurrió con el globo «SÍ.». No equivale a una
transcripción humana ni a revisar visualmente cada palabra.

El candidato con PP-OCRv5 como único lector mejoró varias líneas manuscritas,
pero falló el control rojo «FOR REVENGE», que leyó como «FOR REVENUE». No se
aceptó ese candidato. La compilación 8006 conserva PP-OCRv5 y consulta además
el lector inglés PP-OCRv4 ante lecturas inciertas. Los pesos de traducción no
cambiaron. La suite optimizada pasó en x86_64 (52.147 ms) y ARM64 en el POCO
(22.089 ms): 29 textos, nueve casos de preparación, nueve casos de color y
rotación, tres recortes reales, duplicados, imagen vacía, cancelación y
recuperación. Solo la ejecución del emulador desactivó la red.

La primera ejecución etiquetada `motion8006-handwriting` conservó por error
la página de colores de una actividad Android ya abierta. Sus capturas no
validan los párrafos manuscritos. Se corrigió el arnés para reiniciar el lector
auxiliar antes de cargar cada URL. La ejecución repetida y comprobada está en
`motion8006-handwriting-fresh/report.json`: tres párrafos visibles, toque
inerte y arrastre conservados, y retirada al deslizar, con el mismo proceso.

La prueba física `poco8006-handwriting/report.json` también pasó los gestos
y mantuvo vivo el proceso 19646. Sin embargo, la inspección de su imagen
traducida encontró «YOL» y «YOUNG» en un párrafo español. Esta prueba confirma
estabilidad y gestos, pero **no** una traducción correcta del párrafo. El
diagnóstico `poco8006-line-selection.log` mostró que ML Kit leía «MET YOu,
WE WERE» y «BOTH YOUNG.», mientras el recorte del reconocedor local producía
«MET YOL, WE WERE» y «BOTH YOLNG.» con confianza superior a 0,95. Comparar
directamente las confianzas de esos motores hizo que prevaleciera la lectura
incorrecta. El lector inglés independiente coincidía con ML Kit en «YOU».

La corrección 8007 consulta ese lector cuando hay una discrepancia pequeña y
exige acuerdo con el OCR del sistema. Conserva la confianza real de la lectura
elegida; no la eleva artificialmente. Los párrafos confirmados no vuelven a ser
sustituidos por un reintento de otro motor basado únicamente en su confianza.
La comprobación nativa de los diez renglones de esa misma captura recuperó las
tres frases completas. La validación de la aplicación instalada y de su
canalización completa se registra aparte; una prueba aislada del detector ya
no basta para certificar estos renglones.

La compilación 8007 ya pasó la prueba de la canalización completa sobre la
misma captura física, tanto en ARM64 como en el emulador x86_64. Se verifican
las tres frases completas, incluido «MET YOU, WE WERE BOTH YOUNG», usando el
objeto de reconocimiento que utiliza el servicio de la aplicación. No se
sustituye esta comprobación por llamadas aisladas al detector. Los registros
son `poco8007-pipeline.log` y `emulator8007-pipeline.log`.

En la captura real `poco8007-handwriting/translated.png`, el segundo párrafo
ya muestra «Ahora que lo pienso, cuando te conocí por primera vez, ambos
éramos jóvenes». El usuario confirmó también el resultado visible. Los
gestos de esa secuencia conservaron los tres párrafos al tocar un margen y
mover la barra, y los retiraron al desplazar la página, sin reiniciar el
proceso. Las suites optimizadas pasaron en 23.943 ms en ARM64 y 19.046 ms en
x86_64. Pasaron las cinco pruebas JVM de movimiento y las comprobaciones
nativas Windows; cinco imágenes reales produjeron doce regiones sin errores
de ejecución. Ambos APK contienen los mismos DEX y bibliotecas x86_64, y se
verificaron sus modelos y los de Windows.

En una repetición física de la página de colores, mover la barra retiró la
traducción sin desplazar la página; la causa no está aislada. En el emulador,
la repetición aislada con los párrafos conservó los resultados durante tres
arrastres consecutivos y los retiró solo al desplazar. No se modificó el
detector de movimiento a partir de esa observación no reproducida. La página
física de colores también muestra que una palabra decorativa cortada por la
barra de navegación puede recibir una lectura incorrecta: «DEMON» llegó a
traducirse como «HOMBRE». Las máscaras siguen dejando trazos originales
fuera de ciertas cajas. Estos casos permanecen abiertos; no se certifican
todos los colores, todas las formas ni todos los segmentos de los capítulos.

El recorrido inglés 8006 se detuvo tras 16 capítulos al encontrar la
discrepancia de lectura física. Sus informes se conservan. La nueva ejecución
usa una copia completa e inmutable del motor 8007 y otra carpeta de informes,
para que sus resultados no se mezclen con la línea base ni con ese candidato.

La página de colores del emulador también conservó cuatro resultados durante
tres arrastres, y la segunda traducción solo se inició al volver a pulsar el
icono. Con «DEMON» visible completo se comprobó «DEMONIO»; «THE BATTLE IS OVER»
se mostró como «LA BATALLA HA TERMINADO». «SKIRMISH» quedó sin traducir en esa
escala. El diagnóstico obtuvo «SKURMISH» (0,769) con el lector combinado y
«SKIRMIBH» (0,848) con el inglés anterior, ambos por debajo del umbral de
aceptación del detector. No se redujo ese umbral para forzar una lectura.
Se conservan estas capturas y `skirmish8007-*.json` como casos abiertos.

El paquete Windows 8007 está en
`build/releases/Luma-Windows-1.0.0+8007.zip`. El APK universal 8007 permanece
en `build/app/outputs/flutter-apk/app-release.apk` y está instalado en el POCO.
El informe de artefactos, código, validaciones y límites conocidos es
`build/full-comics/release8007.json`. El recorrido nuevo produce
`ocr-en8007`, `translated-en8007`, `comparison8007` y el visor `review8007`;
su finalización automática no implica revisión humana de todas las palabras.

## Captura limpia e imágenes completas de revisión · 8008–8010

La barra y la capa traducida se ocultan antes de adquirir la captura. Se
restaura la animación de trabajo en cuanto llega esa imagen. Se retiró el
descarte del texto situado detrás de la barra; al terminar, esta busca un
espacio libre entre todas las regiones reconocidas. Los textos cortados por
los bordes útiles de la pantalla se conservan. Las pruebas nativas Windows
recuperaron un texto realmente tapado por la barra y comprobaron que esta
vuelve a mostrarse y evita las regiones. Pasaron diez pruebas JVM de
movimiento y colocación.

En el POCO se probaron vistas reales de los capítulos 1, 31 y 124, además
de la plantilla controlada. Se conservaron capturas del original, el trabajo,
la traducción y los gestos. Cada secuencia cubre una vista y su desplazamiento;
no representa una revisión completa de ese capítulo. Sus informes están en
`poco8008-chapter-1`, `poco8008-chapter-31-retry` y
`poco8008-chapter-124-retry`. La plantilla controlada todavía produjo
«POR INGRESOS» para «FOR REVENGE» en esa geometría; la observación aislada
con la palabra completa produjo «POR VENGANZA». No se dio por resuelta toda
la tipografía artística a partir de una sola captura correcta.

El usuario detectó otro fallo al continuar leyendo el capítulo 124. Se
reprodujo en el teléfono: «A MEAL UNDERWATER» se reconocía como
«A MEAL LNDERWATER» incluso con el globo completo visible y la barra fuera
de las letras. La línea base de Windows además contenía «&HOST$» y
«YAN&TZE». La comparación guardada mostraba fielmente esos errores.

Se midió la geometría del texto sobre la captura real y se conservó un caso
reproducible proyectando los píxeles originales a ese tamaño, sin redibujar
las letras. Dos píxeles del margen cambiaban la lectura de U a L. La
compilación 8009 recuperó la frase en Android, pero la pasada de Windows
todavía falló. La 8010 contrasta márgenes verticales de dos a cinco píxeles
con ambos lectores locales cuando hay una discrepancia pequeña. Exige que
la lectura local coincida con el OCR del sistema y tenga confianza mínima
de 0,90. Conserva todo el ancho de la línea. No se añadieron respuestas del
capítulo a la aplicación ni se cambiaron los pesos del traductor.

La prueba real del motor de Windows y el flujo de producción de Android
recuperaron el párrafo completo y produjeron «bajo el agua» y «fantasmas del
agua». También se comprobó que una sugerencia no respaldada por la imagen
no se copie. El capítulo 124 completo se repitió con el motor Windows 8010:
22 imágenes, 152 ventanas, 108 regiones y cero excepciones. Ese resultado
no aprueba todos sus diálogos: «THEN FOLLOW ME» continúa fragmentado en
varias regiones. Olympus usa «kappas» en el diálogo; Luma conserva una
traducción más literal del inglés. Se verificó el globo español en su imagen,
ya que su propio OCR había leído «AGLA» en lugar de «AGUA».

`tools/export_chapter_photos.py` exporta las 1854 imágenes inglesas de los
124 capítulos de Regresión Absoluta. Su visor es
`build/full-comics/chapter-photos/index.html`: conserva todas las zonas del
original, incluidas las que Luma no detectó, y muestra sus salidas guardadas.
Reutiliza el pintor de texto de producción de Windows, reconstruyendo el
centrado y el color de fondo a partir de las posiciones. Estas imágenes son
reproducciones de revisión; no son nuevas capturas del teléfono. Cada
capítulo muestra su cohorte: línea base, pasada 8007 o prueba 8010. Los
informes y las imágenes llevan huellas SHA-256. Una nueva cohorte se publica
en otra carpeta para conservar la procedencia de las fotos anteriores.

`tools/audit_chapter_translations.py` recorre las salidas de los 124 capítulos
y publica `build/full-comics/chapter-audit/index.html`. Busca símbolos dentro
de palabras y términos conservados en el idioma de origen. Son candidatos
para revisión; los nombres propios y cognados también pueden aparecer.
No se aprueba el significado de las regiones sin alertas. El visor de
cobertura distingue la pasada ampliada 8007, que continúa con su copia
inmutable, de la prueba completa del capítulo 124 con la 8010. La revisión
visual de cada palabra de todos los capítulos sigue pendiente.

La compilación 8010 está instalada en el POCO. Se verificaron el párrafo
señalado, los diálogos manuscritos previos, nueve casos de color/rotación,
29 muestras de traducción, nueve casos de preparación, cancelación y
recuperación con el APK optimizado. Pasaron las pruebas nativas de Windows
y la comprobación de los modelos incluidos. Las salidas y límites quedan
registrados en `build/full-comics/release8010.json`.

## Agrupación, capturas solapadas y revisión por palabras · 8011

El conjunto solicitado sigue siendo Regresión Absoluta 1–124. El usuario
aclaró que el capítulo 125 todavía no existe.

La aplicación 8011 reconstruye las palabras de una misma línea antes de
agrupar párrafos. En el capítulo 124, `ME.` comenzaba cuatro píxeles más
arriba que `FOLLOW`, lo que dividía `THEN FOLLOW ME.` en tres traducciones.
La prueba geométrica de Windows, el recorrido del capítulo real y el
proceso de OCR y traducción en el POCO recuperan la frase completa y
producen «Entonces sígueme». Las pruebas incluyen columnas separadas,
duplicados, tamaños de letra diferentes y tres escalas.

Se corrigió además el recorrido de evaluación: conservar la primera caja
solapada descartaba lecturas posteriores más completas. Ahora el ejecutable
puede exportar todos los candidatos; `comic_capture_selection.py` conserva
la región más completa y, entre cajas comparables, la más alejada del borde
de la captura. No consulta transcripciones ni respuestas esperadas. Así se
recuperan, entre otras, `THE COUNCIL OF ELDERS` y la continuación de
`THE REASON BI SA-IN...`. Los PNG temporales de cada pasada usan directorios
distintos. La selección no cambia la captura de pantalla del teléfono.

La pasada de control 8010 y la anterior 8007 se retiraron después de guardar
sus informes y puntos de recuperación. La pasada vigente para los 124
capítulos usa `ocr-en8011-context`, `translated-en8011-context`,
`comparison8011-context` y `review8011-context`. Su ejecutable inmutable está
en `frozen-windows801101`: 801101 identifica la copia de evaluación de la
aplicación 8011 con exportación de candidatos, no una versión Android nueva.
El publicador actualiza `chapter-photos` y nunca debe sustituir imágenes de
una pasada posterior por una anterior. Cada capítulo mantiene su procedencia.

Se documentaron 67 parejas de diálogo y narración del capítulo 124 en
`benchmarks/full-comics/visual-reviews/absolute-regression-124.json`, con
transcripciones cotejadas en los píxeles originales y observaciones de
significado. Son 749 tokens del OCR español contrastados y 760 palabras en
la lectura española corregida. Las marcas, créditos y palabras fuera de
estos recortes siguen pendientes; no es una revisión completa del capítulo.
La evaluación anterior 8010 se conserva en `visual-reviews/history`.

El visor `word-review/index.html` publica el avance visual real.
`visual-evaluation8011-context/absolute-regression-124.html` compara las 724
palabras inglesas de esas parejas con el OCR guardado: las ediciones de
palabras bajaron de 77 a 46. Esta medida incluye pérdidas, sustituciones e
inserciones; no es precisión semántica ni un porcentaje de toda la serie.
Las casillas del visor de palabras se guardan por capítulo y huellas de los
informes, y marcar una palabra inspeccionada no aprueba su significado.

Hay diferencias reales entre las ediciones: el inglés dice `FOUR HOURS`
y Olympus `DOS HORAS`; otro diálogo distingue artes no ortodoxas de artes
demoníacas de forma diferente. Las observaciones registran estas diferencias
sin convertir la edición humana en respuestas de producción.

La 8011 pasó 16 pruebas JVM, 15 casos de agrupación Windows, el proceso de
OCR y traducción Android para FOLLOW y UNDERWATER, y la batería de release
con 29 traducciones, nueve casos de preparación, nueve casos de color y
rotación, cancelación y recuperación. El APK instalado en el POCO es 8011;
el usuario anunció que desconectaría el teléfono después de las pruebas.
No se ha probado esta compilación en el emulador. La verificación está en
`build/full-comics/release8011.json`; el ZIP es
`build/releases/Luma-Windows-1.0.0+8011.zip`.

Siguen pendientes errores reales: se pierde NO en la tipografía estrecha
de `WHAT DO YOU MEAN...`, `UNFORTUNATE` puede acabar como «afortunada»,
`FOUNDATION` como «pasión», y la narración con contorno queda fragmentada.
Una prueba diagnóstica de diez recortes originales, documentada en
`ocr-reader-probe8011`, muestra que los dos lectores ya incluidos reconocen
UNFORTUNATE y FOUNDATION en el globo recortado. No cambia el código de la
aplicación ni pasa las respuestas esperadas al OCR. Apunta a investigar la
delimitación y el segundo reconocimiento de regiones antes de cambiar pesos.
La revisión visual de cada palabra de los 124 capítulos sigue incompleta.

### Informe agregado y muestra distribuida

`tools/audit_corpus_quality.py` publica `build/full-comics/metrics/index.html`
sin ejemplos ni identificadores de capítulos en la página principal. Examina
los resultados guardados de los 124 capítulos, conserva la procedencia de cada
pasada y vuelve a calcular las alertas cuando termina una nueva inferencia.
La comparación automática usa el mismo criterio y los mismos capítulos en
ambas pasadas. La variación de alertas no es precisión semántica.

El detector incluye símbolos dentro de palabras, secuencias inglesas sin
traducir, repeticiones, posibles negaciones perdidas, alternancia anómala de
mayúsculas y palabras copiadas que no coinciden con una pieza completa del
vocabulario. Ese vocabulario es de subpalabras, no un diccionario completo:
su ausencia también puede marcar nombres o términos válidos. Cada señal
requiere revisión; su combinación no certifica que una frase esté bien.

Se fijó una muestra de una región elegible por capítulo, elegida por el menor
hash de sus identificadores sin consultar el resultado de la traducción.
`prepare_corpus_review_sample.py` guarda las lecturas reales, las coordenadas,
las huellas de inferencia y las imágenes originales. Sus 31 hojas contienen
124 recortes ingleses junto a propuestas de referencia española y las salidas
anterior y posterior. Se inspeccionaron visualmente esas 124 regiones; dos
quedaron sin dictamen comparable por evidencia insuficiente. Una propuesta
de referencia desalineada se documentó como tal; los fallos léxicos de esa
región se contrastaron directamente con el original inglés.

En las 122 regiones comparables se contaron 84 resultados con errores claros
en la base y 51 en la instantánea posterior: 36 correcciones y 3 regresiones,
reducción relativa acumulada del 39,2857 %. El criterio cuenta significado
incorrecto, palabras esenciales corruptas o sin traducir, omisiones y
fragmentación; los problemas menores de estilo quedan separados. Una región
con varios errores se cuenta una vez. Las evaluaciones manuales se conservan
en `benchmarks/full-comics/corpus-semantic-review.json`, enlazadas por hash
a la muestra y a las inferencias.

Esta comparación utiliza una instantánea de las últimas salidas disponibles
al seleccionar la muestra: 21 capítulos de `translated-en8011-context`, 62 de
`translated-en8007` y 41 de la base `translated-en-final`. No es una evaluación
de los 124 capítulos con la última compilación. Tampoco es una estimación de
precisión poblacional: solo incluye regiones detectadas de longitud acotada
con una correspondencia propuesta, sin medir las palabras nunca detectadas.
El 12 % de reducción en las 67 parejas cotejadas entre 8010 y 8011 sigue siendo
una comparación distinta y no debe mezclarse con el 39,2857 % acumulado.

`verify_corpus_quality.py` verifica las imágenes, hojas, inferencias y métricas.
`test_corpus_quality.py` comprueba reglas de detección, exclusiones, regresiones
y cálculo de reducción. Este paso mejora la evaluación y no modifica las
traducciones guardadas, el ejecutable publicado ni los pesos del modelo.
La pasada completa de Windows continúa de forma independiente; sigue pendiente
la revisión de cada palabra de todos los capítulos.

### Pasada uniforme y ampliación del cotejo visual

La pasada `translated-en8011-context` terminó los 124 capítulos con 18.179
regiones. Sus galerías comparativas usan una misma versión. Recorrer archivos
no equivale a aprobar todas sus palabras.

Se inspeccionaron otras 248 regiones, dos distintas por capítulo, con las
imágenes originales y las referencias propuestas. La instantánea histórica
de esta ampliación tenía 243 comparaciones resolubles y 169 → 101 errores
claros, 76 correcciones y ocho regresiones. Se conserva en
`corpus-semantic-review-b.json`; mezclaba resultados de varias versiones.

Después se actualizaron ambas muestras a la pasada uniforme. Solo se reutiliza
un dictamen cuando la traducción es idéntica y la correspondencia geométrica
es inequívoca. Se reinspeccionaron las 91 salidas modificadas. El registro
`current8011-full-semantic-review.json` reúne 372 regiones, tres por capítulo:
365 comparables, siete sin evidencia suficiente, 253 → 107 errores claros,
162 correcciones y 16 regresiones. La reducción relativa del 57,7075 % mide
esas regiones frente a la base. No mide los textos nunca detectados ni la
precisión poblacional. Los pesos del traductor no cambiaron.

### Recuperación de párrafos de Windows · 8012 en evaluación

La aplicación compila una política que coteja dos recortes del mismo párrafo
con los dos lectores locales ya incluidos. Solo acepta texto obtenido de los
píxeles, con coincidencia entre lectores, cambios acotados y conservación de
contenido, números, códigos y negaciones. La copia inmutable `801201`
identifica este motor de evaluación. Android sigue con el APK 8011; no se ha
compilado ni instalado una versión Android 8012 durante este trabajo.

La batería nativa pasó 11 guardas de recuperación y 15 casos geométricos.
La prueba de 124 capturas fijas produjo 26 regiones recuperadas. Se revisaron
todas; en esa selección de salidas modificadas hubo 14 → 2 errores claros y
cero regresiones. Su reducción del 85,7143 % está condicionada a las regiones
recuperadas y no es una medida de toda la muestra ni del conjunto de capítulos.

Para evitar ese sesgo se ejecutaron los motores anterior y nuevo sobre los
mismos 124 PNG, sin mover el recorte entre versiones. Se tradujeron las 228
regiones resultantes con el mismo motor offline; solo se reutilizaron salidas
previas para fuentes exactamente iguales y con implementación y modelos
idénticos. En la ubicación elegida previamente por capítulo, 122 comparaciones
resolubles registran 33 → 22 errores, 11 correcciones y ninguna regresión:
reducción adicional del 33,3333 %. Los dictámenes están en
`paired8012-seed-semantic-review.json`. No se suma este porcentaje al de la
muestra principal y no aprueba los capítulos completos.

La nueva pasada completa `ocr-en8012-recovery` y su traducción independiente
continúan con la copia inmutable del motor. Los resultados de inferencia
anteriores se conservan para repetir las comparaciones.

### Comprobación de posibles omisiones

Se buscaron propuestas de ausencia de región en los 124 capítulos y se fijó
una región elegible por capítulo cuando había candidatos. Se inspeccionaron
las 47 propuestas resultantes: cinco fallos de detección inglesa completa o
parcial y tres defectos de traducción o fragmentación; además, una región usa
otra escritura y dos corresponden a dibujos reconocidos como caracteres.
También hay anuncios, notas y leyendas añadidas, duplicados y desalineaciones
que no son omisiones del original. Se ampliaron los contextos dudosos antes
de decidir. El registro `undetected-semantic-review8011.json` mantiene cada
decisión y las huellas de las imágenes y las inferencias. Estos recuentos de
diagnóstico no se añaden a los de la muestra principal sin deduplicación y
no establecen la tasa de omisiones de todos los capítulos.

Una prueba separada ejecutó ambos lectores locales sobre 56 variantes reales
de ocho capturas, incluyendo controles de dibujos sin texto. Conserva los
resultados en `omitted-lettering-probe8012`. Contraste, canales de color y
rotación no funcionan igual en todos los estilos; sus propuestas no se
sustituyen automáticamente en las inferencias de producción.

### Ampliación a texto corto y fragmentos

Se seleccionó otra región de dos a seis palabras por capítulo, excluyendo
geométricamente las 372 anteriores. La selección fue determinista y no
consultó el resultado de la traducción. Se ampliaron los recortes de revisión
para ver el contexto: varias regiones cortas son fragmentos de oraciones
largas, no frases completas. En 123 comparaciones válidas hubo 76 → 34 errores,
45 correcciones y tres regresiones. Una falsa detección sobre el dibujo queda
fuera de la comparación semántica; permanece registrada.

El informe principal consolidado usa ahora 496 ubicaciones distintas, cuatro
por capítulo, de una sola pasada Windows 8011. En las 488 comparaciones
resolubles se cuentan 329 → 141 errores claros, 207 correcciones y 19 regresiones:
reducción relativa del 57,1429 %. Ocho comparaciones se excluyen por evidencia
insuficiente o ausencia de texto real. `current8011-expanded-semantic-review.json`
conserva las huellas y las decisiones, sin sustituir la instantánea anterior
de 372 regiones. Esta ampliación cambia la muestra, no los pesos del modelo;
el porcentaje sigue sin medir todos los textos de los 124 capítulos.

### Completado de líneas parciales · Windows 8013 en prueba

Se investiga el descarte de una detección completa cuando solapa una lectura
pequeña del OCR del sistema. El nuevo paso exige dos lecturas independientes
con alta confianza, conservar el contenido reconocido y sus números y
negaciones, y limitar el cambio a extender los extremos de la línea. Usa las
coordenadas originales de las palabras para comprobar el solapamiento, ya que
la relectura local puede haber ampliado una caja parcial hasta el borde del
globo. La salida exporta `line_completed` y conserva la evidencia nativa.

La primera pasada `801302` recorrió 132 capturas sin fallos de ejecución ni
cambios en las 124 capturas fijas, pero no completó ninguna línea. Se conservó
como diagnóstico, no como mejora confirmada. La versión ajustada `801303`
terminó sus 132 capturas sin errores de ejecución. Conservó las salidas de las
124 capturas fijas y completó una línea del diagnóstico. La traducción posterior
recuperó el contenido principal de esa advertencia, pero siguió omitiendo una
interjección; no se registra como traducción perfecta. Pasa 21 guardas de
recuperación, 15 comprobaciones geométricas y las pruebas reales de barra y
superposición. No se instaló una nueva versión Android durante estas pruebas.

### Quinta ubicación por capítulo · muestra consolidada

Se inspeccionaron 124 ubicaciones adicionales, excluyendo las 496 anteriores
por solapamiento. La muestra consolidada tiene 620 regiones diferentes, cinco
por capítulo, y 612 comparaciones resolubles. En la misma pasada Windows 8011
hay 406 → 170 errores claros: 260 correcciones y 24 regresiones frente a la base,
reducción relativa del 58,1281 %. Se conservan las ocho exclusiones y todos los
dictámenes anteriores. `current8011-extended-semantic-review.json` identifica
este consolidado; no reemplaza las instantáneas de 372 y 496 regiones. Esta
ampliación de la revisión no modifica los pesos ni establece la precisión de
todas las palabras de los capítulos.

### Recuperación de oraciones omitidas · Windows 8014 en evaluación

El traductor nativo conserva primero la inferencia completa. Solo reintenta
por oración cuando el original contiene entre dos y cuatro frases completas
y la salida es significativamente corta y contiene menos cláusulas. Las comas
también cuentan como cláusulas para conservar paráfrasis válidas que unen
oraciones. Abreviaturas, iniciales, puntos suspensivos y finales incompletos
restringen el reintento. Cada parte usa el mismo modelo local; el paso no recibe
referencias, respuestas esperadas ni transcripciones por capítulo.

Se ejecutaron 723 inferencias nativas nuevas, correspondientes a 620 ubicaciones
revisadas y 117 propuestas de omisión, con deduplicación de fuentes idénticas.
Las salidas sin recuperación coincidieron exactamente con las anteriores; en
las recuperadas, la primera inferencia completa también coincidió. Con el OCR
fijo y las mismas ocho exclusiones, ocho salidas de la muestra cambiaron y se
volvieron a inspeccionar contra las imágenes. Las 612 salidas idénticas conservan
su dictamen. Las 612 comparaciones válidas pasan de 170 a 164 errores, seis
correcciones y cero regresiones observadas: reducción adicional del 3,5294 %.
Este porcentaje no se suma al 58,1281 % ni incorpora las mejoras nuevas del OCR.

En el diagnóstico condicionado a salidas que recuperan frases, 68 → 16 errores,
52 correcciones y cero regresiones. Se reutilizaron 52 dictámenes únicamente
cuando la nueva salida nativa coincidió con el candidato previamente cotejado;
se inspeccionaron otras 16 ubicaciones contra el inglés visible al no disponer
de correspondencia española alineada. Esta selección se solapa con la muestra
principal y no estima la precisión global. Varias recuperaciones conservan
fallos de letras, palabras o significado; no equivalen a solucionar todos los
casos. `coverage8014-fixed-ocr-semantic-review.json` y
`coverage8014-omission-diagnostic-semantic-review.json` conservan las decisiones.

Windows 8014 compila y pasa 17 guardas de cobertura de oraciones, 21 guardas de
recuperación OCR, 15 pruebas geométricas, una traducción offline superpuesta y
la prueba de barra móvil, animación, cancelación y retirada por movimiento.
No se modificaron los pesos. Android todavía no tiene una compilación nueva
verificada de esta política. La pasada `translated-en8014-fixed-ocr` está
retraduciendo el OCR guardado de los 124 capítulos con la implementación nativa
nueva y una caché que solo admite inferencias idénticas de esa implementación.
El recorrido completo del OCR 8012 sigue separado; ninguno de esos trabajos
en curso acredita una revisión humana de todas las palabras.

### Sexta ubicación por capítulo · 744 regiones cotejadas

Se inspeccionó otro lote determinista de 124 ubicaciones, una por capítulo,
sin repetir las 620 anteriores. Sus 31 hojas muestran los píxeles originales
en inglés y la referencia española junto a las salidas nativas sin editar.
En 123 comparaciones válidas hubo 85 → 33 errores, 54 correcciones y dos
regresiones. Una detección sobre el dibujo se excluye del cálculo semántico,
pero queda registrada como falsa detección. La selección y sus 124 decisiones
están en `corpus-review-sixth8011`.

El consolidado histórico con OCR 8011 alcanza 744 ubicaciones diferentes,
735 comparaciones válidas y nueve exclusiones: 491 → 203 errores, 314
correcciones y 26 regresiones, reducción del 58,6558 %. No se sobrescribió
la muestra anterior. Se ejecutaron 124 inferencias nuevas adicionales con el
traductor nativo 8014, suministrando únicamente las fuentes reconocidas;
todas conservaron exactamente la salida 8011 de estas ubicaciones. Ese lote
no añade beneficios ni regresiones a la recuperación de oraciones.

Al ampliar la prueba de traducción con OCR fijo a las mismas 735 comparaciones,
el último ajuste pasa de 203 a 197 errores: seis correcciones y cero regresiones,
reducción adicional del 2,9557 %. Frente a la base histórica, el resultado
consolidado actual es 491 → 197, 320 correcciones y 26 regresiones, reducción
del 59,8778 %. Este resultado se calcula directamente sobre la misma muestra;
no suma porcentajes. `current8011-six-regions-semantic-review.json` y
`coverage8014-six-regions-semantic-review.json` identifican ambas etapas.
El aumento de la muestra cambia el porcentaje aunque no se entrenen pesos.
El total semántico de todos los capítulos sigue sin estar establecido.

La retraducción completa también se coteja registro por registro con el OCR
guardado: fuente, imagen y coordenadas deben permanecer iguales. Toda salida
modificada debe conservar la primera inferencia completa anterior y registrar
la recuperación por oraciones. Solo se reutiliza un dictamen de diagnóstico
si coinciden capítulo, ubicación, fuente y traducción; una fuente repetida en
otro lugar no basta. `full-corpus-translation8014-validation.json` distingue
estos controles de ejecución de una revisión semántica completa.

### Punto de control del recorrido completo del OCR mejorado

Se congelaron las seis ubicaciones ya elegidas de cada uno de los 53 capítulos
con recorrido completo disponible en ese momento, sin seleccionar por su
resultado: 318 ubicaciones. Se inspeccionaron las 48 fuentes o salidas modificadas
y se conservaron 270 dictámenes únicamente cuando fuente y traducción eran
idénticas en una sola región correspondiente. En 314 comparaciones válidas
hubo 92 → 72 errores, 20 correcciones y cero regresiones observadas, reducción
del 21,7391 %. Las cuatro exclusiones originales se conservaron. El documento
`full8012-checkpoint01-semantic-review.json` y las 12 hojas de
`full8012-review-checkpoint01` fijan este resultado parcial. Se solapa con la
muestra principal: sus cuentas y porcentajes no se añaden a los del consolidado.

La pasada `translated-en8014-recovery` combina el OCR completo 8012 disponible
con el traductor nativo 8014. Su caché solo admite inferencias reales de ese mismo
binario, runtime y modelos con fuente exacta. Las referencias y los dictámenes
no se cargan durante esa inferencia. Este recorrido combinado sigue separado
de la prueba que mantiene fijo el OCR, y tampoco sustituye una pasada completa
del OCR 8013 ni la revisión de todas las palabras.

### Retraducción y galería terminadas · 124 capítulos

La pasada `translated-en8014-fixed-ocr` terminó los 124 capítulos y sus 18.179
regiones. Hubo 12.576 registros de inferencia nueva y 5.603 reutilizados de
inferencias reales de la misma implementación 8014 y fuente exacta. El cotejo
registro por registro conservó fuente, imagen y coordenadas: 18.111 traducciones
idénticas y 68 modificadas. Todas las modificadas coinciden con la misma ubicación,
fuente y salida del diagnóstico semántico ya cotejado; no hubo cambios inesperados
ni salidas modificadas pendientes de ese cotejo. Esto verifica todos los cambios
de esta pasada, no todos los posibles errores de las salidas que no cambiaron.

La galería separada `chapter-photos8014-fixed-ocr` contiene los 124 capítulos y
1.854 imágenes completas. Se verificaron píxeles de origen, hashes, dimensiones,
inferencia y procedencia de cada imagen. En 1.786 imágenes, las entradas exactas
del mismo pintor no cambian; se reutiliza el render guardado mediante enlaces
duros, sin modificarlo. Otras 68 se reprodujeron por el mismo binario de Windows.
La galería 8011 se conserva. `review8014-fixed-ocr` contiene la comparación
automática por palabras de las 124 parejas con Olympus. Sus correspondencias
no aprueban automáticamente significado, alineación ni lectura humana.

### Fondo de superposición · Windows 8015

Una inspección de los ocho renders modificados de la muestra reveló que un
borde oscuro podía determinar erróneamente el fondo de un globo blanco. El
nuevo paso solo actúa después del reconocimiento y la traducción; no cambia
la agrupación OCR, las fuentes, el texto ni los pesos. Si tres cuartas partes
de una rejilla interior coinciden en una familia de color, usa su mediana;
en zonas pequeñas o sin consenso conserva el fondo anterior. El pintor de
revisión usa el mismo paso que la superposición de Windows.

Windows compila y pasa diez guardas nativas de fondo, 21 de recuperación OCR,
15 comprobaciones geométricas y las pruebas reales de barra, animación,
cancelación, movimiento y traducción superpuesta. Ocho pares se reprodujeron
con ambos binarios reales y se inspeccionaron: un fondo corregido, siete
JPEG idénticos y cero cambios de traducción. Las traducciones incorrectas
siguen visibles y esta mejora no se añade a la precisión semántica.

La lógica equivalente Android está conectada después de la traducción. Su
fuente Kotlin real se compiló con el compilador 2.3.20 ya almacenado y pasó
seis pruebas JUnit, más paridad exacta con C++ en los ocho recortes BGRA reales.
No se generó ni instaló un APK nuevo: Gradle falla al establecer una conexión
de loopback de Java antes de compilar la aplicación, tanto con JBR 21 como
con el JDK 17 local. Esos registros se conservan separados de la prueba Kotlin
independiente; no se usó el teléfono ni el emulador.

El ZIP `Luma-Windows-1.0.0+8015.zip` incluye el binario probado y los modelos
offline verificados dentro del archivo. `release8015.json` fija sus huellas,
resultados y límites. Continúan la pasada completa del OCR 8012 y su combinación
con el traductor 8014; el OCR completo de la compilación actual y la revisión
semántica de todas las palabras todavía no están terminados.

### Cobertura de diálogo y criterio por uso · Windows 8016

La aclaración del usuario fija la prioridad en Windows y en no omitir ninguna
palabra de diálogo o narración. Una onomatopeya como «sniff» puede conservarse.
El objetivo es que menos del 5 % de los usos completos fallen: una omisión,
un cambio de sentido, un cierre, un bloqueo o una traducción que no termina
cuentan como fallo. Una tasa de error por palabra o por región no acredita
esa probabilidad por pantalla. `screen-acceptance-policy.json` recoge el
criterio y mantiene la probabilidad actual sin establecer.

El ajuste 8016 recupera preguntas omitidas aunque la traducción restante no
sea suficientemente corta para activar la guarda anterior. También admite
un último fragmento visible de al menos cinco palabras después de oraciones
completas, sin inventar su continuación. Conserva los límites y las guardas
de abreviaturas, puntos suspensivos y segmentación. No se entrenaron ni
cambiaron pesos de traducción o reconocimiento.

Se recorrieron las 18.179 regiones de los 124 capítulos con OCR fijo para
identificar cambios de este ajuste. Se inspeccionaron las 37 traducciones
modificadas: 36 → 10 errores, 26 correcciones completas y cero regresiones
observadas. La reducción del 72,2222 % corresponde únicamente a esas 37
regiones seleccionadas por el cambio. Las otras 18.142 salidas idénticas no
quedan aprobadas semánticamente por ese cotejo. El informe independiente es
`full-omission8016-semantic-review.json`.

En las 735 comparaciones válidas de la muestra fija anterior se detectaron
dos preguntas omitidas que antes se habían considerado aceptables. La revisión
explícita de esos dos dictámenes deja una comparación coherente con la nueva
prioridad: 199 → 196 errores, tres correcciones completas y cero regresiones.
Los archivos históricos y sus resultados 203 → 197 se conservan. No se suman
las cuentas de estas muestras solapadas. `coverage8016-candidate-semantic-review.json`
documenta las revisiones y los siete cambios inspeccionados.

El binario de producción coincide con el candidato en 850 inferencias nuevas,
incluidos sus campos de recuperación, y pasa 23 guardas nativas. Cuatro imágenes
reales se procesaron y pintaron con las dos compilaciones de Windows: dos
procesos y ocho intentos de pantalla, cero errores de ejecución y cuatro
traducciones modificadas. Los ocho intentos no equivalen a ocho arranques ni
aprueban todo su significado. Las pruebas de barra flotante, animación,
movimiento, cancelación, reconocimiento y geometría pasan. El ZIP experimental
`Luma-Windows-1.0.0+8016.zip` contiene el binario congelado y sus modelos offline
verificados; `release8016.json` y `metrics/verification8016.json` fijan la evidencia.

Para el reconocimiento se compararon tres lectores sobre 124 recortes reales,
uno por capítulo, transcribiendo manualmente sus 1.562 palabras de diálogo y
narración. El lector actual comete 44 errores de palabra y falla en 34 recortes.
Los otros lectores introducen regresiones si se sustituyen directamente. Una
combinación conservadora experimental baja a 27 errores y 19 recortes fallidos,
con 15 correcciones completas y cero regresiones en esta muestra; todavía
conserva diez omisiones de palabras. Estos resultados separan error por palabra
y error por recorte, y tampoco son una probabilidad de fallo de la aplicación.

Se congeló esa política antes de elegir otras 124 ubicaciones que no estaban
en las 744 anteriores. Cambió doce recortes: se inspeccionaron todos los cambios,
con diez correcciones completas, cero regresiones y dos recortes aún defectuosos.
Los otros 112 recortes no recibieron revisión semántica. Este lector combinado
todavía no está integrado en la captura de Windows ni incluido en el ZIP.
`ocr8016-reader-comparison.json`, `ocr8016-consensus-conservative-candidate.json`
y `ocr8016-consensus-heldout-review.json` conservan las cuentas separadas.

El punto de control combinado de OCR 8012 y traductor 8014 abarca 426 ubicaciones,
422 válidas: 115 → 92 errores, 23 correcciones y cero regresiones. Es parcial y
se solapa con la muestra anterior; no se añade a los resultados 8016. Continúan
las pasadas congeladas completas. Aún falta revisar todas las palabras visibles,
incluido texto nunca detectado, y establecer la medida por pantalla completa.
El objetivo inferior al 5 % sigue sin demostrarse. La construcción del APK
queda aplazada según la prioridad indicada por el usuario.

## Windows 8017: revisión ampliada y conservación del reconocimiento

La revisión OCR de las otras 124 ubicaciones ahora incluye los 112 recortes
sin cambios que antes quedaban pendientes: se transcribieron manualmente las
1.483 palabras visibles de los 124 originales. El lector aislado actual deja
41 errores de palabra en 34 recortes. La combinación conservadora congelada
deja 28 en 24 recortes, diez correcciones completas y cero regresiones; mantiene
seis omisiones. Cuatro recortes tienen texto cortado por un borde y se publica
también el subconjunto de 120 sin esos cortes. El informe previo de doce
cambios permanece intacto como punto de control histórico.

Además se ejecutaron los binarios reales Windows8015 y Windows8016 sobre esas
124 imágenes originales. Se cotejaron todas sus salidas, el inglés visible y
Olympus. Con aprobación estricta del contenido completo, quedan 45 → 44
traducciones sin aprobar: una corrección y cero regresiones. Dentro de las 44
actuales hay 36 errores claros y ocho casos que requieren mejora. No se
penalizan variaciones menores de estilo. La edición inglesa visible prevalece
si Olympus cambia números o contenido. El OCR de la aplicación completa deja
34 errores de palabra en 20 recortes y siete omisiones; no debe confundirse con
los resultados del lector aislado.

La corrección de Windows8017 permite unir renglones inclinados cuyos cuadros
se solapan ligeramente, conservando antes las lecturas corroboradas del motor
anterior. El primer ensayo alteró una palabra y se descartó. El ensayo
conservador mantiene exactamente los 124 textos reconocidos, incluida su
puntuación: 44 → 41 traducciones sin aprobar, tres correcciones completas y
cero regresiones observadas. La reducción relativa del 6,82 % pertenece
únicamente a estas mismas 124 ubicaciones; quedan 35 errores claros y seis
casos que requieren mejora. El subconjunto de 120 recortes sin cortes pasa
de 41 a 38 sin aprobar.

La inspección del dibujo detectó además que el fondo de un renglón posterior
podía borrar parte de una traducción anterior. La implementación final pinta
primero todos los fondos y reparte el espacio de los renglones contiguos antes
de ajustar las letras. Las pruebas nativas comprueban 37 casos de geometría,
preservación y separación del texto, además de reconocimiento, superposición,
barra, animación, movimiento y cancelación. La compilación congelada801704 es
la versión experimental1.0.0+8017; las compilaciones801701,801702 y801703 se
conservan como ensayos y no son el binario del paquete final.

Por separado, otro candidato recupera frases breves omitidas. Se planificaron
1.008 fuentes reales y 19 activaron nuevos reintentos. El primer ensayo produjo
repeticiones y se rechazó; la revisión con 15 guardas cambia 14 salidas. Todas
se cotejaron con originales y referencia: 13 → 5 sin aprobar, ocho correcciones
completas y cero regresiones observadas. Es un diagnóstico de desarrollo y
todavía no está incorporado a Windows8017.

Otra selección de 124 ubicaciones, distintas de las 868 anteriores, prueba
una regla OCR congelada que añade palabras solo con acuerdo de dos lectores
y anclas intactas. Los 16 cambios se inspeccionaron: 22 → 3 errores de palabra,
14 recortes corregidos por completo y cero regresiones; dos conservan errores.
Las 108 lecturas sin cambios siguen pendientes de inspección. Esta regla no
está incorporada y debe proteger los apóstrofos internos antes de integrarse.
Los resultados de estos candidatos no se suman a la mejora de la aplicación.

Terminaron los controles congelados de los 124 capítulos: 18.179 regiones,
cero errores de ejecución. El punto de control02 conserva 744 ubicaciones
fijas: 645 salidas idénticas pueden reutilizar su dictamen anterior y 99
cambiadas requieren cotejo adicional. No se aprueba por extensión el resto
del capítulo. La revisión de todas las palabras y la medición de intentos de
pantalla completa continúan pendientes. Los pesos no cambiaron y el objetivo
de menos del 5 % de usos fallidos sigue sin acreditarse.

## Windows 8018–8019: validación amplia del reintento y precisión numérica

El cierre del punto de control02 inspeccionó las 51 ubicaciones cambiadas que
faltaban y reutilizó 48 cotejos exactos: sobre 735 comparaciones válidas de las
744 ubicaciones, quedan 301 → 255 sin aprobar, 47 correcciones completas y una
regresión. Se conserva una rectificación explícita de un dictamen anterior.
Es el control anterior de OCR, no la compilación actual.

El ensayo801801 de recuperación de frases se comprobó sobre las 18.179
regiones de los 124 capítulos del control OCR fijo. Las fuentes que activaron
alguna política recibieron 524 resultados nativos pareados: 376 inferencias
nuevas y 148 reutilizaciones de fuente idéntica, binario, runtime y modelos
fijados. Donde ninguna política reintenta se conserva la inferencia completa
real de la implementación común. Esto no aprueba semánticamente esas salidas.
Se inspeccionaron los 119 cambios del ensayo: 117 → 36 sin aprobar, 82
correcciones completas, una regresión completa y un empeoramiento parcial
adicional en una región que ya fallaba. El ensayo no se empaquetó.

La política801901 exige retener al menos el 80 % de las palabras de la
inferencia completa en las nuevas rutas de reintento, contando repeticiones y
apóstrofos, y protege negaciones explícitas. Conserva el comportamiento de las
rutas largas anteriores y rechaza repeticiones artificiales. Estas son
protecciones conservadoras, no una prueba automática de equivalencia semántica.
Se verificaron 1.160 inferencias nuevas de producción de la unión de ambos
conjuntos contra el plan nativo, sin desacuerdos, además de 46 guardas.
Los mismos 119 dictámenes, reutilizados únicamente por identidad de salida y
ubicación, dejan 117 → 41 sin aprobar: 76 correcciones completas, cero
regresiones completas y el empeoramiento parcial del ensayo anterior eliminado.
Se rechazaron 16 recuperaciones, incluidas seis que habían sido correctas.
La reducción relativa del 64,96 % corresponde a estos cambios inspeccionados;
no es la probabilidad de fallo por pantalla ni un resultado global de todas
las palabras de los capítulos.

La app Windows801901 procesó los 124 recortes reales con 137 regiones y cero
errores de ejecución. Conservó exactamente todas las fuentes OCR: 34 errores
de palabra en 1.483 palabras, incluidas siete omisiones. Los significados de
las salidas se vinculan a cotejos anteriores únicamente por identidad en la
misma ubicación. Dos dictámenes se rectificaron en ambos lados al descubrir
defectos presentes en ambas variantes; los informes históricos no se alteran.
Con ese criterio pareado, Windows801704 →801901 deja 43 →41 sin aprobar,
dos correcciones completas y cero regresiones completas. La protección
retiene una inferencia completa en lugar de una recuperación parcial del
ensayo801801. Pasaron 37 comprobaciones de geometría, reconocimiento,
superposición y barra. Se inspeccionaron cuatro dibujos nativos; uno conserva
un resto pequeño de puntuación original y dos aún tienen defectos de contenido.
La compilación está congelada para validación y no se publicó un ZIP nuevo.

También se tradujeron las 137 fuentes de esos mismos recortes con una variante
int8 existente del mismo modelo, usando el mismo tokenizer y terminología.
Se cotejaron los 52 cambios y se conservaron 72 dictámenes de salidas idénticas.
Con las dos rectificaciones aplicadas por igual, quedan 41 →41 sin aprobar,
cuatro correcciones y cuatro regresiones. Se descartó esa variante para la app.
No hubo entrenamiento ni cambios en sus pesos instalados.

El candidato OCR ahora protege apóstrofos internos: exige acuerdo entre los
dos lectores sobre el apóstrofo y no lo elimina al reemplazar letras.
Pasaron 17 guardas y 496 evaluaciones nativas de política sobre 372 ubicaciones
de píxeles; el puente de Windows se solapa con el segundo lote. Esto reutiliza
lecturas OCR reales congeladas, no son 496 ejecuciones nuevas de los modelos.
Se inspeccionaron y transcribieron las 108 ubicaciones sin cambios del tercer
lote; junto con las 16 transcripciones anteriores cubren sus 124 recortes y
1.553 palabras. Incluye un control sin diálogo. El reconocimiento pasa de
46 a27 errores de palabra y de33 a19 recortes con errores, 14 correcciones
completas y cero regresiones; conserva cinco palabras omitidas. Se publican
por separado la comparación histórica que ignoraba apóstrofos y la nueva
comparación estricta. Todavía es un candidato aislado; no aprueba el sentido
de sus traducciones españolas ni la cobertura de pantallas completas.

La prioridad sigue siendo Windows y no omitir diálogo o narración. No se han
revisado todas las palabras de todos los capítulos. La probabilidad de fallo
por uso sigue sin establecerse, y el objetivo inferior al5 % no está logrado.

## Windows 8020–8021: inventario de vistas completas

Se inspeccionaron los 124 originales guardados, una vista de lectura por
capítulo, y se inventarió todo el diálogo visible, incluyendo texto omitido
por los detectores. Se cotejaron los significados completos de las 124 vistas,
también los resultados sin cambios. Diecisiete capturas cortan diálogo visible;
se informa además el conjunto de 107 vistas sin ese defecto. No es un recorrido
manual de todas las palabras de todos los capítulos ni una muestra aleatoria
de usos completos: la selección original estaba anclada a detecciones previas.

El ensayo integrado 802001 conserva las 228 regiones antes del consenso,
procesa las 124 vistas sin errores de ejecución y deja 62 → 60 sin aprobar:
tres correcciones completas y una regresión de significado. El resultado de
recortes anterior (41 → 36) no reemplaza este denominador más amplio.

El candidato 802101 añade consenso sobre lecturas completas, protegiendo
números, negaciones, apóstrofos, palabras desconocidas y puntuación de palabras
intactas. Requiere dos lectores concordantes y compara con la lectura ya
reparada conservadoramente. Pasaron 17 guardas del selector. Las 724 llamadas
de política usan lecturas congeladas; no son inferencias nuevas de OCR.

El ejecutable real 802101 procesó las 124 vistas y 228 regiones sin errores
de ejecución. Conserva todas las fuentes antes del consenso y los límites,
y sus 228 fuentes seleccionadas coinciden con la predicción del selector.
Se revisaron los diez cambios y solo se reutilizaron los 114 dictámenes con
identidad de todas las salidas en la misma ubicación. Quedan 60 → 58 vistas
sin aprobar, dos correcciones completas y ninguna regresión nueva. Frente al
control 801901 anterior a ambos ensayos, quedan 62 → 58: cuatro correcciones
completas y ninguna regresión restante, reducción relativa del 6,45 % en este
mismo conjunto. No es la probabilidad de fallo por uso completo.

Pasaron 37 comprobaciones del ejecutable y 36 de integridad de informes.
Se inspeccionaron los diez dibujos nativos nuevos: persisten restos de letras
y puntuación original fuera de algunas máscaras conservadas. No están
aprobadas visualmente las 124 superposiciones. El consenso sigue limitado a
la configuración explícita de pruebas; no se activó en el trabajador normal.
No se entrenaron pesos ni se sustituyeron los modelos de la aplicación.

La galería reutiliza las imágenes existentes y el contenido de versiones
congeladas idéntico se comparte mediante enlaces físicos de solo lectura.
Véase `docs/quality-storage.md`. No se creó otro ZIP ni APK.

## Modelo local alternativo: dos configuraciones descartadas

Se descargó el modelo público existente Qwen3-4B-Q4_K_M y el runtime Windows
Vulkan b11869 de llama.cpp, verificando sus SHA-256. Ningún texto del cómic ni
respuesta humana se envió a un proveedor: las inferencias usaron exclusivamente
el servidor local y las mismas 228 fuentes OCR, con sus defectos originales,
agrupadas por las mismas 124 vistas. No hubo entrenamiento ni cambios en la app.

El ensayo con selección codiciosa procesó las 124 vistas sin errores de
ejecución. Se cotejaron todos sus significados con el inventario de originales:
58 →85 sin aprobar, ocho correcciones completas y 35 regresiones. El ensayo
con los parámetros no reflexivos recomendados por la ficha oficial (temperatura
0,7; top-p0,8; top-k20; min-p0; penalización de presencia1,5; semilla8021)
también procesó todas las vistas: 58 →89 sin aprobar, ocho correcciones y
39 regresiones. Se conservan ambos informes, incluidas las regresiones.
Son resultados de estas configuraciones concretas, no una conclusión universal
sobre cualquier versión o configuración del modelo.

Persisten español mal formado, palabras sin traducir y cambios de sentido.
Se descartaron ambas configuraciones para la app. Las vistas con contenido
comprensible pero gramática deficiente no certifican un uso completo correcto.
No se evaluó la captura en vivo ni la pintura con este proveedor experimental.

Se cerró su servidor y se retiró únicamente el GGUF descargado para este
experimento (2.497.280.256 bytes), conservando inferencias, dictámenes, huellas,
licencia y procedencia de descarga reproducible. El archivo no formaba parte
de la app. Los modelos instalados, capturas e informes se conservaron.

Fuentes del experimento: https://huggingface.co/Qwen/Qwen3-4B-GGUF y
https://github.com/ggml-org/llama.cpp/releases/tag/b11869.

## Búsqueda ampliada 8022: sin mejora del lote

Se compiló una variante aislada desde las fuentes exactas de 802101,
cambiando únicamente el ancho de búsqueda de4 a6 y el exponente de
normalización de longitud de1 a1,1. Se conservaron el modelo, tokenizer,
terminología, reparaciones de OCR y reglas de protección. Las fuentes y los
modelos de la aplicación permanecieron intactos; el diff del experimento
se guarda en `build/full-comics/translation-search8022/source.diff`.

Se ejecutaron 215 inferencias nuevas de fuente única para las mismas 228
regiones de las 124 vistas, sin errores de ejecución ni texto de referencia
en las entradas. Se cotejaron las 12 vistas con cambios y se reutilizaron
112 dictámenes solo por identidad de todas las salidas mostradas en la
misma ubicación. El resultado es 58 →58 sin aprobar: cero correcciones
completas y cero regresiones completas, pero dos empeoramientos parciales
en vistas que ya fallaban. Una instrucción mejoró, aunque su captura cortada
impide aprobar la vista completa. El ensayo se descartó para la app.

La mejor variante experimental evaluada conserva 62 →58 vistas sin aprobar
sobre124: del50 % al46,77 %, reducción relativa del6,45 %. Son cuatro vistas
completamente corregidas desde ese control; no es una tasa global de fallos
de todos los capítulos ni del APK instalado. Sus58 vistas sin aprobar incluyen
44 con errores claros de contenido,11 sin aprobar por corte y3 con dudas
de significado. Las categorías no cuentan errores individuales por palabra.
La revisión manual de cada palabra de los capítulos completos sigue pendiente.
La probabilidad de fallo por uso completo sigue desconocida y el objetivo
inferior al5 % no está acreditado. Pasaron37 pruebas de integridad de informes.

## Reconocimiento de todo el diálogo visible: 8023

Se alinearon las 2.265 palabras inventariadas de las mismas124 vistas completas,
incluyendo el texto que ningún detector encontró. Se excluyeron únicamente21
regiones identificadas como marcas de agua, detecciones sin diálogo y dos
onomatopeyas exentas; esta clasificación solo entra en la evaluación.
Se conservan los apóstrofos internos y los números. El control anterior tiene80
errores de palabra y la variante802101 tiene48: del3,53 % al2,12 %, reducción
relativa del40 %. Las vistas con discrepancias pasan de40 a24, sin regresiones
de palabra en este lote. Las25 eliminaciones de la alineación también incluyen
defectos de separación de palabras; no son25 omisiones físicas demostradas.

En107 vistas sin diálogo cortado quedan29 errores de1.867 palabras y15 vistas
con discrepancias. El denominador completo se conserva en el informe principal.
Este índice solo mide OCR: no mide traducciones correctas ni usos completos.
Hay28 vistas sin cortes con reconocimiento de palabras exacto que siguen sin
aprobarse en significado; la interpretación sigue necesitando mejoras.

## Comparación de entrada normalizada: 8023

Se recuperó temporalmente una única copia del mismo Qwen3-4B-Q4_K_M verificado
para corregir una diferencia del experimento anterior. La función nativa
PrepareInput preparó las215 fuentes únicas:206 cambian únicamente mayúsculas
y minúsculas, y ninguna cambia palabras o puntuación. Modelo, prompt, runtime
y muestreo permanecen iguales a la configuración recomendada anterior.
Se revisaron las124 vistas y228 regiones nuevas. La variante normalizada mejora
el propio ensayo Qwen de89 a74 sin aprobar, pero frente al modelo de Luma
empeora de58 a74: diez correcciones completas y26 regresiones. Se descartó.
El servidor se cerró; la copia restaurada del GGUF sigue en la caché experimental.

## Traductor local especializado: 8024

Se evaluó HY-MT1.5-1.8B-Q8_0 mediante215 llamadas locales independientes sobre
las mismas fuentes normalizadas, usando el prompt y muestreo de traducción
de su ficha oficial. Las228 regiones originales conservan fuentes y coordenadas.
No se proporcionaron referencias, inventarios humanos ni imágenes a la inferencia.
Todas las124 vistas tienen un nuevo dictamen frente al diálogo original completo.
Resultado:58 a57 sin aprobar,15 correcciones completas y14 regresiones; entre
las107 vistas sin cortes:41 a40. La mejora neta es insuficiente para sustituir
el proveedor actual. No se modificaron los modelos ni el uso normal de la app.

La licencia es Tencent HY Community License Agreement, con restricciones
territoriales, de redistribución y de uso de salidas para entrenar otros modelos.
Este ensayo evalúa HY de forma privada; sus salidas no entrenan otro modelo y
no se prepara su distribución. Se guardan licencia, revisión, SHA-256, respuestas
crudas y dictámenes. El servidor se cerró al acabar la inferencia.
Fuentes: https://huggingface.co/tencent/HY-MT1.5-1.8B-GGUF y
https://github.com/Tencent-Hunyuan/Hy-MT.

Los tres resultados anteriores corresponden a vistas guardadas, una por capítulo.
La revisión manual de todas las palabras de los124 capítulos y la validación
de usos completos siguen pendientes. No se ha acreditado el objetivo inferior al5 %.

## Recuperación conservadora de diálogo muy corto: 8024

Se inspeccionaron todas las detecciones de las124 capturas:805 recuadros,
19 con menos de dos letras. El cálculo de orientación por eje principal puede
deformar una letra con serifas y hacer que desaparezca un globo entero.
La variante vuelve a leer el recuadro vertical y una ampliación acotada con
ambos lectores incluidos. Solo acepta el pronombre inglés I con puntos
suspensivos si las cuatro lecturas son compatibles y tienen confianza mínima
de0,95; el detector debe superar0,90. Rechaza trazos sueltos, letras ambiguas,
puntuación sola y recuadros que toquen texto existente. No hay identificadores
de capítulos ni respuestas esperadas en esta regla.

La compilación real802401 procesó las124 vistas,229 regiones y cero errores
de ejecución. Solo cambió una vista: se recuperó una omisión completa.
Resultado:58 a57 sin aprobar, una corrección y cero regresiones. Las123 salidas
completas idénticas conservan su dictamen anterior. El acumulado frente al
control801901 es62 a57, cinco correcciones y cero regresiones restantes,
reducción relativa del8,06 % en las mismas vistas.

El OCR pasa de48 a47 errores sobre las mismas2.265 palabras; frente al control
de80 errores, la reducción relativa es41,25 %. Quedan23 vistas con discrepancias
de palabras. Entre las107 vistas sin cortes:29 a28 errores de1.867 palabras,
y15 a14 vistas con discrepancias. Estos índices no son la probabilidad de
fallo de la app. No se eliminan del denominador palabras que el detector omita.

Se inspeccionó el único dibujo nuevo: el texto recuperado cabe en su globo,
sin restos visibles del original a la escala revisada. Las123 fotografías
restantes se enlazan desde sus versiones anteriores. Eso no añade una
aprobación visual nueva de todas las superposiciones.

Pasaron ocho controles de la regla y las37 pruebas nativas de geometría,
además de recuperación, superposición y barra. La compilación802402 activa
solo esta recuperación corta en el valor predeterminado de Windows. Los
lectores adicionales de consenso siguen fuera del uso normal. La comprobación
de esta configuración normal tiene una pasada separada sobre las124 vistas,
sin parámetros de activación ni lectores adicionales; no se mezcla su tasa
con la variante combinada802401.

Esta comprobación normal terminó las124 vistas y229 regiones, sin errores
de ejecución:62 a61 sin aprobar, una corrección completa y cero regresiones.
Las123 salidas idénticas conservan exactamente el dictamen del control normal
anterior. En107 vistas sin diálogo cortado:45 a44 sin aprobar. La reducción
relativa de1,61 % corresponde exclusivamente a este control normal, mientras
que el8,06 % anterior corresponde a la variante experimental combinada.
El dibujo nuevo coincide en todos sus campos mostrados con el ya inspeccionado.
Pasaron las42 pruebas de integridad de los informes. No se entrenaron pesos,
no se sustituyeron modelos de traducción y no se creó APK ni ZIP nuevo.

Se inició un recorrido separado de todos los archivos de los124 capítulos
con la configuración normal corregida802402, un trabajador y reserva de4 GiB.
El control anterior801704 continúa desde su checkpoint. Los resultados de ambas
versiones se guardan por separado y los contadores no equivalen a revisión
semántica ni a aprobación de todas las palabras.

## Lectores incluidos en el uso normal de Windows: 8025

La compilación802501 incorpora los dos lectores que antes solo se activaban
con rutas del experimento. Tanto Worker como el benchmark sin parámetros
especiales los buscan junto al ejecutable. Se cargan una vez, únicamente para
inglés, y conservan la política de acuerdo previamente evaluada. Si faltan los
archivos, permanece el lector anterior. No se entrenaron pesos ni se cambió
el modelo de traducción; son lectores OCR preentrenados ya descargados.

Una pasada nueva de las124 capturas originales,229 regiones y cero errores
de ejecución reproduce exactamente los campos mostrados y coordenadas del
ensayo802401 en todas las ubicaciones. No se proporcionan rutas de lectores,
activación especial, inventario ni referencia española a la inferencia. Se
reutilizan los dictámenes anteriores solamente después de comprobar esa
identidad de ubicación completa, sin aprobar automáticamente ningún fallo.
La integridad incluye el ejecutable, la instantánea, los resultados, las
entradas y todos los archivos de los lectores empaquetados.

Frente al uso normal802402:61 a57 vistas sin aprobar, cuatro correcciones
completas y cero regresiones nuevas, reducción relativa del6,56 %. Frente
al control801901:62 a57, cinco correcciones completas y cero regresiones
restantes, reducción relativa del8,06 %. En las107 vistas sin diálogo
cortado, el control inmediato pasa de44 a40 sin aprobar; el histórico,
de45 a40. Estas comparaciones comparten capturas y no se suman.

De las57 vistas sin aprobar quedan43 con defectos confirmados de contenido,
11 con diálogo cortado y tres con significado pendiente de resolver. El OCR
conserva47 errores de alineación de palabras sobre2.265 palabras esperadas;
los errores de alineación no equivalen automáticamente a palabras físicamente
omitidas. Ninguna de estas cifras mide probabilidad de fallo por uso completo.

Pasaron las43 comprobaciones de integridad de informes y las37 guardas
nativas de geometría, además de recuperación, barra y superposición. La
apertura mediante el control de escritorio no produjo una ventana verificable
de Luma; ese intento no se cuenta como prueba de uso real. Las fotografías
se reutilizan por identidad de los campos mostrados; no se afirma una nueva
revisión visual de todas las superposiciones.

El coordinador8025 termina primero el control congelado801704 y después
recorre los124 capítulos con802501, en una carpeta separada. Hay un solo
trabajador nativo en total, reserva de4 GiB de disco y espera si faltan3 GiB
de RAM antes de otra inferencia. El control intermedio802402 conserva sus
dos capítulos completos y sus parciales como evidencia histórica. La revisión
de cada palabra de todos los capítulos sigue pendiente y el objetivo de
menos del5 % de usos fallidos no se ha acreditado.

## Corroboración de formas con raíz conocida: 8026

Una palabra correcta puede faltar como token completo en el vocabulario
subpalabra del traductor. El nuevo corrector exige que dos lectores de
píxeles coincidan en su escritura, que solo cambie una letra del original
desconocido y que una raíz de al menos cuatro letras ya esté presente en
el vocabulario. Admite prefijos y terminaciones generales; no contiene
frases, identificadores de capítulos ni respuestas esperadas. Conserva
las guardas anteriores y rechaza contradicciones de números o negaciones.

Pasaron12 guardas nativas. En los372 recortes distintos ya conservados se
corrige un error adicional de reconocimiento y no empeora ninguno; el
puente de124 recortes se solapa con otro lote y no se suma como muestra
independiente. Sobre las lecturas guardadas de las124 vistas completas,
las discrepancias pasan de47 a45 en las mismas2.265 palabras esperadas.
No se eliminan del denominador palabras que el sistema no haya detectado.

Dos fuentes cambian y se tradujeron de nuevo con el modelo nativo actual.
Se revisaron las dos ubicaciones originales completas. Ambas traducciones
mejoran parcialmente, pero siguen sin aprobar: una omite un énfasis del
original y la otra añade una unidad temporal que no está visible. La
primera valoración provisional de corrección completa se retiró antes de
publicar el informe, aplicando el mismo criterio estricto de conservación
de contenido que en las otras vistas. No se atribuyen correcciones
completas ni una reducción de vistas fallidas a este control aislado.

La compilación802601 incorpora la regla en Windows y pasó37 comprobaciones
de geometría, además de recuperación, barra y superposición. Su verificación
nueva sobre las124 capturas usa píxeles originales y parámetros normales;
el inventario, las referencias y los dictámenes no se entregan a la app.

Se preparó una comparación de todos los capítulos actuales con Olympus,
incluyendo cada palabra que su OCR extraiga. Su lectura, alineación y
coincidencia literal son propuestas automáticas. Además, el registro de
diferencias nativas conserva todas las salidas modificadas en la misma
posición y todas las regiones sin pareja, aunque no activen alertas. Las
regiones duplicadas se contabilizan por separado; una región sin pareja
puede deberse a fragmentación o agrupación y no confirma una omisión.

La verificación nueva de Windows terminó las124 capturas y229 regiones,
sin errores de ejecución. Todos los campos mostrados coinciden con el
plan cotejado: dos vistas modificadas y122 idénticas. Resultado estricto:
57 a57 sin aprobar, cero correcciones completas y cero regresiones nuevas.
El acumulado del control801901 permanece en62 a57, reducción relativa
del8,06 % de vistas sin aprobar. En107 vistas sin cortes permanece40 a40.
La mejora de OCR de47 a45 supone4,26 % menos discrepancias, pero no se
presenta como una reducción de fallos por uso completo. Pasaron45 pruebas
de integridad de métricas y registro de regiones, además de los controles
nativos anteriores.

Se inspeccionaron los dos renders nuevos. El texto cabe, pero en uno
persisten pequeños trazos del original fuera de la zona borrada. Se
conservan como defecto visual pendiente y no se aprueba toda la
superposición. Las otras122 fotografías se reutilizan por identidad de
los campos mostrados; no reciben una aprobación visual nueva. El render
de revisión no sustituye una prueba de captura, barra y movimiento en vivo.

El coordinador8026 conserva el recorrido801704 que ya estaba activo.
Después de terminar la comprobación de capturas y recuperar memoria,
se inició también el recorrido802601 en otra carpeta. Hay un trabajador
por recorrido, como máximo dos, y cada inferencia nueva espera si quedan
menos de3 GiB de RAM disponible. Cuando termine el control, se retirará
únicamente la siguiente etapa obsoleta802501, conservando sus resultados.
La comparación por palabras y el registro de todas las diferencias se
actualizan desde esos resultados. La revisión humana de cada palabra y
la probabilidad de fallo por uso completo siguen pendientes.

## Conservación de preguntas: 8027

El modelo puede devolver una afirmación aunque la fuente sea una pregunta.
La compilación802701 conserva la interrogación cuando el original contiene
una sola pregunta completa y la salida no tiene otros límites de oración.
La regla no cambia palabras. Excluye citas, preguntas indirectas, pasajes
de pensamiento o discurso referido, fuentes corruptas y originales retenidos.
Pasaron20 guardas nativas, incluyendo negaciones, números y casos que deben
permanecer intactos. No se entrenaron ni descargaron pesos nuevos.

Se aplicó primero la regla a18.179 regiones de un recorrido histórico de los
124 capítulos. Se revisaron también229 regiones de las vistas fijas y17.426
regiones del control disponibles en esa instantánea. Los lotes se solapan:
no se suman como muestras independientes. Las variantes modificadas se
cotejaron contra los originales. Corregir la interrogación no aprueba un
pasaje que todavía contiene otro defecto.

El ejecutable Windows nuevo volvió a traducir las229 fuentes OCR de las
124 vistas fijas; recibió únicamente texto reconocido y coordenadas, sin
referencias españolas ni respuestas esperadas. Las229 salidas coinciden
con la predicción de la regla final. Hubo una ubicación modificada, cuyo
significado se cotejó completo, y123 dictámenes reutilizados solamente
después de comprobar identidad de fuente, traducción y coordenadas. No se
repitieron la captura ni el OCR en esta prueba de traducción.

Resultado:57 a56 vistas sin aprobar, una corrección completa de significado
y cero regresiones nuevas. Reducción relativa inmediata:1,75 %. Frente al
control inicial de las mismas vistas:62 a56, seis correcciones completas y
cero regresiones restantes, reducción relativa del9,68 %. En107 vistas sin
diálogo cortado:40 a39 sin aprobar. El OCR mantiene45 discrepancias sobre
las mismas2.265 palabras esperadas; esta regla no modifica el reconocimiento.

Pasaron47 pruebas de integridad y las37 guardas nativas de geometría, además
de los controles de recuperación, barra y superposición. El render nuevo
conserva pequeños trazos originales fuera del borrado: el significado está
aprobado, pero la apariencia de toda la superposición no. Las otras123
fotografías se reutilizan por identidad; no recibieron una inspección visual
nueva. El ensayo no sustituye un uso completo en vivo.

El control nativo anterior terminó los124 capítulos sin errores de ejecución.
Su siguiente etapa obsoleta se retiró conservando los informes. El recorrido
del núcleo802601 continúa desde sus capítulos terminados, sin reiniciarse.
El cuerpo del traductor y el reconocimiento no cambiaron en802701; se
verificó esa equivalencia en las fuentes y con la retraducción real anterior.
Para los capítulos completos se conservan sus resultados nativos y se aplica
solo la regla final validada. Esos informes derivados identifican núcleo,
compilación de presentación y hashes; no se presentan como nuevas inferencias
de OCR ni del decodificador802701. Las tablas con Olympus incluyen cada
palabra que su OCR proponga y el registro de diferencias conserva todas las
salidas modificadas, sin limitarse a las que activan alertas.

La revisión humana de todas las palabras de los124 capítulos sigue pendiente.
La probabilidad de fallo por uso completo no está medida y no se acredita el
objetivo de menos del5 %. Reducir vistas sin aprobar en esta muestra no
equivale a medir esa probabilidad.

La comprobación de publicación verifica los hashes de los informes de origen,
los índices de región y cada token del OCR español en su orden original.
La primera instantánea actual comprobada contiene23.836 tokens en12 tablas:
ninguno perdido, cambiado, repetido o reordenado por el formato compacto.
Las tres páginas locales responden correctamente y distinguen el alcance de
las pruebas. Esta comprobación de integridad no valida la lectura del OCR
español, la alineación con el dibujo ni el significado de sus palabras.

## Recuperación conservadora de aperturas: 8028

El recorrido de las fuentes de los124 capítulos del control encuentra68
bloques con una primera palabra seguida de interrogación o exclamación.
Algunas aperturas desaparecen aunque el resto del bloque se traduzca.
Se realizaron178 inferencias nativas para los originales, las aperturas y
los cuerpos distintos, más42 para comprobar la normalización de mayúsculas.
No se entregaron referencias ni traducciones esperadas al modelo.

La variante inicial produjo traducciones ambiguas de palabras aisladas y
no se incorporó. La regla final admite un vocabulario cerrado de funciones
del habla: preguntas, llamadas, órdenes breves y respuestas. Excluye sonidos,
risas y fragmentos nominales o adjetivales que requieren resolver contexto,
número o género. No contiene términos de la serie ni respuestas españolas.
Normaliza únicamente la entrada de la apertura. Solo la añade cuando una
traducción independiente del cuerpo conserva todas las palabras de la
traducción completa, en el mismo orden. La salida anterior se conserva como
sufijo sin cambiar sus bytes. Los nombres copiados y las traducciones
retenidas no autorizan una recuperación.

La compilación802801 incorpora esa regla en el camino normal del traductor.
El decodificador y las políticas anteriores permanecen sin cambios. La
cancelación por movimiento conserva una misma generación durante las
inferencias adicionales. Pasaron28 guardas de la regla,37 de geometría y
los controles nativos de recuperación, barra y superposición. Pasaron49
pruebas de integridad y procedencia de los informes.

Una prueba real con el ejecutable empaquetado volvió a traducir229 regiones
de las124 vistas fijas y los68 candidatos ampliados:297 registros, sin
errores de ejecución. Las124 vistas fijas conservan exactamente su texto
y sus coordenadas:56 a56 sin aprobar, cero correcciones y cero regresiones
en ese control. Su reducción histórica permanece en9,68 %; el OCR mantiene
45 discrepancias sobre2.265 palabras. No se repitió la captura ni el OCR.

Se cotejaron todas las17 salidas ampliadas que modifica la política final
contra sus píxeles originales y las referencias Olympus disponibles. Una
referencia inicialmente sin alineación se localizó y cotejó manualmente.
Once ubicaciones quedan completamente corregidas, cinco recuperan la
apertura pero conservan otros defectos y una permanece pendiente por su
referencia pronominal. No se observaron regresiones completas nuevas en
este diagnóstico. Las51 candidatas sin cambios no reciben una evaluación
semántica nueva. Este grupo diagnóstico tiene otra selección y no se suma
al control fijo ni se presenta como nuevo porcentaje global de errores.

Se crearon e inspeccionaron17 renders mediante el pintor de producción:
todo el texto traducido cabe. Persisten algunos trazos del original y, en
una ubicación, una cláusula visible que el OCR no había incluido. La
apariencia de toda la superposición sigue sin aprobarse; no se sustituye
una prueba completa en vivo con una fotografía renderizada.

El recorrido del núcleo802601 continúa desde sus resultados conservados.
Un segundo paso usa el nuevo ejecutable únicamente para las regiones con
aperturas elegibles de los capítulos terminados. Comprueba que toda salida
sin recuperar sea idéntica y que cada salida recuperada conserve el cuerpo
anterior íntegro. Los demás registros se reutilizan, con marcas que
distinguen las inferencias nuevas del núcleo de OCR conservado. Las tablas
de palabras con Olympus y el registro de todas las diferencias se actualizan
con ese resultado. No se reanuda ninguna etapa obsoleta ni se reinicia el
recorrido completo. La revisión de cada palabra de los124 capítulos y el
objetivo de menos del5 % de fallos por uso siguen pendientes.

## Letras corroboradas y preguntas cortas: 8029

Se probaron dos extensiones generales. La primera comprueba preguntas
iniciales de dos a cuatro palabras encabezadas por una forma interrogativa
o auxiliar inglés. Un barrido de los124 capítulos del control reúne35
candidatos distintos y98 registros de traducción nativa real. La comparación
excluye los archivos transitorios de trabajo. Solo una pregunta cumple la
recuperación estricta: el cuerpo traducido independientemente conserva las
mismas palabras que la salida existente y la apertura no pierde negación.
Los otros candidatos permanecen intactos. Pasaron17 guardas de esta regla.

La segunda extensión permite corregir una letra omitida o duplicada en una
forma con raíz conocida, aunque la palabra completa no figure en el
vocabulario subpalabra. Ambos lectores de píxeles deben dar la misma grafía,
con una sola edición, anclas contiguas e idéntico contenido numérico y
negativo. No cambia palabras conocidas ni nombres sin respaldo de raíz.
La sustitución es por palabra: no autoriza otros cambios del párrafo. No
contiene términos de la serie ni respuestas españolas. Pasaron12 guardas.

La selección se comprobó sobre372 recortes distintos ya cotejados, con un
puente solapado registrado aparte: ninguno empeora. También se congelaron
4.285 regiones de30 capítulos terminados y las229 regiones de las124 vistas
fijas. Aparecen seis cambios de palabra en capítulos completos; uno coincide
con la vista fija modificada y no se suma como otra ubicación independiente.
Las lecturas guardadas proceden de píxeles reales; esta prueba aislada de
selección no ejecuta de nuevo los modelos OCR. Las transcripciones de
evaluación solo puntúan las salidas obtenidas y no son entradas del selector.

Se cotejaron todas las siete ubicaciones modificadas contra sus imágenes
inglesas y Olympus. Cinco referencias que no tenían una alineación automática
útil se localizaron y verificaron visualmente. Hay tres correcciones completas
de significado y cuatro mejoras parciales que conservan otros defectos:
contenido del globo incompleto, un verbo mal reconocido o un sentido verbal
equivocado. No se observaron regresiones completas nuevas en este diagnóstico.
Estas cuentas no se suman a las124 vistas fijas.

La compilación802901 integra ambas reglas y mantiene los pesos anteriores.
Se repitieron reconocimiento y traducción nativos sobre las124 vistas
originales y siete estados de lectura adicionales:131 imágenes,246 regiones,
cero errores de ejecución. Los estados adicionales usan exactamente la
ventana registrada en la pasada anterior, sin elegir un recorte mejor. No
se proporcionan textos, referencias ni rutas especiales de lectores a la app.
Todas las fuentes nuevas de las229 regiones fijas coinciden con la predicción
del selector puro. Solo una vista fija modifica su texto y se coteja completa;
las otras123 reutilizan su dictamen por identidad de todos los campos
mostrados y coordenadas.

El control semántico permanece56 a56 sin aprobar: la vista modificada mejora
una palabra pero conserva otro error. La reducción histórica de las mismas
vistas permanece en9,68 %. El OCR pasa de45 a44 discrepancias sobre las
mismas2.265 palabras; no se retiran del denominador palabras no detectadas.
El2,22 % de reducción relativa de discrepancias OCR no es una reducción
medida de fallos por uso. Pasaron51 comprobaciones de integridad y37 de
geometría, además de recuperación, barra y superposición.

Se inspeccionaron ocho renders nuevos de producción. El texto traducido cabe,
pero quedan algunos trazos del original y texto visible no detectado fuera
de las regiones. No se aprueba toda la apariencia ni se cuentan estas fotos
como usos nuevos completos de captura, barra y movimiento en vivo.

El recorrido completo del núcleo conservado continúa. El paso8029 vuelve a
seleccionar palabras desde el texto anterior al consenso y los dos lectores
originales registrados; así reproduce la entrada real de la política de la
app, sin aplicar dos veces el corrector anterior. Se reutilizaron24 informes
ya terminados solo después de comprobar, en cada fila, que esa selección
desde las entradas originales era idéntica a la fuente publicada. Los bytes
de los informes y las traducciones no cambiaron; se conservan las marcas
anteriores y pruebas de equivalencia de sus entradas. Los capítulos nuevos
usan directamente las entradas originales y el vocabulario del ejecutable
congelado, con hashes de ambos selectores y del programa de ejecución.

Solo se ejecuta traducción nativa nueva para las fuentes modificadas o las
preguntas elegibles. Las tablas actuales con Olympus incluyen cada palabra
propuesta por su OCR y conservan todos los cambios y regiones sin pareja.
Los informes derivados no se presentan como nuevo reconocimiento de todos
los capítulos. La revisión de cada palabra de los124 capítulos y la
probabilidad de fallo por uso completo siguen pendientes; no se acredita
el objetivo de menos del5 %.

La comprobación de las tablas actuales conserva47.901 tokens del OCR español
en35 pares de capítulos, en el mismo orden y con índices y hashes válidos.
No falta ni cambia ninguno por la compactación. Esta instantánea verifica el
formato y su procedencia; no aprueba la lectura, la alineación ni el significado
de cada palabra de Olympus.


## Recuperación de frases finales: 8030

Se examinaron los124 informes completos del recorrido histórico801704,
con15.879 regiones no promocionales. La selección detectó98 posibles
omisiones de frases finales completas;84 no tenían alertas automáticas.
Es un diagnóstico dirigido, no una estimación de la probabilidad de fallo.
No se han revisado visualmente todas las palabras de los capítulos.

La prueba inicial ejecutó294 traducciones nativas independientes del bloque,
su encabezado y su frase final. Once adiciones superaron el primer filtro.
Se cotejaron los once cambios con los píxeles originales ingleses y la
ubicación española de Olympus. Una adición cambiaba varios destinatarios a
uno; la regla final la rechaza por esa discordancia explícita. Se recuperan
diez frases: seis correcciones completas de contenido y cuatro mejoras
parciales sin aprobar. Dos adiciones conservan defectos gramaticales. La
identidad de las palabras anteriores no garantiza que las nuevas sean buenas;
las correcciones parciales no se presentan como traducciones resueltas.

La compilación803001 incorpora la recuperación en el trabajador normal.
Solo añade una frase capturada y terminada si una traducción independiente
del encabezado reproduce exactamente las palabras de la salida existente.
Conserva ese prefijo byte por byte y comprueba copia de inglés, negación,
números, repetición y contradicción explícita del número de destinatarios.
Excluye texto citado, finales cortados y onomatopeyas breves. No recibe
respuestas esperadas ni texto de Olympus y no modifica pesos del modelo.

Se ejecutaron334 traducciones con el nuevo ejecutable:229 regiones de las
124 vistas fijas, siete ubicaciones de control anteriores y98 candidatos.
No hubo errores de ejecución. Las229 regiones fijas y las siete ubicaciones
anteriores mantienen exactamente el mismo texto. Se reutiliza su dictamen
por identidad:56 de124 vistas siguen sin aprobar y la reducción histórica
semántica del control permanece en9,68 %. El OCR sigue con44 discrepancias
sobre las mismas2.265 palabras. Los resultados adicionales no se suman a
ese control ni son un porcentaje de fallo de toda la aplicación.

Pasaron18 guardas de recuperación de frases finales,37 de geometría,
las comprobaciones de recuperación, barra y superposición y54 pruebas de
integridad del informe en22,488 segundos. Se inspeccionaron los diez renders
nativos: el texto traducido cabe y se lee, pero cuatro conservan pequeños
trazos originales. Se distingue aprobación de contenido de calidad visual.
No son capturas nuevas ni pruebas completas de uso en vivo.

El paso `tools/postprocess_full_tails8030.py` conserva todos los registros del
paso8029, traduce con el ejecutable congelado solo los candidatos y comparte
el JSONL inmutable cuando nada cambia. La nueva comparación compacta está en
`comparison8030-tails` y `review8030-tails`; conserva también todas las
palabras propuestas por el OCR español. La instantánea de comprobación
incluye43 tablas y61.205 tokens, sin pérdidas ni cambios de orden. Ese cotejo
verifica el almacenamiento y la procedencia; no aprueba su significado.
La revisión palabra por palabra y menos del5 % de fallos por uso siguen
pendientes. No se crea APK ni se utiliza el teléfono.


## Adaptación real de pesos: 8031–8033

El nuevo material contiene217 parejas bilingües; se separó por capítulo antes
de entrenar. Se cotejaron184 propuestas con sus imágenes y se aceptaron129
etiquetas:86 para entrenamiento,14 para validación y29 de dos pruebas.
Las252 imágenes conservadas son selecciones acotadas de siete parejas, no
capítulos completos revisados. Quedan41 capítulos de prueba sin inspeccionar.

Se entrenaron tres adaptadores LoRA de294.912 parámetros sobre el OPUS
original, con base congelada y pesos de la app intactos. El primer piloto
no corrigió contenido del lote reservado y añadió una omisión. Los dos
ensayos ampliados usan86 diálogos reales y130 concatenaciones de esos mismos
diálogos. En la validación fija, los errores confirmados pasan de5 a3 sobre14
diálogos; tres casos necesitan contexto. El40 % es una reducción relativa
solo de esos cinco errores, no una probabilidad de fallo de la aplicación.

La nueva prueba reservada de16 diálogos produce una corrección completa y una
recuperación parcial con redacción defectuosa, sin pérdidas nuevas. Tras
inspeccionarse, se conserva como control conocido para el tercer ensayo y
no se vuelve a llamar prueba ciega. Sus referencias no entran en gradientes.

En el núcleo flotante sobre las229 fuentes OCR de124 vistas, el segundo
adaptador corrige12 fragmentos de contenido pero introduce3 regresiones y2
pérdidas parciales adicionales. El tercero, con penalización respecto a la
base y dropout desactivado, corrige9 e introduce2 regresiones y1 pérdida
parcial adicional. Ambos copian un artefacto de la fuente. No son nuevos
usos completos ni repiten las reparaciones y recuperaciones de producción.

Pasaron16 guardas del segundo ensayo y10 del tercero. No se incorpora ninguno
a la app. El control instalado sigue con56 de124 vistas sin aprobar y la
reducción histórica de9,68 %. No se entrenaron pesos OCR; la lectura de cada
palabra y el objetivo de menos del5 % por uso siguen pendientes. Protocolos,
criterios, hashes y límites están en[la revisión de adaptación local](local-model-adaptation.md).


## Ampliación de datos cotejados: 8034

Se inspeccionaron 111 propuestas nuevas: 77 diálogos para entrenamiento,
11 para otra selección de validación y 23 excluidas. El entrenamiento pasa
de 86 a 163 diálogos originales, más 254 concatenaciones explícitas. Los
312 pasos siguen una regla proporcional fijada antes de generar resultados.
Se descargaron 167 imágenes, unos 42 MB; los 41 capítulos de prueba aún
sin inspeccionar permanecen intactos.

La validación fija pasa de cinco errores de la base y tres del candidato
anterior a dos ahora, manteniendo tres dudas de contexto. El 60 % relativo
frente a la base se limita a esa muestra de 14 diálogos. En las 11 entradas
nuevas se recuperan tres unidades de contenido, pero aparecen una regresión
confirmada y un cambio de tiempo que requiere contexto. No se acredita una
tasa global de fallo.

El control del núcleo sobre 229 fuentes conservadas de 124 vistas presenta
79 cambios: 35 dictámenes por identidad exacta y 44 variantes nuevas cotejadas.
Se corrigen 11 regiones de contenido capturado, sin nuevas regresiones completas
confirmadas en ese control. Aun así, conserva una pérdida parcial adicional,
un artefacto copiado y dos cambios de relación pendientes de contexto.
El núcleo no repite captura ni OCR y no aplica las recuperaciones de producción.

Las pruebas conocidas de 16 y 13 diálogos también se conservaron. En la primera
se recuperan dos traducciones completas y una parcialmente; en la segunda se
corrige una omisión, pero aparece una salida sin palabras, solo signos, y una
pérdida parcial dentro de otro diálogo ya fallido. La salida degenerada se
reproduce tanto en bfloat16 como en float32. No se reemplazó por el resultado
de un diagnóstico ni se descartó de las cuentas.

Pasaron 18 guardas de procedencia, separación, matemáticas, pesos y auditoría;
el modelo no superó los criterios de calidad. La auditoría de formato revisó
566 salidas de base y candidato, no 566 muestras independientes ni significados
certificados. El adaptador no se incorpora y no se exporta otro modelo nativo.
La app instalada mantiene 56 de 124 vistas sin aprobar y la reducción histórica
del 9,68 %. Todas las comparaciones de esta iteración están en
`build/finetune8034/index.html`; la revisión completa de capítulos y menos del
5 % de fallos por uso siguen pendientes.
