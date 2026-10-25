"""Count whole-view corrections and regressions, retaining failed experiments."""
import collections
import json
from audit_corpus_quality import ROOT, QA, atomic, digest, read, records


def main():
    folder=QA/'translation-search8022'
    previous_path=ROOT/'benchmarks/full-comics/windows8021-full-viewports-semantic-review.json'
    previous=read(previous_path);summary=read(folder/'summary.json')
    assert summary['viewports']==124 and summary['regions']==228 and summary['runtime_errors']==0
    old=records(QA/'windows8021-full-viewports-full-agreement/output.jsonl');new=records(folder/'output.jsonl')
    assert [(r['image'],r['source'],r['bounds']) for r in old]==[(r['image'],r['source'],r['bounds']) for r in new]
    expected_assets=read(QA/'frozen-windows802101/data/flutter_assets/assets/models/opus-en-es/manifest.json')['files']
    build=read(folder/'build-provenance.json')
    assert all(expected_assets[name]==sha for name,sha in build['model_assets'].items())
    changed={a['image'] for a,b in zip(old,new) if a['translation']!=b['translation']}
    manual_path=ROOT/'benchmarks/full-comics/search8022-meaning-decisions.json'
    manual={r[0]:r for r in read(manual_path)};assert set(manual)==changed
    entries=[]
    for row in previous['entries']:
        ident=row['id'];outputs=[r for r in new if r['image']==ident]
        if ident in changed:
            _,judgment,note,partial_worsening=manual[ident]
            assert judgment in ['acceptable','incorrect','incomplete','clipped','needs_review']
        else:
            displayed=['source','bounds','translation','retained_original']
            assert [[r[k] for k in displayed] for r in outputs]==[[r[k] for k in displayed] for r in row['consensus_outputs']]
            judgment=row['after'];note='Exact full-location outputs retained; prior judgment reused.';partial_worsening=False
        entries.append(dict(id=ident,before=row['after'],after=judgment,note=note,
            visible_dialogue_clipped=row['visible_dialogue_clipped'],outputs=outputs,
            changed_meaning_reviewed=ident in changed,
            exact_same_location_judgment_reused=ident not in changed,
            already_failed_view_with_partial_worsening=partial_worsening))
    cohorts={}
    for name,subset in [('all124_fixed_reading_viewports',entries),
                        ('no_visible_dialogue_clipped',[r for r in entries if not r['visible_dialogue_clipped']])]:
        b=collections.Counter(r['before'] for r in subset);a=collections.Counter(r['after'] for r in subset)
        be=len(subset)-b['acceptable'];ae=len(subset)-a['acceptable']
        cohorts[name]=dict(viewports=len(subset),before_categories=dict(b),after_categories=dict(a),
            before_not_approved=be,after_not_approved=ae,
            corrected=sum(r['before']!='acceptable' and r['after']=='acceptable' for r in subset),
            regressed=sum(r['before']=='acceptable' and r['after']!='acceptable' for r in subset),
            already_failed_views_partially_worsened=sum(r['already_failed_view_with_partial_worsening'] for r in subset),
            relative_unapproved_reduction_percent=100*(be-ae)/be)
    value=dict(schema=1,viewports=124,regions=228,cohorts=cohorts,entries=entries,
        changed_viewports_reviewed=len(changed),identical_full_location_judgments_reused=124-len(changed),
        all_changed_meanings_reviewed_against_original_inventory=True,
        unchanged_native_ocr_sources_and_bounds=True,model_weights_changed=False,
        previous_review_sha256=digest(previous_path),manual_sha256=digest(manual_path),
        output_sha256=digest(folder/'output.jsonl'),build_provenance_sha256=digest(folder/'build-provenance.json'),
        inference_provenance_sha256=digest(folder/'inference-provenance.json'),
        application_modified=False,accepted_for_application=False,all_chapter_words_visually_reviewed=False,
        screen_attempt_failure_probability=None,target_achieved=False,ready_for_release=False)
    atomic(ROOT/'benchmarks/full-comics/search8022-full-viewports-semantic-review.json',json.dumps(value,ensure_ascii=False,indent=2))
    atomic(folder/'semantic-summary.json',json.dumps({k:v for k,v in value.items() if k!='entries'},indent=2))
    print(json.dumps(dict(cohorts=cohorts,changed_viewports_reviewed=len(changed),accepted_for_application=False)),flush=True)


if __name__=='__main__':main()
