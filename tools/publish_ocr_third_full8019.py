"""Close all124 third-cohort OCR inventories, including the108 unchanged crops."""
import collections
import json
from audit_corpus_quality import ROOT,QA,atomic,digest,read,records
from evaluate_ocr_reader_comparison import compare
from evaluate_ocr_apostrophes8019 import strict_compare


def main():
    out=QA/'ocr-apostrophes8019';review=out/'remaining-third';sample=read(review/'sample.json')
    manual_path=review/'manual-transcriptions.json';manual={r[0]:r for r in read(manual_path)}
    assert set(manual)==set(range(1,109))
    old_path=ROOT/'benchmarks/full-comics/ocr8017-coverage-heldout-review.json';old=read(old_path)
    assert digest(old_path)==sample['previous_changed_review_sha256']
    previous={r['location_id']:r for r in old['entries']}
    folder=QA/'ocr-coverage8017-holdout';all_cases=read(folder/'sample.json')['cases']
    assert digest(folder/'sample.json')==sample['original_sample_sha256']
    target=out/'ocr-coverage8017-holdout-output.jsonl';actual={r['id']:r for r in records(target)}
    assert digest(target)==sample['native_output_sha256']
    remaining={c['id']:(c,manual[c['review_id']]) for c in sample['cases']}
    entries=[]
    for case in all_cases:
        ident=case['id'];row=actual[ident]
        if ident in remaining:
            selected,(_,truth,clipped,note)=remaining[ident]
            assert selected['candidate']==row['selected']
            reused=False
        else:
            prior=previous[ident];truth=prior['expected_visible_english'];clipped=None;note=prior['note_es'];reused=True
        assert row['base']==case['readings']['current']
        entries.append(dict(id=ident,expected_visible_english=truth,source=row['base'],selected=row['selected'],
            before=compare(truth,row['base']),after=compare(truth,row['selected']),
            before_strict=strict_compare(truth,row['base']),after_strict=strict_compare(truth,row['selected']),
            edge_clipped=clipped,text_present=bool(truth.strip()),note_es=note,
            transcription_reused_from_previously_inspected_identical_pixels=reused))
    metrics={}
    for policy in ['legacy','strict_apostrophes']:
        suffix='' if policy=='legacy' else '_strict';before=[r['before'+suffix] for r in entries];after=[r['after'+suffix] for r in entries]
        metrics[policy]=dict(words=sum(r['expected_words'] for r in before),
            before_word_errors=sum(r['word_errors'] for r in before),after_word_errors=sum(r['word_errors'] for r in after),
            before_crops_with_word_errors=sum(r['word_errors']>0 for r in before),after_crops_with_word_errors=sum(r['word_errors']>0 for r in after),
            fully_corrected=sum(b['word_errors']>0 and a['word_errors']==0 for b,a in zip(before,after)),
            regressed=sum(b['word_errors']==0 and a['word_errors']>0 for b,a in zip(before,after)))
    for label in ['before','after']:
        counts=collections.Counter()
        for r in entries:counts.update(r[label]['edit_categories'])
        metrics['legacy'][label+'_edit_categories']=dict(counts)
    value=dict(schema=1,crops_visually_reviewed=124,additional_unchanged_crops_reviewed=108,
        prior_changed_pixel_transcriptions_reused=16,words=metrics['legacy']['words'],metrics=metrics,entries=entries,
        negative_control_crops_without_dialogue=sum(not r['text_present'] for r in entries),
        manual_sha256=digest(manual_path),source_sample_sha256=digest(review/'sample.json'),previous_review_sha256=digest(old_path),
        native_output_sha256=digest(target),candidate_provenance_sha256=digest(out/'summary.json'),
        internal_apostrophes_preserved=True,meanings_of_spanish_outputs_reviewed=False,
        transcription_supplied_to_policy=False,application_modified=False,model_weights_changed=False,
        all_chapter_words_visually_reviewed=False,screen_attempt_failure_probability=None,target_achieved=False)
    atomic(ROOT/'benchmarks/full-comics/ocr8019-third-full-review.json',json.dumps(value,ensure_ascii=False,indent=2))
    m=metrics['strict_apostrophes'];images=''.join(f'<img loading="lazy" src="sheet-{i:02d}.jpg" alt="Lecturas {i}">' for i in range(1,28))
    atomic(review/'index.html',f'''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luma · inventario OCR completo del lote</title><style>body{{font:17px system-ui;background:#f1f4ed;color:#243b2b;margin:24px}}p{{max-width:1100px;line-height:1.6}}img{{max-width:100%;display:block;margin:24px auto}}</style><h1>Inventario OCR · tercer lote completo</h1><p>Se inspeccionaron las 108 lecturas sin cambios y se conservaron las 16 transcripciones anteriores sobre los mismos píxeles. Son 124 recortes con {value['words']} palabras visibles y un control sin diálogo. Se cuentan también las palabras omitidas en salidas que no cambiaron.</p><p>Con apóstrofos conservados: <b>{m['before_word_errors']} → {m['after_word_errors']} errores de palabra</b>, <b>{m['before_crops_with_word_errors']} → {m['after_crops_with_word_errors']} recortes con errores</b>, {m['fully_corrected']} correcciones completas y {m['regressed']} regresiones observadas. La comparación histórica que ignoraba apóstrofos se conserva por separado.</p><p>El candidato sigue aislado de la aplicación. Este es un inventario de lectura de recortes; no acredita el sentido de la traducción española ni la cobertura de pantallas o capítulos completos. La probabilidad de fallo por uso sigue sin establecerse.</p><p><a href="../../metrics/index.html">Resultados agregados</a></p>{images}</html>''')
    print(json.dumps({k:v for k,v in value.items() if k!='entries'}),flush=True)


if __name__=='__main__':main()
