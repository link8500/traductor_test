"""Consolidate the sixth independent location per chapter, preserving history."""
import json
import pathlib
from audit_corpus_quality import ROOT, QA, CURRENT, BASELINE, CLEAR_ERRORS, read, records, digest, atomic, extended_semantic_comparison
from prepare_corpus_review_sample import overlap
from publish_coverage_regression import counts


def main():
    folder=QA/'corpus-review-sixth8011';sample_path=folder/'sample.json';sample=read(sample_path)
    manual_path=folder/'manual-decisions.json';manual=read(manual_path);decisions={r[0]:r for r in manual}
    assert len(decisions)==len(manual)==len(sample['cases'])==124
    assert set(decisions)=={c['id'] for c in sample['cases']}
    previous_path=ROOT/'benchmarks/full-comics/current8011-extended-semantic-review.json'
    previous=read(previous_path);extended_semantic_comparison();entries=[];validated=set()
    for case in sample['cases']:
        assert case['current_folder']==CURRENT and case['baseline_folder']==BASELINE
        for key,sha in [('current_folder','current_report_sha256'),('baseline_folder','baseline_report_sha256')]:
            assert digest(QA/case[key]/(case['chapter']+'-en.jsonl'))==case[sha]
        row=records(QA/CURRENT/(case['chapter']+'-en.jsonl'))[case['current_region']]
        assert all(row[k]==case[k] for k in ['source','translation','bounds'])
        assert all(not(e['chapter']==case['chapter'] and e['source_image']==case['source_image'] and overlap(e['bounds'],case['bounds'])>.5) for e in previous['entries'])
        for key in ['source_page','reference_page']:
            page=case[key];path=pathlib.Path(page['path'])
            if path not in validated:assert digest(path)==page['sha256'];validated.add(path)
        _,before,after,note=decisions[case['id']]
        assert before in CLEAR_ERRORS|{'acceptable','needs_improvement','unresolved'} and after in CLEAR_ERRORS|{'acceptable','needs_improvement','unresolved'}
        entries.append(dict(id=case['id'],before=before,after=after,note_es=note,source_pixels_inspected=True,reference_pixels_inspected=True))
    review=dict(schema=1,reviewer='assistant',**counts(entries),sample_path=sample_path.relative_to(ROOT).as_posix(),sample_sha256=digest(sample_path),
        manual_decisions_sha256=digest(manual_path),chapters_sampled=124,all_chapter_words_visually_reviewed=False,population_accuracy_estimate=False,
        app_uses_review_answers=False,entries=entries)
    review_path=ROOT/'benchmarks/full-comics/corpus-semantic-review-sixth.json'
    atomic(review_path,json.dumps(review,ensure_ascii=False,indent=2))
    combined=list(previous['entries']);cases={c['id']:c for c in sample['cases']}
    for entry in entries:
        case=cases[entry['id']]
        combined.append({**entry,'id':'sixth-'+str(entry['id']),'original_id':entry['id'],'group':'sixth',
            **{k:case[k] for k in ['chapter','source_image','bounds','source','translation','current_report_sha256','baseline_report_sha256']}})
    value=dict(schema=1,reviewer='assistant',**counts(combined),current_engine=CURRENT,native_engine=previous['native_engine'],
        translation_signature=previous['translation_signature'],chapters_sampled=124,regions_per_chapter=6,single_build_comparison=True,
        original_extended_review_sha256=digest(previous_path),additional_review_sha256=digest(review_path),additional_sample_sha256=digest(sample_path),
        newly_inspected_regions=124,population_accuracy_estimate=False,all_chapter_words_visually_reviewed=False,app_uses_review_answers=False,
        scope='Six disjoint eligible aligned OCR locations per chapter. Never-detected text is not measured. Not an all-word review.',entries=combined)
    assert len(combined)==744 and len({e['chapter'] for e in combined})==124
    combined_path=ROOT/'benchmarks/full-comics/current8011-six-regions-semantic-review.json'
    atomic(combined_path,json.dumps(value,ensure_ascii=False,indent=2))

    # Reuse only byte-identical native output in the same location. Every new
    # source was inferred afresh; no reference or manual answer was an input.
    native_folder=QA/'sentence-coverage8014/additional-sample';native=records(native_folder/'output.jsonl');status=read(native_folder/'summary.json')
    assert status['sample_sha256']==digest(sample_path) and status['output_sha256']==digest(native_folder/'output.jsonl')
    assert len(native)==124 and status['changed_outputs']==0
    old_fixed_path=ROOT/'benchmarks/full-comics/coverage8014-fixed-ocr-semantic-review.json';old_fixed=read(old_fixed_path)
    fixed=list(old_fixed['entries'])
    for case,row in zip(sample['cases'],native):
        assert case['source']==row['source'] and case['translation']==row['translation']
        _,baseline,judgment,note=decisions[case['id']]
        fixed.append(dict(id='sixth-'+str(case['id']),chapter=case['chapter'],bounds=case['bounds'],source=case['source'],
            before_translation=case['translation'],translation=row['translation'],before=judgment,after=judgment,note_es=note,
            judgment_reused_for_identical_output=True,comparison_excluded='unresolved' in (baseline,judgment)))
    baseline_by_id={e['id']:e for e in combined}
    historical=[dict(before=baseline_by_id[e['id']]['before'],after=e['after'],comparison_excluded=e['comparison_excluded']) for e in fixed]
    fixed_value=dict(schema=1,**counts(fixed),chapters_sampled=124,changed_outputs_visually_reinspected=old_fixed['changed_outputs_visually_reinspected'],
        identical_output_judgments_reused=len(fixed)-old_fixed['changed_outputs_visually_reinspected'],
        ocr_pixels_and_source_held_fixed=True,translator_weights_changed=False,population_accuracy_estimate=False,
        all_chapter_words_visually_reviewed=False,app_uses_review_answers=False,previous_six_region_review_sha256=digest(combined_path),
        original_fixed_review_sha256=digest(old_fixed_path),additional_native_summary_sha256=digest(native_folder/'summary.json'),
        additional_native_output_sha256=digest(native_folder/'output.jsonl'),historical_baseline_comparison=counts(historical),entries=fixed)
    assert fixed_value['comparable_regions']==value['comparable_regions'] and fixed_value['before_errors']==value['after_errors']
    atomic(ROOT/'benchmarks/full-comics/coverage8014-six-regions-semantic-review.json',json.dumps(fixed_value,ensure_ascii=False,indent=2))
    pictures=''.join(f'<img loading="lazy" src="sheet-{i:02d}.jpg" alt="Hoja de comparación {i}">' for i in range(1,32))
    atomic(folder/'index.html','<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luma · 124 comparaciones adicionales</title><style>body{font:17px system-ui;background:#f1f4ed;color:#243b2b;margin:24px}img{display:block;width:100%;max-width:1440px;margin:24px auto}p{line-height:1.6;max-width:1000px}a{color:#226045}</style><h1>Luma · 124 comparaciones adicionales</h1><p>Una ubicación por capítulo, sin repetir las 620 anteriores. Original inglés, referencia española y salidas reales de Luma sin editar. Los recortes pueden ser fragmentos de un diálogo; aprobar uno no aprueba el globo completo. La versión nativa 8014 produjo exactamente las mismas traducciones en estas 124 ubicaciones.</p><p><a href="../metrics/index.html">Resultados agregados y alcance</a></p>'+pictures+'</html>')
    print(json.dumps(dict(additional={k:v for k,v in review.items() if k!='entries'},consolidated={k:v for k,v in value.items() if k!='entries'},fixed_native={k:v for k,v in fixed_value.items() if k!='entries'})))


if __name__=='__main__':main()
