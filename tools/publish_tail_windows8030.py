"""Publish strictly scoped integrated tail evidence without inflating coverage."""
import json
from audit_corpus_quality import ROOT,QA,atomic,digest,read,records


def main():
    folder=QA/'windows8030-tail-translation-replay';run=read(folder/'summary.json')
    assert run['actual_native_output_records']==334 and run['fixed_regions']==229 and run['tail_candidates']==98
    assert not run['runtime_errors'] and not run['fixed_changed_regions'] and not run['previous_diagnostic_changed_regions']
    previous_path=ROOT/'benchmarks/full-comics/windows8029-refinement-semantic-review.json';previous=read(previous_path)
    decisions_path=ROOT/'benchmarks/full-comics/tail8030-meaning-decisions.json';decisions=read(decisions_path)
    before=records(QA/'windows8029-refinement-full-viewports/output.jsonl');after=records(folder/'fixed-output.jsonl')
    show=lambda rows:[(r['image'],r['bounds'],r['source'],r['translation'],r['retained_original']) for r in rows]
    assert show(before)==show(after)
    changed=read(folder/'changes.json');assert {r['id'] for r in changed}=={r['id'] for r in decisions['entries'] if r['tail_accepted']}
    assert sum(r['complete_correction'] for r in decisions['entries'])==6
    for r in changed:
        assert r['actual_native']['translation']==r['policy']['candidate_translation']
        assert r['actual_native']['translation'].startswith(r['policy']['translation'])
    entries=[dict(r,before=r['after'],same_complete_location_output_judgment_reused=True) for r in previous['entries']]
    cohorts={name:dict(m,before_categories=m['after_categories'],before_not_approved=m['after_not_approved'],corrected=0,regressed=0,
                         relative_unapproved_reduction_percent=0.0) for name,m in previous['cohorts'].items()}
    diagnostic=dict(source_reports_scanned=124,nonpromotional_rows_scanned=read(QA/'tail8030/sample.json')['meaningful_or_nonpromotional_rows_scanned'],
                    candidates=98,candidates_without_automatic_alert=84,initial_changed_regions=11,accepted_changed_regions=10,
                    complete_corrections=6,partial_improvements_with_residual_errors=4,rejected_additions=1,
                    new_complete_region_regressions_observed=0,added_clauses_with_residual_grammar_defects=2,
                    initial_diagnostic_before_not_approved=11,initial_diagnostic_after_not_approved=5,
                    all_changed_original_and_olympus_pixels_inspected=True,all_changed_meanings_reviewed=True,
                    diagnostic_selection_not_population_estimate=True,counts_not_added_to_fixed_views_or_previous_diagnostics=True)
    value=dict(schema=1,build='803001',baseline_build='802901',viewports=124,native_regions=229,entries=entries,cohorts=cohorts,
               historical_baseline_comparison=previous['historical_baseline_comparison'],
               dialogue_ocr={name:dict(w,before=w['after']) for name,w in previous['dialogue_ocr'].items()},
               tail_diagnostic=diagnostic,actual_native_output_records=334,actual_native_trial_output_records=294,
               fixed_complete_location_judgments_reused_by_identity=124,previous_diagnostic_judgments_reused_by_identity=7,
               fresh_native_ocr=False,fresh_translation_inference=True,fresh_screen_capture=False,model_weights_trained=False,
               normal_live_worker_uses_same_tail_rule=True,reference_or_manual_answers_supplied_to_app=False,
               native_tail_guards=run['native_guards'],previous_review_sha256=digest(previous_path),
               snapshot_sha256=digest(QA/'windows-engine803001.json'),native_summary_sha256=digest(folder/'summary.json'),
               native_provenance_sha256=digest(folder/'provenance.json'),fixed_output_sha256=digest(folder/'fixed-output.jsonl'),
               previous_diagnostic_output_sha256=digest(folder/'prior-diagnostic-output.jsonl'),tail_output_sha256=digest(folder/'tail-output.jsonl'),
               native_changes_sha256=digest(folder/'changes.json'),decisions_sha256=digest(decisions_path),
               runtime_checks_sha256=digest(QA/'windows8030-tail-runtime-checks.json'),
               original_and_olympus_review_sample_sha256=digest(QA/'tail8030/review/sample.json'),
               native_paint_provenance_sha256=digest(folder/'paint/provenance.json'),native_paint_manual_review_sha256=digest(folder/'paint/manual-review.json'),
               all_chapter_words_visually_reviewed=False,complete_live_app_use_including_capture_and_movement=False,
               screen_attempt_failure_probability=None,target_achieved=False,ready_for_release=False)
    atomic(ROOT/'benchmarks/full-comics/windows8030-tail-semantic-review.json',json.dumps(value,ensure_ascii=False,indent=2))
    atomic(folder/'semantic-summary.json',json.dumps({k:v for k,v in value.items() if k!='entries'},indent=2))
    print(json.dumps(dict(fixed=cohorts['all124_fixed_reading_viewports'],diagnostic=diagnostic,target_achieved=False)),flush=True)


if __name__=='__main__':main()
