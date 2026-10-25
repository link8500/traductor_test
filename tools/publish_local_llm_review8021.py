"""Bind all 124 whole-viewport meanings to exact isolated local-model outputs."""
import collections
import argparse
import json
from audit_corpus_quality import ROOT, QA, atomic, digest, read, records


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--recommended',action='store_true');args=parser.parse_args()
    prefix='local-llm8021'+('-recommended' if args.recommended else '')
    previous_path=ROOT/'benchmarks/full-comics/windows8021-full-viewports-semantic-review.json'
    previous=read(previous_path)
    folder=QA/('local-llm8021-full-viewports'+('-recommended' if args.recommended else ''));summary=read(folder/'summary.json')
    assert summary['completed']==124 and summary['regions']==228 and not summary['errors']
    manual_path=ROOT/f'benchmarks/full-comics/{prefix}-meaning-decisions.json'
    manual=read(manual_path);assert [r[0] for r in manual]==list(range(1,125))
    rows=records(folder/'output.jsonl');old=records(QA/'windows8021-full-viewports-full-agreement/output.jsonl')
    assert [(r['image'],r['bounds'],r['source']) for r in old]==[(r['image'],r['bounds'],r['source']) for r in rows]
    entries=[]
    for original,(ident,judgment,note) in zip(previous['entries'],manual):
        assert original['id']==ident
        output=read(folder/f'{ident:03d}.json')
        selected=[r for r in rows if r['image']==ident]
        assert output['translations']==[r['translation'] for r in selected]
        assert judgment in ['acceptable','incorrect','incomplete','needs_review','clipped']
        entries.append(dict(id=ident,before=original['after'],after=judgment,note=note,
            visible_dialogue_clipped=original['visible_dialogue_clipped'],
            original_dialogue_inventory_sha256=previous['inventory_sha256'],
            isolated_output_sha256=digest(folder/f'{ident:03d}.json'),
            all_new_meanings_reviewed_against_full_original_inventory=True))
    cohorts={}
    for name,subset in [('all124_fixed_reading_viewports',entries),
                        ('no_visible_dialogue_clipped',[r for r in entries if not r['visible_dialogue_clipped']])]:
        b=collections.Counter(r['before'] for r in subset);a=collections.Counter(r['after'] for r in subset)
        be=len(subset)-b['acceptable'];ae=len(subset)-a['acceptable']
        cohorts[name]=dict(viewports=len(subset),before_categories=dict(b),after_categories=dict(a),
            before_not_approved=be,after_not_approved=ae,
            corrected=sum(r['before']!='acceptable' and r['after']=='acceptable' for r in subset),
            regressed=sum(r['before']=='acceptable' and r['after']!='acceptable' for r in subset),
            relative_unapproved_reduction_percent=100*(be-ae)/be)
    report=dict(schema=1,viewports=124,source_regions=228,native_ocr_sources_and_bounds_all_identical=True,
        all124_new_meanings_reviewed=True,all124_previous_meanings_bound_to_exact_same_location_outputs=True,
        cohorts=cohorts,entries=entries,manual_sha256=digest(manual_path),
        previous_native_review_sha256=digest(previous_path),
        output_sha256=digest(folder/'output.jsonl'),provenance_sha256=digest(folder/'provenance.json'),
        local_model='Qwen3-4B-Q4_K_M',sampling='official recommended nonthinking parameters; fixed seed8021' if args.recommended else 'greedy temperature0; isolated configuration only',
        model_weights_trained=False,application_modified=False,provider_accepted_for_deployment=False,
        poor_spanish_grammar_also_observed=True,semantic_pass_is_not_complete_app_use_approval=True,
        original_paint_and_live_capture_not_evaluated=True,all_chapter_words_visually_reviewed=False,
        screen_attempt_failure_probability=None,target_achieved=False,ready_for_release=False)
    atomic(ROOT/f'benchmarks/full-comics/{prefix}-full-viewports-semantic-review.json',json.dumps(report,ensure_ascii=False,indent=2))
    atomic(folder/'semantic-summary.json',json.dumps({k:v for k,v in report.items() if k!='entries'},indent=2))
    print(json.dumps(dict(cohorts=cohorts,provider_accepted_for_deployment=False)),flush=True)


if __name__=='__main__':main()
