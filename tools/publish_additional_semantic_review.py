"""Publish another inspected, disjoint 124-location batch without altering inference.

The 496-location report remains immutable. The new combined report records
its inputs and preserves every regression and unresolved comparison.
"""
import collections
import json
import pathlib

from audit_corpus_quality import ROOT, QA, CURRENT, BASELINE, CLEAR_ERRORS, read, records, digest, atomic, reduction, expanded_semantic_comparison
from prepare_corpus_review_sample import overlap


def main():
    folder=QA/'corpus-review-next8011'
    sample_path=folder/'sample.json';manual_path=folder/'manual-decisions.json'
    sample=read(sample_path);manual_rows=read(manual_path)
    decisions={r[0]:r for r in manual_rows}
    assert len(decisions)==len(manual_rows)==len(sample['cases'])==124
    assert set(decisions)=={c['id'] for c in sample['cases']}
    previous_path=ROOT/'benchmarks/full-comics/current8011-expanded-semantic-review.json'
    previous=read(previous_path);expanded_semantic_comparison()
    entries=[];validated=set()
    for case in sample['cases']:
        assert case['current_folder']==CURRENT and case['baseline_folder']==BASELINE
        for key,sha in [('current_folder','current_report_sha256'),('baseline_folder','baseline_report_sha256')]:
            path=QA/case[key]/(case['chapter']+'-en.jsonl')
            assert digest(path)==case[sha]
        actual=records(QA/CURRENT/(case['chapter']+'-en.jsonl'))[case['current_region']]
        assert all(actual[k]==case[k] for k in ['source','translation','bounds'])
        for key in ['source_page','reference_page']:
            page=case[key];path=pathlib.Path(page['path'])
            if path not in validated:assert digest(path)==page['sha256'];validated.add(path)
        assert all(not(e['chapter']==case['chapter'] and e['source_image']==case['source_image'] and overlap(e['bounds'],case['bounds'])>.5) for e in previous['entries'])
        _,before,after,note=decisions[case['id']]
        assert before in CLEAR_ERRORS|{'acceptable','needs_improvement','unresolved'} and after in CLEAR_ERRORS|{'acceptable','needs_improvement','unresolved'}
        entries.append(dict(id=case['id'],before=before,after=after,note_es=note,source_pixels_inspected=True,reference_pixels_inspected=True))
    valid=[e for e in entries if 'unresolved' not in [e['before'],e['after']]]
    count=lambda rows,key:sum(e[key] in CLEAR_ERRORS for e in rows)
    review=dict(schema=1,reviewer='assistant',sample_path=sample_path.relative_to(ROOT).as_posix(),sample_sha256=digest(sample_path),
        manual_decisions_sha256=digest(manual_path),reviewed_regions=len(entries),chapters_sampled=124,comparable_regions=len(valid),
        excluded_unresolved_regions=len(entries)-len(valid),before_errors=count(valid,'before'),after_errors=count(valid,'after'),
        corrected_regions=sum(e['before'] in CLEAR_ERRORS and e['after'] not in CLEAR_ERRORS for e in valid),
        regressed_regions=sum(e['before'] not in CLEAR_ERRORS and e['after'] in CLEAR_ERRORS for e in valid),
        relative_error_reduction_percent=reduction(count(valid,'before'),count(valid,'after')),
        all_chapter_words_visually_reviewed=False,population_accuracy_estimate=False,app_uses_review_answers=False,entries=entries)
    review_path=ROOT/'benchmarks/full-comics/corpus-semantic-review-next.json'
    atomic(review_path,json.dumps(review,ensure_ascii=False,indent=2))
    combined=list(previous['entries']);cases={c['id']:c for c in sample['cases']}
    for e in entries:
        case=cases[e['id']]
        combined.append(dict(**e,group='next',original_id=e['id'],chapter=case['chapter'],source_image=case['source_image'],bounds=case['bounds'],
            source=case['source'],translation=case['translation'],current_report_sha256=case['current_report_sha256'],baseline_report_sha256=case['baseline_report_sha256']))
        combined[-1]['id']='next-'+str(e['id'])
    valid=[e for e in combined if 'unresolved' not in [e['before'],e['after']]]
    before=count(valid,'before');after=count(valid,'after')
    value=dict(schema=1,reviewer='assistant',current_engine=CURRENT,native_engine=previous['native_engine'],translation_signature=previous['translation_signature'],
        reviewed_regions=len(combined),chapters_sampled=124,regions_per_chapter=5,comparable_regions=len(valid),excluded_unresolved_regions=len(combined)-len(valid),
        before_errors=before,after_errors=after,corrected_regions=sum(e['before'] in CLEAR_ERRORS and e['after'] not in CLEAR_ERRORS for e in valid),
        regressed_regions=sum(e['before'] not in CLEAR_ERRORS and e['after'] in CLEAR_ERRORS for e in valid),
        relative_error_reduction_percent=reduction(before,after),single_build_comparison=True,
        before_categories=dict(collections.Counter(e['before'] for e in valid)),after_categories=dict(collections.Counter(e['after'] for e in valid)),
        original_expanded_review_sha256=digest(previous_path),additional_review_sha256=digest(review_path),additional_sample_sha256=digest(sample_path),
        newly_inspected_regions=124,app_uses_review_answers=False,all_chapter_words_visually_reviewed=False,population_accuracy_estimate=False,
        scope='Five distinct eligible aligned OCR regions per chapter. This sample excludes never-detected text and is not an all-word corpus review.',entries=combined)
    assert len(combined)==620 and before-after==value['corrected_regions']-value['regressed_regions']
    atomic(ROOT/'benchmarks/full-comics/current8011-extended-semantic-review.json',json.dumps(value,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in value.items() if k!='entries'}))


if __name__=='__main__':main()
