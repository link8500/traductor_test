"""Persist truthful aggregate state while broad chapter traversal continues."""
import datetime
import json
import shutil
from audit_corpus_quality import ROOT, QA, atomic, digest, read


def main():
    reports={}
    for key,name in [('best_native','windows8021-full-viewports-semantic-review.json'),
        ('ocr_component','viewport8023-dialogue-ocr-review.json'),
        ('normalized_qwen','normalized8023-full-viewports-semantic-review.json'),
        ('specialist_hy','hy8024-full-viewports-semantic-review.json'),
        ('native_short_candidate','windows8024-short-full-viewports-semantic-review.json'),
        ('default_windows_short_recovery','windows8024-default-full-viewports-semantic-review.json')]:
        path=ROOT/'benchmarks/full-comics'/name
        if path.exists():reports[key]=dict(path=str(path.relative_to(ROOT)),sha256=digest(path),
            summary={k:v for k,v in read(path).items() if k not in ['entries','ocr_entries']})
    progress={}
    for name in ['ocr-en8012-recovery','translated-en8014-fixed-ocr','translated-en8014-recovery','translated-en8017-geometry','translated-en8024-short-default']:
        rows=[read(p) for p in (QA/name).glob('*.done.json')]
        progress[name]=dict(chapters_complete=len(rows),regions=sum(r['regions'] for r in rows),
            runtime_errors=sum(r['runtime_errors'] for r in rows),all_words_manually_reviewed=False)
    candidate=QA/'windows8024-short-default-full-viewports'
    parts=[]
    for part in range(4):
        output=candidate/f'part-{part}.output.jsonl';done=candidate/f'part-{part}.output.jsonl.summary.json'
        parts.append(dict(part=part,complete=done.exists(),summary=read(done) if done.exists() else None,
            output_bytes=output.stat().st_size if output.exists() else 0))
    value=dict(updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        objective='Improve offline Windows translation and avoid omitted dialogue; measure complete-use failures below5 percent honestly',
        reports=reports,progress=progress,native_short_candidate_parts=parts,
        screen_attempt_failure_probability=None,target_achieved=False,all_chapter_words_manually_reviewed=False,
        completed_work=['All124 normalized-Qwen meanings reviewed:58to74 unapproved,10fixes26regressions; rejected.',
            'All124 HY specialist meanings reviewed:58to57 unapproved,15fixes14regressions; not accepted as replacement.',
            'All124 detector frames audited:805 boxes,19 short detections,38 upright dual-reader proposals.',
            'Eight guard checks passed. Native802401 completed124 views,229 regions,0runtime errors;58to57unapproved,1fix0regressions.',
            'New painting inspected: recovered short dialogue fits without conspicuous original remnants.123 existing photographs reused.',
            'Default802402 completed124 views,229regions,0runtime errors:62to61 unapproved,1fix0regressions. Optional consensus readers remain off.',
            'Both802401 and802402 passed37 native geometry checks plus recovery/overlay/toolbar checks.42report-integrity tests passed.',
            'Both local LLM evaluation servers stopped after completion; one copy of each cached model remains.'],
        sessions=[dict(session=83848,job='Resumed frozen801704 full124 chapter traversal',log='build/full-comics/full-en8017-geometry-resumed8024.log'),
            dict(session=82574,job='Native802402 normal/default configuration on124 fixed full viewports,4parts',log='build/windows8024-default.log',
                complete=(candidate/'summary.json').exists()),
            dict(session=92735,job='Full124-chapter traversal using corrected normal Windows802402,1worker',log='build/full-comics/full-en8024-short-default.log'),
            dict(session=40219,job='Metrics watch includes corrected complete traversal and both reviewed fixed-view cohorts',log='build/full-comics/metrics/experimental-progress8024c.log'),
            dict(job='HTTP loopback8765 serves build directory; healthy after restart; session id unavailable')],
        dead_old_sessions_not_to_poll=[21650,51606,53356,25398,41589],
        completed_sessions=[73017,43584,8168,65250,73175,90011,29379,17189,16064,82574],
        storage=dict(free_bytes_now=shutil.disk_usage(ROOT).free,reserve_bytes=4*1024**3,
            no_personal_files_removed=True,no_apk_or_zip_created=True,temporary_pixels_only=True),
        constraints=dict(android_deferred=True,keep_awake_stays_deleted=True,no_drive_upload=True,
            credentials_not_used_or_saved=True,do_not_retry_or_bypass_blocked_git_deletion=True,
            user_updates_aggregates_only=True,do_not_claim_all124_chapter_words_reviewed=True,
            hy_outputs_not_used_to_train_other_models=True,hy_distribution_not_approved=True),
        remaining_work=['Both default802402 and combined802401 cohorts are complete and reviewed; do not repeat them without a new change or failure.',
            'Extra OCR readers remain off in the normal worker. Short-pronoun recovery is enabled after the completed124-view candidate and native-paint review.',
            'Preserve original124 full-dialogue inventories, clipped cases and rejected-model regressions.',
            'Continue corrected802402 full-chapter traversal92735 and frozen801704 baseline83848, then compare all matched outputs and review omissions. No new250-chapter series yet.',
            'App-use failure probability remains unknown; saved viewports and word scores are separate component measurements.'])
    atomic(QA/'continuation8024.json',json.dumps(value,ensure_ascii=False,indent=2))
    atomic(QA/'continuation-latest.json',json.dumps(dict(path='continuation8024.json',sha256=digest(QA/'continuation8024.json')),indent=2))
    print(json.dumps(dict(saved='continuation8024.json',full_traversal=progress['translated-en8017-geometry'],
        completed_native_parts=sum(p['complete'] for p in parts),free_GiB=round(shutil.disk_usage(ROOT).free/1024**3,2),target_achieved=False)),flush=True)


if __name__=='__main__':main()
