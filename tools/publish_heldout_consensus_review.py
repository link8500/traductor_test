"""Adjudicate every changed held-out output; unchanged inputs stay unapproved."""
import json
import pathlib
from audit_corpus_quality import ROOT,QA,read,records,digest,atomic
from evaluate_ocr_reader_comparison import compare


def main():
    folder=QA/'ocr-reader-heldout8016/consensus';sample=read(folder/'sample.json')
    manual_path=folder/'manual-transcriptions.json';manual={r[0]:r for r in read(manual_path)}
    assert set(manual)=={c['id'] for c in sample['cases']}
    assert digest(folder/'input.jsonl')==sample['input_sha256'] and digest(folder/'output.jsonl')==sample['output_sha256']
    source=QA/'ocr-reader-heldout8016-source';selection=read(source/'selection-provenance.json')
    assert digest(source/'sample.json')==selection['selection_sha256'] and selection['selection_before_inference']
    assert sample['policy_sha256']==selection['frozen_policy_sha256'] and sample['binary_sha256']==selection['frozen_binary_sha256']
    entries=[]
    for case in sample['cases']:
        assert digest(pathlib.Path(case['source_page']['path']))==case['source_page']['sha256']
        assert digest(pathlib.Path(case['preview']))==case['preview_sha256']
        _,truth,note=manual[case['id']];before=compare(truth,case['consensus']['base']);after=compare(truth,case['consensus']['selected'])
        entries.append(dict(id=case['id'],location_id=case['original_id'],expected_visible_english=truth,before=before,after=after,note_es=note))
    value=dict(schema=1,locations_inferred=124,changed_locations_visually_reviewed=len(entries),unchanged_locations_without_meaning_approval=124-len(entries),
        before_word_errors=sum(e['before']['word_errors'] for e in entries),after_word_errors=sum(e['after']['word_errors'] for e in entries),
        changed_crops_fixed=sum(e['before']['word_errors']>0 and e['after']['word_errors']==0 for e in entries),
        changed_crops_regressed=sum(e['before']['word_errors']==0 and e['after']['word_errors']>0 for e in entries),
        changed_crops_still_have_word_errors=sum(e['after']['word_errors']>0 for e in entries),
        source_locations_disjoint_from_previous_744=True,rule_frozen_before_location_selection=True,manual_transcription_used_for_inference=False,
        screen_attempt_failure_probability=None,all_chapter_words_visually_reviewed=False,population_accuracy_estimate=False,
        application_modified=False,policy_sha256=sample['policy_sha256'],selection_provenance_sha256=sample['selection_provenance_sha256'],
        sample_sha256=digest(folder/'sample.json'),manual_sha256=digest(manual_path),entries=entries)
    atomic(ROOT/'benchmarks/full-comics/ocr8016-consensus-heldout-review.json',json.dumps(value,ensure_ascii=False,indent=2))
    images=''.join(f'<img loading="lazy" src="sheet-{i:02d}.jpg" alt="Cotejo {i}">' for i in range(1,5))
    atomic(folder/'index.html',f'<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luma · Consenso OCR en ubicaciones nuevas</title><style>body{{font:17px system-ui;background:#f1f4ed;color:#243b2b;margin:24px}}img{{display:block;width:100%;max-width:1500px;margin:24px auto}}p{{line-height:1.6;max-width:1050px}}</style><h1>Consenso OCR · validación en ubicaciones nuevas</h1><p>Se fijó la regla antes de seleccionar otras 124 ubicaciones, excluyendo las 744 anteriores. Se ejecutaron los tres lectores y el consenso congelado. Cambiaron 12 recortes y se cotejaron todos: {value["before_word_errors"]} → {value["after_word_errors"]} errores de palabra entre esas salidas, {value["changed_crops_fixed"]} recortes corregidos por completo y {value["changed_crops_regressed"]} regresiones. {value["changed_crops_still_have_word_errors"]} recortes modificados conservan otro defecto y no se aprueban.</p><p>Los otros 112 recortes conservaron su salida y no se aprueban automáticamente. La regla no puede borrar ni insertar palabras de la lectura base. Todavía no está incorporada a la app: requiere pruebas sobre capturas completas y evaluación de su coste. Este diagnóstico no mide la probabilidad de fallo por pantalla.</p><p><a href="../../metrics/index.html">Resultados agregados</a></p>'+images+'</html>')
    print(json.dumps({k:v for k,v in value.items() if k!='entries'}),flush=True)


if __name__=='__main__':main()
