"""Grade the normal Windows configuration without optional consensus readers."""
import json
from audit_corpus_quality import ROOT, QA, atomic, digest, read, records
from publish_normalized_llm8023 import count


def displayed(rows):
    return [{k:r.get(k) for k in ['source','translation','bounds','retained_original','sentence_recovered']} for r in rows]


def main():
    folder=QA/'windows8024-short-default-full-viewports';summary=read(folder/'summary.json')
    assert summary['viewports']==124 and summary['runtime_errors']==0 and summary['default_live_worker_enabled']
    previous_path=ROOT/'benchmarks/full-comics/windows8021-full-viewports-semantic-review.json'
    previous=read(previous_path);old=records(QA/'windows8020-full-viewports-baseline/output.jsonl');new=records(folder/'output.jsonl')
    changed={r['id'] for r in read(folder/'changes.json')}
    manual_path=ROOT/'benchmarks/full-comics/short8024-default-meaning-decisions.json'
    manual={r[0]:r for r in read(manual_path)};assert set(manual)==changed
    painted=records(QA/'windows8024-short-full-viewports/output.jsonl')
    paint_review=read(QA/'windows8024-short-full-viewports/paint/manual-review.json')
    painted_ids={r['id'] for r in paint_review['entries'] if r['visually_reviewed']}
    inputs=records(folder/'part-0.input.jsonl')+records(folder/'part-1.input.jsonl')+records(folder/'part-2.input.jsonl')+records(folder/'part-3.input.jsonl')
    assert len(inputs)==124 and all(not any(k in r for k in ['recover_short_dialogue','consensus_first_directory','consensus_second_directory']) for r in inputs)
    entries=[]
    for original in previous['entries']:
        ident=original['id'];before=[r for r in old if r['image']==ident];after=[r for r in new if r['image']==ident]
        item=dict(id=ident,before=original['historical_baseline'],after=original['historical_baseline'],
            dialogue=original['dialogue'],visible_dialogue_clipped=original['visible_dialogue_clipped'])
        if ident in changed:
            _,judgment,note=manual[ident];assert judgment in ['acceptable','incorrect','incomplete','clipped','needs_review']
            assert ident in painted_ids and displayed(after)==displayed([r for r in painted if r['image']==ident])
            item.update(after=judgment,note=note,new_meaning_reviewed_against_complete_original_inventory=True,
                candidate_outputs=after)
        else:
            assert displayed(before)==displayed(after)
            item.update(note='Original baseline output judgment reused only for identical full-location output.',
                same_full_location_output_judgment_reused=True)
        entries.append(item)
    cohorts={name:count(subset,'before') for name,subset in [
        ('all124_fixed_reading_viewports',entries),('no_visible_dialogue_clipped',[r for r in entries if not r['visible_dialogue_clipped']])]}
    value=dict(build='802402',baseline_build='801901',viewports=124,native_regions=len(new),cohorts=cohorts,
        entries=entries,default_short_recovery_enabled=True,optional_consensus_readers_enabled=False,
        explicit_short_override_supplied=False,changed_viewports_reviewed=len(changed),
        identical_full_location_judgments_reused=124-len(changed),manual_sha256=digest(manual_path),
        changed_native_paint_reused_only_for_identical_displayed_fields=True,
        reused_paint_manual_review_sha256=digest(QA/'windows8024-short-full-viewports/paint/manual-review.json'),
        original_baseline_review_sha256=digest(previous_path),baseline_output_sha256=digest(QA/'windows8020-full-viewports-baseline/output.jsonl'),
        native_output_sha256=digest(folder/'output.jsonl'),provenance_sha256=digest(folder/'provenance.json'),
        native_summary_sha256=digest(folder/'summary.json'),snapshot_sha256=digest(QA/'windows-engine802402.json'),
        all_original_visible_dialogue_inventoried=True,no_reference_or_inventory_inputs=True,
        model_weights_trained=False,all_chapter_words_visually_reviewed=False,
        complete_live_app_use_including_capture_and_movement=False,screen_attempt_failure_probability=None,
        target_achieved=False,ready_for_release=False)
    target=ROOT/'benchmarks/full-comics/windows8024-default-full-viewports-semantic-review.json'
    atomic(target,json.dumps(value,ensure_ascii=False,indent=2))
    print(json.dumps(dict(cohorts=cohorts,default_short_recovery_enabled=True,optional_consensus_readers_enabled=False,target_achieved=False)),flush=True)


if __name__=='__main__':main()
