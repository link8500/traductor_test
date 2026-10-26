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

Las imágenes, salidas completas, páginas de comparación, entornos y adaptadores
experimentales permanecen en `build/`. Los pesos distribuidos y su manifiesto
están en `assets/models/opus-en-es/`.

Las particiones de entrenamiento, validación y prueba se conservan. No cambiar
una referencia, un hash o una decisión revisada para ocultar un fallo. Un ensayo
posterior debe tener su propia identidad y documentar sus cambios.

El 8034 es el candidato más reciente; **no está instalado**. Sus resultados y
regresiones se explican en [el informe de adaptación](../docs/local-model-adaptation.md).
Una reducción de errores en una muestra no certifica la probabilidad de fallo
de la aplicación sobre todos los capítulos.
