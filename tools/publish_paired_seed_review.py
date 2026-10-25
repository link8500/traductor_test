"""Validate the same-pixel 124-location semantic comparison for Windows 8012."""
import json
from audit_corpus_quality import ROOT, QA, read, digest, atomic, CLEAR_ERRORS, reduction


def main():
    folder=QA/'paired-seed801201';path=folder/'sample.json';manual_path=folder/'manual-decisions.json'
    sample=read(path);manual_rows=read(manual_path);manual={d[0]:d for d in manual_rows}
    assert len(manual)==len(manual_rows)
    assert set(manual)=={c['id'] for c in sample['cases'] if c['needs_visual_review']}
    old_path=ROOT/'benchmarks/full-comics/current8011-full-semantic-review.json'
    assert digest(old_path)==sample['old_judgments_sha256']
    judgments={e['original_id']:e for e in read(old_path)['entries'] if e['group']=='a'}
    entries=[]
    for case in sample['cases']:
        inference=ROOT/case['paired_evaluation_path']
        assert digest(inference)==case['paired_evaluation_sha256']
        assert case['before_judgment']==judgments[case['id']]['after']
        if case['needs_visual_review']:
            _,after,note=manual[case['id']]
        else:
            assert case['translation']==case['refreshed_translation']
            after=case['full_engine_judgment'];note='Salida idéntica en la misma región; se conserva el juicio previo.'
            assert after==case['before_judgment']
        entries.append(dict(id=case['id'],before=case['before_judgment'],after=after,note_es=note,
            source_pixels_inspected=True,reference_pixels_inspected=True,reused_identical_output_judgment=not case['needs_visual_review']))
    assert len(entries)==124
    comparable=[e for e in entries if 'unresolved' not in [e['before'],e['after']]]
    old=sum(e['before'] in CLEAR_ERRORS for e in comparable);new=sum(e['after'] in CLEAR_ERRORS for e in comparable)
    value=dict(schema=1,sample_path=str(path.relative_to(ROOT)).replace('\\','/'),sample_sha256=digest(path),
        manual_decisions_sha256=digest(manual_path),old_native_snapshot='801101',new_native_snapshot='801201',
        paired_same_pixels=True,regions=124,comparable_regions=len(comparable),excluded_regions=124-len(comparable),
        before_errors=old,after_errors=new,corrected_regions=sum(e['before'] in CLEAR_ERRORS and e['after'] not in CLEAR_ERRORS for e in comparable),
        regressed_regions=sum(e['before'] not in CLEAR_ERRORS and e['after'] in CLEAR_ERRORS for e in comparable),
        relative_error_reduction_percent=reduction(old,new),all_chapter_words_visually_reviewed=False,
        population_accuracy_estimate=False,app_uses_review_answers=False,
        scope='One originally selected region per chapter, on the exact same full screen image in both Windows binaries. No entire chapter accuracy approval.',entries=entries)
    atomic(ROOT/'benchmarks/full-comics/paired8012-seed-semantic-review.json',json.dumps(value,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in value.items() if k!='entries'}))


if __name__=='__main__':main()
