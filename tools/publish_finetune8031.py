"""Bind the first real local weight-training pilot to its scoped quality review."""
import html
import json
import pathlib
import shutil
from prepare_finetune8031 import ROOT,OUT,META,sha


def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
    folder=OUT/'lora-pilot';training=read(folder/'summary.json');proof=read(folder/'run-input-proof.json')
    data=read(META/'approved-pairs.json');decisions=read(META/'heldout-meaning-decisions.json');core=read(folder/'regression-core-summary.json')
    assert proof['dataset_sha256']==sha(META/'approved-pairs.json') and proof['protocol_sha256']==sha(META/'protocol.json')
    assert proof['execution_script_sha256']==sha(ROOT/'tools/train_opus_lora8031.py')
    assert training['actual_weight_training_completed'] and training['base_weights_unchanged']
    assert sha(folder/'adapter/adapter_model.safetensors')==training['trained_adapter_sha256']
    assert not decisions['pilot_supports_replacing_the_app_model'] and decisions['complete_content_corrections']==0 and decisions['new_content_losses']==1
    app_manifest=ROOT/'assets/models/opus-en-es/manifest.json';manifest=read(app_manifest)
    assert sha(app_manifest)==read(ROOT/'build/full-comics/windows-engine803001.json')['manifest_sha256']
    for name in ['encoder.onnx','decoder.onnx']:assert sha(app_manifest.parent/name)==manifest['files'][name]
    files=[META/'sources.json',META/'protocol.json',META/'approved-pairs.json',META/'heldout-meaning-decisions.json',META/'regression-core-meaning-decisions.json',
           OUT/'base-model-provenance.json',OUT/'ocr-provenance.json',OUT/'review-selection.json',OUT/'training-environment.freeze.txt',
           folder/'summary.json',folder/'run-input-proof.json',folder/'training-log.json',folder/'baseline-heldout.json',folder/'candidate-heldout.json',
           folder/'regression-core-summary.json',folder/'regression-core-changes.json',ROOT/'build/full-comics/finetune8031-tests.log']
    report=dict(schema=1,experiment='8031-local-opus-lora-pilot',app_build_unchanged='803001',user_source_pairs=217,
        chapter_split_counts={s:len(v) for s,v in read(META/'sources.json')['assignments'].items()},
        pages_downloaded=144,initial_chapter_pairs_downloaded=4,proposal_pairs_reviewed=100,approved_pair_counts=data['approved_counts'],
        excluded_proposals=data['excluded'],all_accepted_pairs_visually_checked=True,chapter_split_disjoint=True,
        actual_weight_training_completed=True,optimizer_steps=40,trainable_parameters=294912,
        training_seconds=training['training_seconds'],peak_cuda_allocated_bytes=training['peak_cuda_allocated_bytes'],
        new_heldout_complete_content_corrections=0,new_heldout_content_losses=1,
        validation_confirmed_content_errors=dict(before=5,after=5),validation_unresolved_context=3,
        test_confirmed_content_errors=dict(before=3,after=4),
        old_core_diagnostic=dict(regions=229,saved_views=124,changed_regions=22,captured_region_corrections=5,new_captured_region_content_losses=2,
            additional_partial_meaning_worsenings=1,additional_partial_quality_worsenings=1,new_source_artifacts=1,
            comparable_to_production_app_failure_rate=False,not_added_to_new_heldout_results=True),
        adapter_reloaded_with_exact_output_parity=True,new_integrity_guards_passed=15,
        application_weights_modified=False,installed_app_model_sha256={n:manifest['files'][n] for n in ['encoder.onnx','decoder.onnx']},
        experiment_promoted=False,reason_not_promoted='New heldout set has no complete content corrections and one added omission; the training set is only a feasibility pilot',
        future_unseen_test_chapters_remaining=42,initial_test_set_is_not_blind_for_later_tuning=True,
        expansion_queue=read(OUT/'expansion-v1/summary.json') if (OUT/'expansion-v1/summary.json').exists() else None,
        evidence=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)) for p in files],
        all217_chapters_reviewed=False,all124_original_chapter_words_reviewed=False,
        full_live_app_use_evaluated=False,screen_attempt_failure_probability=None,target_achieved=False,
        free_disk_bytes=shutil.disk_usage(OUT).free)
    (META/'pilot-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    scores=training['heldout_scores'];loss=read(folder/'training-log.json');lo=min(r['training_loss'] for r in loss);hi=max(r['training_loss'] for r in loss)
    points=' '.join(f'{30+i*900/39:.1f},{180-(r["training_loss"]-lo)/max(hi-lo,.01)*145:.1f}' for i,r in enumerate(loss))
    page='''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Luma · primer ajuste fino local</title><style>body{font:17px system-ui;max-width:1050px;margin:30px auto;padding:0 18px;background:#f1f4ed;color:#243b2b;line-height:1.65}table{border-collapse:collapse;width:100%}td,th{border:1px solid #b5c2b3;padding:10px;text-align:left}svg{width:100%;background:white}details{margin:20px 0}</style>
<h1>Primer ajuste fino local de OPUS-MT</h1><p><b>Se entrenaron pesos reales de un adaptador. La app conserva su modelo anterior.</b> El primer candidato no se incorpora porque no mejora el lote nuevo reservado: cero correcciones completas de contenido y una omisión nueva.</p>
<p>El inventario nuevo contiene217 parejas de capítulos. Para comprobar el método se descargaron144 páginas de cuatro parejas:35 diálogos revisados para entrenar,14 para validar y13 para probar. Las38 propuestas restantes del lote inicial se excluyeron. No son217 capítulos entrenados ni revisados por completo.</p>
<table><tr><th>Comprobación</th><th>Resultado</th></tr><tr><td>Entrenamiento</td><td>40 actualizaciones;294.912 parámetros del adaptador;pesos base congelados</td></tr><tr><td>Validación nueva</td><td>5 errores confirmados antes y después;3 casos requieren contexto</td></tr><tr><td>Prueba nueva</td><td>3 →4 errores de contenido en13 diálogos;sin correcciones completas</td></tr><tr><td>Integridad</td><td>15 comprobaciones aprobadas;recarga del adaptador con salidas idénticas</td></tr></table>
<p>Una vacilación recuperada no se cuenta como corrección de significado. Variaciones naturales de traducción tampoco se penalizan por diferir literalmente de la referencia. Los recuentos son de este diagnóstico pequeño; no estiman el porcentaje de fallos por uso completo.</p>
<p>También se compararon229 fuentes OCR de124 vistas anteriores usando únicamente el núcleo flotante:22 cambios,cinco correcciones del contenido capturado y dos pérdidas nuevas,además de empeoramientos parciales. Ese núcleo no aplica las reparaciones ni recuperaciones de la app y algunas fuentes están cortadas: sus cuentas no se suman al lote nuevo ni actualizan el control de producción.</p>
<h2>Pérdida de entrenamiento</h2><p>Esta curva describe el ajuste sobre los ejemplos de entrenamiento. No es una tasa de fallos ni una precisión.</p>
'''
    page+=f'<svg viewBox="0 0 960 210" role="img" aria-label="Pérdida durante40 actualizaciones"><polyline points="{points}" fill="none" stroke="#356b47" stroke-width="3"/><text x="30" y="205">Actualización1</text><text x="810" y="205">Actualización40</text></svg>'
    page+='<details><summary>Similitud automática con la referencia, no precisión</summary><p>'
    for name,s in scores.items():page+=f'{html.escape(name)} · chrF++ {s["baseline_chrfpp"]:.2f} → {s["candidate_chrfpp"]:.2f}. '
    page+='</p></details><p>Se preparó otra cola de60 propuestas solo para entrenamiento. Cada pareja necesita cotejo bilingüe antes de usarse. Quedan42 capítulos asignados a prueba que aún no se han inspeccionado; la prueba inicial ya conocida no se presentará como una prueba nueva ciega.</p><p>Menos del5 % de fallos por uso sigue sin acreditarse. No se exportó otro APK ni se modificaron los modelos instalados.</p><p><a href="../full-comics/metrics/index.html">Control de la app conservado</a> · <a href="review/index.html">Propuestas fotográficas del primer lote</a></p></html>'
    (OUT/'index.html').write_text(page,encoding='utf-8')
    (OUT/'review/index.html').write_text('<!doctype html><meta charset="utf-8"><title>Propuestas bilingües</title><h1>Propuestas OCR antes de corregir las transcripciones</h1><p>100 propuestas inspeccionadas;62 etiquetas aceptadas tras cotejo y38 excluidas. El OCR mostrado es una ayuda de transcripción y no representa los textos definitivos usados para entrenar.</p>'+''.join(f'<p>Comparación{i:02d}</p><img loading="lazy" style="max-width:100%" src="sheet-{i:02d}.jpg">' for i in range(1,26)),encoding='utf-8')
    print(json.dumps(dict(actual_weight_training=True,promoted=False,heldout_corrections=0,heldout_losses=1,guards=15)),flush=True)


if __name__=='__main__':main()
