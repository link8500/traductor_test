"""Publish an auditable aggregate report, separate from production app metrics."""
import json
import shutil
import finetune8032_guards as g


def main():
    training=g.validate_checkpoint();folder=g.OUT/'lora-pilot'
    validation=g.read(g.META/'validation-meaning-decisions.json')
    fresh=g.read(g.META/'fresh-test-meaning-decisions.json');core=g.read(g.META/'regression-core-meaning-decisions.json')
    assert core['all_changed_outputs_reviewed'] and fresh['all16_outputs_reviewed']
    app=g.ROOT/'assets/models/opus-en-es/manifest.json';manifest=g.read(app)
    assert g.sha(app)==g.read(g.ROOT/'build/full-comics/windows-engine803001.json')['manifest_sha256']
    for name in ['encoder.onnx','decoder.onnx']:assert g.sha(app.parent/name)==manifest['files'][name]
    evidence=[g.META/n for n in ['protocol.json','dataset.json','validation-meaning-decisions.json','fresh-test-protocol.json',
        'fresh-test-labels.json','fresh-test-meaning-decisions.json','regression-core-meaning-decisions.json']]
    evidence += [folder/n for n in ['summary.json','run-input-proof.json','training-log.json','baseline-validation.json','candidate-validation.json',
        'fresh-test-summary.json','fresh-test-baseline.json','fresh-test-candidate.json','regression-core-summary.json','regression-core-changes.json']]
    evidence += [g.ROOT/'build/full-comics/finetune8032-tests.log']
    report=dict(schema=1,experiment='8032-expanded-opus-lora',application_build_unchanged='803001',actual_weight_training_completed=True,
        reviewed_bilingual_proposals_total=184,accepted_original_training_pairs=86,packed_training_sequences=130,
        validation_pairs=14,previous_known_test_pairs_not_reopened_for_training=13,newly_opened_test_pairs=16,
        pages_total_bounded=252,full_chapters_reviewed=False,validation_errors=dict(before=5,after=3,relative_reduction_percent=40,context_unresolved=3),
        new_test=dict(complete_corrections=1,partial_content_recovery_with_quality_defect=1,new_content_losses=0,
            unapproved_core_outputs_before=4,unapproved_core_outputs_after=3,context_unresolved=2),
        old_saved_core_control=dict(regions=229,views=124,changed_regions=81,complete_captured_corrections=12,
            new_captured_regressions=3,additional_partial_losses=2,new_source_artifacts=1,not_comparable_to_production_failure_rate=True),
        optimizer_steps=160,adapter_sha256=training['adapter_sha256'],frozen_base_unchanged=True,checks_passed=16,
        future_untouched_test_chapters=41,newly_opened_test_no_longer_blind_for_future_tuning=True,
        installed_app_fixed_control=dict(unapproved_views=56,total_views=124,historical_relative_reduction_percent=9.6774193548),
        application_weights_modified=False,experiment_promoted=False,screen_attempt_failure_probability=None,target_achieved=False,
        reason_not_promoted=fresh['reason_not_promoted'],free_disk_bytes=shutil.disk_usage(g.OUT).free,
        evidence=[dict(path=p.relative_to(g.ROOT).as_posix(),sha256=g.sha(p)) for p in evidence])
    (g.META/'pilot-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    page='''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Luma · segundo ajuste de pesos</title><style>body{font:17px system-ui;max-width:1060px;margin:30px auto;padding:0 18px;background:#f1f4ed;color:#243b2b;line-height:1.6}table{border-collapse:collapse;width:100%}td,th{border:1px solid #b5c2b3;padding:11px;text-align:left}strong{color:#743721}a{color:#245f83}</style>
<h1>Segundo ajuste local de pesos</h1><p><strong>El candidato mejora algunos diálogos, pero introduce regresiones. Se conserva el modelo instalado.</strong></p>
<p>Se entrenó un adaptador de 294.912 parámetros sobre OPUS-MT: 86 diálogos bilingües cotejados con sus imágenes y 130 secuencias que concatenan únicamente esos diálogos de entrenamiento. Las concatenaciones no son muestras independientes nuevas ni conversaciones atribuidas al mismo personaje.</p>
<table><tr><th>Conjunto</th><th>Resultado revisado</th><th>Límite</th></tr>
<tr><td>Validación fija: 14 diálogos</td><td>5 → 3 errores confirmados; 2 correcciones, ninguna pérdida nueva</td><td>Reducción relativa del 40 % en este conjunto pequeño; 3 casos de contexto sin resolver</td></tr>
<tr><td>Nueva prueba reservada: 16 diálogos</td><td>1 corrección completa, 1 recuperación parcial con redacción defectuosa, ninguna pérdida nueva</td><td>4 → 3 salidas sin aprobar; 2 casos requieren contexto</td></tr>
<tr><td>Control del núcleo: 229 regiones de 124 vistas</td><td>81 cambios cotejados: 12 correcciones del contenido capturado, 3 regresiones y 2 pérdidas parciales adicionales</td><td>Incluye fuentes OCR cortadas y no aplica las recuperaciones de la app; no son 12 usos completos corregidos</td></tr>
<tr><td>Integridad</td><td>16 comprobaciones aprobadas; recarga con salidas idénticas</td><td>Pesos base congelados y referencias de prueba excluidas del entrenamiento</td></tr></table>
<p>Las correcciones de validación, la prueba nueva y el control antiguo tienen denominadores distintos y no se suman para obtener una tasa de fallo. La similitud chrF++ subió de 66,62 a 70,90 en validación, pero no mide la probabilidad de que falle la app.</p>
<p>Se revisaron 184 propuestas bilingües entre los lotes; se conservaron 252 imágenes acotadas. Esto no equivale a revisar completos los 217 capítulos nuevos ni todas las palabras de los 124 capítulos anteriores. Los géneros no deducibles del inglés aislado quedan pendientes de contexto; las onomatopeyas y muletillas no inflan las correcciones de contenido.</p>
<p>La app mantiene su control de 56 vistas sin aprobar sobre 124, con la reducción histórica del 9,68 %. Todavía no está acreditado menos del 5 % de fallos por uso completo.</p>
<p><a href="fresh-test/review/index.html">Comparaciones fotográficas del lote reservado</a> · <a href="../finetune8031/index.html">Primer ensayo</a> · <a href="../full-comics/metrics/index.html">Control instalado</a></p></html>'''
    (g.OUT/'index.html').write_text(page,encoding='utf-8')
    gallery=g.OUT/'fresh-test/review/index.html'
    gallery.write_text('<!doctype html><meta charset="utf-8"><title>Comparaciones reservadas</title><h1>Propuestas cotejadas antes de generar traducciones</h1><p>24 propuestas inspeccionadas; 16 referencias aceptadas y 8 excluidas. Las hojas muestran OCR sin corregir; las etiquetas definitivas documentan los cambios fieles al inglés. Dos recortes amplios completan el cotejo.</p>'+''.join(f'<p>Hoja {i}</p><img loading="lazy" style="max-width:100%" src="sheet-{i:02d}.jpg">' for i in range(1,7))+''.join(f'<p>Recorte amplio {i}</p><img loading="lazy" style="max-width:100%" src="wide-{i:02d}.jpg">' for i in range(1,3)),encoding='utf-8')
    print(json.dumps(dict(promoted=False,validation_content_errors='5 -> 3',new_test_complete_fixes=1,old_core_fixes=12,old_core_regressions=3,checks=16)),flush=True)


if __name__=='__main__':main()
