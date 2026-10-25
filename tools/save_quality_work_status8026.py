"""Save actual evidence and pending work without predicting completed validation."""
import argparse
import datetime
import json
import shutil
from audit_corpus_quality import ROOT, QA, atomic, digest, read
from quality_resources import available_memory_bytes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['matrix-session','old-traversal-session','traversal-session','metrics-session','comparison-session','report-tests-passed']:
        parser.add_argument('--'+name,type=int)
    args=parser.parse_args();reports={}
    for key,path in [('previous_normal',ROOT/'benchmarks/full-comics/windows8025-packaged-full-viewports-semantic-review.json'),
                     ('current_normal',ROOT/'benchmarks/full-comics/windows8026-inflection-full-viewports-semantic-review.json'),
                     ('inflection_selection',QA/'ocr-morph-consensus8026/summary.json'),
                     ('runtime_checks',QA/'windows8026-inflection-runtime-checks.json'),
                     ('compact_ledger_integrity',QA/'compact-ledger8026-validation.json')]:
        if path.exists():reports[key]=dict(path=str(path.relative_to(ROOT)),sha256=digest(path),
            summary={k:v for k,v in read(path).items() if k not in ['entries','ocr_entries','proofs']})
    if 'inflection_selection' in reports:
        for cohort in reports['inflection_selection']['summary']['cohorts'].values():cohort.pop('entries',None)
    progress={}
    for name in ['translated-en8017-geometry','translated-en8024-short-default','translated-en8025-packaged','translated-en8026-inflection']:
        rows=[read(path) for path in (QA/name).glob('*.done.json')]
        progress[name]=dict(chapters_complete=len(rows),regions=sum(r['regions'] for r in rows),
                            runtime_errors=sum(r['runtime_errors'] for r in rows),all_words_manually_reviewed=False)
    folder=QA/'windows8026-inflection-full-viewports'
    parts=[dict(part=part,complete=(folder/f'part-{part}.output.jsonl.summary.json').exists()) for part in range(4)]
    states={name:read(QA/name) for name in ['full-quality8025-status.json','full-quality8026-status.json','full-quality8026-adopted-control-status.json',
        'comparison8026-inflection/summary.json','full-native-delta8026/summary.json'] if (QA/name).exists()}
    complete=(folder/'summary.json').exists()
    value=dict(updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),reports=reports,progress=progress,
        current_compiled_windows_build='802601',fresh_fixed_view_comparison_complete=complete,parts=parts,
        report_integrity_tests_passed=args.report_tests_passed,states=states,
        sessions=[dict(session=args.matrix_session,job='Native802601 default124 fixed viewports,one worker',log='build/windows8026-inflection.log',complete=complete),
                  dict(session=args.old_traversal_session,job='Prior coordinator: preserve running801704 control until latest-build handoff',log='build/full-comics/full-quality8025.log'),
                  dict(session=args.traversal_session,job='One latest802601 full worker plus preserved existing control;retire only obsolete802501 next stage after control completes',log='build/full-comics/full-quality8026-active.log'),
                  dict(session=args.metrics_session,job='Metrics watcher,full outputs delta and word-review counters',log='build/full-comics/metrics/experimental-progress8026-active.log'),
                  dict(session=args.comparison_session,job='All124 compact Olympus comparison ledgers; waits for current full chapter outputs',log='build/full-comics/comparison8026-inflection-compact.log'),
                  dict(session=6292,job='HTTP8765 loopback; recheck health')],session_liveness_must_be_rechecked=True,
        completed_work=['Generic affix support requires two identical pixel readings,one letter difference,known stem,protected numbers and negation.',
            '12 native guards passed. All372 distinct control crops plus overlapping bridge tested:one further OCR correction,no worsening.',
            'Isolated selector on all124 full views reduces word discrepancies47to45 of2265expected words. All expected words remain in the denominator.',
            'Both modified complete original views inspected; two fresh native translations reviewed:one improves but still omits degree/emphasis,and one still invents a time unit. Neither complete view is approved.',
            'Windows802601 compiled and passed37 geometry checks plus recovery/overlay/toolbar checks.',
            'Full chapter deltas preserve every changed exact-geometry output and every unmatched row; unmatched geometry is not automatically an omission.',
            'Olympus comparison pages prepared for all124; machine proposals never count as semantic approvals.'],
        remaining_work=['If fixed-view validation is incomplete,resume its existing process/checkpoint; do not launch a duplicate.',
            'Require all124 actual displayed outputs to match reviewed selection and translations before publishing native8026 results.',
            'After valid native output:run publish_inflection_windows8026.py,inspect both new native paintings,save paint/manual-review.json,publish gallery,and run45 integrity tests.',
            'Start run_full_quality8026.py only after the valid review exists. Preserve the in-flight801704 control;one worker per traversal,maximum2native full workers,memory gate before each new inference.',
            'Reload metrics watcher after code edits; preserve comparison watcher and its current outputs.',
            'Finish full124-chapter native traversal,all-word inspection and complete live capture/overlay/movement testing.'],
        storage=dict(free_bytes_now=shutil.disk_usage(ROOT).free,reserve_bytes=4*1024**3,available_memory_bytes=available_memory_bytes(),
                     no_new_model_download=True,no_personal_files_removed=True,no_apk_or_zip_created=True,new_paintings_only=2),
        constraints=dict(android_deferred=True,keep_awake_stays_deleted=True,no_drive_upload=True,credentials_not_used_or_saved=True,
                         do_not_retry_or_bypass_blocked_git_deletion=True,user_updates_aggregates_only=True,no_subagents_authorized=True,
                         hy_outputs_not_used_to_train_other_models=True),
        all_chapter_words_manually_reviewed=False,screen_attempt_failure_probability=None,target_achieved=False)
    if complete and 'current_normal' in reports:
        value['completed_work'].extend(['Actual Windows802601 finished all124 fixed views,229regions,0runtime errors;every displayed location matches the reviewed plan.',
            'Strict full-view judgments stay57to57 unapproved,0full corrections0regressions;historical62to57 remains8.06percent relative reduction.',
            'Both new review renders inspected;small original strokes remain in one. Neither full viewport is approved.122 prior pictures reused.',
            'All144482 reference-word records across124 existing ledgers round-trip exactly with the compact format;projected72.38percent fewer ledger bytes,no historical evidence deleted.'])
        value['remaining_work']=['Do not rerun completed124-view inference,selector controls,publishing or integrity checks unless a new change,failure or unresolved concern requires it.',
            'Keep coordinator8026 running:latest802601 full traversal and existing801704 control each have one worker;at most2native workers and a3GiB memory gate before each new job. It retires only obsolete802501 next stage after control completes.',
            'Keep compact comparison watcher and metrics watcher running;inspect every full-chapter difference and potential omission as output becomes available.',
            'All124 chapter words are not yet visually reviewed. Captured-use failure probability and the below5percent goal remain unverified.',
            'Small original text remnants observed in one review rendering remain a separate visual issue. No new live GUI trial was verified.']
    atomic(QA/'continuation8026.json',json.dumps(value,ensure_ascii=False,indent=2))
    atomic(QA/'continuation-latest.json',json.dumps(dict(path='continuation8026.json',sha256=digest(QA/'continuation8026.json')),indent=2))
    print(json.dumps(dict(saved='continuation8026.json',fixed_view_comparison_complete=complete,progress=progress,target_achieved=False)),flush=True)


if __name__=='__main__':main()
