"""Publish the scoped regularized-weight trial and bind every count to evidence."""
import json
import shutil
import finetune8032_guards as g
from train_opus_lora8033 import META,OUT


def main():
    folder=OUT/'lora-pilot';training=g.read(folder/'summary.json');proof=g.read(folder/'run-input-proof.json')
    validation=g.read(META/'validation-meaning-decisions.json');known=g.read(META/'known-test-meaning-decisions.json')
    core=g.read(META/'regression-core-meaning-decisions.json')
    assert proof['execution_script_sha256']==g.sha(g.ROOT/'tools/train_opus_lora8033.py')
    assert proof['protocol_sha256']==g.sha(META/'protocol.json')
    assert proof['dataset_sha256']==g.sha(g.META/'dataset.json')
    assert g.sha(folder/'adapter/adapter_model.safetensors')==training['adapter_sha256']
    assert training['frozen_base_sha256_before']==training['frozen_base_sha256_after']
    assert core['all_changed_outputs_reviewed'] and known['all16_outputs_reviewed']
    log=g.ROOT/'build/full-comics/finetune8033-tests.log'
    assert 'Ran 10 tests' in log.read_text(encoding='utf-8') and log.read_text(encoding='utf-8').rstrip().endswith('OK')
    app=g.ROOT/'assets/models/opus-en-es/manifest.json';manifest=g.read(app)
    assert g.sha(app)==g.read(g.ROOT/'build/full-comics/windows-engine803001.json')['manifest_sha256']
    for n in ['encoder.onnx','decoder.onnx']:assert g.sha(app.parent/n)==manifest['files'][n]
    evidence=[META/n for n in ['protocol.json','validation-meaning-decisions.json','regression-core-meaning-decisions.json','known-test-meaning-decisions.json']]
    evidence += [folder/n for n in ['summary.json','run-input-proof.json','training-log.json','baseline-validation.json','candidate-validation.json',
        'regression-core-summary.json','regression-core-changes.json','regression-core-vs8032.json','fresh-test-summary.json','fresh-test-vs8032.json']]
    evidence += [log,g.META/'pilot-review.json']
    report=dict(schema=1,experiment='8033-regularized-local-opus-lora',application_build_unchanged='803001',actual_weight_training_completed=True,
        original_training_pairs=86,packed_training_examples=130,validation_pairs=14,known_test_pairs=16,optimizer_steps=160,
        trainable_parameters=294912,training_seconds=training['training_seconds'],peak_cuda_allocated_bytes=training['peak_cuda_allocated_bytes'],
        frozen_base_unchanged=True,adapter_sha256=training['adapter_sha256'],kl_weight=.5,initial_token_kl=training['initial_token_kl'],
        dropout_also_disabled_not_a_causal_ablation_of_kl_alone=True,
        validation=dict(confirmed_errors_before=5,confirmed_errors_after=3,relative_reduction_percent=40,unresolved_context=3),
        known_test=dict(complete_corrections=1,partial_content_recovery_without_usable_approval=1,new_content_losses=0,unapproved_before=4,unapproved_after=3,context_unresolved=2,already_inspected_not_blind=True),
        old_core=dict(regions=229,saved_views=124,changed_regions=59,complete_captured_corrections=9,new_captured_regressions=2,additional_partial_meaning_loss=1,new_source_artifact=1,
            verdicts_reused_by_exact_output_identity=48,additional_changed_region_verdicts_reviewed=11,full_live_app_use_evaluated=False),
        integrity_guards_passed=10,previous_expanded_trial_guards_passed=16,
        application_weights_modified=False,experiment_promoted=False,reason_not_promoted=known['reason_not_promoted'],
        historical_installed_fixed_control=dict(unapproved_views=56,saved_views=124,historical_relative_reduction_percent=9.6774193548),
        all124_complete_chapter_words_reviewed=False,new217_complete_chapters_reviewed=False,ocr_weights_trained=False,
        reviewed_bilingual_proposals_total=184,accepted_labels_total=129,original_source_images_saved=252,
        future_untouched_test_chapters_remaining=41,screen_attempt_failure_probability=None,target_achieved=False,
        free_disk_bytes=shutil.disk_usage(OUT).free,
        next_priority='Expand genuinely reviewed training dialogue and linguistic variety; keep all old and newly inspected test sources evaluation-only. Do not continue a blind hyperparameter search or replace production weights on these results.',
        evidence=[dict(path=p.relative_to(g.ROOT).as_posix(),sha256=g.sha(p)) for p in evidence])
    (META/'pilot-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    page='''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Luma · ajustes locales de pesos</title><style>body{font:17px system-ui;max-width:1080px;margin:30px auto;padding:0 18px;background:#f1f4ed;color:#243b2b;line-height:1.6}table{border-collapse:collapse;width:100%}td,th{border:1px solid #b5c2b3;padding:11px;text-align:left}.warning{padding:14px;background:#f8e9d7;border-left:5px solid #8f5326}a{color:#245f83}</style>
<h1>Ajuste local de pesos de traducción</h1><p class="warning"><b>Se entrenaron tres adaptadores reales. Ninguno sustituye todavía el modelo de la app:</b> las mejoras siguen acompañadas de regresiones. Menos del 5 % de fallos por uso completo no está demostrado.</p>
<p>El ensayo ampliado usa 86 diálogos bilingües cotejados visualmente y 130 concatenaciones de esas mismas frases. Las referencias de validación y prueba nunca entran en los gradientes ni en las peticiones de traducción. Las etiquetas fueron revisadas por el asistente, sin certificación humana final; las correcciones a referencias publicadas están documentadas.</p>
<table><tr><th>Ensayo</th><th>Validación fija: 14 diálogos</th><th>Control del núcleo: 229 regiones de 124 vistas</th></tr>
<tr><td>Inicial: 35 diálogos de entrenamiento</td><td>5 → 5 errores confirmados</td><td>5 correcciones de contenido capturado y 2 pérdidas nuevas</td></tr>
<tr><td>Ampliado: 86 diálogos + 130 concatenaciones</td><td>5 → 3 errores; ninguna pérdida nueva en validación</td><td>12 correcciones, 3 regresiones y 2 pérdidas parciales adicionales</td></tr>
<tr><td>Con penalización respecto al modelo base</td><td>5 → 3 errores; ninguna pérdida nueva en validación</td><td>9 correcciones, 2 regresiones y 1 pérdida parcial adicional</td></tr></table>
<p>La reducción relativa del 40 % corresponde únicamente a los errores confirmados de esa validación pequeña. Sus 3 casos de género o referentes pendientes de contexto se mantienen separados. No es una tasa de fallo de la aplicación.</p>
<p>La prueba reservada nueva tuvo 16 diálogos: una corrección completa y una recuperación parcial que conserva redacción defectuosa, sin pérdidas de contenido nuevas. Quedan 3 salidas sin aprobar y 2 casos de contexto. Este conjunto ya se inspeccionó y se reutiliza como control conocido en el tercer ensayo; no se presenta dos veces como prueba ciega.</p>
<p>La penalización redujo algunos cambios respecto al modelo base, pero también perdió correcciones. El tercer ensayo desactiva además el dropout: esta comparación no aísla el efecto causal de la penalización por sí sola. Pasaron 16 comprobaciones del segundo ensayo y 10 del tercero, incluidas las matemáticas de la penalización, los gradientes, los píxeles, los hashes y la recarga exacta.</p>
<p>En total se inspeccionaron 184 propuestas bilingües: 129 etiquetas aceptadas, de las cuales 86 son entrenamiento, 14 validación y 29 pruebas. Se conservan 252 imágenes acotadas de siete parejas de capítulos. No se revisaron completos los 217 capítulos nuevos ni todas las palabras de los 124 anteriores. Permanecen 41 capítulos de prueba sin inspeccionar.</p>
<p>El núcleo flotante no aplica las reparaciones, glosario ni recuperación de frases de producción. Sus regiones pueden estar cortadas y sus correcciones no equivalen a usos completos resueltos. La app sigue en 56 vistas sin aprobar sobre 124, con la reducción histórica del 9,68 %. Los pesos de OCR no se entrenaron en estos ensayos.</p>
<p>El siguiente trabajo es ampliar ejemplos reales cotejados y su diversidad lingüística. Se conservan los adaptadores y sus resultados para reproducirlos; las fuentes de prueba permanecen excluidas del entrenamiento.</p>
<p><a href="../finetune8032/index.html">Informe del ensayo ampliado</a> · <a href="../finetune8032/fresh-test/review/index.html">Comparaciones fotográficas</a> · <a href="../finetune8031/index.html">Primer ensayo</a> · <a href="../full-comics/metrics/index.html">Control de la app instalada</a></p></html>'''
    (OUT/'index.html').write_text(page,encoding='utf-8')
    print(json.dumps(dict(promoted=False,validation_errors='5 -> 3',old_core_fixes=9,old_core_regressions=2,new_guards=26,free_disk_gib=round(report['free_disk_bytes']/1024**3,2))),flush=True)


if __name__=='__main__':main()
