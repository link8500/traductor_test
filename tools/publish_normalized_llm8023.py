"""Bind full visible-dialogue judgments to all isolated normalized outputs."""
import collections
import json
from audit_corpus_quality import ROOT, QA, atomic, digest, read, records


def count(rows,before):
    b=collections.Counter(r[before] for r in rows);a=collections.Counter(r['after'] for r in rows)
    be=len(rows)-b['acceptable'];ae=len(rows)-a['acceptable']
    return dict(viewports=len(rows),before_categories=dict(b),after_categories=dict(a),
        before_not_approved=be,after_not_approved=ae,
        corrected=sum(r[before]!='acceptable' and r['after']=='acceptable' for r in rows),
        regressed=sum(r[before]=='acceptable' and r['after']!='acceptable' for r in rows),
        relative_unapproved_reduction_percent=100*(be-ae)/be)


def main():
    previous_path=ROOT/'benchmarks/full-comics/windows8021-full-viewports-semantic-review.json'
    previous=read(previous_path);folder=QA/'local-llm8023-normalized';summary=read(folder/'summary.json')
    assert summary['completed']==124 and summary['regions']==228 and not summary['errors']
    raw_recommended_path=ROOT/'benchmarks/full-comics/local-llm8021-recommended-full-viewports-semantic-review.json'
    raw_recommended={r['id']:r for r in read(raw_recommended_path)['entries']}
    manual_path=ROOT/'benchmarks/full-comics/normalized8023-meaning-decisions.json';manual=read(manual_path)
    assert [r[0] for r in manual]==list(range(1,125))
    rows=records(folder/'output.jsonl');old=records(QA/'windows8021-full-viewports-full-agreement/output.jsonl')
    assert [(r['image'],r['bounds'],r['source']) for r in old]==[(r['image'],r['bounds'],r['source']) for r in rows]
    prepared={r['source']:r['prepared'] for r in records(folder/'native-prepared.jsonl')}
    assert all(r['prepared_model_input']==prepared[r['source']] for r in rows)
    proof=read(folder/'provenance.json');assert proof['preparation_only_changes_case']
    entries=[]
    for original,(ident,judgment,note) in zip(previous['entries'],manual):
        assert original['id']==ident and judgment in ['acceptable','incorrect','incomplete','clipped','needs_review']
        candidate=read(folder/f'{ident:03d}.json')
        assert candidate['translations']==[r['translation'] for r in rows if r['image']==ident]
        entries.append(dict(id=ident,before=original['after'],prior_same_model=raw_recommended[ident]['after'],
            after=judgment,note=note,visible_dialogue_clipped=original['visible_dialogue_clipped'],
            isolated_output_sha256=digest(folder/f'{ident:03d}.json'),meaning_reviewed_against_complete_original_inventory=True))
    cohorts={};same_model={}
    for name,subset in [('all124_fixed_reading_viewports',entries),
                        ('no_visible_dialogue_clipped',[r for r in entries if not r['visible_dialogue_clipped']])]:
        cohorts[name]=count(subset,'before');same_model[name]=count(subset,'prior_same_model')
    value=dict(schema=1,viewports=124,source_regions=228,all124_new_meanings_reviewed=True,
        all_original_visible_dialogue_inventoried=True,native_ocr_sources_and_bounds_all_identical=True,
        cohorts=cohorts,prior_same_model_recommended_comparison=same_model,entries=entries,
        manual_sha256=digest(manual_path),previous_native_review_sha256=digest(previous_path),
        prior_same_model_review_sha256=digest(raw_recommended_path),
        output_sha256=digest(folder/'output.jsonl'),provenance_sha256=digest(folder/'provenance.json'),
        preparation_provenance_sha256=digest(folder/'prepare-provenance.json'),
        local_model='Qwen3-4B-Q4_K_M',only_user_passage_casing_changed_from_prior_recommended=True,
        prompt_sampling_model_and_runtime_unchanged=True,weights_trained=False,application_modified=False,
        candidate_improved_on_this_cohort=cohorts['all124_fixed_reading_viewports']['after_not_approved']<cohorts['all124_fixed_reading_viewports']['before_not_approved'],
        provider_accepted_for_deployment=False,all_paintings_visually_reviewed=False,
        all_chapter_words_visually_reviewed=False,complete_live_app_use_including_capture_and_movement=False,
        screen_attempt_failure_probability=None,target_achieved=False,ready_for_release=False)
    target=ROOT/'benchmarks/full-comics/normalized8023-full-viewports-semantic-review.json'
    atomic(target,json.dumps(value,ensure_ascii=False,indent=2))
    atomic(folder/'semantic-summary.json',json.dumps({k:v for k,v in value.items() if k!='entries'},indent=2))
    print(json.dumps(dict(cohorts=cohorts,prior_same_model=same_model,candidate_improved=value['candidate_improved_on_this_cohort'],ready_for_release=False)),flush=True)


if __name__=='__main__':main()
