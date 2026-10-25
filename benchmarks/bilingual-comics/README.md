# Banco bilingüe de desarrollo

`sources.json` indexa los 120 enlaces aportados por el usuario.
`spanish-reader.json` conserva las listas de imágenes observadas en el lector
normal tras recuperarse de un fallo temporal. `s` identifica la serie (`a`:
Absolute Regression, `g`: The Greatest Estate Developer), `c` el capítulo,
`d` su directorio, `n` el número de imágenes y `h` la comprobación FNV-1a.
En `f`, `1_{01-05}` representa los cinco nombres observados `1_01.webp` a
`1_05.webp`, en ese orden. La expansión comprueba el recuento y la suma.

`visual-alignments.json` fija tres emparejamientos confirmados visualmente por
el asistente a los hashes de sus imágenes. Son comprobaciones de escena;
no certifican las transcripciones ni el significado de todos los diálogos.

`ocr-normalization-cases.json` contiene frases sintéticas de regresión,
independientes de los diálogos del corpus. Se comparten con la instrumentación
Android mediante una carpeta de assets exclusiva del APK de pruebas.

Los capítulos, sus transcripciones y los informes están en `build/`, fuera
de los assets distribuidos. Este banco se ha utilizado para desarrollar la
app; no se presenta como conjunto independiente de validación semántica.

Detalles y cobertura: `docs/bilingual-comic-quality.md`.
