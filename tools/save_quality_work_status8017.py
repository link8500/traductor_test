"""Save an honest continuation point for Windows QA, preserving older versions."""
import argparse
import datetime
import json
from audit_corpus_quality import ROOT, QA, atomic, digest, read


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--traversal-session',type=int,required=True)
    parser.add_argument('--metrics-session',type=int,required=True)
    args=parser.parse_args()
    names=['ocr-en8012-recovery','translated-en8012-recovery','translated-en8014-recovery','translated-en8017-geometry']
    progress={}
    for name in names:
        rows=[read(p) for p in (QA/name).glob('*.done.json')]
        progress[name]=dict(chapters=len(rows),regions=sum(r['regions'] for r in rows),runtime_errors=sum(r['runtime_errors'] for r in rows),
            word_review_complete=False,all_files_traversed=len(rows)==124)
    files=[
        'benchmarks/full-comics/ocr8016-consensus-heldout-full-review.json',
        'benchmarks/full-comics/windows8016-heldout-semantic-review.json',
        'benchmarks/full-comics/windows8017-geometry-semantic-review.json',
        'benchmarks/full-comics/windows8017-render-geometry-semantic-review.json',
        'benchmarks/full-comics/ocr8017-coverage-heldout-review.json',
        'benchmarks/full-comics/short-clause8017-candidate-semantic-review.json',
        'build/full-comics/full8012-review-checkpoint02/sample.json',
        'build/full-comics/release8017.json','build/full-comics/metrics/verification8017.json']
    value=dict(updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),objective_complete=False,
        constraints=dict(priority='Windows; complete dialogue and narration; Android APK deferred',offline_only=True,
            report_aggregates_without_chapter_examples=True,only_124_chapters=True,phone_work=False,
            keep_awake_automation_deleted=True,onomatopoeia_may_remain_unchanged=True,
            target_failure_probability_below=.05,screen_attempt_failure_probability=None,target_achieved=False,
            all_chapter_words_visually_reviewed=False,translation_weights_changed=False,ocr_weights_changed=False),
        release=read(QA/'release8017.json'),progress=progress,
        evidence=[dict(path=name,sha256=digest(ROOT/name)) for name in files],
        active_sessions=[dict(session=args.traversal_session,command='run_full_comics.py --language en --workers 2 --series absolute-regression --start 1 --end 124 --report-name translated-en8017-geometry --engine-snapshot build/full-comics/windows-engine801704.json --binary build/full-comics/frozen-windows801704/traductor.exe',log='build/full-comics/full-en8017-geometry.log'),
            dict(session=args.metrics_session,command='audit_corpus_quality.py --watch --track-experiments',log='build/full-comics/metrics/experimental-progress8017-final.log'),
            dict(session=53356,command='python -m http.server 8765 --bind 127.0.0.1 --directory build')],
        completed_sessions=[64881,39150,77418,60210,22344,3551,42360,34744,8281],
        abandoned_trials_preserved=dict(naive_geometry='801701: OCR regression; not packaged',
            grouping_only='801702 and801703: semantic improvement but overpaint observed; not packaged',
            short_clause_unprotected='Repetition; output preserved, not incorporated'),
        remaining_work=[
            'Inspect active process/log before resuming; never duplicate writers. Keep all frozen trials and historical reports.',
            'Current packaged build is801704 (version8017), with conservative grouping and two-pass nonoverlapping text painting. OCR/NMT candidates are not in it.',
            'Follow the complete current801704 real-app pixel traversal across124chapters, distinct from the finished older801201 controls. It does not certify per-word semantics.',
            'Review the99 changed locations of full8012 checkpoint02;645 byte-identical same-location outputs retain their previous judgments. Reuse partialcheckpoint01 only with exact source/output and pixel identity. Do not add overlapping counts.',
            'Guarded short-clause candidate has14 changed outputs reviewed:13to5 unapproved,8fixed,0regressions. Integrate only after broader fresh production parity and complete current pixel trial; preserve rejected repetition result.',
            'Experimental OCR coverage ruleR3 third independent cohort has16changed crops reviewed,14fixed,0regressed,2stillbad;108unchanged crops still unreviewed. Existing full124second-cohort OCR manual review is finished.',
            'Before OCR candidate integration, preserve internal apostrophes. R2/R3 can turn malformed contractions into another valid word by dropping punctuation; do not silently accept that as improved meaning.',
            'Build complete visible dialogue/narration inventories against original pixels, including text no detector found. SFX may remain. Current sampled sources do not provide an omission denominator for entire screens.',
            'Measure complete screen attempts with missing content, wrong meaning, crash, block or unfinished output counted as failed use. Current probability is unknown and target below5percent is not achieved.',
            'No phone work, no Android APK, no model weight training this turn. Do not restart the deleted keep-awake automation.'])
    atomic(QA/'continuation8017.json',json.dumps(value,ensure_ascii=False,indent=2))
    print(json.dumps(dict(saved='continuation8017.json',objective_complete=False,progress=progress)),flush=True)


if __name__=='__main__':main()
