"""Publish every evaluated output, scoped counts and rejection evidence."""
import html
import json
import pathlib
import shutil
from prepare_finetune8031 import ROOT,sha

META=ROOT/'benchmarks/finetune8034';OUT=ROOT/'build/finetune8034';RUN=OUT/'lora-pilot'
def read(p):return json.loads(pathlib.Path(p).read_text(encoding='utf-8'))

STYLE='''body{font:17px system-ui;max-width:1250px;margin:28px auto;padding:0 18px;background:#f1f4ed;color:#243b2b;line-height:1.6}table{border-collapse:collapse;width:100%;background:#fff}td,th{border:1px solid #b5c2b3;padding:10px;text-align:left;vertical-align:top}td{min-width:150px;max-width:340px;overflow-wrap:anywhere;font-size:15px}.warning{padding:16px;background:#f8e9d7;border-left:5px solid #8f5326}.scroll{overflow:auto}.failed_generation,.incorrect,.incomplete,.quality_defect{color:#8c2721}.needs_context,.needs_source_review{color:#725a18}a{color:#245f83}.note{font-size:14px;color:#526050}.output{max-height:260px;overflow:auto;overflow-wrap:anywhere}small{font-size:14px}'''
def page(title,body):return f'<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{STYLE}</style>{body}</html>'


def comparisons(name,title,baseline,candidate,verdicts,references=None,photos=None,scope=''):
    by={r['id']:r for r in verdicts};references=references or {};photos=photos or {}
    body=f'<p><a href="index.html">← Informe</a></p><h1>{html.escape(title)}</h1><p>{html.escape(scope)}</p><p>Se muestran todas las salidas de este conjunto, incluidas las que no cambian. «Sin dictamen nuevo» no significa aprobado.</p><div class="scroll"><table><tr><th>ID / dictamen</th><th>Fuente</th>'
    if references:body+='<th>Referencia revisada</th>'
    body+='<th>Modelo base</th><th>Candidato</th></tr>'
    for a,b in zip(baseline,candidate):
        assert a['id']==b['id'] and a['source']==b['source'];ident=a['id'];v=by.get(ident);status=v['after'] if v else 'sin dictamen nuevo'
        label=html.escape(status);note=html.escape(v.get('note','') if v else 'Sin nueva calificación de significado para esta salida sin cambios.')
        body+=f'<tr><td><b>{ident}</b><p class="{html.escape(status)}">{label}</p><small>{note}</small>'
        if ident in photos:body+=f'<p><a href="{html.escape(photos[ident],quote=True)}">Ver propuesta en imágenes</a></p>'
        body+=f'</td><td>{html.escape(a["source"])}</td>'
        if references:body+=f'<td>{html.escape(references.get(ident,""))}</td>'
        body+=f'<td><div class="output">{html.escape(a["translation"])}</div></td><td><div class="output">{html.escape(b["translation"])}</div></td></tr>'
    body+='</table></div>'
    (OUT/name).write_text(page(title,body),encoding='utf-8')


def main():
    data=read(META/'dataset.json');curation=read(META/'curation.json');training=read(RUN/'summary.json');gates=read(META/'quality-gates.json')
    validation=read(META/'validation-meaning-decisions.json');core=read(META/'regression-core-meaning-decisions.json')
    known=read(META/'known-test-meaning-decisions.json');early=read(META/'early-known-test-meaning-decisions.json');audit=read(RUN/'generation-format-audit.json')
    tests=ROOT/'build/full-comics/finetune8034-tests.log';log=tests.read_text(encoding='utf-8')
    assert 'Ran 18 tests' in log and log.rstrip().endswith('OK')
    assert not gates['ready_for_native_parity'] and not gates['ready_for_installation']
    manifest=ROOT/'assets/models/opus-en-es/manifest.json';assets=read(manifest)
    assert sha(manifest)==read(ROOT/'build/full-comics/windows-engine803001.json')['manifest_sha256']
    for n in ['encoder.onnx','decoder.onnx']:assert sha(manifest.parent/n)==assets['files'][n]
    images=read(OUT/'images.json');all_images=images[:]
    for name in ['finetune8031/images.json','finetune8031/expansion-v1/images.json','finetune8032/fresh-test/images.json']:all_images+=read(ROOT/'build'/name)
    evidence=[META/n for n in ['data-protocol.json','training-protocol.json','curation.json','dataset.json','baseline-validation-meaning-decisions.json',
        'validation-meaning-decisions.json','regression-core-meaning-decisions.json','known-test-meaning-decisions.json','early-known-test-meaning-decisions.json','quality-gates.json']]
    evidence+=[RUN/n for n in ['summary.json','run-input-proof.json','training-log.json','baseline-validation.json','candidate-validation.json',
        'regression-core-summary.json','regression-core-changes.json','known-test-summary.json','early-known-test-summary.json','generation-format-audit.json','precision-diagnostic.json']]
    evidence+=[OUT/'images.json',OUT/'ocr-provenance.json',OUT/'review-selection.json',OUT/'preparation-provenance.json',tests]
    report=dict(schema=1,experiment='8034-expanded-reviewed-data',actual_weight_training_completed=True,application_build_unchanged='803001',application_weights_modified=False,
        user_inventory_chapter_pairs=217,reviewed_proposals_this_iteration=111,accepted_labels_this_iteration=88,excluded_proposals_this_iteration=23,
        reviewed_proposals_total=295,accepted_labels_total=217,**data['counts'],new_images=len(images),new_image_bytes=sum(r['bytes'] for r in images),total_saved_images=len(all_images),
        total_image_bytes=sum(r['bytes'] for r in all_images),all_images_are_bounded_slices_not_full_chapter_review=True,
        original_english_training_words=1740,original_spanish_training_words=1717,optimizer_steps=training['optimizer_steps'],trainable_parameters=294912,
        adapter_sha256=training['adapter_sha256'],training_seconds=training['training_seconds'],peak_cuda_allocated_bytes=training['peak_cuda_allocated_bytes'],
        base_weights_unchanged=training['frozen_base_sha256_before']==training['frozen_base_sha256_after'],
        known_validation=dict(pairs=14,base_errors=5,previous_candidate_errors=3,current_candidate_errors=2,relative_reduction_from_base_percent=60,relative_reduction_from_previous_candidate_percent=100/3,context_uncertain=3),
        new_validation=dict(pairs=11,complete_content_corrections=3,new_confirmed_content_regressions=1,new_uncertain_tense_change=1,no_global_error_percentage_inferred=True),
        old_core=dict(regions=229,saved_views=124,changed_regions=79,complete_captured_corrections=11,new_confirmed_complete_region_regressions=0,additional_partial_meaning_losses=1,new_source_artifacts=1,additional_uncertain_relation_changes=2,verdicts_reused_by_exact_identity=35,new_variants_manually_reviewed=44),
        known_test16=dict(complete_usable_corrections=2,partial_content_recoveries=1,new_confirmed_content_regressions=0,new_context_uncertainty=1,new_suffix_artifacts=1),
        known_test13=dict(complete_content_corrections=1,new_complete_generation_failures=1,additional_partial_meaning_losses=1,new_context_uncertainty=1),
        format_audit=dict(outputs_scanned=566,candidate_alerts=1,semantic_certification=False),collapse_reproduced_in_bfloat16_and_float32=True,
        diagnostic_did_not_replace_official_results=True,integrity_checks_passed=18,quality_gates_passed=False,
        failed_predeclared_gates=[k for k,v in gates['predeclared_checks'].items() if not v],additional_observed_generation_collapse=True,
        experiment_promoted=False,ready_for_native_export=False,reason_not_promoted='New validation has a confirmed regression; old core retains a partial loss and source artifact; the early known control also contains an entire punctuation-only generation failure.',
        new_blind_test_chapters_opened=0,future_uninspected_test_chapters_remaining=41,ocr_weights_trained=False,
        historical_installed_control=dict(unapproved_saved_views=56,saved_views=124,historical_relative_reduction_percent=9.6774193548),
        all124_complete_chapter_words_reviewed=False,all217_new_chapters_reviewed=False,screen_attempt_failure_probability=None,target_achieved=False,
        free_disk_bytes=shutil.disk_usage(OUT).free,evidence=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)) for p in evidence])
    text=json.dumps(report,ensure_ascii=False,indent=2)
    (META/'pilot-review.json').write_text(text,encoding='utf-8');(OUT/'report.json').write_text(text,encoding='utf-8')
    body='''<h1>Luma · ampliación de datos y cuarto ajuste de pesos</h1>
<p class="warning"><b>El candidato recupera más contenido, pero no supera los criterios de calidad y no se incorpora a la app.</b> Hay una regresión en la validación nueva, una pérdida parcial y un artefacto en el control anterior, además de una salida sin palabras en otra prueba conocida.</p>
<p>Se cotejaron 111 propuestas con sus imágenes: 88 etiquetas aceptadas y 23 excluidas. El entrenamiento pasó de 86 a <b>163 diálogos originales</b>, y se añadieron <b>11 frases nuevas de validación</b>. Las 254 concatenaciones de entrenamiento reutilizan esos diálogos: no son 254 muestras originales adicionales. No se abrió ninguno de los 41 capítulos de prueba aún reservados.</p>
<div class="scroll"><table><tr><th>Conjunto</th><th>Resultado</th><th>Alcance</th></tr>
<tr><td>Validación fija: 14 diálogos</td><td>5 errores de la base → 3 en el candidato anterior → 2 ahora. Ninguna pérdida nueva confirmada en este lote.</td><td>60 % menos frente a la base y 33,3 % menos frente al candidato anterior, solo en esta muestra. Otros 3 casos requieren contexto.</td></tr>
<tr><td>Validación nueva: 11 diálogos</td><td>3 recuperaciones completas, 1 regresión confirmada y 1 cambio de tiempo que requiere contexto.</td><td>Referencias y dictámenes de la base registrados antes de revisar la salida candidata. No se deriva una tasa global.</td></tr>
<tr><td>Control del núcleo: 229 regiones de 124 vistas</td><td>11 correcciones del contenido capturado; 0 regresiones completas nuevas confirmadas. Persisten 1 pérdida parcial adicional y 1 artefacto copiado.</td><td>79 cambios cotejados: 35 dictámenes reutilizados por identidad exacta y 44 variantes nuevas revisadas. No son capítulos completos ni usos en vivo.</td></tr>
<tr><td>Pruebas conocidas: 16 y 13 diálogos</td><td>En el primer conjunto, 2 correcciones completas y 1 recuperación parcial. En el segundo, 1 corrección, 1 fallo completo de generación y 1 pérdida parcial adicional.</td><td>Se registran aparte dudas de contexto y un sufijo de habla mal presentado. Estos conjuntos ya eran conocidos; no se presentan como nuevas pruebas ciegas.</td></tr></table></div>
<p>Una salida formada solo por signos se reprodujo usando el mismo lote con bfloat16 y float32. El diagnóstico no reemplazó la salida fallida ni sus cuentas. La auditoría automática recorrió 566 salidas de base y candidato y señaló un caso; detectar formato anormal no certifica el significado del resto.</p>
<p>Pasaron <b>18 comprobaciones de integridad</b>, mientras que <b>las pruebas de calidad del modelo no se superaron</b>. Subir chrF++ o recuperar algunas frases no permite ignorar las nuevas pérdidas. Se conservan los pesos instalados y los cuatro adaptadores experimentales.</p>
<p>El inglés de validación fue transcrito y corregido contra los píxeles antes de traducir. El otro control usa fuentes OCR guardadas y el núcleo flotante, sin las reparaciones ni recuperaciones de producción. No se entrenaron pesos OCR. Las etiquetas son revisiones del asistente, sin certificación humana final; las correcciones a la edición española están documentadas.</p>
<p>Se conservan 419 imágenes acotadas, unos 98,2 MiB. No equivalen a revisar completos los 217 capítulos nuevos ni cada palabra de los 124 anteriores. La app instalada conserva su control de 56 vistas sin aprobar sobre 124; menos del 5 % de fallos por uso sigue sin acreditarse.</p>
<ul><li><a href="validation-comparisons.html">Todas las 25 comparaciones de validación</a></li><li><a href="core-comparisons.html">Las 229 fuentes del control OCR conservado</a></li><li><a href="known-test-comparisons.html">Las 29 comparaciones de pruebas conocidas</a></li><li><a href="review/index.html">Todas las propuestas fotográficas cotejadas</a></li><li><a href="report.json">Informe con hashes y procedencia</a></li></ul>
<p><a href="../finetune8033/index.html">Ensayos anteriores</a> · <a href="../full-comics/metrics/index.html">Control de la app instalada</a></p>'''
    (OUT/'index.html').write_text(page('Luma · cuarto ajuste de pesos',body),encoding='utf-8')
    selected=read(OUT/'review-selection.json');photo_positions={r['id']:i//4+1 for i,r in enumerate(selected)}
    old=read(ROOT/'build/finetune8031/review-selection.json');old_positions={r['id']:i//4+1 for i,r in enumerate(old)}
    photos={r['id']:(f'review/sheet-{photo_positions[r["proposal_id"]]:02d}.jpg' if r.get('origin')=='8034-pixel-reviewed' else f'../finetune8031/review/sheet-{old_positions[r["id"]]:02d}.jpg') for r in data['validation']}
    comparisons('validation-comparisons.html','Todas las comparaciones de validación',read(RUN/'baseline-validation.json'),read(RUN/'candidate-validation.json'),validation['entries'],
        references={r['id']:r['target'] for r in data['validation']},photos=photos,scope='25 entradas transcritas, no OCR nuevo de producción. Los errores, la calidad de redacción y la incertidumbre de contexto se distinguen.')
    comparisons('core-comparisons.html','Control de fuentes OCR conservadas',read(RUN/'regression-core-baseline.json'),read(RUN/'regression-core-candidate.json'),core['entries'],
        scope='229 fuentes de124 vistas conservadas. Solo los79 cambios recibieron dictamen nuevo o reutilizado con prueba de identidad. Algunas fuentes están cortadas o corruptas. No se aplican las recuperaciones de la app.')
    a=[];b=[];v=[]
    for offset,name,review in [(0,'known-test',known),(1000,'early-known-test',early)]:
        a.extend(dict(r,id=r['id']+offset) for r in read(RUN/(name+'-baseline.json')))
        b.extend(dict(r,id=r['id']+offset) for r in read(RUN/(name+'-candidate.json')))
        v.extend(dict(r,id=r['id']+offset) for r in review['entries'])
    comparisons('known-test-comparisons.html','Todas las pruebas ya conocidas',a,b,v,scope='29 diálogos de dos conjuntos inspeccionados anteriormente. Se mantienen fuera del entrenamiento y no son una nueva prueba ciega. Se conserva también la salida fallida completa.')
    gallery='<h1>Propuestas cotejadas con imágenes</h1><p>111 propuestas inspeccionadas:88 etiquetas aceptadas,23 excluidas. El OCR mostrado es una ayuda sin corregir; la entrada definitiva de entrenamiento o validación se transcribió contra los píxeles. No todas las propuestas de estas hojas se usaron.</p>'
    for f in sorted((OUT/'review').glob('*.jpg')):gallery+=f'<p>{html.escape(f.stem)}</p><img loading="lazy" style="max-width:100%" src="{html.escape(f.name,quote=True)}">'
    (OUT/'review/index.html').write_text(page('Propuestas bilingües cotejadas',gallery),encoding='utf-8')
    print(json.dumps(dict(promoted=False,original_training=163,new_validation=11,known_errors='5 -> 2',core_fixes=11,generation_collapses=1,integrity_checks=18,quality_passed=False,free_GiB=round(report['free_disk_bytes']/1024**3,2))),flush=True)


if __name__=='__main__':main()
