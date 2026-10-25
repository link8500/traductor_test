"""Checkpoint measured Windows progress, keeping whole-chapter review pending."""
import argparse
import datetime
import json
import shutil
from audit_corpus_quality import ROOT, QA, atomic, digest, read
from quality_resources import available_memory_bytes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--traversal-session',type=int)
    parser.add_argument('--metrics-session',type=int)
    args=parser.parse_args()
    reports={}
    for key,name in [('packaged_normal','windows8025-packaged-full-viewports-semantic-review.json'),
        ('prior_normal','windows8024-default-full-viewports-semantic-review.json'),
        ('identical_reviewed_trial','windows8024-short-full-viewports-semantic-review.json'),
        ('ocr_component','viewport8023-dialogue-ocr-review.json')]:
        path=ROOT/'benchmarks/full-comics'/name
        reports[key]=dict(path=str(path.relative_to(ROOT)),sha256=digest(path),
                         summary={k:v for k,v in read(path).items() if k not in ['entries','ocr_entries']})
    progress={}
    for name in ['translated-en8017-geometry','translated-en8024-short-default','translated-en8025-packaged']:
        rows=[read(path) for path in (QA/name).glob('*.done.json')]
        progress[name]=dict(chapters_complete=len(rows),regions=sum(r['regions'] for r in rows),
                            runtime_errors=sum(r['runtime_errors'] for r in rows),
                            automatic_traversal_only=True,all_words_manually_reviewed=False)
    status_path=QA/'full-quality8025-status.json'
    value=dict(updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        objective='Improve offline Windows translation, preserve every dialogue word and measure complete-use failures below5 percent honestly',
        reports=reports,progress=progress,full_traversal_status=read(status_path) if status_path.exists() else None,
        current_windows_build='802501',normal_worker_and_default_benchmark_use_bundled_readers=True,
        live_ui_attempt=dict(verified_luma_window=False,counted_as_complete_app_use=False,
            note='Desktop launcher did not expose a verifiable Luma window; no translation was initiated through that interface.'),
        completed_work=['Windows802501 freshly reproduced all124 reviewed full-location outputs and229regions without explicit reader paths or activation.',
            'Previous normal61to57 unapproved,4full corrections0regressions; historical62to57,5full corrections0remaining regressions.',
            'OCR component remains47word errors of2265expected words; not a complete-app failure probability.',
            '37native geometry checks plus recovery/overlay/toolbar checks and43report-integrity tests passed.',
            'All new Windows reader files verified by SHA256; no new download or model training.',
            'QA memory pressure corrected by checkpointing and stopping only own jobs; resumed fixed views with1nativeworker.'],
        sessions=[dict(session=args.traversal_session,job='Sequential frozen801704 then packaged802501 full124-chapter traversals,1worker total',
                       log='build/full-comics/full-quality8025.log'),
                  dict(session=args.metrics_session,job='Metrics watcher including packaged normal Windows and all broad-traversal counters',
                       log='build/full-comics/metrics/experimental-progress8025.log'),
                  dict(session=6292,job='HTTP loopback8765 serves build; recheck health on continuation')],
        session_liveness_must_be_rechecked=True,
        intentionally_stopped_jobs=['802402full-traversal2workers','801704full-traversal1worker','802501fixed-views4workers'],
        previous_normal802402_full_traversal_retained_as_historical_control=True,
        storage=dict(free_bytes_now=shutil.disk_usage(ROOT).free,reserve_bytes=4*1024**3,
                     available_memory_bytes=available_memory_bytes(),minimum_memory_before_new_inference_bytes=3*1024**3,
                     no_personal_files_removed=True,no_apk_or_zip_created=True,windows_readers_logical_bytes=44559053),
        constraints=dict(android_deferred=True,keep_awake_stays_deleted=True,no_drive_upload=True,
                         credentials_not_used_or_saved=True,do_not_retry_or_bypass_blocked_git_deletion=True,
                         user_updates_aggregates_only=True,no_subagents_authorized=True,
                         hy_outputs_not_used_to_train_other_models=True,hy_distribution_not_approved=True),
        remaining_work=['Do not rerun completed fixed-view comparisons without new changes, failures or unresolved concerns.',
            'Finish remaining frozen801704 baseline chapters, then traverse all124 with packaged802501 in separate folder. Use one native worker total.',
            'Compare all matched full-chapter outputs and inspect dialogue omissions, including undetected text; traversal is not semantic approval.',
            'All words of every chapter remain unreviewed. No new250-chapter series yet.',
            'Complete-app capture/overlay/movement use testing remains separate; its failure probability and the less-than5percent goal remain unverified.'],
        all_chapter_words_manually_reviewed=False,screen_attempt_failure_probability=None,target_achieved=False)
    atomic(QA/'continuation8025.json',json.dumps(value,ensure_ascii=False,indent=2))
    atomic(QA/'continuation-latest.json',json.dumps(dict(path='continuation8025.json',sha256=digest(QA/'continuation8025.json')),indent=2))
    print(json.dumps(dict(saved='continuation8025.json',progress=progress,free_GiB=round(shutil.disk_usage(ROOT).free/1024**3,2),target_achieved=False)),flush=True)


if __name__=='__main__':main()
