# Datos de evaluación

Esta carpeta contiene los archivos pequeños y versionables que permiten
interpretar y reproducir las pruebas. No contiene los modelos instalados en la
app ni todos los capítulos descargados.

| Directorio | Contenido |
|---|---|
| `bilingual-comics/` | Muestras y referencias bilingües del banco inicial; también se utilizan como assets de pruebas instrumentadas. |
| `full-comics/` | Inventarios y controles del corpus ampliado. |
| `finetune8031/` | Primer protocolo, particiones y revisión de la adaptación OPUS. |
| `finetune8032/` | Evidencia del segundo ensayo. |
| `finetune8033/` | Evidencia del tercer ensayo. |
| `finetune8034/` | Ampliación de datos, protocolos separados de datos y entrenamiento, curación, decisiones semánticas y criterios de aceptación. |
| `stability8035/` | Dos intensidades del adaptador existente; selección previa a controles, revisión y descarte. |
| `onpolicy8036/` | Nuevo entrenamiento con prefijos generados solo desde fuentes de entrenamiento; selección de tres puntos y descarte. |
| `decoder8037/` | Cuatro variantes de decodificación, revisión de validación y rechazo. |
| `qe8038/` | Procedencia de COMET y base nativa real; revisión anterior a las puntuaciones y rechazo del selector. |
| `roundtrip8039/` | Verosimilitud inversa y acuerdo entre puntuaciones, con criterios congelados y rechazo. |
| `temporal8040/` | Protección temporal, revisión de 25 + 258 fuentes, enmienda de normalización y descarte. |

Las imágenes, salidas completas, páginas de comparación, entornos y adaptadores
experimentales permanecen en `build/`. Los pesos distribuidos y su manifiesto
están en `assets/models/opus-en-es/`.

Las particiones de entrenamiento, validación y prueba se conservan. No cambiar
una referencia, un hash o una decisión revisada para ocultar un fallo. Un ensayo
posterior debe tener su propia identidad y documentar sus cambios.

El ensayo más reciente es el 8040; **no está instalado**. Los resultados de
8031–8034 están en [el informe de adaptación](../docs/local-model-adaptation.md)
y las continuaciones en [estabilidad](../docs/model-stability.md) y
[selección de traducciones](../docs/translation-selection.md).
Una reducción de errores en una muestra no certifica la probabilidad de fallo
de la aplicación sobre todos los capítulos.
