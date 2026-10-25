# Pruebas bilingües de 60 capítulos

Evaluación del 23 de octubre de 2026. **Luma todavía presenta errores de
lectura y de significado. No se ha establecido una precisión semántica del
corpus ni se ha entrenado un modelo nuevo con estos capítulos.**

## Material y acceso

El archivo del usuario contiene 120 enlaces: capítulos 1–30 de dos series,
cada uno en inglés y español. `benchmarks/bilingual-comics/sources.json`
conserva los enlaces y el SHA-256 del archivo original.

| Inglés | Español |
|---|---|
| Absolute Regression | Geom Mugeuk |
| The Greatest Estate Developer | Loco Frontera |

Inicialmente Olympus devolvía páginas HTTP 200 con nueve imágenes temporales
`/cp/cp-*.jpg` que respondían 404. Recargar el lector en el navegador permitió
recuperar sus listas reales. Se registraron las listas observadas, sus
recuentos y una comprobación FNV-1a de los nombres en `spanish-reader.json`.

Se descargaron y verificaron **2.419 imágenes de los lectores españoles**.
Incluyen créditos y páginas promocionales que deben descartarse antes de
preparar datos de entrenamiento. El inventario inglés contiene 824 enlaces
a imágenes; se descargaron 60 imágenes de muestra, una por capítulo.

Las imágenes, HTML y diálogos permanecen en `build/bilingual-quality/`.
Los capítulos no se incluyen en el APK ni en el paquete Windows.

## Cobertura ejecutada

La selección toma la imagen central de cada capítulo y, para la vista
estrecha, su recorte central de 390 × 844 píxeles. Es una selección fija,
anterior a revisar si una traducción era buena o mala.

| Pasada nativa de Windows | Imágenes | Recortes | Registros de regiones | Excepciones |
|---|---:|---:|---:|---:|
| Página central completa | 60 | 587 | 616 | 0 |
| Vista estrecha de esa página | 60 | 60 | 78 | 0 |

**No es una lectura completa de los 60 capítulos.** Los registros de ambas
pasadas pueden solaparse. Dieciséis recortes estrechos y dos páginas de
muestra no produjeron texto; hay que inspeccionar sus píxeles para distinguir
una zona de dibujo de una omisión del OCR. Cero excepciones mide estabilidad,
no la corrección de los diálogos.

La vista estrecha corresponde a píxeles de Windows. No reproduce la densidad
de píxeles, permisos ni el OCR ML Kit de un teléfono Android.

## Emparejamiento de referencias

Las dos ediciones recortan las páginas de forma diferente. Se reconstruyeron
las tiras españolas y se buscaron las escenas por el dibujo, con correlación
visual y comprobaciones geométricas.

Se obtuvieron 57 coincidencias automáticas fuertes. Las muestras de Loco
Frontera 15, 17 y 20 se confirmaron visualmente con una búsqueda por color de
la página completa. Las 60 escenas tienen una referencia correspondiente;
las tres confirmaciones manuales están fijadas a hashes de sus imágenes en
`visual-alignments.json`. Una coincidencia del dibujo no certifica la
transcripción ni la traducción.

Se revisaron visualmente ocho segmentos, registrados como revisión del
asistente, sin presentarlos como anotaciones humanas independientes. El visor
permite escribir el inglés correcto, revisar la traducción y exportar las
confirmaciones del usuario. No calcula un porcentaje semántico a partir de
estos ocho ejemplos seleccionados.

## Cambios aplicados a la app

El núcleo compartido de Android y Windows repara algunas confusiones de OCR
antes de traducir:

- Cifras dentro de palabras largas, como `ANCE5TOR5` y `D1SCIPLES`, solo si
  existe una única palabra completa compatible en el vocabulario del modelo.
- La letra O confundida con cero en una medida con prefijo numérico y una
  unidad conocida, como `5OCM` → `50CM`.
- Conserva números, identificadores, direcciones, rutas y fragmentos ambiguos.

La comparación detectó una regresión de desarrollo: interpretar `QUE5T/ON`
como la palabra `QUEST` introducía otro significado. Se corrigió el límite de
palabra para conservar ese fragmento. Las pruebas incluyen direcciones web,
correos, versiones de productos y medidas dentro de identificadores.

En las dos muestras estrechas comprobadas con sus viñetas españolas:

- La salida que contenía `ance5tor5` recupera «nuestros antepasados». Todavía
  admite mejoras de redacción y matiz verbal.
- La salida que contenía `5ocm` pasa a conservar la medida «50 cm».

En la pasada de escritorio, ese mismo bocadillo de los antepasados conserva
otros errores de OCR y una oración defectuosa. Corregir una palabra no aprueba
automáticamente la oración completa ni todas las resoluciones.

Los pesos OPUS y sus hashes permanecen iguales. La mejora está en la
preparación del texto y conserva el funcionamiento sin conexión.

## Errores comprobados que siguen abiertos

En Absolute Regression 21, el dibujo dice que alguien tiene buen ojo para
juzgar a las personas. El OCR genera `40T` y el modelo produce una referencia
incorrecta a «40 años». La edición española usa una paráfrasis libre, por lo
que tampoco debe tratarse como una equivalencia literal palabra por palabra.

En The Greatest Estate Developer 30, `stand behind` se interpreta literalmente
como «estar detrás», aunque el contexto exige respaldar lo dicho o hacerse
responsable. Además, el recorte estrecho corta el principio del bocadillo.

También hay errores en las referencias. En Loco Frontera 20, el inglés
`simulation skill` aparece en español como «habilidad de estimulación»,
mientras Luma conserva correctamente «simulación». En esa misma escena,
`one shot it all` se convierte en «tome una foto de todo» aunque el dibujo
muestra beber; la traducción de Luma también necesita revisión en ese caso.
Imitar automáticamente la versión española podría empeorar el resultado.

Persisten letras decorativas mal leídas, partes de oraciones omitidas,
agrupaciones imperfectas y expresiones sin contexto suficiente. Estos casos
están visibles en el informe; no se sustituyeron por respuestas guardadas de
los capítulos.

## Validación y repetición

- 18 casos independientes de normalización y protección de identificadores
  pasaron a través del motor nativo real.
- Se auditó la preparación de los 616 + 78 registros guardados. Se reutilizó
  una traducción únicamente cuando el texto preparado era idéntico y el
  decodificador/modelo no habían cambiado: 603 registros de escritorio y 77
  estrechos. Hubo 13 y 1 inferencias nuevas, respectivamente. Esta repetición
  no vuelve a ejecutar captura ni OCR.
- En el POCO ARM64/Android 16 pasaron 7 casos de tokenización, 29 textos y 5
  casos nuevos de reparación, además de OCR, cancelación, recuperación,
  geometría y máscara. Suite: 16.266 ms. No es una pasada Android de los 60
  capítulos.
- Tras añadir la protección del dominio `5Ocm.com`, el APK final optimizado
  pasó otros 6 casos de reparación/protección, los 29 textos, cancelación y
  recuperación en el mismo teléfono: 16.237 ms. Esta prueba usa las entradas
  públicas de `LocalMarian` y no necesita desactivar R8. La suite anterior
  conserva las comprobaciones de OCR y geometría; no se repitió esa captura.
- Windows pasó OCR y traducción de la imagen de control `Hello world` →
  `Hola mundo`. Se verificaron los modelos y licencias del APK y Windows.
- La versión 1.0.0, código 6004, quedó instalada en el teléfono conservando
  sus datos. Se retiró el APK temporal de instrumentación.

El ajuste de pesos necesita pares de texto alineados y revisados. Antes de
entrenar hay que corregir las transcripciones, conservar las unidades y
nombres, identificar los fragmentos incompletos y reservar material que no
se use para desarrollar reglas ni entrenar. Los 60 capítulos actuales son un
banco de desarrollo; todavía no constituyen una evaluación semántica
independiente.

## Archivos

- `build/bilingual-quality/review.html`: visor local con inglés, español y
  resultados antes/después; se puede abrir en Brave conservando sus carpetas
  de imágenes junto al archivo.
- `reviewed-comparison.png`: dos ejemplos comprobados.
- `reviewed-segments.json`: ocho revisiones visuales del asistente.
- `review-summary.json`: cobertura y límites.
- `repair-audit.json`: reutilización de inferencias y cambios de texto.
- `mobile-translations.jsonl`, `desktop-translations.jsonl`: primeras pasadas.
- `final-mobile-translated-regions.jsonl`,
  `final-desktop-translated-regions.jsonl`: repetición con la preparación final.
- `android-final/android-model-summary.json`: pruebas físicas Android.
- `android-optimized-smoke.log`: comprobación del APK optimizado final.

APK final: `build/app/outputs/flutter-apk/app-release.apk`.
SHA-256: `df8ab0fe2e018be2d60a1cf00e3c5d18b97d6d29aff726df33d44354ccecc05e`.

Los scripts de preparación, alineación y revisión están en `tools/` con
prefijo o sufijo `bilingual`. Los comandos de evaluación usan el ejecutable
nativo de Windows y el CLI compartido compilados desde los fuentes actuales.
