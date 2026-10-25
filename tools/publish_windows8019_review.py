"""Bind the protected policy to actual124-crop Windows outputs and prior pixel reviews."""
import collections
import json
from audit_corpus_quality import ROOT,QA,CLEAR_ERRORS,atomic,digest,read


def main():
    folder=QA/'windows8019-heldout-pixels';actual_path=folder/'summary.json';actual=read(actual_path)
    prior_path=ROOT/'benchmarks/full-comics/windows8018-heldout-semantic-review.json';prior=read(prior_path)
    baseline_path=ROOT/'benchmarks/full-comics/windows8017-render-geometry-semantic-review.json';baseline=read(baseline_path)
    base={r['id']:r for r in baseline['entries']};old={r['id']:r for r in prior['entries']}
    old_pixels=read(QA/'windows8018-heldout-pixels/summary.json');assert len(actual['entries'])==124
    quant_sample=read(QA/'int8-translation8018/visual-review/sample.json');quant={r['id']:r for r in quant_sample['cases']}
    revisions_path=QA/'int8-translation8018/visual-review/baseline-judgment-revisions.json'
    revisions={quant[r[0]]['location_id']:r for r in read(revisions_path)}
    entries=[];withheld=[]
    for a,p in zip(actual['entries'],old_pixels['entries']):
        ident=a['id'];assert a['source']==p['source'] and a['regions']==p['regions']
        entry=dict(old[ident],before=base[ident]['after'],before_translation=base[ident]['translation'],
            translation=' '.join(a['translations']),previous_trial_translation=old[ident]['translation'])
        if a['translations']==p['translations']:
            entry.update(meaning_judgment_reused_only_for_identical_same_location_output=True)
        else:
            # This guard returned the exact whole inference already inspected
            # in the previous packaged-build cohort, not a new invented string.
            assert entry['translation']==base[ident]['translation']
            entry.update(after=base[ident]['after'],meaning_judgment_reused_only_for_identical_same_location_output=True,
                guarded_recovery_withheld=True,note_es='Se conserva la inferencia completa previa; la recuperación parcial fue rechazada por retención de contenido.')
            withheld.append(ident)
        if ident in revisions:
            _,previous,revised,note=revisions[ident]
            assert base[ident]['translation']==old[ident]['translation']==entry['translation']
            assert entry['before']==entry['after']==previous
            entry.update(before=revised,after=revised,previous_before_judgment=previous,before_judgment_revision_es=note)
        entries.append(entry)
    cohorts={}
    for label,selected in [('all_124_including_clipped_edges',entries),('uncut_120',[r for r in entries if not r['edge_clipped']])]:
        b=collections.Counter(r['before'] for r in selected);a=collections.Counter(r['after'] for r in selected)
        old_errors=len(selected)-b['acceptable'];new_errors=len(selected)-a['acceptable']
        cohorts[label]=dict(locations=len(selected),before_categories=dict(b),after_categories=dict(a),
            before_not_approved=old_errors,after_not_approved=new_errors,
            corrected=sum(r['before']!='acceptable' and r['after']=='acceptable' for r in selected),
            regressed=sum(r['before']=='acceptable' and r['after']!='acceptable' for r in selected),
            before_clear_errors=sum(b[k] for k in CLEAR_ERRORS),after_clear_errors=sum(a[k] for k in CLEAR_ERRORS),
            relative_unapproved_reduction_percent=100*(old_errors-new_errors)/old_errors)
    value=dict(schema=1,platform='Windows',before_build='801704',after_build='801901',reviewed_locations=124,
        original_pixel_source_strings_preserved=124,all_124_original_source_strings_preserved=True,
        all124_meaning_judgments_bound_to_exact_same_location_outputs=True,baseline_judgment_revisions=len(revisions),
        recoveries_withheld_vs_unguarded_trial=len(withheld),withheld_locations=withheld,
        cohorts=cohorts,entries=entries,previous_semantic_review_sha256=digest(prior_path),
        baseline_semantic_review_sha256=digest(baseline_path),current_summary_sha256=digest(actual_path),
        native_output_sha256=digest(folder/'output.jsonl'),judgment_revisions_sha256=digest(revisions_path),
        application_modified=True,model_weights_changed=False,all_chapter_words_visually_reviewed=False,
        population_accuracy_estimate=False,screen_attempt_failure_probability=None,target_achieved=False,ready_for_release=False)
    atomic(ROOT/'benchmarks/full-comics/windows8019-heldout-semantic-review.json',json.dumps(value,ensure_ascii=False,indent=2))
    m=cohorts['all_124_including_clipped_edges']
    atomic(folder/'index.html',f'''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luma · Windows protegido</title><style>body{{font:17px system-ui;background:#f1f4ed;color:#243b2b;max-width:1100px;margin:35px auto;padding:20px}}p{{line-height:1.6}}</style><h1>Windows · prueba real del reintento protegido</h1><p>La compilación801901 procesó los 124 recortes originales sin errores de ejecución y conservó exactamente el OCR y las 137 regiones. Cada salida conserva un cotejo visual anterior solo por ser idéntica en la misma ubicación. Se rechazó una recuperación parcial respecto al ensayo anterior; su salida completa coincide exactamente con la ya revisada.</p><p><b>{m['before_not_approved']} → {m['after_not_approved']} sin aprobar</b> frente a801704 con los dos dictámenes rectificados aplicados a ambos lados: {m['corrected']} correcciones completas y {m['regressed']} regresiones completas observadas. Se mantienen {m['after_clear_errors']} errores claros y {m['after_categories'].get('needs_improvement',0)} casos que requieren mejora. Los informes históricos anteriores se conservan sin modificarse.</p><p>El reconocimiento conserva 34 errores de palabra y siete omisiones entre las 1.483 palabras de este lote. La probabilidad de fallo por pantalla sigue sin establecerse y la compilación permanece en validación.</p><p><a href="../windows8018-heldout-pixels/visual-review/index.html">Originales y comparaciones previas</a> · <a href="../metrics/index.html">Resultados agregados</a></p></html>''')
    print(json.dumps({k:v for k,v in value.items() if k!='entries'}),flush=True)


if __name__=='__main__':main()
