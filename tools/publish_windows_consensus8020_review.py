"""Publish every integrated-reader change and retain all117 unchanged judgments."""
import collections
import json
from audit_corpus_quality import ROOT,QA,CLEAR_ERRORS,atomic,digest,read


def main():
    folder=QA/'windows8020-consensus-heldout-pixels';review=folder/'visual-review';sample=read(review/'sample.json')
    previous=ROOT/'benchmarks/full-comics/windows8019-heldout-semantic-review.json'
    assert digest(previous)==sample['previous_review_sha256'] and digest(folder/'summary.json')==sample['inference_summary_sha256']
    changed={r['location_id']:r for r in sample['cases']};same={r['id']:r for r in sample['identical_location_outputs']}
    manual_path=review/'manual-decisions.json';manual={r[0]:r for r in read(manual_path)}
    assert set(manual)==set(range(1,len(changed)+1)) and len(changed)==7
    entries=[]
    for old in read(previous)['entries']:
        ident=old['id'];entry=dict(old,before=old['after'],before_translation=old['translation'])
        if ident in changed:
            case=changed[ident];_,judgment,note=manual[case['id']]
            entry.update(after=judgment,translation=case['translation'],current_source=case['source'],
                previous_current_source=case['before_source'],note_es=note,meaning_reinspected_against_original_and_reference=True)
        else:
            assert same[ident]['translation']==old['translation']
            entry.update(meaning_judgment_reused_only_for_identical_same_location_output=True)
        entries.append(entry)
    cohorts={}
    for name,rows in [('all_124_including_clipped_edges',entries),('uncut_120',[r for r in entries if not r['edge_clipped']])]:
        b=collections.Counter(r['before'] for r in rows);a=collections.Counter(r['after'] for r in rows);be=len(rows)-b['acceptable'];ae=len(rows)-a['acceptable']
        cohorts[name]=dict(locations=len(rows),before_categories=dict(b),after_categories=dict(a),before_not_approved=be,after_not_approved=ae,
            corrected=sum(r['before']!='acceptable' and r['after']=='acceptable' for r in rows),
            regressed=sum(r['before']=='acceptable' and r['after']!='acceptable' for r in rows),
            before_clear_errors=sum(b[k] for k in CLEAR_ERRORS),after_clear_errors=sum(a[k] for k in CLEAR_ERRORS),
            relative_unapproved_reduction_percent=100*(be-ae)/be)
    value=dict(schema=1,platform='Windows native integrated-reader experiment',before_build='801901',after_build='802001',
        reviewed_locations=124,changed_locations_reinspected=7,identical_location_judgments_reused=117,
        cohorts=cohorts,entries=entries,original_137_baseline_sources_and_bounds_preserved_before_policy=True,
        previous_semantic_review_sha256=digest(previous),sample_sha256=digest(review/'sample.json'),manual_sha256=digest(manual_path),
        inference_summary_sha256=digest(folder/'summary.json'),native_output_sha256=digest(folder/'output.jsonl'),
        current_summary_sha256=digest(folder/'summary.json'),
        live_worker_enabled=False,additional_readers_supplied_by_explicit_benchmark_configuration=True,
        model_weights_trained=False,installed_model_assets_modified=False,
        all_chapter_words_visually_reviewed=False,population_accuracy_estimate=False,
        screen_attempt_failure_probability=None,target_achieved=False,ready_for_release=False)
    atomic(ROOT/'benchmarks/full-comics/windows8020-consensus-semantic-review.json',json.dumps(value,ensure_ascii=False,indent=2))
    m=cohorts['all_124_including_clipped_edges'];images=''.join(f'<img loading="lazy" src="sheet-{i:02d}.jpg" alt="Comparación {i}">' for i in range(1,5))
    atomic(review/'index.html',f'''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luma · lectores integrados en Windows</title><style>body{{font:17px system-ui;background:#f1f4ed;color:#243b2b;margin:24px}}p{{max-width:1100px;line-height:1.6}}img{{display:block;max-width:100%;margin:24px auto}}</style><h1>Windows · prueba de lectores combinados</h1><p>El ejecutable real802001 reconoció y tradujo los 124 recortes usando los lectores locales adicionales. Conservó las 137 fuentes y geometrías originales antes de aplicar el consenso. Se cotejaron los siete cambios con sus originales y las referencias; 117 resultados idénticos conservaron únicamente su dictamen de la misma ubicación.</p><p><b>{m['before_not_approved']} → {m['after_not_approved']} sin aprobar</b>, {m['corrected']} correcciones completas y {m['regressed']} regresiones observadas; reducción relativa del {m['relative_unapproved_reduction_percent']:.2f} % en este mismo lote. El OCR pasa de34 a27 errores de palabra y mantiene siete omisiones.</p><p>El ensayo usa rutas explícitas de modelos locales en el benchmark; la barra de uso normal todavía no activa estos lectores. No hubo entrenamiento ni cambio de los modelos instalados. Se amplía ahora la comprobación a las 124 vistas de lectura completas guardadas. La probabilidad de fallo de un uso completo sigue sin establecerse y esta compilación no se presenta como lista.</p><p><a href="../../metrics/index.html">Resultados agregados</a></p>{images}</html>''')
    print(json.dumps({k:v for k,v in value.items() if k!='entries'}),flush=True)


if __name__=='__main__':main()
