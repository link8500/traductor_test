"""Publish adjudicated real inference, preserving the fixed OCR comparison.

The 620-location sample and the selected omission diagnosis are separate.
Reference material and manual answers are read only after native inference.
"""
import collections
import json
import pathlib
from audit_corpus_quality import ROOT, QA, CLEAR_ERRORS, read, records, digest, atomic, reduction, extended_semantic_comparison


def counts(entries):
    valid=[e for e in entries if not e.get('comparison_excluded',False) and 'unresolved' not in (e['before'],e['after'])]
    before=sum(e['before'] in CLEAR_ERRORS for e in valid);after=sum(e['after'] in CLEAR_ERRORS for e in valid)
    fixed=sum(e['before'] in CLEAR_ERRORS and e['after'] not in CLEAR_ERRORS for e in valid)
    regressed=sum(e['before'] not in CLEAR_ERRORS and e['after'] in CLEAR_ERRORS for e in valid)
    assert before-after==fixed-regressed
    return dict(reviewed_regions=len(entries),comparable_regions=len(valid),excluded_unresolved_regions=len(entries)-len(valid),
        before_errors=before,after_errors=after,corrected_regions=fixed,regressed_regions=regressed,
        relative_error_reduction_percent=reduction(before,after),before_categories=dict(collections.Counter(e['before'] for e in valid)),
        after_categories=dict(collections.Counter(e['after'] for e in valid)))


def validate_sample(folder,output_sha):
    sample=read(folder/'sample.json');assert sample.get('inference_output_sha256',sample.get('native_output_sha256'))==output_sha
    decisions=read(folder/'manual-decisions.json');manual={r[0]:r for r in decisions}
    assert len(manual)==len(decisions)==len(sample['cases']) and set(manual)=={c['id'] for c in sample['cases']}
    for case in sample['cases']:
        for key in ['source_page','reference_page']:
            if key in case:assert digest(pathlib.Path(case[key]['path']))==case[key]['sha256']
    return sample,manual


def main():
    folder=QA/'sentence-coverage8014';proof=read(folder/'provenance.json');summary=read(folder/'summary.json')
    assert summary['inputs']==len(records(folder/'input.jsonl'))==len(records(folder/'output.jsonl'))==723
    assert digest(folder/'output.jsonl')==summary['output_sha256'] and digest(folder/'provenance.json')==summary['provenance_sha256']
    for key,path in [('source_sha256',ROOT/'native/local_translation.cpp'),('header_sha256',ROOT/'native/local_translation.h'),
        ('coverage_policy_sha256',ROOT/'native/translation_coverage.h'),('binary_sha256',ROOT/'build/local-model8014/Release/luma_translate.exe')]:
        assert digest(path)==proof[key],('Native implementation changed',key)
    for name,sha in proof['assets'].items():assert digest(ROOT/'assets/models/opus-en-es'/name)==sha
    previous_path=ROOT/'benchmarks/full-comics/current8011-extended-semantic-review.json';previous=read(previous_path);extended_semantic_comparison()
    visual,manual=validate_sample(folder/'visual-review',summary['output_sha256'])
    assert visual['inference_complete'] and visual['source_review_sha256']==digest(previous_path)
    changed={c['original_id']:c for c in visual['cases']};pairs={c['id']:c for c in read(folder/'reviewed.json')['cases']}
    entries=[]
    for old in previous['entries']:
        pair=pairs[old['id']];row=pair['current'];assert pair['source']==old['source'] and pair['control_translation']==old['translation']
        note='Salida idéntica en la misma ubicación; se conserva el dictamen anterior.';after=old['after']
        if row['translation']!=old['translation']:
            case=changed[old['id']];_,before,after,note=manual[case['id']]
            assert before==old['after'] and case['translation']==row['translation'] and case['bounds']==old['bounds']
            assert row['whole_translation']==old['translation'] and row['sentence_recovered']
        else:assert old['id'] not in changed
        entries.append(dict(id=old['id'],chapter=old['chapter'],bounds=old['bounds'],source=old['source'],
            before_translation=old['translation'],translation=row['translation'],before=old['after'],after=after,note_es=note,
            judgment_reused_for_identical_output=old['id'] not in changed,
            comparison_excluded='unresolved' in (old['before'],old['after'])))
    assert sum(not e['comparison_excluded'] for e in entries)==previous['comparable_regions']
    fixed=dict(schema=1,**counts(entries),chapters_sampled=124,changed_outputs_visually_reinspected=len(changed),
        identical_output_judgments_reused=len(entries)-len(changed),ocr_pixels_and_source_held_fixed=True,
        translator_weights_changed=False,population_accuracy_estimate=False,all_chapter_words_visually_reviewed=False,
        previous_review_sha256=digest(previous_path),native_provenance_sha256=digest(folder/'provenance.json'),
        native_output_sha256=summary['output_sha256'],visual_sample_sha256=digest(folder/'visual-review/sample.json'),
        manual_decisions_sha256=digest(folder/'visual-review/manual-decisions.json'),app_uses_review_answers=False,entries=entries)
    atomic(ROOT/'benchmarks/full-comics/coverage8014-fixed-ocr-semantic-review.json',json.dumps(fixed,ensure_ascii=False,indent=2))

    # Actual unchanged candidate outputs may reuse an earlier pixel adjudication.
    old_sample=read(QA/'omission-review8011/sample.json');old_manual={r[0]:r for r in read(QA/'omission-review8011/manual-decisions.json')}
    known={(c['chapter']+'-en',c['region_index']):c for c in old_sample['cases']}
    unaligned,new_manual=validate_sample(folder/'unaligned-review',summary['output_sha256'])
    extra={(c['chapter'],c['region_index']):c for c in unaligned['cases']}
    entries=[]
    for pair in read(folder/'omission-candidate.json')['cases']:
        row=pair['current']
        if not row['sentence_recovered']:continue
        key=(pair['chapter'],pair['region_index'])
        if key in known:
            case=known[key];_,before,after,note=old_manual[case['id']]
            assert case['source']==pair['source'] and case['translation']==row['translation'] and case['before_translation']==pair['control_translation']
            for p in [case['source_page'],case['reference_page']]:assert digest(pathlib.Path(p['path']))==p['sha256']
            reused=True
        else:
            case=extra[key];_,before,after,note=new_manual[case['id']];reused=False
            assert case['source']==pair['source'] and case['translation']==row['translation'] and case['before_translation']==pair['control_translation']
        assert row['whole_translation']==pair['control_translation']
        entries.append(dict(chapter=pair['chapter'],region_index=pair['region_index'],source=pair['source'],before_translation=pair['control_translation'],
            translation=row['translation'],before=before,after=after,note_es=note,prior_identical_candidate_judgment_reused=reused,
            spanish_reference_aligned=key in known))
    diagnostic=dict(schema=1,**counts(entries),changed_candidates_only=True,automatic_candidate_selection=True,
        prior_identical_candidate_judgments_reused=sum(e['prior_identical_candidate_judgment_reused'] for e in entries),
        newly_inspected_unaligned_regions=len(extra),native_output_sha256=summary['output_sha256'],
        previous_sample_sha256=digest(QA/'omission-review8011/sample.json'),previous_manual_sha256=digest(QA/'omission-review8011/manual-decisions.json'),
        new_sample_sha256=digest(folder/'unaligned-review/sample.json'),new_manual_sha256=digest(folder/'unaligned-review/manual-decisions.json'),
        overlaps_with_fixed_sample_not_added=True,app_uses_review_answers=False,population_accuracy_estimate=False,
        all_chapter_words_visually_reviewed=False,entries=entries)
    atomic(ROOT/'benchmarks/full-comics/coverage8014-omission-diagnostic-semantic-review.json',json.dumps(diagnostic,ensure_ascii=False,indent=2))
    for name,title,note in [('visual-review','Recuperación de frases · comparación fija','Original inglés, referencia española y traducciones nativas anterior y actual.'),
        ('unaligned-review','Diagnóstico sin referencia alineada','Evaluación contra los píxeles del original inglés. No se presenta un globo español ajeno como referencia.')]:
        location=folder/name;sample=read(location/'sample.json')
        pictures=''.join(f'<img loading="lazy" src="sheet-{i+1:02d}.jpg" alt="Hoja de comparación {i+1}">' for i in range((len(sample['cases'])+3)//4))
        atomic(location/'index.html',f'<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luma · {title}</title><style>body{{font:17px system-ui;background:#f1f4ed;color:#243b2b;margin:24px}}img{{display:block;width:100%;max-width:1440px;margin:24px auto}}p{{max-width:950px;line-height:1.6}}a{{color:#226045}}</style><h1>{title}</h1><p>{len(sample["cases"])} salidas modificadas inspeccionadas. {note} Los textos esperados no se suministran al traductor. Esto no aprueba todas las palabras de los capítulos.</p><p><a href="../../metrics/index.html">Resultados agregados</a> · <a href="../unaligned-review/index.html">Diagnóstico sin referencia alineada</a></p>{pictures}</html>')
    print(json.dumps(dict(fixed_sample={k:v for k,v in fixed.items() if k!='entries'},diagnostic={k:v for k,v in diagnostic.items() if k!='entries'})))


if __name__=='__main__':main()
