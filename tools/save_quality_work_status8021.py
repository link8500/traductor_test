"""Save exact completed evidence, storage gains and active jobs for continuation."""
import datetime
import json
import shutil
from audit_corpus_quality import ROOT, QA, atomic, digest, read


def main():
    files=[
        'benchmarks/full-comics/viewport8020-original-inventory.json',
        'benchmarks/full-comics/windows8020-full-viewports-semantic-review.json',
        'benchmarks/full-comics/windows8021-full-viewports-semantic-review.json',
        'build/full-comics/windows-engine802101.json',
        'build/full-comics/windows8021-runtime-checks.json',
        'build/full-comics/windows8021-full-viewports-full-agreement/paint/manual-review.json',
        'build/full-comics/storage-optimization.json',
        'build/full-comics/storage-opt-verification/verification.json',
        'benchmarks/full-comics/local-llm8021-full-viewports-semantic-review.json',
        'benchmarks/full-comics/local-llm8021-recommended-full-viewports-semantic-review.json',
        'build/llm-quality8021/cache-release.json']
    progress={}
    for name in ['ocr-en8012-recovery','translated-en8014-recovery','translated-en8017-geometry']:
        rows=[read(p) for p in (QA/name).glob('*.done.json')]
        progress[name]=dict(chapters_complete=len(rows),regions=sum(r['regions'] for r in rows),
            runtime_errors=sum(r['runtime_errors'] for r in rows),all_words_manually_reviewed=False)
    model=ROOT/'build/llm-quality8021';partial=model/'Qwen3-4B-Q4_K_M.gguf.part'
    storage=read(QA/'storage-optimization.json')
    experiment=QA/'local-llm8021-full-viewports/summary.json'
    data=dict(updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),objective_complete=False,
        target_failure_probability_strictly_below=.05,screen_attempt_failure_probability=None,target_achieved=False,
        constraints=dict(windows_first=True,android_apk_deferred=True,phone_work=False,offline_only=True,
            only124_chapters=True,dialogue_and_narration_must_not_be_omitted=True,sfx_may_remain_unchanged=True,
            report_aggregate_counts_without_chapter_examples=True,keep_awake_automation_deleted=True,
            personal_files_must_remain_untouched=True,no_subagents_authorized=True),
        latest_packaged_experimental_build='801704 / version8017',latest_unshipped_experimental_build='802101',
        evidence=[dict(path=p,sha256=digest(ROOT/p)) for p in files],progress=progress,
        fixed_viewport_trial=dict(viewports=124,regions=228,all_visible_original_dialogue_inventoried=True,
            meanings_before_after_reviewed=True,strict_unapproved_before=60,strict_unapproved_after=58,
            whole_view_fixes=2,new_regressions=0,historical_before=62,historical_after=58,
            historical_relative_reduction_percent=100*4/62,
            actual_windows_selector_predictions_all_match=True,native_runtime_errors=0,
            native_paintings_visually_reviewed=10,paint_approved=False,
            original_letter_remnants_outside_unchanged_masks=True,default_live_worker_enabled=False,
            all_chapter_words_reviewed=False,complete_app_use_attempts=False),
        storage=dict(physical_bytes_reclaimed=storage['physical_bytes_reclaimed'],
            consolidated_files=len(storage['linked_files']),busy_files_skipped=len(storage['busy_files_skipped']),
            immutable_pool_read_only=True,future_snapshots_reuse_pool=True,
            future_snapshots_and_traversals_minimum_reserve_bytes=4*1024**3,
            free_bytes_now=shutil.disk_usage(ROOT).free,
            compression_saved_bytes=0,cache_recursive_deletion_rejected=True,
            flutter_clean_must_not_be_run_here=True,personal_files_touched=False),
        local_model_experiment=dict(download_provenance_preserved=(model/'download-provenance.json').exists(),
            model_cached=(model/'Qwen3-4B-Q4_K_M.gguf').exists(),server_stopped=True,
            resumable_partial_bytes=partial.stat().st_size if partial.exists() else 0,
            inference_summary=read(experiment) if experiment.exists() else None,
            both124_meaning_reviews_complete=True,baseline_unapproved=58,
            greedy_unapproved=85,recommended_unapproved=89,both_configurations_rejected=True,
            released_trial_model_bytes=2497280256,
            model_weights_trained=False,model_installed_in_app=False,reference_text_supplied=False),
        active_sessions=[
            dict(session=21650,job='full frozen801704 traversal across124 chapters',log='build/full-comics/full-en8017-geometry.log'),
            dict(session=41435,job='audit_corpus_quality.py --watch --track-experiments',log='build/full-comics/metrics/experimental-progress8021.log'),
            dict(session=53356,job='HTTP server127.0.0.1:8765 rootbuild')],
        completed_sessions=[10333,66254,67306,12213,97836,31471,23750,83885,64046,45500],
        remaining_work=[
            'Inspect active jobs before resuming. Never duplicate output writers or overwrite frozen trials.',
            'Download and runtime preparation do not imply inferences or model improvement. Qwen is a public existing model, not a trained Luma model.',
            'Both local Qwen configurations are fully processed and reviewed on124 same fixed views:58to85 and58to89 unapproved. They were rejected. Do not restart the server or repeat these completed jobs. Server stopped and downloaded GGUF removed after preserving reports and reproducible download provenance.',
            'The isolated local model comparison must keep all228 same OCR passages, including omissions and recognition errors; no original inventory or Spanish answers may enter inference.',
            'Review every changed whole-viewport meaning against the original inventory before assigning passes; retain unchanged judgments only for exact outputs in the same viewport.',
            'Original painting remnants require paint geometry work separately from semantic recovery. Do not edit read-only frozen snapshots.',
            'Continue full124 chapter traversal; it uses the older frozen engine and is not a manual review of every word.',
            'Use complete original-pixel inventories including text missed by all detectors. Fixed viewports and cropped cohorts do not establish complete chapter coverage or full-use failure probability.',
            'No APK, new ZIP, phone work, keep-awake automation, or ready-for-release claim. Goal below5percent remains unachieved.'])
    atomic(QA/'continuation8021.json',json.dumps(data,ensure_ascii=False,indent=2))
    atomic(QA/'continuation-latest.json',json.dumps(dict(path='continuation8021.json',sha256=digest(QA/'continuation8021.json')),indent=2))
    print(json.dumps(dict(saved='continuation8021.json',progress=progress,
        free_GiB=round(data['storage']['free_bytes_now']/1024**3,2),objective_complete=False)),flush=True)


if __name__=='__main__':main()
