"""Verify all changed outputs of the complete 124-report omission trial."""
import json
import pathlib
from audit_corpus_quality import ROOT,QA,read,records,digest,atomic
from publish_coverage_regression import counts


def main():
    folder=QA/'full-omission-candidate8016';visual=folder/'visual-review';sample=read(visual/'sample.json');summary=read(folder/'summary.json')
    assert digest(folder/'changed.json')==sample['candidate_output_sha256']==summary['changed_sha256']
    decisions={r[0]:r for r in read(visual/'manual-decisions.json')};assert set(decisions)=={c['id'] for c in sample['cases']}
    entries=[]
    for case in sample['cases']:
        for key in ['source_page','reference_page']:
            page=case[key]
            if page:assert digest(pathlib.Path(page['path']))==page['sha256']
        _,before,after,note=decisions[case['id']]
        entries.append(dict(chapter=case['chapter'],region=case['region'],source=case['source'],before_translation=case['before_translation'],translation=case['translation'],
            before=before,after=after,note_es=note,reference_proposal_present=case['reference_page'] is not None,new_pixel_inspection=True))
    for case in sample['reused_pixel_judgments']:
        _,before,after,note=case['decision'];assert digest(pathlib.Path(case['source_page']['path']))==case['source_page']['sha256']
        entries.append(dict(chapter=case['chapter'],region=case['region'],source=case['source'],before_translation=case['before_translation'],translation=case['translation'],
            before=before,after=after,note_es=note,new_pixel_inspection=False))
    assert len(entries)==len({(e['chapter'],e['region']) for e in entries})==sample['changed_regions']==summary['changed_regions']==37
    proof=read(folder/'provenance.json');assert digest(folder/'provenance.json')==summary['provenance_sha256']
    for chapter,hashes in proof['chapters'].items():
        path=QA/'translated-en8014-fixed-ocr'/(chapter+'-en.jsonl')
        assert digest(path)==hashes['report_sha256'] and digest(path.with_name(path.stem+'.done.json'))==hashes['status_sha256']
    value=dict(schema=1,**counts(entries),chapters_scanned=124,regions_scanned=18179,changed_candidates_only=True,
        fresh_native_inferences=summary['fresh_inferences'],reused_identical_source_native_inferences=summary['reused_identical_native_seed_sources'],
        new_pixel_inspections=len(sample['cases']),same_pixels_output_judgments_reused=len(sample['reused_pixel_judgments']),
        all_changed_regions_semantically_reviewed=True,unchanged_region_meaning_reviewed=False,
        application_modified=False,translator_weights_changed=False,screen_attempt_failure_probability=None,
        all_chapter_words_visually_reviewed=False,population_accuracy_estimate=False,overlaps_with_744_sample_do_not_add_counts=True,
        sample_sha256=digest(visual/'sample.json'),manual_sha256=digest(visual/'manual-decisions.json'),provenance_sha256=digest(folder/'provenance.json'),entries=entries)
    atomic(ROOT/'benchmarks/full-comics/full-omission8016-semantic-review.json',json.dumps(value,ensure_ascii=False,indent=2))
    pictures=''.join(f'<img loading="lazy" src="sheet-{i:02d}.jpg" alt="Comparación {i}">' for i in range(1,17))
    atomic(visual/'index.html',f'<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luma · Omisiones en el recorrido completo</title><style>body{{font:17px system-ui;background:#f1f4ed;color:#243b2b;margin:24px}}img{{display:block;width:100%;max-width:1440px;margin:24px auto}}p{{line-height:1.6;max-width:1050px}}</style><h1>Recuperación de omisiones · recorrido completo de candidatos</h1><p>Se aplicó la selección nativa a las 18.179 regiones de 124 capítulos. Cambiaron 37 traducciones y se cotejaron todas: 32 regiones inspeccionadas aquí y cinco dictámenes de la misma fuente, salida y píxeles reutilizados de la muestra anterior. Entre estas salidas seleccionadas, los errores claros pasan de {value["before_errors"]} a {value["after_errors"]}: {value["corrected_regions"]} correcciones completas y {value["regressed_regions"]} regresiones. Las otras 18.142 salidas se conservaron; eso no aprueba su significado.</p><p>Las referencias españolas son propuestas de alineación y pueden adaptar el inglés. Las evaluaciones se basan en los píxeles del original, sin suministrarlos como respuestas al modelo. Los recuentos se solapan con la muestra fija y no se suman. No es una revisión de todas las palabras ni mide la probabilidad de fallo de pantallas completas.</p><p><a href="../../metrics/index.html">Resultados agregados</a></p>'+pictures+'</html>')
    print(json.dumps({k:v for k,v in value.items() if k!='entries'}),flush=True)


if __name__=='__main__':main()
