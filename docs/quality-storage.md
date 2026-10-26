# Almacenamiento de las pruebas

No ejecutar `flutter clean` en este proyecto: `build/full-comics` conserva
capturas originales, informes y pruebas históricas que aún se necesitan.
Tampoco hace falta borrar archivos personales para continuar las pruebas.

El 24 de octubre se consolidaron 215 copias idénticas de archivos grandes
de 23 versiones Windows congeladas. Se recuperaron 7.078.448.311 bytes
(6,59 GiB), con dos archivos ocupados omitidos. Se conservaron las rutas y
el contenido; se verificaron los ejecutables y manifiestos. El informe es
`build/full-comics/storage-optimization.json`.

Los archivos idénticos comparten contenido mediante enlaces físicos NTFS
en `build/full-comics/immutable-file-content`. Se marcan como solo lectura.
No se debe editar una versión congelada: los cambios se hacen en las fuentes
y en la compilación mutable antes de crear otra versión de pruebas.
`tools/freeze_windows_engine.py` reutiliza este almacén para nuevas versiones,
sin vincular los archivos modificables de la compilación al contenido histórico.

La verificación `build/full-comics/storage-opt-verification/verification.json`
comprueba la reutilización, el contenido y la independencia de la compilación.
Las capturas y los informes quedaron fuera de la consolidación. Las galerías
nuevas enlazan las imágenes existentes, sin copiarlas para cada comparación.
La suma de tamaños lógicos de carpetas puede contar un archivo compartido
varias veces; no representa el espacio físico ocupado.

Para seguir ahorrando espacio: mantener los modelos en un único almacén,
congelar solo binarios nuevos, no crear ZIP para cada experimento, conservar
los resultados textuales y reutilizar las capturas originales. Los PNG
temporales de los recorridos se eliminan por el propio proceso únicamente
después de guardar los resultados completos del capítulo.

Las próximas ejecuciones de creación de versiones y recorridos conservan
una reserva de 4 GiB. Si no alcanza, se aplaza el trabajo nuevo conservando
los resultados previos. Los procesos que ya estaban en ejecución mantienen
su código cargado hasta terminar; no se reiniciaron para aplicar esta guarda.

La compresión NTFS intentada no comprimió archivos y no se atribuye ningún
ahorro a ella. La eliminación recursiva de cachés fue rechazada por la revisión
automática; este ahorro procede de consolidar contenido idéntico verificado.

También se cerró el servidor del ensayo alternativo descartado y se retiró
su único GGUF descargado por esta tarea: 2.497.280.256 bytes (2,33 GiB).
Se conservaron los resultados de ambas pasadas sobre las 124 vistas y su
procedencia verificada. El archivo puede descargarse otra vez por su revisión
y SHA-256 fijados; no era un modelo instalado de Luma. Su retirada libera el
espacio usado por el propio experimento, y se informa aparte del ahorro de
6,59 GiB obtenido al consolidar las versiones históricas.

En el control8023 se restauró temporalmente una sola copia verificada de ese
Qwen para igualar la preparación de entrada con la de la app. El ensayo8024
añade una sola copia HY-MT1.5-1.8B-Q8_0 de1.908.528.288 bytes. Ambos ensayos
usan el mismo runtime Windows ya descargado. Los servidores se cerraron al
terminar; las cachés de pesos están presentes y no se cuentan como espacio
liberado. No se añadieron paquetes de Android ni ZIP nuevos.

La inspección de texto corto conserva resultados JSON y reutiliza las124
capturas existentes. Emplea un único búfer BGRA temporal cada vez, que se
retira al terminar el proceso. La versión congelada802401 reutiliza el almacén
inmutable para sus archivos idénticos; no copia otra vez todos los modelos.
La versión normal802402 aplica la misma reutilización de contenido.
La pasada completa retomada en8024 ya usa la reserva de4 GiB del script actual.

## Integración Windows y memoria: 8025

Windows incluye los dos lectores ya evaluados, con sus diccionarios, respaldo
y licencia, en `assets/windows-ocr-readers`:44.559.053 bytes lógicos. Se
reutilizaron las descargas verificadas existentes; no se descargaron pesos
nuevos. CMake instala estos archivos solo para Windows, sin añadirlos al
paquete Flutter de Android. La instantánea802501 verifica cada SHA-256 y
reutiliza el almacén de contenido inmutable para los archivos grandes.

La ejecución simultánea de siete procesos nativos de QA agotó casi toda la
memoria física del equipo de16 GB. Se detuvieron únicamente los procesos de
prueba propios, conservando las salidas parciales. El control de124 vistas
se retomó con un único proceso nativo y unos6,5 GB libres. Esto fue presión
de memoria del entorno de pruebas, no una medición de fallos de la app.

Los recorridos completos usan ahora un trabajador por defecto y esperan
antes de iniciar otra inferencia si quedan menos de3 GiB de memoria física
disponible. El coordinador8025 ejecuta el control conservado y la versión
actual por turnos. Mantiene la reserva de4 GiB de disco y no cierra programas
del usuario. La reanudación de las vistas descarta solo el último grupo de
imagen posiblemente incompleto y vuelve a procesarlo desde sus píxeles.

## Referencias compactas por palabra: 8026

Las nuevas tablas de comparación pueden usar `--compact-ledger`: guardan
la palabra, sus índices de región y estado, y consultan los informes EN/ES
originales para el texto completo y las coordenadas. Los informes quedan
vinculados por SHA-256. No se vuelven a guardar el mismo párrafo y sus
coordenadas por cada palabra. La página de comparación usa directamente
estos índices y conserva las propuestas de palabras sin región de Luma.

La comprobación sobre124 tablas existentes reconstruyó144.482 registros
sin diferencias ni palabras perdidas. El formato equivalente pasa de
89.814.108 a24.805.630 bytes:72,38 % menos, o65.008.478 bytes evitados por
una pasada equivalente. Es una proyección de escritura futura; no se
presenta como espacio ya liberado. Los archivos históricos permanecen.
La comprobación de formato no aprueba la lectura ni el significado de
esas palabras. Solo se crean dos fotografías nuevas para la regla8026;
las122 restantes y todos los originales se enlazan desde su ubicación.

La versión congelada802601 reutiliza el almacén de contenido para los
modelos y bibliotecas idénticos. No se descargaron pesos ni se generaron
APK o ZIP nuevos para esta corrección.

## Regla final y reutilización verificable: 8027

La versión802701 reutiliza los mismos modelos y bibliotecas inmutables.
La validación de traducción usa las229 fuentes OCR conservadas, sin crear
nuevas capturas ni cargar lectores adicionales. Solo se añade una fotografía
de superposición; las otras123 se enlazan desde sus pruebas anteriores.
No se crean APK, ZIP ni nuevas copias de los pesos.

El recorrido de capítulos continúa con el núcleo802601 que ya estaba activo.
Los informes derivados8027 aplican un postprocesador pequeño y verificado a
cada capítulo terminado. Si ninguna salida cambia, el JSONL completo se
comparte mediante un enlace físico NTFS y se marca como solo lectura. Si
hay cambios, se escribe otro JSONL pequeño y se conserva el texto nativo
anterior. Los originales mantienen sus bytes, acreditados por SHA-256; no
se repite el OCR ni el decodificador para aplicar esta regla final. Las
marcas de finalización, hashes y alcance distinguen los resultados derivados
de una ejecución nativa nueva. No se debe reescribir un informe nativo
terminado que esté compartido de esta forma.

La comparación por palabras sigue usando índices de región compactos y
las imágenes originales existentes. Los nuevos trabajos mantienen la
reserva de4 GiB de disco. El recorrido completo conserva la espera de3 GiB
de RAM; la retraducción aislada de fuentes OCR, sin imágenes ni lectores,
se ejecutó con una espera de2,5 GiB y un único proceso de inferencia.

## Aperturas y fotos de diagnóstico: 8028

La compilación802801 vuelve a compartir los pesos y bibliotecas idénticos
con el almacén inmutable. Las inferencias adicionales usan solo texto de
regiones elegibles; no se descargan modelos ni se repite el OCR completo.
Los capítulos sin cambios comparten su JSONL mediante enlaces físicos
de solo lectura. Cuando hay una recuperación se escribe otro informe
pequeño, conservando cada fila, su procedencia y la traducción anterior.

Las comparaciones ampliadas usan los originales ya guardados. Se añaden
13 hojas bilingües de la variante exploratoria,17 recortes pequeños y17
renders de producción, con cinco hojas de contacto. No se copian capítulos
completos para estas fotografías. La comparación actual con Olympus sigue
usando referencias compactas por índice de región. Se mantienen4 GiB de
reserva de disco,3 GiB de espera para inferencias con imágenes y2,5 GiB
para la traducción aislada de texto. No se crean APK ni ZIP nuevos.

## Selección de letras y nueva comprobación de píxeles: 8029

La compilación802901 comparte otra vez los modelos y bibliotecas idénticos
con el almacén inmutable. No hay descargas ni pesos entrenados nuevos. Se
reutilizan las124 capturas existentes y solo se guardan siete ventanas de
lectura adicionales, tomadas en la posición registrada de sus originales.
Se generan ocho renders y dos hojas de contacto; las123 fotografías fijas
sin cambios se enlazan desde su ubicación anterior.

Los capítulos derivados comparten su JSONL de solo lectura cuando no hay
cambios. Si cambia una palabra o se recupera una pregunta, se conservan el
texto anterior, todos los registros y sus hashes; solo esas regiones o las
preguntas elegibles requieren traducción nativa adicional. Se usa el
tokenizador del ejecutable congelado, con SHA-256 fijado. La corrección
de palabras reutiliza las lecturas originales de los dos modelos OCR y no
repite su inferencia sobre todos los capítulos.

Se conservaron24 marcas anteriores y sus pruebas pequeñas de equivalencia
de entradas, sin duplicar los JSONL ni repetir el modelo de traducción. La
nueva comprobación de131 imágenes usó un único trabajador de prueba y la
espera de3 GiB de RAM; el paso derivado esperó a su finalización antes de
cargar otro modelo. La traducción aislada mantiene su espera de2,5 GiB y
todos los trabajos mantienen4 GiB de reserva de disco. No se crean APK o ZIP.


## Frases finales: 8030

El ejecutable803001 vuelve a compartir modelos y bibliotecas idénticos con
el almacén inmutable. No se descargaron modelos ni se entrenaron pesos.
Se conservan solo diez recortes pequeños de originales, sus diez renders,
tres hojas de contacto y seis comparaciones bilingües; no se duplican los
capítulos ni las124 capturas fijas. Los informes sin cambios comparten su
contenido de solo lectura mediante enlaces físicos NTFS.

La derivación8030 espera la validación nativa antes de inferir y solo
traduce candidatos. Mantiene2,5 GiB de RAM disponible antes de la traducción
aislada y4 GiB de reserva de disco; el recorrido con imágenes mantiene3 GiB.
No se reinicia el recorrido del núcleo ni se borran resultados. La instantánea
posterior a estas pruebas conserva aproximadamente18,29 GiB de disco libre.
No se generan APK, ZIP ni duplicados de pesos para Android.


## Entorno de entrenamiento y adaptadores: 8031–8033

Se añadió un entorno aislado `build/training-venv8031`, con dependencias
fijadas, y una sola copia de los pesos OPUS originales no cuantizados
de465.549.630 bytes. Los tres entrenamientos reutilizan esa base; guardan
solo adaptadores LoRA pequeños, salidas y procedencia. Los modelos ONNX de
la app permanecen idénticos. No se descargan modelos alternativos ni se
crean APK o ZIP.

Las252 imágenes bilingües ocupan alrededor de60 MB y se guardan una sola
vez. Los recortes de cotejo son hojas pequeñas; los informes mantienen
referencias y hashes, sin copiar capítulos completos. Las concatenaciones
de entrenamiento son texto, no imágenes duplicadas. Se conservan también
los resultados del OCR interrumpido, sin descartarlos ni presentarlos como
un recorrido completo.

El tercer ensayo reutiliza los datos y la base del segundo. Las salidas base
del control se reutilizan tras verificar procedencia y recarga exacta de la
validación; solo se ejecuta la nueva traducción candidata. La memoria CUDA
máxima registrada es aproximadamente1,12 GiB en el segundo ensayo y1,65 GiB
en el tercero. Se mantienen4 GiB de reserva de disco y esperas de memoria
antes de inferir. La instantánea posterior conserva aproximadamente12,45 GiB
libres. No se eliminan archivos personales, historial Git ni evidencia de
ensayos fallidos.


## Datos ampliados y cuarto adaptador: 8034

Se reutilizan el mismo entorno y la única base OPUS original. Las 167 imágenes
nuevas ocupan 42.156.701 bytes. Las 419 imágenes conservadas suman 102.984.298
bytes, unos 98,2 MiB; son selecciones de páginas, no nuevas copias de capítulos
completos. La vista previa de cotejo referencia los mismos originales y los
58 registros revisados inicialmente se contrastaron por identidad exacta con
la selección final. Se conservan sus hojas como evidencia.

El cuarto ensayo guarda otro adaptador pequeño y texto de resultados. No se
descargan otras bases, se duplican los modelos instalados ni se crea APK.
La memoria CUDA máxima registrada es de 1.765.566.976 bytes. Se mantienen
4 GiB de reserva; la instantánea posterior conserva unos 12,36 GiB libres.
No se borra ningún resultado fallido, archivo personal ni historial Git.
