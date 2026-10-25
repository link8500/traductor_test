"""Combine distinct long/short reviewed regions from the same Windows cohort."""
import collections
import json
from audit_corpus_quality import ROOT, QA, CURRENT, read, digest, atomic, CLEAR_ERRORS, reduction, distributed_semantic_comparison, uniform_semantic_comparison
from prepare_corpus_review_sample import overlap


def main():
    long_path=ROOT/'benchmarks/full-comics/current8011-full-semantic-review.json'
    short_path=ROOT/'benchmarks/full-comics/corpus-semantic-review-short.json'
    previous=read(long_path);short=read(short_path)
    uniform_semantic_comparison()
    short_metric=distributed_semantic_comparison(short_path.name)
    sample_path=ROOT/short['sample_path'];sample=read(sample_path)
    assert len(sample['cases'])==124 and all(c['current_folder']==CURRENT for c in sample['cases'])
    assert digest(sample_path.parent/'manual-decisions.json')==short['manual_decisions_sha256']
    entries=list(previous['entries']);cases={c['id']:c for c in sample['cases']}
    for row in short['entries']:
        case=cases[row['id']]
        assert all(not(e['chapter']==case['chapter'] and e['source_image']==case['source_image'] and overlap(e['bounds'],case['bounds'])>.5) for e in entries)
        entries.append(dict(**row,group='short',original_id=row['id'],chapter=case['chapter'],source_image=case['source_image'],bounds=case['bounds'],
            source=case['source'],translation=case['translation'],current_report_sha256=case['current_report_sha256'],baseline_report_sha256=case['baseline_report_sha256']))
        entries[-1]['id']='short-'+str(row['id'])
    valid=[e for e in entries if 'unresolved' not in [e['before'],e['after']]]
    before=collections.Counter(e['before'] for e in valid);after=collections.Counter(e['after'] for e in valid)
    old=sum(before[k] for k in CLEAR_ERRORS);new=sum(after[k] for k in CLEAR_ERRORS)
    value=dict(schema=1,reviewer='assistant',current_engine=CURRENT,native_engine=previous['native_engine'],translation_signature=previous['translation_signature'],
        reviewed_regions=len(entries),chapters_sampled=124,regions_per_chapter=4,comparable_regions=len(valid),excluded_unresolved_regions=len(entries)-len(valid),
        before_errors=old,after_errors=new,corrected_regions=sum(e['before'] in CLEAR_ERRORS and e['after'] not in CLEAR_ERRORS for e in valid),
        regressed_regions=sum(e['before'] not in CLEAR_ERRORS and e['after'] in CLEAR_ERRORS for e in valid),relative_error_reduction_percent=reduction(old,new),
        before_categories=dict(before),after_categories=dict(after),single_build_comparison=True,
        original_uniform_review_sha256=digest(long_path),short_review_sha256=digest(short_path),short_sample_sha256=digest(sample_path),
        newly_inspected_short_regions=124,app_uses_review_answers=False,all_chapter_words_visually_reviewed=False,population_accuracy_estimate=False,
        scope='Three previously selected aligned long OCR regions and one additional aligned short OCR region per chapter; partial regions remain partial, and never-detected text is not measured.',entries=entries)
    assert len(entries)==496 and len({e['chapter'] for e in entries})==124
    assert old-new==value['corrected_regions']-value['regressed_regions']
    atomic(ROOT/'benchmarks/full-comics/current8011-expanded-semantic-review.json',json.dumps(value,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in value.items() if k!='entries'}))


if __name__=='__main__':main()
