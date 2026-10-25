"""Record every changed meaning in the complete fixed-OCR trial, including regressions."""
import collections
import json
from audit_corpus_quality import ROOT, QA, atomic, digest, read


def main():
    folder=QA/'full-corpus-coverage8018';review=folder/'visual-review-compact'
    sample=read(review/'sample.json');summary=read(folder/'summary.json')
    assert digest(folder/'changed.json')==sample['changed_output_sha256']==summary['changed_sha256']
    assert digest(folder/'summary.json')==sample['corpus_summary_sha256']
    manual_path=review/'manual-decisions.json';manual={r[0]:r for r in read(manual_path)}
    assert set(manual)==set(range(1,len(sample['cases'])+1)) and len(manual)==119
    allowed={'acceptable','incorrect','incomplete','needs_improvement','fragmented'}
    entries=[]
    for case in sample['cases']:
        ident,before,after,note=manual[case['id']]
        assert before in allowed and after in allowed and note
        entries.append(dict(case,before=before,after=after,note_es=note,meaning_reviewed=True,
            original_english_pixels_visually_inspected=True,
            spanish_reference_alignment_individually_checked=True,
            spanish_reference_not_assumed_literal_gold=True,
            partial_content_worsening_observed=ident==50))
    before=collections.Counter(r['before'] for r in entries);after=collections.Counter(r['after'] for r in entries)
    b=len(entries)-before['acceptable'];a=len(entries)-after['acceptable']
    value=dict(schema=1,variant='801801',scope='All changed outputs in a complete124-chapter fixed-OCR policy comparison',
        chapters_scanned=124,source_locations_scanned=18179,changed_chapters=len({r['chapter'] for r in entries}),
        changed_locations_reviewed=len(entries),unchanged_locations_not_newly_approved=18179-len(entries),
        paired_source_results=summary['paired_source_results'],fresh_native_inferences=summary['fresh_native_inferences'],
        reused_exact_source_native_results=summary['reused_identical_native_results'],
        before_categories=dict(before),after_categories=dict(after),before_not_approved=b,after_not_approved=a,
        fully_corrected=sum(r['before']!='acceptable' and r['after']=='acceptable' for r in entries),
        full_region_regressions=sum(r['before']=='acceptable' and r['after']!='acceptable' for r in entries),
        already_failed_regions_with_partial_content_worsening=sum(r['partial_content_worsening_observed'] for r in entries),
        relative_unapproved_reduction_percent=100*(b-a)/b,
        entries=entries,sample_sha256=digest(review/'sample.json'),manual_sha256=digest(manual_path),
        inference_summary_sha256=digest(folder/'summary.json'),paired_inferences_sha256=summary['paired_inferences_sha256'],
        provenance_sha256=summary['provenance_sha256'],
        all_changed_outputs_reviewed=True,all_chapter_words_visually_reviewed=False,
        unchanged_regions_automatically_approved=False,original_ocr_preserved=True,
        model_weights_changed=False,reference_or_manual_answers_supplied_to_translator=False,
        screen_attempt_failure_probability=None,target_achieved=False,ready_for_release=False)
    dest=ROOT/'benchmarks/full-comics/full-corpus-coverage8018-semantic-review.json'
    atomic(dest,json.dumps(value,ensure_ascii=False,indent=2))
    images=''.join(f'<img loading="lazy" src="sheet-{i:02d}.jpg" alt="Comparación {i}">' for i in range(1,31))
    atomic(review/'index.html',f'''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luma · revisión amplia</title><style>body{{font:17px system-ui;margin:24px;background:#f1f4ed;color:#243b2b}}p{{max-width:1100px;line-height:1.6}}img{{max-width:100%;display:block;margin:24px auto}}</style><h1>Recuperación de frases · ensayo amplio</h1><p>Se recorrieron las 18.179 regiones del control de 124 capítulos con el mismo OCR. Los 119 resultados que cambiaron se revisaron visualmente contra sus originales: <b>{b} → {a} sin aprobar</b>, {value['fully_corrected']} correcciones completas y {value['full_region_regressions']} regresión completa. También empeoró parte de una región que ya tenía otro error.</p><p>Este ensayo se conserva como evidencia y no está listo para publicarse: requiere proteger el contenido previamente correcto. Las regiones sin cambios no se dan por aprobadas. El OCR de este control es anterior al Windows actual, y no se ha revisado palabra por palabra el contenido completo. La probabilidad de fallo por pantalla sigue sin establecerse.</p><p><a href="../../metrics/index.html">Resultados agregados</a></p>{images}</html>''')
    print(json.dumps({k:v for k,v in value.items() if k!='entries'}),flush=True)


if __name__=='__main__':main()
