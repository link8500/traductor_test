"""Bind fresh native readings to strict whole-location meaning decisions."""
import json

from audit_corpus_quality import ROOT, QA, atomic, digest, read, records
from publish_normalized_llm8023 import count


def shown(rows):return [{k:r.get(k) for k in ['source','translation','bounds','retained_original','sentence_recovered']} for r in rows]


def main():
    folder=QA/'windows8029-refinement-full-viewports';run=read(folder/'summary.json')
    assert run['fixed_viewports']==124 and run['fixed_regions']==229 and run['total_native_images']==131 and not run['runtime_errors']
    assert run['all_fixed_sources_match_pure_policy_prediction']
    previous_path=ROOT/'benchmarks/full-comics/windows8028-opening-semantic-review.json';previous=read(previous_path)
    decisions_path=ROOT/'benchmarks/full-comics/refinement8029-meaning-decisions.json';decisions=read(decisions_path)
    changes=read(folder/'changes.json');assert {r['id'] for r in changes}=={decisions['fixed_changed_view']['id']}
    old_path=QA/'windows8028-opening-translation-replay/fixed-output.jsonl';old=records(old_path);new=records(folder/'output.jsonl')
    entries=[]
    for original in previous['entries']:
        ident=original['id'];row=dict(id=ident,before=original['after'],after=original['after'],historical_baseline=original['historical_baseline'],visible_dialogue_clipped=original['visible_dialogue_clipped'])
        if ident==decisions['fixed_changed_view']['id']:
            row.update(after=decisions['fixed_changed_view']['after'],note=decisions['fixed_changed_view']['note'],new_complete_location_meaning_reviewed=True)
        else:
            assert shown([r for r in old if r['image']==ident])==shown([r for r in new if r['image']==ident])
            row['same_complete_location_output_judgment_reused']=True
        entries.append(row)
    cohorts={};historical={}
    for label,subset in [('all124_fixed_reading_viewports',entries),('no_visible_dialogue_clipped',[r for r in entries if not r['visible_dialogue_clipped']])]:
        cohorts[label]=count(subset,'before');historical[label]=count(subset,'historical_baseline')
    candidate={r['id']:r for r in read(QA/'refinement8029/changes.json')};broad=read(folder/'broad-selected.json')
    assert {r['case_id'] for r in broad}=={r['id'] for r in decisions['entries']}==set(range(1,8))
    for r in broad:
        expected=candidate[r['case_id']]
        assert r['after']['source']==expected.get('selected_source',expected['source'])
        assert r['after']['translation']==expected['policy']['candidate_translation']
    selector_path=QA/'ocr-morph-edit8029/summary.json';selector=read(selector_path)
    assert all(not r['scores']['crops_worsened'] for name,r in selector['cohorts'].items() if 'scores' in r)
    diagnostic=dict(changed_physical_locations=7,complete_corrections=3,partial_improvements_with_residual_errors=4,
                    before_not_approved=7,after_not_approved=4,new_complete_region_regressions=0,
                    ocr_corrected_words=6,short_question_recoveries=1,
                    all_original_and_olympus_pixels_inspected=True,all_changed_meanings_reviewed=True,
                    includes_one_location_overlapping_fixed_views=True,counts_not_added_to_fixed_view_results=True,
                    diagnostic_selection_not_population_estimate=True)
    value=dict(schema=1,build='802901',baseline_build='802801',viewports=124,native_regions=229,entries=entries,cohorts=cohorts,
               historical_baseline_comparison=dict(build='801901',cohorts=historical),expanded_refinement_diagnostic=diagnostic,
               dialogue_ocr=selector['dialogue_ocr'],changed_complete_location_meanings_reviewed=1,identical_complete_location_judgments_reused=123,
               fresh_native_ocr=True,fresh_translation_inference=True,fresh_screen_capture=False,
               actual_native_images=131,actual_native_output_records=run['total_native_output_records'],
               normal_worker_uses_same_rules=True,no_explicit_reader_paths_or_activation=True,
               morph_edit_guards=selector['guards'],short_question_guards=read(QA/'question-clause8029/guards.json'),
               unique_control_crop_pixels=372,control_cohorts_overlap_not_added=True,
               word_counts_do_not_exclude_undetected_dialogue=True,model_weights_trained=False,
               previous_review_sha256=digest(previous_path),previous_native_output_sha256=digest(old_path),
               native_output_sha256=digest(folder/'output.jsonl'),native_summary_sha256=digest(folder/'summary.json'),
               native_provenance_sha256=digest(folder/'provenance.json'),broad_selected_sha256=digest(folder/'broad-selected.json'),
               snapshot_sha256=digest(QA/'windows-engine802901.json'),runtime_checks_sha256=digest(QA/'windows8029-refinement-runtime-checks.json'),
               decisions_sha256=digest(decisions_path),selector_summary_sha256=digest(selector_path),
               original_and_olympus_review_sample_sha256=digest(QA/'refinement8029/review/sample.json'),
               native_paint_provenance_sha256=digest(folder/'paint/provenance.json'),
               native_paint_manual_review_sha256=digest(folder/'paint/manual-review.json'),
               reference_or_manual_answers_supplied_to_app=False,all_chapter_words_visually_reviewed=False,
               all_native_paints_visually_approved=False,complete_live_app_use_including_capture_and_movement=False,
               screen_attempt_failure_probability=None,target_achieved=False,ready_for_release=False)
    atomic(ROOT/'benchmarks/full-comics/windows8029-refinement-semantic-review.json',json.dumps(value,ensure_ascii=False,indent=2))
    atomic(folder/'semantic-summary.json',json.dumps({k:v for k,v in value.items() if k!='entries'},indent=2))
    print(json.dumps(dict(fixed=cohorts['all124_fixed_reading_viewports'],expanded=diagnostic,ocr=value['dialogue_ocr']['all124_fixed_reading_viewports'],target_achieved=False)),flush=True)


if __name__=='__main__':main()
