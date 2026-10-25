"""Publish all124 actual Windows results, without approving partial repairs."""
import collections
import json
from audit_corpus_quality import ROOT,QA,CLEAR_ERRORS,atomic,digest,read


def main():
    folder=QA/'windows8018-heldout-pixels';review=folder/'visual-review';sample=read(review/'sample.json')
    previous_path=ROOT/'benchmarks/full-comics/windows8017-render-geometry-semantic-review.json'
    assert digest(previous_path)==sample['previous_semantic_review_sha256']
    before=read(QA/'windows8017-render-heldout-pixels/summary.json');after=read(folder/'summary.json')
    assert digest(folder/'summary.json')==sample['after_summary_sha256']
    assert digest(QA/'windows8017-render-heldout-pixels/summary.json')==sample['before_summary_sha256']
    assert all(a['id']==b['id'] and a['source']==b['source'] for a,b in zip(before['entries'],after['entries']))
    manual_path=review/'manual-decisions.json';manual={r[0]:r for r in read(manual_path)}
    assert set(manual)=={c['id'] for c in sample['cases']}
    changed={c['location_id']:c for c in sample['cases']};same={c['id']:c for c in sample['identical_location_judgments']}
    entries=[]
    for old in read(previous_path)['entries']:
        ident=old['id'];entry=dict(old,before=old['after'],before_translation=old['translation'])
        if ident in changed:
            case=changed[ident];_,judgment,note=manual[case['id']]
            entry.update(after=judgment,translation=case['translation'],note_es=note,meaning_reinspected_against_original_and_reference=True)
        else:
            assert ' '.join(same[ident]['translations'])==old['translation'] and same[ident]['source']==old['current_source']
            entry.update(meaning_judgment_reused_only_for_identical_same_location_output=True)
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
    value=dict(schema=1,platform='Windows',before_build='801704',after_build='801801',reviewed_locations=124,
        chapters_sampled=124,changed_locations_reinspected=len(changed),identical_location_judgments_reused=len(same),
        all_124_original_source_strings_preserved=True,cohorts=cohorts,entries=entries,
        original_semantic_review_sha256=digest(previous_path),sample_sha256=digest(review/'sample.json'),manual_sha256=digest(manual_path),
        before_summary_sha256=sample['before_summary_sha256'],current_summary_sha256=sample['after_summary_sha256'],
        native_output_sha256=digest(folder/'output.jsonl'),application_modified=True,short_clause_recovery_in_application=True,
        frozen_candidate_reference_not_supplied_to_application=True,model_weights_changed=False,
        all_chapter_words_visually_reviewed=False,population_accuracy_estimate=False,screen_attempt_failure_probability=None,target_achieved=False)
    atomic(ROOT/'benchmarks/full-comics/windows8018-heldout-semantic-review.json',json.dumps(value,ensure_ascii=False,indent=2))
    m=cohorts['all_124_including_clipped_edges'];images=''.join(f'<img loading="lazy" src="sheet-{i:02d}.jpg" alt="Comparación {i}">' for i in range(1,(len(changed)+1)//2+1))
    atomic(review/'index.html',f'''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luma · Windows8018</title><style>body{{font:17px system-ui;background:#f1f4ed;color:#243b2b;margin:24px}}img{{display:block;max-width:100%;margin:24px auto}}p{{max-width:1100px;line-height:1.6}}</style><h1>Windows8018 · recuperación de frases cortas</h1><p>La aplicación real procesó los mismos 124 recortes originales, sin recibir las referencias ni respuestas. Conservó exactamente el reconocimiento en todas las ubicaciones. Las cuatro traducciones que cambiaron se cotejaron con ambos originales; 120 salidas idénticas conservaron su dictamen anterior.</p><p><b>{m['before_not_approved']} → {m['after_not_approved']} sin aprobar</b>, {m['corrected']} correcciones completas y {m['regressed']} regresiones observadas. Dos cambios recuperan una parte pero conservan otro defecto y siguen sin aprobarse. Quedan {m['after_clear_errors']} errores claros y {m['after_categories'].get('needs_improvement',0)} casos que requieren mejora.</p><p>Estas son ubicaciones de diálogo, no intentos de pantalla completa. La probabilidad de fallo de la app sigue sin establecerse; el objetivo inferior al 5 % todavía no está acreditado. La revisión del conjunto completo continúa y los modelos permanecen sin cambios.</p><p><a href="../../metrics/index.html">Resultados agregados</a> · <a href="../paint/index.html">Dibujo de la aplicación</a></p>{images}</html>''')
    print(json.dumps({k:v for k,v in value.items() if k!='entries'}),flush=True)


if __name__=='__main__':main()
