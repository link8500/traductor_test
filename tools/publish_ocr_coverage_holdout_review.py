"""Publish every changed reading of the separately frozen third OCR trial."""
import json
import pathlib
from audit_corpus_quality import ROOT,QA,atomic,digest,read
from evaluate_ocr_reader_comparison import compare


def main():
    folder=QA/'ocr-coverage8017-holdout/coverage';sample=read(folder/'sample.json')
    manual_path=folder/'manual-transcriptions.json';manual={r[0]:r for r in read(manual_path)}
    assert len(manual)==len(sample['cases'])==16
    assert digest(folder/'output.jsonl')==sample['output_sha256']
    selection=read(QA/'ocr-coverage8017-holdout-source/selection-provenance.json')
    assert selection['rule_frozen_before_selection'] and selection['excluded_previously_reviewed_locations']==868
    assert sample['policy_sha256']==selection['policy_sha256'] and sample['binary_sha256']==selection['binary_sha256']
    entries=[]
    for case in sample['cases']:
        assert digest(pathlib.Path(case['preview']))==case['preview_sha256']
        ident,truth,note=manual[case['id']];row=case['candidate']
        entries.append(dict(id=ident,location_id=case['original_id'],expected_visible_english=truth,
            before=compare(truth,row['base']),after=compare(truth,row['selected']),
            insertions=row['insertions'],replacements=row['replacements'],note_es=note))
    value=dict(schema=1,locations_inferred=124,changed_locations_visually_reviewed=16,
        unchanged_locations_without_meaning_approval=108,
        before_word_errors=sum(e['before']['word_errors'] for e in entries),
        after_word_errors=sum(e['after']['word_errors'] for e in entries),
        changed_crops_fixed=sum(e['before']['word_errors']>0 and e['after']['word_errors']==0 for e in entries),
        changed_crops_regressed=sum(e['before']['word_errors']==0 and e['after']['word_errors']>0 for e in entries),
        changed_crops_still_have_word_errors=sum(e['after']['word_errors']>0 for e in entries),
        before_omitted_words=sum(e['before']['edit_categories'].get('omitted_word',0) for e in entries),
        after_omitted_words=sum(e['after']['edit_categories'].get('omitted_word',0) for e in entries),
        source_locations_disjoint_from_previous_868=True,rule_frozen_before_location_selection=True,
        manual_transcription_used_for_inference=False,application_modified=False,
        screen_attempt_failure_probability=None,all_chapter_words_visually_reviewed=False,
        population_accuracy_estimate=False,sample_sha256=digest(folder/'sample.json'),
        manual_sha256=digest(manual_path),selection_provenance_sha256=sample['selection_provenance_sha256'],
        policy_sha256=sample['policy_sha256'],binary_sha256=sample['binary_sha256'],entries=entries)
    atomic(ROOT/'benchmarks/full-comics/ocr8017-coverage-heldout-review.json',json.dumps(value,ensure_ascii=False,indent=2))
    images=''.join(f'<img loading="lazy" src="sheet-{i:02d}.jpg" alt="Cotejo {i}">' for i in range(1,7))
    atomic(folder/'index.html',f'''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luma · Recuperación OCR en ubicaciones nuevas</title><style>body{{font:17px system-ui;background:#f1f4ed;color:#243b2b;margin:24px}}img{{display:block;width:100%;max-width:1500px;margin:24px auto}}p{{line-height:1.6;max-width:1100px}}</style><h1>Recuperación OCR · tercer lote</h1><p>Se fijó el candidato antes de seleccionar otras 124 ubicaciones, excluyendo las 868 anteriores. Se cotejaron los 16 cambios: <b>{value['before_word_errors']} → {value['after_word_errors']} errores de palabra entre esas salidas</b>, {value['changed_crops_fixed']} recortes corregidos por completo, {value['changed_crops_regressed']} regresiones y {value['changed_crops_still_have_word_errors']} recortes modificados aún defectuosos. Omisiones entre los cambios: {value['before_omitted_words']} → {value['after_omitted_words']}.</p><p>Los otros 108 recortes no han recibido revisión semántica. No se estima una tasa global ni la probabilidad de fallo de la aplicación. Este lector sigue siendo experimental y no está incluido en el ejecutable de Windows.</p><p><a href="../../metrics/index.html">Resultados agregados</a></p>{images}</html>''')
    print(json.dumps({k:v for k,v in value.items() if k!='entries'}),flush=True)


if __name__=='__main__':main()
