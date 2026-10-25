"""Save resumable evidence and commands without upgrading coverage to approval."""
import datetime
import json
from audit_corpus_quality import ROOT,QA,read,digest,atomic


def main():
    metrics=read(QA/'metrics/summary.json');release=read(QA/'release8015.json')
    active=[
        (53356,'Local web server','.\\build\\quality-venv\\Scripts\\python.exe -u -m http.server 8765 --bind 127.0.0.1 --directory build'),
        (64881,'Full immutable 8012 OCR traversal','.\\build\\quality-venv\\Scripts\\python.exe -u tools/run_full_comics.py --language en --workers 2 --series absolute-regression --start 1 --end 124 --ocr-only --resolve-overlaps --report-name ocr-en8012-recovery --engine-snapshot build/full-comics/windows-engine801201.json --binary build/full-comics/frozen-windows801201/traductor.exe'),
        (39150,'Unchanged old NMT for isolating OCR benefit; pinned snapshot required','.\\build\\quality-venv\\Scripts\\python.exe -u tools/translate_ocr_reports.py --ocr-reports ocr-en8012-recovery --output-name translated-en8012-recovery --translation-snapshot build/full-comics/frozen-translation8011 --watch --expected-chapters 124'),
        (77418,'OCR comparison with Spanish reference','.\\build\\quality-venv\\Scripts\\python.exe -u tools/compare_full_comics.py --english-reports translated-en8012-recovery --output-name comparison8012-recovery --expected-chapters 124 --watch'),
        (60210,'Combine recovered OCR with pinned new NMT','.\\build\\quality-venv\\Scripts\\python.exe -u tools/translate_recovered_coverage_corpus.py'),
        (22344,'Combined OCR/NMT comparison with Spanish reference','.\\build\\quality-venv\\Scripts\\python.exe -u tools/compare_full_comics.py --english-reports translated-en8014-recovery --output-name comparison8014-recovery --expected-chapters 124 --watch'),
        (70340,'Update aggregate web progress; never count automatic flags as confirmed errors','.\\build\\quality-venv\\Scripts\\python.exe -u tools/audit_corpus_quality.py --watch --track-experiments')]
    progress={}
    for name in ['ocr-en8012-recovery','translated-en8012-recovery','translated-en8014-recovery','comparison8012-recovery','comparison8014-recovery']:
        path=QA/name/'summary.json'
        if path.exists():progress[name]={k:v for k,v in read(path).items() if k in ['chapters_completed','pairs_compared','regions','runtime_errors'] or k=='chapters' and isinstance(v,int)}
        progress.setdefault(name,{})['completed_status_files']=len(list((QA/name).glob('absolute-regression-*-en.done.json')))
    value=dict(updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),objective_complete=False,
        constraints=dict(offline_only=True,report_aggregates_without_chapter_examples=True,only_124_chapters=True,
            phone_work=False,deleted_keep_awake_automation_must_not_be_recreated=True,translation_weights_changed=False,
            all_chapter_words_visually_reviewed=False),
        current_metrics=dict(reviewed_regions=744,comparable_regions=735,excluded=9,historical_before_errors=491,after_errors=197,
            corrected_regions=320,regressed_regions=26,relative_error_reduction_percent=59.877800407331975,
            sample_review='benchmarks/full-comics/coverage8014-six-regions-semantic-review.json',
            sample_review_sha256=metrics['six_region_coverage_comparison']['adjudications_sha256']),
        completed_translation_pass=metrics['full_translation_pass'],gallery=metrics['gallery_verification'],
        partial_ocr_review=metrics['full_recovery_checkpoint_comparison'],
        windows_trial=dict(version=release['version'],archive=release['archive'],sha256=release['archive_sha256'],
            frozen_build='801501',background_native_guards=10,kotlin_pure_tests=6,native_kotlin_pixel_parity_cases=8,
            background_changed_cases=1,unchanged_render_cases=7,translation_changes_from_background_fix=0),
        android_full_application_built=False,android_build_issue='Gradle Java NIO loopback connection fails before compilation; standalone real Kotlin source/JUnit and pixel parity passed.',
        progress=progress,active_sessions=[dict(session=s,role=r,command=c) for s,r,c in active],
        next_steps=[
            'Inspect live sessions before restarting; never run duplicate writers in one inference directory.',
            'Preserve every 372/496/620/744 semantic snapshot, gallery and frozen binary.',
            'Once the full 8012 OCR and old-NMT passes reach 124, freeze a new full recovery checkpoint with tools/prepare_full_recovery_checkpoint.py --output-name full8012-review-checkpoint02. The existing checkpoint01 is immutable and contains 48 inspected changed locations of 318 total across 53 chapters.',
            'Reuse checkpoint01 judgments only for matching original_id, frozen report hash, selected source/output and geometry. Reinspect other changed outputs against original English/Spanish pixels.',
            'Evaluate the combined translated-en8014-recovery cohort independently at all 744 fixed locations. Do not add its percentages or counts to overlapping samples.',
            'A full current Windows 8015 capture pass still remains: frozen 801501 has 8013 line completion plus unchanged 8014 NMT and a rendering-only background fix. The current OCR traversal is the older immutable 801201 control.',
            'Continue word-by-word visual review beyond the 744 selected locations, including never-detected lettering. No automatic traversal, token match or unchanged output approves its meaning.',
            'The Windows background fix is applied only after Recognize/translation; it does not change OCR grouping or NMT sources. Android has the same pure Kotlin rule and service call, but no new APK was built or installed.'
        ])
    # Do not embed a duplicate historical entry list in the continuation note.
    atomic(QA/'continuation8015.json',json.dumps(value,ensure_ascii=False,indent=2))
    print(json.dumps(dict(saved='build/full-comics/continuation8015.json',objective_complete=False,progress=progress)))


if __name__=='__main__':main()
