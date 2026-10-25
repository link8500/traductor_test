"""Close the complete paired124-location quantization review, preserving failures."""
import collections
import json
from audit_corpus_quality import ROOT,QA,atomic,digest,read


def main():
    folder=QA/'int8-translation8018';review=folder/'visual-review';sample=read(review/'sample.json')
    previous=ROOT/'benchmarks/full-comics/windows8018-heldout-semantic-review.json'
    assert digest(previous)==sample['previous_semantic_review_sha256']
    assert digest(folder/'summary.json')==sample['inference_summary_sha256']
    manual_path=review/'manual-decisions.json';manual={r[0]:r for r in read(manual_path)}
    revisions_path=review/'baseline-judgment-revisions.json';revisions={r[0]:r for r in read(revisions_path)}
    assert set(manual)==set(range(1,53)) and set(revisions)=={6,9}
    changed={r['location_id']:r for r in sample['cases']};same={r['id']:r for r in sample['identical_location_judgments']}
    entries=[]
    for old in read(previous)['entries']:
        ident=old['id'];entry=dict(old,before=old['after'],before_translation=old['translation'])
        if ident in changed:
            case=changed[ident];_,after,note=manual[case['id']]
            if case['id'] in revisions:
                _,previous_judgment,revised,note_revision=revisions[case['id']]
                assert previous_judgment==entry['before']
                entry.update(before=revised,previous_before_judgment=previous_judgment,before_judgment_revision_es=note_revision)
            entry.update(after=after,translation=case['translation'],note_es=note,meaning_reinspected_against_original_and_reference=True)
        else:
            assert same[ident]['translation']==old['translation']
            entry.update(meaning_judgment_reused_only_for_identical_same_location_output=True)
        entries.append(entry)
    b=collections.Counter(r['before'] for r in entries);a=collections.Counter(r['after'] for r in entries)
    value=dict(schema=1,policy_build='801801',comparison='int4 versus existing int8 of the same upstream model',
        reviewed_locations=124,changed_locations_visually_reviewed=52,identical_location_judgments_reused=72,
        baseline_judgment_revisions=len(revisions),before_categories=dict(b),after_categories=dict(a),
        before_not_approved=124-b['acceptable'],after_not_approved=124-a['acceptable'],
        fully_corrected=sum(r['before']!='acceptable' and r['after']=='acceptable' for r in entries),
        regressed=sum(r['before']=='acceptable' and r['after']!='acceptable' for r in entries),entries=entries,
        previous_semantic_review_sha256=digest(previous),sample_sha256=digest(review/'sample.json'),manual_sha256=digest(manual_path),
        judgment_revisions_sha256=digest(revisions_path),summary_sha256=digest(folder/'summary.json'),
        all_changed_outputs_reviewed=True,application_assets_modified=False,model_training_performed=False,
        quantization_variant_accepted_for_deployment=False,screen_attempt_failure_probability=None,
        all_chapter_words_visually_reviewed=False,population_accuracy_estimate=False,target_achieved=False)
    atomic(ROOT/'benchmarks/full-comics/int8-translation8018-semantic-review.json',json.dumps(value,ensure_ascii=False,indent=2))
    images=''.join(f'<img loading="lazy" src="sheet-{i:02d}.jpg" alt="Comparación {i}">' for i in range(1,14))
    atomic(review/'index.html',f'''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luma · precisión numérica</title><style>body{{font:17px system-ui;margin:24px;background:#f1f4ed;color:#243b2b}}p{{max-width:1100px;line-height:1.6}}img{{max-width:100%;display:block;margin:24px auto}}</style><h1>Modelo local · comparación de precisión numérica</h1><p>Se tradujeron las 137 entradas de los mismos 124 recortes con int8. Se cotejaron los 52 resultados que cambiaron contra los originales y se conservaron 72 dictámenes de salidas idénticas. Se corrigieron dos dictámenes anteriores al detectar defectos presentes en ambas variantes.</p><p><b>{value['before_not_approved']} → {value['after_not_approved']} sin aprobar</b>, {value['fully_corrected']} correcciones completas y {value['regressed']} regresiones. Esta variante no se incorpora a la aplicación: no acredita una mejora global en este conjunto. No hubo entrenamiento ni cambios en los modelos instalados.</p><p>Estas ubicaciones no son pantallas completas; el riesgo de fallo por uso sigue sin establecerse.</p>{images}</html>''')
    print(json.dumps({k:v for k,v in value.items() if k!='entries'}),flush=True)


if __name__=='__main__':main()
