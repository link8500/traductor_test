"""Persist current Windows validation and resumable jobs without claiming completion."""
import datetime
import json
from audit_corpus_quality import ROOT,QA,atomic,digest,read


def main():
    files=[
        'benchmarks/full-comics/full8012-checkpoint02-semantic-review.json',
        'benchmarks/full-comics/windows8018-heldout-semantic-review.json',
        'benchmarks/full-comics/full-corpus-coverage8018-semantic-review.json',
        'benchmarks/full-comics/full-corpus-coverage8019-semantic-review.json',
        'benchmarks/full-comics/windows8019-heldout-semantic-review.json',
        'benchmarks/full-comics/int8-translation8018-semantic-review.json',
        'benchmarks/full-comics/ocr8019-third-full-review.json',
        'build/full-comics/production-coverage8019/summary.json',
        'build/full-comics/metrics/verification8019.json',
        'build/full-comics/windows-engine801901.json',
        'build/full-comics/windows-engine802001.json']
    files.extend(['benchmarks/full-comics/windows8020-consensus-semantic-review.json',
        'build/full-comics/windows8020-consensus-heldout-pixels/summary.json'])
    progress={}
    for name in ['ocr-en8012-recovery','translated-en8014-recovery','translated-en8017-geometry']:
        rows=[read(p) for p in (QA/name).glob('*.done.json')]
        progress[name]=dict(chapters_complete=len(rows),regions=sum(r['regions'] for r in rows),
            runtime_errors=sum(r['runtime_errors'] for r in rows),word_review_complete=False)
    value=dict(updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),objective_complete=False,
        target_failure_probability_strictly_below=.05,screen_attempt_failure_probability=None,target_achieved=False,
        constraints=dict(windows_first=True,android_apk_deferred=True,phone_work=False,offline_only=True,
            only_124_chapters=True,dialogue_and_narration_must_not_be_omitted=True,sfx_may_remain_unchanged=True,
            report_aggregate_counts_without_chapter_examples=True,keep_awake_automation_deleted=True),
        latest_packaged_experimental_build='801704 / version8017',latest_validated_unshipped_build='801901',
        current_isolated_reader_experiment='802001; enabled only by benchmark input reader directories; live worker unchanged',
        evidence=[dict(path=name,sha256=digest(ROOT/name)) for name in files],progress=progress,
        active_sessions=[
            dict(session=21650,command='run_full_comics.py --language en --workers 2 --series absolute-regression --start 1 --end 124 --report-name translated-en8017-geometry --engine-snapshot build/full-comics/windows-engine801704.json --binary build/full-comics/frozen-windows801704/traductor.exe',log='build/full-comics/full-en8017-geometry.log'),
            dict(session=17726,command='run_windows_viewports8020.py --variant baseline',log='build/full-comics/windows8020-viewports-baseline.log'),
            dict(session=26342,command='run_windows_viewports8020.py --variant consensus',log='build/full-comics/windows8020-viewports-consensus.log'),
            dict(session=43225,command='audit_corpus_quality.py --watch --track-experiments; restart after loader code edits',log='build/full-comics/metrics/experimental-progress8019.log'),
            dict(session=53356,command='python -m http.server 8765 --bind 127.0.0.1 --directory build')],
        remaining_work=[
            'Inspect active sessions/logs before resuming. Never duplicate writers or overwrite frozen trials.',
            '801901 is validated but not ready:119 manually inspected changed regions117to41 unapproved,76fixed,0fullregressions; six valid recoveries are conservatively withheld. This is not a screen failure probability.',
            'Full actual801901 same124 crop test has41 unapproved after two explicit baseline judgment revisions;43to41 paired. Seven source words remain omitted.',
            'Int8 existing-model experiment is rejected:41to41 unapproved,4fixed4regressed. Preserve all52 manual decisions and two baseline judgment revisions.',
            'All108 previously unchanged third-cohort OCR locations are now transcribed;124 crops1553 words. Candidate46to27 word errors,33to19 bad crops,14fixed0regressed,5omissions. One negative control has no dialogue.',
            'OCR apostrophes are protected in the isolated header;496 policy evaluations over372 unique pixels include an overlapping Windows bridge. No new model inference is implied by these policy evaluations.',
            'The actual802001 Windows integration crop trial is complete:137baseline sources/bounds preserved,7sourcechanges6translationchanges,all7 visually reviewed;41to36 unapproved,5fixed0regressed. OCR34to27 word errors,20to14badcrops,7omissions unchanged. This is an explicit benchmark configuration; live worker remains disabled.',
            'Follow both full reading-viewport comparison jobs. The baseline uses801901 and the consensus802001, on the same124 frozen original viewports. They do not include live desktop capture or toolbar actions and cannot certify complete-app-use failure probability.',
            'The802001 live worker still uses existing installed readers. Additional cached models are passed explicitly only to the native benchmark; no new weights are bundled or trained.',
            'Continue the full801704 real-app traversal across124 chapters; it is separate from the completed fixed old-OCR controls.',
            'Complete original-pixel dialogue inventories must include text missed by all detectors, not just existing OCR boxes. None of the crop cohorts establish that denominator for whole chapters/screens.',
            'Measure complete-screen attempts, with omissions, wrong meaning, crash, block or unfinished output counted as failed uses. Current failure probability is unknown and goal below5percent is not achieved.',
            'Do not build Android, work on the phone, restart the deleted keep-awake automation, or publish the trial as ready.'])
    atomic(QA/'continuation8019.json',json.dumps(value,ensure_ascii=False,indent=2))
    print(json.dumps(dict(saved='continuation8019.json',objective_complete=False,progress=progress)),flush=True)


if __name__=='__main__':main()
