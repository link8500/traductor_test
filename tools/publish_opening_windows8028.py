"""Publish reviewed whole-region meanings without inflating fixed-view metrics."""
import collections
import json
import pathlib

from audit_corpus_quality import ROOT, QA, atomic, digest, read, records
from publish_normalized_llm8023 import count


def main():
    folder=QA/'windows8028-opening-translation-replay';run=read(folder/'summary.json')
    assert run['actual_native_output_records']==297 and run['runtime_errors']==0
    assert run['all_outputs_match_conservative_prediction'] and run['fixed_displayed_outputs_changed']==0
    previous_path=ROOT/'benchmarks/full-comics/windows8027-question-semantic-review.json';previous=read(previous_path)
    decisions_path=ROOT/'benchmarks/full-comics/opening8028-meaning-decisions.json';decisions=read(decisions_path)
    changes=read(folder/'expanded-changes.json');manual={r['id']:r for r in decisions['entries']}
    assert set(manual)=={r['id'] for r in changes} and len(manual)==17
    entries=[dict(id=r['id'],before=r['after'],after=r['after'],historical_baseline=r['historical_baseline'],
                  visible_dialogue_clipped=r['visible_dialogue_clipped'],same_complete_location_output_judgment_reused=True)
             for r in previous['entries']]
    cohorts={};historical={}
    for label,subset in [('all124_fixed_reading_viewports',entries),('no_visible_dialogue_clipped',[r for r in entries if not r['visible_dialogue_clipped']])]:
        cohorts[label]=count(subset,'before');historical[label]=count(subset,'historical_baseline')
    fixed_old=records(QA/'windows8027-question-translation-replay/output.jsonl');fixed_new=records(folder/'fixed-output.jsonl')
    for before,after in zip(fixed_old,fixed_new):
        assert all(before.get(k)==after.get(k) for k in ['image','source','translation','bounds','retained_original','sentence_recovered'])
    after_categories=collections.Counter(r['after'] for r in manual.values())
    expanded=dict(chapters_scanned=124,candidates=68,changed_regions=17,unchanged_candidates=51,
                  all_changed_original_dialogue_visually_reviewed=True,
                  before_not_approved=17,after_not_approved=6,complete_corrections=11,new_complete_region_regressions=0,
                  partial_recoveries_with_confirmed_residual_defects=5,still_needs_review=1,
                  after_categories=dict(after_categories),all_unchanged_candidates_meanings_reviewed=False,
                  selection_is_diagnostic_not_population_estimate=True,not_added_to_fixed124_counts=True,
                  all_existing_translation_bytes_preserved=True)
    assert after_categories==dict(acceptable=11,incorrect=3,incomplete=2,needs_review=1)
    value=dict(schema=1,build='802801',baseline_build='802701',viewports=124,native_regions=229,entries=entries,
               cohorts=cohorts,historical_baseline_comparison=dict(build='801901',cohorts=historical),
               expanded_opening_diagnostic=expanded,dialogue_ocr={k:dict(before=v['after'],after=v['after']) for k,v in previous['dialogue_ocr'].items()},
               fresh_translation_inference=True,new_ocr_inference=False,fresh_screen_capture=False,
               identical_complete_location_judgments_reused=124,changed_fixed_location_meanings=0,
               actual_native_output_records=297,opening_policy_guards=read(QA/'opening8028/speech-policy-guards.json'),
               normal_live_worker_uses_same_opening_rule=True,decoder_core_and_ocr_unchanged=True,model_weights_trained=False,
               manual_or_reference_answers_supplied_to_app=False,
               previous_review_sha256=digest(previous_path),previous_native_output_sha256=digest(QA/'windows8027-question-translation-replay/output.jsonl'),
               fixed_output_sha256=digest(folder/'fixed-output.jsonl'),native_output_sha256=digest(folder/'native-output.jsonl'),
               native_summary_sha256=digest(folder/'summary.json'),native_provenance_sha256=digest(folder/'provenance.json'),
               snapshot_sha256=digest(QA/'windows-engine802801.json'),runtime_checks_sha256=digest(QA/'windows8028-opening-runtime-checks.json'),
               core_equivalence_sha256=digest(QA/'opening8028/core-equivalence.json'),decisions_sha256=digest(decisions_path),
               expanded_changes_sha256=digest(folder/'expanded-changes.json'),
               native_paint_provenance_sha256=digest(folder/'paint/provenance.json'),
               native_paint_manual_review_sha256=digest(folder/'paint/manual-review.json'),
               visual_review_sample_sha256=digest(QA/'opening8028/review/sample.json'),
               all_chapter_words_visually_reviewed=False,all_native_paints_visually_approved=False,
               complete_live_app_use_including_capture_and_movement=False,
               screen_attempt_failure_probability=None,target_achieved=False,ready_for_release=False)
    atomic(ROOT/'benchmarks/full-comics/windows8028-opening-semantic-review.json',json.dumps(value,ensure_ascii=False,indent=2))
    atomic(folder/'semantic-summary.json',json.dumps({k:v for k,v in value.items() if k!='entries'},indent=2))
    print(json.dumps(dict(fixed=cohorts['all124_fixed_reading_viewports'],expanded=expanded,target_achieved=False)),flush=True)


if __name__=='__main__':main()
