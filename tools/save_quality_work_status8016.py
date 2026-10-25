"""Record the current Windows work without rewriting historical checkpoints."""
import datetime
import json

from audit_corpus_quality import QA, atomic, digest, read


def main():
    previous = read(QA / 'continuation8015.json')
    release = read(QA / 'release8016.json')
    active = previous['active_sessions']
    for item in active:
        if 'audit_corpus_quality.py' in item['command']:
            item['session'] = 63038
    progress = {}
    for name in [
        'ocr-en8012-recovery', 'translated-en8012-recovery',
        'translated-en8014-recovery', 'comparison8012-recovery',
        'comparison8014-recovery',
    ]:
        folder = QA / name
        source = read(folder / 'summary.json')
        progress[name] = {
            key: value for key, value in source.items()
            if key in ('chapters_completed', 'pairs_compared', 'regions', 'runtime_errors')
            or key == 'chapters' and isinstance(value, int)
        }
        progress[name]['completed_status_files'] = len(list(
            folder.glob('absolute-regression-*-en.done.json')))
    evidence_paths = [
        'benchmarks/full-comics/screen-acceptance-policy.json',
        'benchmarks/full-comics/coverage8016-candidate-semantic-review.json',
        'benchmarks/full-comics/full-omission8016-semantic-review.json',
        'benchmarks/full-comics/combined-recovery8016-checkpoint01-semantic-review.json',
        'benchmarks/full-comics/ocr8016-reader-comparison.json',
        'benchmarks/full-comics/ocr8016-consensus-conservative-candidate.json',
        'benchmarks/full-comics/ocr8016-consensus-heldout-review.json',
        'build/full-comics/production-coverage8016/summary.json',
        'build/full-comics/windows8016-real-pixels/summary.json',
        'build/full-comics/release8016.json',
        'build/full-comics/metrics/verification8016.json',
    ]
    from audit_corpus_quality import ROOT
    value = dict(
        updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        objective_complete=False,
        constraints=dict(
            priority='Windows; complete dialogue and narration before Android APK',
            offline_only=True, report_aggregates_without_chapter_examples=True,
            only_124_chapters=True, phone_work=False,
            deleted_keep_awake_automation_must_not_be_recreated=True,
            onomatopoeia_may_remain_unchanged=True,
            target_failure_probability_below=0.05,
            screen_attempt_failure_probability=None, target_achieved=False,
            all_chapter_words_visually_reviewed=False,
            translation_weights_changed=False,
            experimental_ocr_consensus_in_app=False),
        release=release,
        evidence=[dict(path=p, sha256=digest(ROOT / p)) for p in evidence_paths],
        progress=progress, active_sessions=active,
        results_do_not_add_overlapping_samples=dict(
            selected_changed_translation_regions=dict(
                reviewed=37, before_errors=36, after_errors=10, corrected=26, regressed=0),
            fixed_ocr_sample=dict(
                valid=735, before_errors=199, after_errors=196, corrected=3, regressed=0,
                explicitly_revised_control_judgments=2),
            reader_development_sample=dict(
                crops=124, words=1562, before_word_errors=44, candidate_word_errors=27,
                before_failed_crops=34, candidate_failed_crops=19,
                candidate_omitted_words_remaining=10),
            reader_heldout=dict(
                locations=124, changed_crops_inspected=12, complete_fixes=10,
                regressed=0, still_failed=2, unchanged_crops_not_semantically_reviewed=112)),
        next_steps=[
            'Inspect existing sessions before restarting; avoid duplicate writers.',
            'Keep every historical checkpoint and frozen binary intact.',
            'Prioritize complete visible dialogue/narration inventories against original pixels, including text never detected. Onomatopoeia unchanged is allowed.',
            'Complete the old frozen 8012 OCR and 8014 combined control traversals, then freeze checkpoint02 separately from partial checkpoint01.',
            'Integrate the conservative three-reader candidate into a separate Windows capture trial only after measuring model loading, latency, grouping and omission behavior; it is not in 8016.',
            'Review the 112 unchanged heldout crops; changed-case-only inspection cannot establish a full error rate.',
            'Run a complete current Windows801601 capture evaluation, distinct from the older801201 background control.',
            'Measure complete screen attempts with any missing dialogue, changed meaning, crash, block or unfinished output counted as failure. Do not substitute word error rate or region sample rate.',
            'The 1854-image all-chapter gallery is 8014 on fixed8011 OCR; the 8016-specific evidence contains37 changed-region comparisons and4 actual paired Windows viewport renders.',
            'Defer Android APK work; no training or model-weight changes were made.',
        ])
    path = QA / 'continuation8016.json'
    atomic(path, json.dumps(value, ensure_ascii=False, indent=2))
    print(json.dumps(dict(saved=str(path), objective_complete=False, progress=progress)))


if __name__ == '__main__':
    main()
