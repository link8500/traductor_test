"""Aggregate repeatable QA over all 124 saved chapters, with matched cohorts.

Semantic errors are counted only from explicit adjudications. Automatic alerts
and changes in their count are reported separately. No app outputs are altered.
"""
import argparse
import collections
import datetime
import hashlib
import html
import json
import pathlib
import time

from translation_quality_signals import LABELS, RULE_VERSION, signals

ROOT = pathlib.Path(__file__).resolve().parents[1]
QA = ROOT / 'build/full-comics'
DEST = QA / 'metrics'
BASELINE = 'translated-en-final'
CURRENT = 'translated-en8011-context'
COHORTS = [CURRENT, 'translated-en8011', 'translated-en8010',
           'translated-en8009', 'translated-en8007', BASELINE]
CHAPTERS = [f'absolute-regression-{n:02d}' for n in range(1, 125)]
CLEAR_ERRORS = {'incorrect', 'incomplete', 'fragmented'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def records(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic(path, value):
    pending = path.with_name(path.name + '.pending')
    pending.write_text(value, encoding='utf-8')
    pending.replace(path)


def complete(folder, chapter):
    path = QA / folder / (chapter + '-en.done.json')
    if not path.exists():
        return False
    status = read(path)
    return bool(status.get('all_files_traversed') and not status.get('runtime_errors'))


def reduction(before, after):
    return 100 * (before - after) / before if before else None


def scan(chapter, folder):
    path = QA / folder / (chapter + '-en.jsonl')
    rows = records(path)
    findings = []
    for index, row in enumerate(rows):
        reasons = signals(row)
        if reasons:
            findings.append(dict(region=index, image=row['image'], bounds=row['bounds'],
                source=row['source'], translation=row.get('translation', ''), signals=reasons,
                semantic_error_confirmed=False, visually_reviewed=False))
    return dict(chapter=chapter, report_directory=folder, report_sha256=digest(path),
                regions=len(rows), alert_regions=len(findings),
                categories=dict(collections.Counter(s for f in findings for s in f['signals'])), findings=findings)


def semantic_comparison():
    """Only match identical reviewed items and validated inference files."""
    before = collections.Counter()
    after = collections.Counter()
    details = []
    for path in sorted((ROOT / 'benchmarks/full-comics/visual-reviews').glob('*.json')):
        current = read(path)
        old_path = path.parent / 'history' / (path.stem + '-8010.json')
        if not old_path.exists():
            continue
        old = read(old_path)
        for value in [old, current]:
            inference = QA / value['evaluated_english_report_directory'] / (value['chapter'] + '-en.jsonl')
            assert digest(inference) == value['evaluated_english_report_sha256']
        previous = {e['id']: e for e in old['entries']}
        for entry in current['entries']:
            prior = previous.get(entry['id'])
            if not prior or prior['english_reading'] != entry['english_reading'] or prior['reference_reading'] != entry['reference_reading']:
                continue
            before[prior['meaning_result']] += 1
            after[entry['meaning_result']] += 1
            details.append(dict(chapter=current['chapter'], id=entry['id'],
                                before=prior['meaning_result'], after=entry['meaning_result']))
    old_errors = sum(before[k] for k in CLEAR_ERRORS)
    new_errors = sum(after[k] for k in CLEAR_ERRORS)
    return dict(unit='dialogue outputs with incorrect meaning, incompleteness or fragmentation',
                pairs=len(details), comparable_pairs=len(details)-after['edition_difference'],
                before_errors=old_errors, after_errors=new_errors,
                relative_error_reduction_percent=reduction(old_errors, new_errors),
                before_categories=dict(before), after_categories=dict(after),
                corpus_wide_estimate=False, all_chapters_visually_reviewed=False, provenance=details)


def ocr_comparison():
    old_path = QA / 'visual-evaluation8010/summary.json'
    new_path = QA / 'visual-evaluation8011-context/summary.json'
    if not old_path.exists() or not new_path.exists():
        return None
    old = {r['chapter']: r for r in read(old_path)}
    pairs = [(old[r['chapter']], r) for r in read(new_path)
             if r['chapter'] in old and r['expected_english_words'] == old[r['chapter']]['expected_english_words']]
    before = sum(a['ocr_word_edits'] for a, _ in pairs)
    after = sum(b['ocr_word_edits'] for _, b in pairs)
    return dict(expected_words=sum(b['expected_english_words'] for _, b in pairs),
                before_word_edits=before, after_word_edits=after,
                relative_word_error_reduction_percent=reduction(before, after),
                semantic_translation_metric=False, corpus_wide_estimate=False)


def distributed_semantic_comparison(review_name='corpus-semantic-review.json'):
    path = ROOT / 'benchmarks/full-comics' / review_name
    if not path.exists():
        return None
    review = read(path)
    sample_path = ROOT / review['sample_path']
    assert digest(sample_path) == review['sample_sha256'], 'Reviewed sample changed'
    sample = read(sample_path)
    cases = {case['id']: case for case in sample['cases']}
    validated = set()
    before, after = collections.Counter(), collections.Counter()
    improved = regressed = unresolved = alerted_errors = unalerted_errors = 0
    provenance = []
    for entry in review['entries']:
        case = cases[entry['id']]
        assert entry['source_pixels_inspected'] and entry['reference_pixels_inspected']
        for folder_key, hash_key in [('current_folder', 'current_report_sha256'), ('baseline_folder', 'baseline_report_sha256')]:
            inference = QA / case[folder_key] / (case['chapter']+'-en.jsonl')
            if inference not in validated:
                assert digest(inference) == case[hash_key]
                validated.add(inference)
        # Reference mismatch can be excluded from reference agreement without
        # discarding a directly visible English-to-Spanish lexical defect.
        if 'unresolved' in [entry['before'], entry['after']]:
            unresolved += 1
            continue
        before[entry['before']] += 1
        after[entry['after']] += 1
        old_bad, new_bad = entry['before'] in CLEAR_ERRORS, entry['after'] in CLEAR_ERRORS
        improved += old_bad and not new_bad
        regressed += new_bad and not old_bad
        if new_bad:
            if signals(dict(source=case['source'], translation=case['translation'])):
                alerted_errors += 1
            else:
                unalerted_errors += 1
        provenance.append(dict(id=entry['id'], chapter=case['chapter'],
            current_report_directory=case['current_folder'], current_report_sha256=case['current_report_sha256'],
            baseline_report_sha256=case['baseline_report_sha256'], before=entry['before'], after=entry['after']))
    old_errors, new_errors = sum(before[k] for k in CLEAR_ERRORS), sum(after[k] for k in CLEAR_ERRORS)
    return dict(reviewed_regions=len(review['entries']), chapters_sampled=len({c['chapter'] for c in cases.values()}),
        comparable_regions=sum(before.values()), excluded_unresolved_regions=unresolved,
        before_errors=old_errors, after_errors=new_errors, corrected_regions=improved, regressed_regions=regressed,
        relative_error_reduction_percent=reduction(old_errors, new_errors),
        before_categories=dict(before), after_categories=dict(after),
        current_sample_cohorts=dict(collections.Counter(c['current_folder'] for c in cases.values())),
        confirmed_errors_with_automatic_signal=alerted_errors,
        confirmed_errors_without_automatic_signal=unalerted_errors,
        snapshot_comparison=True, population_accuracy_estimate=False, single_latest_build_comparison=False,
        sample_sha256=digest(sample_path), adjudications_sha256=digest(path), provenance=provenance)


def uniform_semantic_comparison():
    path = ROOT/'benchmarks/full-comics/current8011-full-semantic-review.json'
    if not path.exists():
        return None
    value = read(path)
    for source in value['inputs']:
        for prefix in ['sample', 'manual_decisions', 'original_review']:
            assert digest(ROOT/source[prefix+'_path']) == source[prefix+'_sha256']
    validated = set()
    for entry in value['entries']:
        for folder, field in [(CURRENT, 'current_report_sha256'), (BASELINE, 'baseline_report_sha256')]:
            report = QA/folder/(entry['chapter']+'-en.jsonl')
            if report not in validated:
                assert digest(report) == entry[field]
                validated.add(report)
    comparable = [e for e in value['entries'] if 'unresolved' not in [e['before'],e['after']]]
    assert value['reviewed_regions'] == len(value['entries'])
    assert value['comparable_regions'] == len(comparable)
    assert value['before_errors'] == sum(e['before'] in CLEAR_ERRORS for e in comparable)
    assert value['after_errors'] == sum(e['after'] in CLEAR_ERRORS for e in comparable)
    assert value['before_errors']-value['after_errors'] == value['corrected_regions']-value['regressed_regions']
    assert len({e['chapter'] for e in value['entries']}) == value['chapters_sampled'] == 124
    assert value['current_engine'] == CURRENT and value['single_build_comparison']
    assert not value['population_accuracy_estimate'] and not value['all_chapter_words_visually_reviewed']
    return dict(**{k:v for k,v in value.items() if k not in ['entries','inputs']},
        adjudications_sha256=digest(path), provenance_path=str(path.relative_to(ROOT)).replace('\\','/'))


def checked_diagnostic_review(name):
    path=ROOT/'benchmarks/full-comics'/name
    value=read(path);sample_path=ROOT/value['sample_path']
    assert digest(sample_path)==value['sample_sha256']
    assert digest(sample_path.parent/'manual-decisions.json')==value['manual_decisions_sha256']
    assert not value['all_chapter_words_visually_reviewed'] and not value['app_uses_review_answers']
    return dict(**{k:v for k,v in value.items() if k!='entries'},adjudications_sha256=digest(path))


def expanded_semantic_comparison():
    path=ROOT/'benchmarks/full-comics/current8011-expanded-semantic-review.json'
    value=read(path)
    assert digest(ROOT/'benchmarks/full-comics/current8011-full-semantic-review.json')==value['original_uniform_review_sha256']
    assert digest(ROOT/'benchmarks/full-comics/corpus-semantic-review-short.json')==value['short_review_sha256']
    short=distributed_semantic_comparison('corpus-semantic-review-short.json')
    assert short['sample_sha256']==value['short_sample_sha256']
    valid=[e for e in value['entries'] if 'unresolved' not in [e['before'],e['after']]]
    assert value['before_errors']==sum(e['before'] in CLEAR_ERRORS for e in valid)
    assert value['after_errors']==sum(e['after'] in CLEAR_ERRORS for e in valid)
    assert value['before_errors']-value['after_errors']==value['corrected_regions']-value['regressed_regions']
    assert value['reviewed_regions']==len(value['entries'])==496
    assert value['comparable_regions']==len(valid)
    assert value['single_build_comparison'] and not value['population_accuracy_estimate']
    return dict(**{k:v for k,v in value.items() if k!='entries'},adjudications_sha256=digest(path))


def extended_semantic_comparison():
    path=ROOT/'benchmarks/full-comics/current8011-extended-semantic-review.json'
    value=read(path);previous=expanded_semantic_comparison()
    assert previous['adjudications_sha256']==value['original_expanded_review_sha256']
    additional_path=ROOT/'benchmarks/full-comics/corpus-semantic-review-next.json'
    assert digest(additional_path)==value['additional_review_sha256']
    additional=distributed_semantic_comparison(additional_path.name)
    assert additional['sample_sha256']==value['additional_sample_sha256']
    manual=read(additional_path)
    assert digest((ROOT/manual['sample_path']).parent/'manual-decisions.json')==manual['manual_decisions_sha256']
    valid=[e for e in value['entries'] if 'unresolved' not in [e['before'],e['after']]]
    assert value['before_errors']==sum(e['before'] in CLEAR_ERRORS for e in valid)
    assert value['after_errors']==sum(e['after'] in CLEAR_ERRORS for e in valid)
    assert value['before_errors']-value['after_errors']==value['corrected_regions']-value['regressed_regions']
    assert value['reviewed_regions']==len(value['entries'])==620
    assert value['comparable_regions']==len(valid)
    assert len({e['chapter'] for e in value['entries']})==124
    assert value['single_build_comparison'] and not value['population_accuracy_estimate']
    return dict(**{k:v for k,v in value.items() if k!='entries'},adjudications_sha256=digest(path))


def coverage_semantic_comparison():
    path=ROOT/'benchmarks/full-comics/coverage8014-fixed-ocr-semantic-review.json'
    value=read(path);previous=extended_semantic_comparison();folder=QA/'sentence-coverage8014'
    assert value['previous_review_sha256']==previous['adjudications_sha256']
    assert digest(folder/'output.jsonl')==value['native_output_sha256']
    assert digest(folder/'provenance.json')==value['native_provenance_sha256']
    assert digest(folder/'visual-review/sample.json')==value['visual_sample_sha256']
    assert digest(folder/'visual-review/manual-decisions.json')==value['manual_decisions_sha256']
    valid=[e for e in value['entries'] if not e['comparison_excluded'] and 'unresolved' not in (e['before'],e['after'])]
    assert value['before_errors']==previous['after_errors']==sum(e['before'] in CLEAR_ERRORS for e in valid)
    assert value['after_errors']==sum(e['after'] in CLEAR_ERRORS for e in valid)
    assert value['comparable_regions']==len(valid)==previous['comparable_regions']
    assert value['before_errors']-value['after_errors']==value['corrected_regions']-value['regressed_regions']
    assert value['changed_outputs_visually_reinspected']+value['identical_output_judgments_reused']==value['reviewed_regions']
    assert not value['translator_weights_changed'] and not value['population_accuracy_estimate']
    diagnostic_path=ROOT/'benchmarks/full-comics/coverage8014-omission-diagnostic-semantic-review.json'
    diagnostic=read(diagnostic_path)
    assert diagnostic['native_output_sha256']==value['native_output_sha256']
    assert digest(folder/'unaligned-review/sample.json')==diagnostic['new_sample_sha256']
    assert digest(folder/'unaligned-review/manual-decisions.json')==diagnostic['new_manual_sha256']
    assert digest(QA/'omission-review8011/sample.json')==diagnostic['previous_sample_sha256']
    assert digest(QA/'omission-review8011/manual-decisions.json')==diagnostic['previous_manual_sha256']
    assert diagnostic['before_errors']-diagnostic['after_errors']==diagnostic['corrected_regions']-diagnostic['regressed_regions']
    assert diagnostic['changed_candidates_only'] and not diagnostic['population_accuracy_estimate']
    return dict(**{k:v for k,v in value.items() if k!='entries'},adjudications_sha256=digest(path),
        selected_omission_diagnostic={k:v for k,v in diagnostic.items() if k!='entries'})


def six_region_semantic_comparison():
    path=ROOT/'benchmarks/full-comics/current8011-six-regions-semantic-review.json';value=read(path)
    previous=extended_semantic_comparison()
    assert value['original_extended_review_sha256']==previous['adjudications_sha256']
    additional=distributed_semantic_comparison('corpus-semantic-review-sixth.json')
    assert value['additional_review_sha256']==additional['adjudications_sha256']
    assert value['additional_sample_sha256']==additional['sample_sha256']
    valid=[e for e in value['entries'] if 'unresolved' not in (e['before'],e['after'])]
    assert len(value['entries'])==value['reviewed_regions']==744 and len(valid)==value['comparable_regions']
    assert value['before_errors']==sum(e['before'] in CLEAR_ERRORS for e in valid)
    assert value['after_errors']==sum(e['after'] in CLEAR_ERRORS for e in valid)
    assert value['before_errors']-value['after_errors']==value['corrected_regions']-value['regressed_regions']
    assert len({e['chapter'] for e in value['entries']})==124 and not value['population_accuracy_estimate']
    return dict(**{k:v for k,v in value.items() if k!='entries'},adjudications_sha256=digest(path))


def six_region_coverage_comparison():
    path=ROOT/'benchmarks/full-comics/coverage8014-six-regions-semantic-review.json';value=read(path)
    previous=six_region_semantic_comparison();original=coverage_semantic_comparison()
    assert value['previous_six_region_review_sha256']==previous['adjudications_sha256']
    assert value['original_fixed_review_sha256']==original['adjudications_sha256']
    folder=QA/'sentence-coverage8014/additional-sample'
    assert digest(folder/'summary.json')==value['additional_native_summary_sha256']
    assert digest(folder/'output.jsonl')==value['additional_native_output_sha256']
    proof=read(folder/'provenance.json')
    assert proof['pinned_native_provenance_sha256']==original['native_provenance_sha256']
    assert not proof['reference_used_for_inference'] and not proof['translator_weights_changed']
    assert proof['sample_sha256']==previous['additional_sample_sha256']
    valid=[e for e in value['entries'] if not e['comparison_excluded'] and 'unresolved' not in (e['before'],e['after'])]
    assert len(valid)==value['comparable_regions']==previous['comparable_regions']
    assert value['before_errors']==previous['after_errors']==sum(e['before'] in CLEAR_ERRORS for e in valid)
    assert value['after_errors']==sum(e['after'] in CLEAR_ERRORS for e in valid)
    assert value['before_errors']-value['after_errors']==value['corrected_regions']-value['regressed_regions']
    historical=value['historical_baseline_comparison']
    assert historical['before_errors']==previous['before_errors'] and historical['after_errors']==value['after_errors']
    assert historical['before_errors']-historical['after_errors']==historical['corrected_regions']-historical['regressed_regions']
    assert not value['population_accuracy_estimate'] and not value['all_chapter_words_visually_reviewed']
    return dict(**{k:v for k,v in value.items() if k!='entries'},adjudications_sha256=digest(path))


def full_recovery_checkpoint_comparison():
    path=ROOT/'benchmarks/full-comics/full8012-checkpoint01-semantic-review.json';value=read(path)
    sample_path=ROOT/value['sample_path'];sample=read(sample_path)
    assert digest(sample_path)==value['sample_sha256']
    assert digest(sample_path.parent/'manual-decisions.json')==value['manual_decisions_sha256']
    assert digest(ROOT/'benchmarks/full-comics/current8011-six-regions-semantic-review.json')==value['previous_review_sha256']
    for chapter,proof in sample['frozen_reports'].items():
        report=QA/value['current_cohort']/(chapter+'-en.jsonl')
        assert digest(report)==proof['report_sha256'] and digest(report.with_name(report.stem+'.done.json'))==proof['done_sha256']
    valid=[e for e in value['entries'] if not e['comparison_excluded'] and 'unresolved' not in (e['before'],e['after'])]
    assert len(valid)==value['comparable_regions'] and len(value['entries'])==value['reviewed_regions']
    assert value['before_errors']==sum(e['before'] in CLEAR_ERRORS for e in valid)
    assert value['after_errors']==sum(e['after'] in CLEAR_ERRORS for e in valid)
    assert value['before_errors']-value['after_errors']==value['corrected_regions']-value['regressed_regions']
    assert value['changed_outputs_visually_reinspected']+value['identical_output_judgments_reused']==value['reviewed_regions']
    assert value['partial_full_chapter_ocr_checkpoint'] and value['overlaps_with_main_sample_do_not_add_counts']
    assert not value['population_accuracy_estimate'] and not value['all_chapter_words_visually_reviewed']
    return dict(**{k:v for k,v in value.items() if k!='entries'},adjudications_sha256=digest(path))


def latest_windows_diagnostics():
    results={}
    for key,name in [('combined','combined-recovery8016-checkpoint01-semantic-review.json'),('omission_candidate','coverage8016-candidate-semantic-review.json'),('full_omission','full-omission8016-semantic-review.json')]:
        path=ROOT/'benchmarks/full-comics'/name;value=read(path)
        valid=[e for e in value['entries'] if not e.get('comparison_excluded',False) and 'unresolved' not in (e['before'],e['after'])]
        assert len(valid)==value['comparable_regions']
        assert value['before_errors']==sum(e['before'] in CLEAR_ERRORS for e in valid)
        assert value['after_errors']==sum(e['after'] in CLEAR_ERRORS for e in valid)
        assert value['before_errors']-value['after_errors']==value['corrected_regions']-value['regressed_regions']
        assert value['screen_attempt_failure_probability'] is None and not value['all_chapter_words_visually_reviewed']
        results[key]=dict(**{k:v for k,v in value.items() if k!='entries'},review_sha256=digest(path))
    policy_path=ROOT/'benchmarks/full-comics/screen-acceptance-policy.json';policy=read(policy_path)
    assert policy['measurement_unit']=='one_complete_screen_translation_attempt' and not policy['target_achieved']
    assert policy['current_screen_attempt_failure_probability'] is None
    results['screen_acceptance']=dict(**policy,policy_sha256=digest(policy_path))
    for key,name in [('ocr_readers','ocr8016-reader-comparison.json'),('ocr_consensus_development','ocr8016-consensus-conservative-candidate.json'),('ocr_consensus_heldout','ocr8016-consensus-heldout-review.json')]:
        path=ROOT/'benchmarks/full-comics'/name;value=read(path)
        assert value['screen_attempt_failure_probability'] is None and not value['application_modified']
        results[key]=dict(**{k:v for k,v in value.items() if k!='entries'},review_sha256=digest(path))
    expanded_path=ROOT/'benchmarks/full-comics/ocr8016-consensus-heldout-full-review.json'
    if expanded_path.exists():
        value=read(expanded_path)
        assert value['crops_visually_reviewed']==124 and value['additional_unchanged_crops_reviewed']==112
        assert value['screen_attempt_failure_probability'] is None and not value['application_modified']
        assert digest(ROOT/'benchmarks/full-comics/ocr8016-heldout-full-manual-transcriptions.json')==value['manual_sha256']
        for cohort in value['cohorts'].values():
            for name,model in cohort['models'].items():
                assert model['word_errors']==sum(row['models'][name]['word_errors'] for row in value['entries'] if cohort['crops']==124 or not row['edge_clipped'])
        results['ocr_consensus_heldout_full']=dict(**{k:v for k,v in value.items() if k!='entries'},review_sha256=digest(expanded_path))
    for key,name in [('windows_heldout','windows8016-heldout-semantic-review.json'),
                     ('geometry_trial','windows8017-geometry-semantic-review.json'),
                     ('geometry_final','windows8017-final-geometry-semantic-review.json'),
                     ('geometry_render','windows8017-render-geometry-semantic-review.json'),
                     ('windows8018_trial','windows8018-heldout-semantic-review.json'),
                     ('windows8019_trial','windows8019-heldout-semantic-review.json'),
                     ('windows8020_trial','windows8020-consensus-semantic-review.json')]:
        path=ROOT/'benchmarks/full-comics'/name
        if not path.exists():continue
        value=read(path)
        assert len(value['entries'])==value['reviewed_locations']==124
        for cohort_name,cohort in value['cohorts'].items():
            entries=[e for e in value['entries'] if cohort_name=='all_124_including_clipped_edges' or not e['edge_clipped']]
            assert len(entries)==cohort['locations']
            assert cohort['before_not_approved']==sum(e['before']!='acceptable' for e in entries)
            assert cohort['after_not_approved']==sum(e['after']!='acceptable' for e in entries)
            assert cohort['before_not_approved']-cohort['after_not_approved']==cohort['corrected']-cohort['regressed']
        assert value['screen_attempt_failure_probability'] is None and not value['all_chapter_words_visually_reviewed']
        results[key]=dict(**{k:v for k,v in value.items() if k!='entries'},review_sha256=digest(path))
    for key,name in [('ocr_coverage_heldout','ocr8017-coverage-heldout-review.json'),
                     ('short_clause_candidate','short-clause8017-candidate-semantic-review.json')]:
        path=ROOT/'benchmarks/full-comics'/name
        if not path.exists():continue
        value=read(path)
        assert value['screen_attempt_failure_probability'] is None and not value['population_accuracy_estimate']
        if key=='ocr_coverage_heldout':
            assert value['changed_locations_visually_reviewed']+value['unchanged_locations_without_meaning_approval']==value['locations_inferred']
            assert not value['application_modified']
        else:
            assert len(value['entries'])==value['reviewed_changed_locations']
            assert value['before_not_approved']-value['after_not_approved']==value['corrected']-value['regressed']
            assert not value['included_in_application']
        results[key]=dict(**{k:v for k,v in value.items() if k!='entries'},review_sha256=digest(path))
    checkpoint_path=ROOT/'benchmarks/full-comics/full8012-checkpoint02-semantic-review.json'
    if checkpoint_path.exists():
        value=read(checkpoint_path);m=value['metrics'];entries=[r for r in value['entries'] if not r['comparison_excluded']]
        assert len(entries)==m['comparable_regions'] and m['before_not_approved']-m['after_not_approved']==m['corrected']-m['regressed']
        assert value['newly_changed_pixel_locations_inspected']+value['prior_changed_pixel_judgments_reused']==value['changed_locations']
        assert not value['current_application_build'] and value['screen_attempt_failure_probability'] is None
        results['older_full_ocr_control']=dict(**{k:v for k,v in value.items() if k!='entries'},review_sha256=digest(checkpoint_path))
    for key,name in [('corpus_coverage8018','full-corpus-coverage8018-semantic-review.json'),
                     ('corpus_coverage8019','full-corpus-coverage8019-semantic-review.json'),
                     ('int8_trial8018','int8-translation8018-semantic-review.json')]:
        path=ROOT/'benchmarks/full-comics'/name
        if not path.exists():continue
        value=read(path);entries=value['entries']
        assert value['before_not_approved']==sum(r['before']!='acceptable' for r in entries)
        assert value['after_not_approved']==sum(r['after']!='acceptable' for r in entries)
        regressions=value.get('full_region_regressions',value.get('regressed'))
        assert value['before_not_approved']-value['after_not_approved']==value['fully_corrected']-regressions
        assert value['screen_attempt_failure_probability'] is None and not value['all_chapter_words_visually_reviewed']
        if key.startswith('corpus_coverage'):
            assert len(entries)==119 and value['source_locations_scanned']==18179
            assert not value['unchanged_regions_automatically_approved']
        else:
            assert len(entries)==124 and value['changed_locations_visually_reviewed']==52
            assert not value['quantization_variant_accepted_for_deployment']
        results[key]=dict(**{k:v for k,v in value.items() if k!='entries'},review_sha256=digest(path))
    third_path=ROOT/'benchmarks/full-comics/ocr8019-third-full-review.json'
    if third_path.exists():
        value=read(third_path)
        assert len(value['entries'])==value['crops_visually_reviewed']==124
        assert value['additional_unchanged_crops_reviewed']+value['prior_changed_pixel_transcriptions_reused']==124
        assert digest(QA/'ocr-apostrophes8019/remaining-third/manual-transcriptions.json')==value['manual_sha256']
        for name,metrics in value['metrics'].items():
            suffix='' if name=='legacy' else '_strict'
            assert metrics['after_word_errors']==sum(r['after'+suffix]['word_errors'] for r in value['entries'])
        assert not value['application_modified'] and value['screen_attempt_failure_probability'] is None
        results['ocr_third_full8019']=dict(**{k:v for k,v in value.items() if k!='entries'},review_sha256=digest(third_path))
    viewport_path=ROOT/'benchmarks/full-comics/windows8020-full-viewports-semantic-review.json'
    if viewport_path.exists():
        value=read(viewport_path)
        assert value['viewports']==len(value['entries'])==124 and value['native_regions']==228
        assert value['all_original_visible_dialogue_inventoried'] and value['all124_paired_meanings_reviewed']
        assert digest(ROOT/'benchmarks/full-comics/viewport8020-original-inventory.json')==value['inventory_sha256']
        assert digest(ROOT/'benchmarks/full-comics/viewport8020-meaning-decisions.json')==value['manual_sha256']
        for name,cohort in value['cohorts'].items():
            rows=[r for r in value['entries'] if name=='all124_fixed_reading_viewports' or not r['visible_dialogue_clipped']]
            assert len(rows)==cohort['viewports']
            assert cohort['before_not_approved']==sum(r['before']!='acceptable' for r in rows)
            assert cohort['after_not_approved']==sum(r['after']!='acceptable' for r in rows)
            assert cohort['corrected']==sum(r['before']!='acceptable' and r['after']=='acceptable' for r in rows)
            assert cohort['regressed']==sum(r['before']=='acceptable' and r['after']!='acceptable' for r in rows)
            assert cohort['before_not_approved']-cohort['after_not_approved']==cohort['corrected']-cohort['regressed']
        for name,sha in value['native_outputs'].items():
            assert digest(QA/('windows8020-full-viewports-'+name)/'output.jsonl')==sha
        assert value['screen_attempt_failure_probability'] is None and not value['ready_for_release']
        assert not value['complete_chapter_traversal'] and not value['all_chapter_words_visually_reviewed']
        results['windows8020_full_viewports']=dict(**{k:v for k,v in value.items() if k!='entries'},review_sha256=digest(viewport_path))
    full_agreement_path=ROOT/'benchmarks/full-comics/windows8021-full-viewports-semantic-review.json'
    if full_agreement_path.exists():
        value=read(full_agreement_path)
        assert len(value['entries'])==value['viewports']==124 and value['native_regions']==228
        assert value['changed_viewports_reinspected']+value['same_full_location_outputs_reused']==124
        assert digest(ROOT/'benchmarks/full-comics/viewport8021-meaning-decisions.json')==value['manual_sha256']
        assert digest(ROOT/'benchmarks/full-comics/windows8020-full-viewports-semantic-review.json')==value['previous_full_viewport_review_sha256']
        assert digest(QA/'windows8021-full-viewports-full-agreement/output.jsonl')==value['native_output_sha256']
        for name,cohort in value['cohorts'].items():
            rows=[r for r in value['entries'] if name=='all124_fixed_reading_viewports' or not r['visible_dialogue_clipped']]
            assert len(rows)==cohort['viewports']
            assert cohort['before_not_approved']==sum(r['before']!='acceptable' for r in rows)
            assert cohort['after_not_approved']==sum(r['after']!='acceptable' for r in rows)
            assert cohort['before_not_approved']-cohort['after_not_approved']==cohort['corrected']-cohort['regressed']
            historical=value['historical_baseline_comparison']['cohorts'][name]
            assert historical['before_not_approved']==sum(r['historical_baseline']!='acceptable' for r in rows)
            assert historical['before_not_approved']-historical['after_not_approved']==historical['corrected']-historical['regressed']
        assert not value['ready_for_release'] and value['screen_attempt_failure_probability'] is None
        assert not value['default_live_worker_enabled'] and not value['all_chapter_words_visually_reviewed']
        results['windows8021_full_viewports']=dict(**{k:v for k,v in value.items() if k!='entries'},review_sha256=digest(full_agreement_path))
    dialogue_ocr_path=ROOT/'benchmarks/full-comics/viewport8023-dialogue-ocr-review.json'
    if dialogue_ocr_path.exists():
        value=read(dialogue_ocr_path)
        assert value['viewports']==len(value['entries'])==124 and value['native_regions']==228
        assert value['dialogue_rows']==207 and value['excluded_non_dialogue_rows']==21
        assert digest(ROOT/'benchmarks/full-comics/viewport8020-original-inventory.json')==value['inventory_sha256']
        assert digest(ROOT/'benchmarks/full-comics/viewport8023-ocr-row-roles.json')==value['manual_row_roles_sha256']
        for variant,relative in [('baseline','windows8020-full-viewports-baseline'),('partial_consensus','windows8020-full-viewports-consensus'),('full_consensus','windows8021-full-viewports-full-agreement')]:
            assert digest(QA/relative/'output.jsonl')==value['native_outputs'][variant]
        for name,cohort in value['cohorts'].items():
            subset=[r for r in value['entries'] if name=='all124_fixed_reading_viewports' or not r['visible_dialogue_clipped']]
            for variant,m in cohort['variants'].items():
                assert len(subset)==m['viewports']
                assert m['expected_dialogue_words']==sum(r['variants'][variant]['expected_words'] for r in subset)
                assert m['word_errors']==sum(r['variants'][variant]['word_errors'] for r in subset)
                assert m['word_errors']==sum(m['alignment_edit_categories'].values())
        assert value['translation_meaning_not_measured_by_this_report']
        assert value['screen_attempt_failure_probability'] is None and not value['target_achieved']
        results['full_viewport_dialogue_ocr8023']=dict(**{k:v for k,v in value.items() if k!='entries'},review_sha256=digest(dialogue_ocr_path))
    local_trials=[]
    for suffix,folder_suffix in [('', ''),('-recommended','-recommended')]:
        prefix='local-llm8021'+suffix
        path=ROOT/f'benchmarks/full-comics/{prefix}-full-viewports-semantic-review.json'
        if not path.exists():continue
        value=read(path);folder=QA/('local-llm8021-full-viewports'+folder_suffix)
        assert value['viewports']==len(value['entries'])==124 and value['source_regions']==228
        assert digest(ROOT/f'benchmarks/full-comics/{prefix}-meaning-decisions.json')==value['manual_sha256']
        assert digest(folder/'output.jsonl')==value['output_sha256']
        assert digest(folder/'provenance.json')==value['provenance_sha256']
        assert value['all124_new_meanings_reviewed'] and value['native_ocr_sources_and_bounds_all_identical']
        for name,m in value['cohorts'].items():
            subset=[r for r in value['entries'] if name=='all124_fixed_reading_viewports' or not r['visible_dialogue_clipped']]
            assert len(subset)==m['viewports']
            assert sum(r['after']!='acceptable' for r in subset)==m['after_not_approved']
            assert sum(r['before']!='acceptable' for r in subset)==m['before_not_approved']
            assert m['before_not_approved']-m['after_not_approved']==m['corrected']-m['regressed']
        assert not value['provider_accepted_for_deployment'] and not value['application_modified']
        assert value['screen_attempt_failure_probability'] is None and not value['target_achieved']
        local_trials.append(dict(**{k:v for k,v in value.items() if k!='entries'},review_sha256=digest(path)))
    if local_trials:results['rejected_local_llm8021_trials']=local_trials
    search_path=ROOT/'benchmarks/full-comics/search8022-full-viewports-semantic-review.json'
    if search_path.exists():
        value=read(search_path);folder=QA/'translation-search8022'
        assert value['viewports']==len(value['entries'])==124 and value['regions']==228
        assert value['changed_viewports_reviewed']+value['identical_full_location_judgments_reused']==124
        assert digest(ROOT/'benchmarks/full-comics/search8022-meaning-decisions.json')==value['manual_sha256']
        assert digest(ROOT/'benchmarks/full-comics/windows8021-full-viewports-semantic-review.json')==value['previous_review_sha256']
        assert digest(folder/'output.jsonl')==value['output_sha256']
        for name,m in value['cohorts'].items():
            subset=[r for r in value['entries'] if name=='all124_fixed_reading_viewports' or not r['visible_dialogue_clipped']]
            assert len(subset)==m['viewports']
            assert sum(r['after']!='acceptable' for r in subset)==m['after_not_approved']
            assert sum(r['before']!='acceptable' for r in subset)==m['before_not_approved']
            assert m['before_not_approved']-m['after_not_approved']==m['corrected']-m['regressed']
            assert m['already_failed_views_partially_worsened']==sum(r['already_failed_view_with_partial_worsening'] for r in subset)
        assert not value['accepted_for_application'] and not value['application_modified']
        assert value['screen_attempt_failure_probability'] is None and not value['target_achieved']
        results['rejected_search8022']=dict(**{k:v for k,v in value.items() if k!='entries'},review_sha256=digest(search_path))
    for key,stem,folder_name,manual_name in [
        ('normalized_llm8023','normalized8023','local-llm8023-normalized','normalized8023'),
        ('specialist_hy8024','hy8024','hy8024-full-viewports','hy8024')]:
        path=ROOT/f'benchmarks/full-comics/{stem}-full-viewports-semantic-review.json'
        if not path.exists():continue
        value=read(path);folder=QA/folder_name
        assert value['viewports']==len(value['entries'])==124 and value['source_regions']==228
        assert digest(ROOT/f'benchmarks/full-comics/{manual_name}-meaning-decisions.json')==value['manual_sha256']
        assert digest(folder/'output.jsonl')==value['output_sha256']
        assert digest(folder/'provenance.json')==value['provenance_sha256']
        assert digest(ROOT/'benchmarks/full-comics/windows8021-full-viewports-semantic-review.json')==value['previous_native_review_sha256']
        assert value['all124_new_meanings_reviewed'] and value['native_ocr_sources_and_bounds_all_identical']
        for name,m in value['cohorts'].items():
            subset=[r for r in value['entries'] if name=='all124_fixed_reading_viewports' or not r['visible_dialogue_clipped']]
            assert len(subset)==m['viewports']
            assert sum(r['after']!='acceptable' for r in subset)==m['after_not_approved']
            assert sum(r['before']!='acceptable' for r in subset)==m['before_not_approved']
            assert m['before_not_approved']-m['after_not_approved']==m['corrected']-m['regressed']
        assert not value['provider_accepted_for_deployment'] and not value['application_modified']
        assert value['screen_attempt_failure_probability'] is None and not value['target_achieved']
        results[key]=dict(**{k:v for k,v in value.items() if k!='entries'},review_sha256=digest(path))
    short_path=ROOT/'benchmarks/full-comics/windows8024-short-full-viewports-semantic-review.json'
    if short_path.exists():
        value=read(short_path);folder=QA/'windows8024-short-full-viewports'
        assert value['viewports']==len(value['entries'])==len(value['ocr_entries'])==124
        assert digest(folder/'output.jsonl')==value['native_output_sha256']
        assert digest(folder/'provenance.json')==value['provenance_sha256']
        assert digest(folder/'summary.json')==value['native_summary_sha256']
        assert digest(ROOT/'benchmarks/full-comics/short8024-meaning-decisions.json')==value['manual_sha256']
        assert digest(ROOT/'benchmarks/full-comics/windows8021-full-viewports-semantic-review.json')==value['previous_native_review_sha256']
        assert digest(ROOT/'benchmarks/full-comics/viewport8020-original-inventory.json')==value['inventory_sha256']
        assert digest(ROOT/'benchmarks/full-comics/viewport8023-ocr-row-roles.json')==value['manual_row_roles_sha256']
        assert value['changed_viewports_reviewed']+value['identical_full_location_judgments_reused']==124
        for name,m in value['cohorts'].items():
            subset=[r for r in value['entries'] if name=='all124_fixed_reading_viewports' or not r['visible_dialogue_clipped']]
            assert len(subset)==m['viewports']
            assert sum(r['after']!='acceptable' for r in subset)==m['after_not_approved']
            assert sum(r['before']!='acceptable' for r in subset)==m['before_not_approved']
            assert m['before_not_approved']-m['after_not_approved']==m['corrected']-m['regressed']
            for label,scores in value['dialogue_ocr'][name].items():
                ocr=[r for r in value['ocr_entries'] if name=='all124_fixed_reading_viewports' or not r['visible_dialogue_clipped']]
                assert sum(r['variants'][label]['word_errors'] for r in ocr)==scores['word_errors']
                assert sum(r['variants'][label]['expected_words'] for r in ocr)==scores['expected_dialogue_words']
        assert not value['default_live_worker_enabled'] and not value['model_weights_trained']
        assert value['screen_attempt_failure_probability'] is None and not value['target_achieved']
        results['windows8024_short_full_viewports']=dict(**{k:v for k,v in value.items() if k not in ['entries','ocr_entries']},review_sha256=digest(short_path))
    default_path=ROOT/'benchmarks/full-comics/windows8024-default-full-viewports-semantic-review.json'
    if default_path.exists():
        value=read(default_path);folder=QA/'windows8024-short-default-full-viewports'
        assert value['viewports']==len(value['entries'])==124
        for filename,key in [('output.jsonl','native_output_sha256'),('provenance.json','provenance_sha256'),('summary.json','native_summary_sha256')]:
            assert digest(folder/filename)==value[key]
        assert digest(ROOT/'benchmarks/full-comics/short8024-default-meaning-decisions.json')==value['manual_sha256']
        assert digest(QA/'windows8020-full-viewports-baseline/output.jsonl')==value['baseline_output_sha256']
        assert digest(ROOT/'benchmarks/full-comics/windows8021-full-viewports-semantic-review.json')==value['original_baseline_review_sha256']
        assert value['default_short_recovery_enabled'] and not value['optional_consensus_readers_enabled']
        assert not value['explicit_short_override_supplied']
        assert value['changed_viewports_reviewed']+value['identical_full_location_judgments_reused']==124
        for name,m in value['cohorts'].items():
            subset=[r for r in value['entries'] if name=='all124_fixed_reading_viewports' or not r['visible_dialogue_clipped']]
            assert len(subset)==m['viewports']
            assert sum(r['after']!='acceptable' for r in subset)==m['after_not_approved']
            assert sum(r['before']!='acceptable' for r in subset)==m['before_not_approved']
            assert m['before_not_approved']-m['after_not_approved']==m['corrected']-m['regressed']
        assert value['screen_attempt_failure_probability'] is None and not value['target_achieved']
        results['windows8024_default_full_viewports']=dict(**{k:v for k,v in value.items() if k!='entries'},review_sha256=digest(default_path))
    packaged_path=ROOT/'benchmarks/full-comics/windows8025-packaged-full-viewports-semantic-review.json'
    if packaged_path.exists():
        value=read(packaged_path);folder=QA/'windows8025-packaged-full-viewports'
        assert value['viewports']==len(value['entries'])==124 and value['native_regions']==229
        for name,key in [('output.jsonl','native_output_sha256'),('provenance.json','native_provenance_sha256'),('summary.json','native_summary_sha256')]:
            assert digest(folder/name)==value[key]
        assert digest(ROOT/'benchmarks/full-comics/windows8024-short-full-viewports-semantic-review.json')==value['source_review_sha256']
        assert digest(ROOT/'benchmarks/full-comics/windows8024-default-full-viewports-semantic-review.json')==value['baseline_review_sha256']
        assert digest(QA/'frozen-windows802501/ocr-readers/manifest.json')==value['reader_manifest_sha256']
        assert digest(QA/'windows8025-packaged-runtime-checks.json')==value['runtime_checks_sha256']
        assert digest(QA/'windows-engine802501.json')==value['snapshot_sha256']
        snapshot=read(QA/'windows-engine802501.json')
        assert digest(QA/'frozen-windows802501/traductor.exe')==snapshot['binary_sha256']
        reader_root=QA/'frozen-windows802501/ocr-readers'
        for name,sha in read(reader_root/'manifest.json')['files'].items():assert digest(reader_root/name)==sha
        assert read(folder/'summary.json')['identical_to_reviewed_experiment_viewports']==list(range(1,125))
        assert value['all124_meaning_judgments_reused_only_for_identical_full_location_outputs']
        assert value['normal_worker_consensus_enabled'] and value['default_benchmark_consensus_enabled']
        assert value['no_explicit_reader_paths_or_activation_flag']
        for name,m in value['cohorts'].items():
            subset=[r for r in value['entries'] if name=='all124_fixed_reading_viewports' or not r['visible_dialogue_clipped']]
            assert len(subset)==m['viewports']
            assert sum(r['after']!='acceptable' for r in subset)==m['after_not_approved']
            assert sum(r['before']!='acceptable' for r in subset)==m['before_not_approved']
            assert m['before_not_approved']-m['after_not_approved']==m['corrected']-m['regressed']
        assert value['screen_attempt_failure_probability'] is None and not value['target_achieved']
        results['windows8025_packaged_full_viewports']=dict(**{k:v for k,v in value.items() if k!='entries'},review_sha256=digest(packaged_path))
    inflection_path=ROOT/'benchmarks/full-comics/windows8026-inflection-full-viewports-semantic-review.json'
    if inflection_path.exists():
        value=read(inflection_path);folder=QA/'windows8026-inflection-full-viewports'
        assert value['viewports']==len(value['entries'])==124 and value['native_regions']==229
        for name,key in [('output.jsonl','native_output_sha256'),('summary.json','native_summary_sha256'),('provenance.json','native_provenance_sha256')]:assert digest(folder/name)==value[key]
        assert digest(ROOT/'benchmarks/full-comics/windows8025-packaged-full-viewports-semantic-review.json')==value['previous_review_sha256']
        assert digest(QA/'windows8025-packaged-full-viewports/output.jsonl')==value['previous_native_output_sha256']
        assert digest(QA/'ocr-morph-consensus8026/summary.json')==value['selector_summary_sha256']
        assert digest(ROOT/'benchmarks/full-comics/morph8026-meaning-decisions.json')==value['manual_sha256']
        assert digest(QA/'ocr-morph-consensus8026/translation-output.jsonl')==value['isolated_translation_output_sha256']
        assert digest(ROOT/'benchmarks/full-comics/viewport8020-original-inventory.json')==value['original_visible_dialogue_inventory_sha256']
        assert digest(QA/'windows-engine802601.json')==value['snapshot_sha256']
        assert digest(QA/'windows8026-inflection-runtime-checks.json')==value['runtime_checks_sha256']
        snapshot=read(QA/'windows-engine802601.json');native=QA/'frozen-windows802601'
        assert digest(native/'traductor.exe')==snapshot['binary_sha256']
        assert digest(native/'ocr-readers/manifest.json')==snapshot['windows_reader_manifest_sha256']
        for name,sha in read(native/'ocr-readers/manifest.json')['files'].items():assert digest(native/'ocr-readers'/name)==sha
        assert read(folder/'summary.json')['identical_to_reviewed_experiment_viewports']==list(range(1,125))
        assert value['changed_full_location_meanings_reviewed']+value['identical_full_location_judgments_reused']==124
        assert value['normal_worker_inflection_support_enabled'] and value['all124_displayed_locations_match_the_reviewed_selection_and_translation_plan']
        assert value['native_guards']['success'] and all(not c['worsened'] for c in value['control_crop_cohorts'].values())
        for name,m in value['cohorts'].items():
            subset=[r for r in value['entries'] if name=='all124_fixed_reading_viewports' or not r['visible_dialogue_clipped']]
            assert len(subset)==m['viewports']
            assert sum(r['after']!='acceptable' for r in subset)==m['after_not_approved']
            assert sum(r['before']!='acceptable' for r in subset)==m['before_not_approved']
            assert m['before_not_approved']-m['after_not_approved']==m['corrected']-m['regressed']
        assert value['screen_attempt_failure_probability'] is None and not value['target_achieved']
        results['windows8026_inflection_full_viewports']=dict(**{k:v for k,v in value.items() if k!='entries'},review_sha256=digest(inflection_path))
    question_path=ROOT/'benchmarks/full-comics/windows8027-question-semantic-review.json'
    if question_path.exists():
        value=read(question_path);folder=QA/'windows8027-question-translation-replay'
        assert value['viewports']==len(value['entries'])==124 and value['native_regions']==229
        for name,key in [('native-output.jsonl','native_output_sha256'),('output.jsonl','combined_output_sha256'),('provenance.json','native_provenance_sha256'),('summary.json','native_summary_sha256')]:assert digest(folder/name)==value[key]
        for path,key in [(ROOT/'benchmarks/full-comics/windows8026-inflection-full-viewports-semantic-review.json','previous_review_sha256'),
                         (QA/'windows8026-inflection-full-viewports/output.jsonl','previous_native_output_sha256'),
                         (QA/'windows-engine802701.json','snapshot_sha256'),(QA/'windows8027-question-runtime-checks.json','runtime_checks_sha256'),
                         (QA/'translation-punctuation8027/core-equivalence.json','core_equivalence_sha256'),
                         (QA/'translation-punctuation8027/summary.json','rule_evaluation_sha256'),
                         (ROOT/'benchmarks/full-comics/question8027-meaning-decisions.json','manual_decisions_sha256')]:assert digest(path)==value[key]
        snapshot=read(QA/'windows-engine802701.json');native=QA/'frozen-windows802701'
        assert digest(native/'traductor.exe')==snapshot['binary_sha256']
        assert digest(native/'data/flutter_assets/assets/models/opus-en-es/manifest.json')==snapshot['manifest_sha256']
        assert read(folder/'summary.json')['all229_actual_model_outputs_match_pure_rule_prediction']
        assert value['fresh_translation_inference'] and not value['new_ocr_inference'] and not value['fresh_screen_capture']
        assert value['changed_complete_location_meanings_reviewed']+value['identical_complete_location_judgments_reused']==124
        assert value['normal_live_worker_uses_same_final_rule'] and value['decoder_core_and_model_weights_unchanged']
        old=records(QA/'windows8026-inflection-full-viewports/output.jsonl');fresh=records(folder/'native-output.jsonl')
        assert len(old)==len(fresh)==229
        assert all((a['source'],a['image'],a['bounds'])==(b['source'],b['image'],b['bounds']) for a,b in zip(old,fresh))
        for name,m in value['cohorts'].items():
            subset=[r for r in value['entries'] if name=='all124_fixed_reading_viewports' or not r['visible_dialogue_clipped']]
            assert len(subset)==m['viewports']
            assert sum(r['before']!='acceptable' for r in subset)==m['before_not_approved']
            assert sum(r['after']!='acceptable' for r in subset)==m['after_not_approved']
            assert m['before_not_approved']-m['after_not_approved']==m['corrected']-m['regressed']
        assert value['screen_attempt_failure_probability'] is None and not value['target_achieved']
        results['windows8027_question_full_viewports']=dict(**{k:v for k,v in value.items() if k!='entries'},review_sha256=digest(question_path))
    from opening8028_quality import diagnostic as opening_diagnostic
    opening=opening_diagnostic()
    if opening:results['windows8028_opening_full_viewports']=opening
    from refinement8029_quality import diagnostic as refinement_diagnostic
    refinement=refinement_diagnostic()
    if refinement:results['windows8029_refinement_full_viewports']=refinement
    from tail8030_quality import diagnostic as tail_diagnostic
    tail=tail_diagnostic()
    if tail:results['windows8030_tail_translation_replay']=tail
    release_path=QA/('release8017.json' if (QA/'release8017.json').exists() else 'release8016.json')
    if release_path.exists():results['windows_release']=dict(**read(release_path),release_report_sha256=digest(release_path))
    return results


def current_windows_review_html(diagnostic):
    pieces=[]
    tail=diagnostic.get('windows8030_tail_translation_replay')
    if tail:
        from tail8030_quality import review_html as tail_html
        pieces.append(tail_html(tail))
    refinement=diagnostic.get('windows8029_refinement_full_viewports')
    if refinement:
        from refinement8029_quality import review_html as refinement_html
        pieces.append(refinement_html(refinement))
        if tail:pieces[-1]=pieces[-1].replace('Windows actual · reconocimiento y preguntas breves','Control anterior · reconocimiento y preguntas breves')
    opening=diagnostic.get('windows8028_opening_full_viewports')
    if opening:
        from opening8028_quality import review_html
        pieces.append(review_html(opening))
        if refinement:pieces[-1]=pieces[-1].replace('Windows actual · recuperación de aperturas omitidas','Control anterior · recuperación de aperturas omitidas')
    question=diagnostic.get('windows8027_question_full_viewports')
    if question:
        m=question['cohorts']['all124_fixed_reading_viewports'];h=question['historical_baseline_comparison']['cohorts']['all124_fixed_reading_viewports']
        pieces.append(f'<h2>Windows actual · conservación de preguntas</h2><p>En las mismas 124 vistas con OCR conservado: <b>{m["before_not_approved"]} → {m["after_not_approved"]} traducciones sin aprobar</b>, {m["corrected"]} corrección completa de significado y {m["regressed"]} regresiones nuevas. Reducción relativa de esta actualización: {m["relative_unapproved_reduction_percent"]:.2f} %. Frente al control inicial de esta muestra: {h["before_not_approved"]} → {h["after_not_approved"]}, reducción relativa del {h["relative_unapproved_reduction_percent"]:.2f} %.</p><p>El ejecutable nuevo volvió a traducir las 229 regiones a partir de las fuentes OCR verificadas; no se repitió el reconocimiento. Se cotejó la ubicación modificada y solo se reutilizaron los otros 123 dictámenes por identidad del texto y coordenadas. La regla final conserva todas las palabras y protege preguntas indirectas y texto citado. Pasaron 20 guardas y se examinaron 18.179 salidas de un recorrido histórico completo, con lotes solapados registrados por separado.</p><p>El OCR mantiene 45 discrepancias sobre 2.265 palabras. La revisión de todas las palabras de los capítulos y de usos completos sigue pendiente; no se acredita menos del 5 % de fallos. Se observaron pequeños trazos originales en el render, como defecto visual separado. <a href="../windows8027-question-translation-replay/index.html">Comparaciones y alcance</a>.</p>')
    if opening and question:pieces[-1]=pieces[-1].replace('Windows actual · conservación de preguntas','Control anterior · conservación de preguntas')
    inflection=diagnostic.get('windows8026_inflection_full_viewports')
    if inflection:
        m=inflection['cohorts']['all124_fixed_reading_viewports'];h=inflection['historical_baseline_comparison']['cohorts']['all124_fixed_reading_viewports']
        word=inflection['dialogue_ocr']['all124_fixed_reading_viewports']
        pieces.append(f'<h2>Control anterior · palabras corroboradas por dos lectores</h2><p>En las mismas 124 capturas: <b>{m["before_not_approved"]} → {m["after_not_approved"]} vistas sin aprobar</b>, {m["corrected"]} correcciones completas y {m["regressed"]} regresiones nuevas. Reducción relativa de esta actualización: {m["relative_unapproved_reduction_percent"]:.2f} %. Acumulado frente al control inicial de esta muestra: {h["before_not_approved"]} → {h["after_not_approved"]}, reducción relativa del {h["relative_unapproved_reduction_percent"]:.2f} %.</p><p>Se revisaron las dos ubicaciones completas modificadas y solo se reutilizaron los otros 122 dictámenes tras comprobar identidad de texto, traducción y coordenadas. Hay dos mejoras parciales de contenido, pero ambas vistas conservan defectos y siguen sin aprobar. La corrección exige que dos lectores coincidan en la palabra visible, una diferencia de una letra y una raíz ya conocida; conserva las protecciones de números y negación. No empeoró ninguno de los 372 recortes de control. OCR: {word["before"]["word_errors"]} → {word["after"]["word_errors"]} discrepancias sobre las mismas {word["after"]["expected_dialogue_words"]} palabras esperadas.</p><p>Son capturas guardadas, una por capítulo. No se han revisado todas las palabras de los capítulos ni se ha medido menos del 5 % de fallos por uso completo. No se entrenaron ni descargaron pesos nuevos. <a href="../windows8026-inflection-full-viewports/index.html">Comparaciones y alcance</a>.</p>')
    packaged=diagnostic.get('windows8025_packaged_full_viewports')
    if packaged:
        m=packaged['cohorts']['all124_fixed_reading_viewports'];h=packaged['historical_baseline_comparison']['cohorts']['all124_fixed_reading_viewports']
        title='Control anterior · lectores integrados en la app' if inflection else 'Windows actual · lectores integrados en la app'
        pieces.append(f'<h2>{title}</h2><p>La configuración normal pasa de <b>{m["before_not_approved"]} → {m["after_not_approved"]} vistas sin aprobar</b>, con {m["corrected"]} correcciones completas y {m["regressed"]} regresiones nuevas en las mismas 124 capturas. El acumulado frente al control inicial de esta muestra es {h["before_not_approved"]} → {h["after_not_approved"]}, reducción relativa del {h["relative_unapproved_reduction_percent"]:.2f} %.</p><p>Las 229 regiones reales reproducen todas las salidas y coordenadas del experimento ya cotejado; se reutilizan sus dictámenes solo por identidad de cada ubicación completa. Los lectores vienen incluidos en Windows y la prueba no proporciona rutas ni activación especial. Los pesos son preentrenados y no se entrenó un modelo nuevo. Persisten errores y omisiones: no se revisó cada palabra de todos los capítulos ni se acredita menos del 5 % de fallos por uso completo. <a href="../windows8024-short-full-viewports/index.html">Comparaciones reutilizadas</a>.</p><p>Los apartados siguientes conservan los controles anteriores de esta muestra.</p>')
    normal=diagnostic.get('windows8024_default_full_viewports')
    if normal:
        m=normal['cohorts']['all124_fixed_reading_viewports']
        pieces.append(f'<h2>Control anterior de Windows · recuperación corta</h2><p>En las mismas 124 vistas guardadas, frente al control normal anterior: <b>{m["before_not_approved"]} → {m["after_not_approved"]} sin aprobar</b>, {m["corrected"]} correcciones completas y {m["regressed"]} regresiones nuevas. Este control usa solamente la recuperación corta y sirve como referencia de la integración nueva.</p><p>Esta comparación conserva las {normal["identical_full_location_judgments_reused"]} salidas completas idénticas y coteja todo cambio. No mide captura en vivo, movimiento ni probabilidad de fallo por uso completo. La revisión de todas las palabras de los capítulos sigue pendiente.</p>')
    short=diagnostic.get('windows8024_short_full_viewports')
    if short:
        m=short['cohorts']['all124_fixed_reading_viewports'];base=short['historical_baseline_comparison']['cohorts']['all124_fixed_reading_viewports']
        word=short['dialogue_ocr']['all124_fixed_reading_viewports']
        deployment='La integración actual reproduce este ensayo con lectores incluidos en Windows.' if packaged else 'La recuperación corta ya se comprobó en la configuración normal; los lectores adicionales siguen limitados al ensayo.' if normal else 'El cambio sigue fuera del uso normal.'
        pieces.append(f'<h2>Recuperación conservadora con lectores adicionales · Windows en prueba</h2><p>En las mismas 124 vistas: <b>{m["before_not_approved"]} → {m["after_not_approved"]} sin aprobar</b>, {m["corrected"]} correcciones completas y {m["regressed"]} regresiones nuevas. Frente al control anterior a ambas mejoras de lectura: {base["before_not_approved"]} → {base["after_not_approved"]}, reducción relativa del {base["relative_unapproved_reduction_percent"]:.2f} %. Se cotejaron las {short["changed_viewports_reviewed"]} vistas con cambios y se conservaron {short["identical_full_location_judgments_reused"]} dictámenes solo por identidad de todas las salidas mostradas en la misma ubicación.</p><p>Se exige acuerdo de dos lectores en dos recortes sobre una detección independiente, con confianza alta, sin tocar bloques existentes. OCR de diálogo: {word["before"]["word_errors"]} → {word["after"]["word_errors"]} errores sobre las mismas {word["after"]["expected_dialogue_words"]} palabras. Es una métrica de reconocimiento; no acredita significado correcto ni el objetivo del 5 % de fallos por uso completo. {deployment} <a href="../windows8024-short-full-viewports/index.html">Comparación y alcance</a>.</p>')
    full_agreement=diagnostic.get('windows8021_full_viewports')
    if full_agreement:
        m=full_agreement['cohorts']['all124_fixed_reading_viewports'];base=full_agreement['historical_baseline_comparison']['cohorts']['all124_fixed_reading_viewports']
        pieces.append(f'<h2>Corrección de lectura completa · ensayo integrado de Windows</h2><p>En las mismas 124 vistas guardadas: <b>{m["before_not_approved"]} → {m["after_not_approved"]} sin aprobar</b>, {m["corrected"]} correcciones completas y {m["regressed"]} regresiones nuevas observadas. Frente al control anterior a ambos ensayos: <b>{base["before_not_approved"]} → {base["after_not_approved"]}</b>, reducción relativa del {base["relative_unapproved_reduction_percent"]:.2f} %, {base["corrected"]} correcciones completas y {base["regressed"]} regresiones restantes. La regresión del ensayo previo quedó corregida. Se cotejaron los diez cambios y solo se reutilizaron los dictámenes de las 114 vistas con todas sus salidas idénticas.</p><p>Se conservan los 228 bloques originales antes del consenso y la política aislada coincide con todas las fuentes producidas por el ejecutable real. Persisten omisiones y errores de significado. La variante sigue fuera del uso normal y no acredita menos del 5 % de fallos por uso completo. <a href="../windows8021-full-viewports-full-agreement/index.html">Resultados y alcance</a>.</p>')
    dialogue_ocr=diagnostic.get('full_viewport_dialogue_ocr8023')
    if dialogue_ocr:
        all_views=dialogue_ocr['cohorts']['all124_fixed_reading_viewports'];before=all_views['variants']['baseline'];after=all_views['variants']['full_consensus']
        pieces.append(f'<h2>Reconocimiento del diálogo · componente OCR</h2><p>Sobre {after["expected_dialogue_words"]} palabras inventariadas en las mismas 124 vistas: <b>{before["word_errors"]} → {after["word_errors"]} errores de palabra</b>, del {before["word_error_rate_percent"]:.2f} % al {after["word_error_rate_percent"]:.2f} %. Las vistas con discrepancias de reconocimiento pasan de {before["viewports_with_word_errors"]} a {after["viewports_with_word_errors"]}. Se excluyeron manualmente 21 bloques de marcas de agua, detecciones sin diálogo y onomatopeyas exentas; los textos omitidos por el detector siguen en el inventario esperado. Los apóstrofos internos se conservan.</p><p>Este porcentaje mide palabras reconocidas, no usos completos correctos ni significado de la traducción. Las eliminaciones de la alineación también incluyen defectos de separación de palabras. El objetivo de menos del 5 % de fallos de uso sigue sin acreditarse.</p>')
    local_trials=diagnostic.get('rejected_local_llm8021_trials',[])
    if local_trials:
        metrics=[r['cohorts']['all124_fixed_reading_viewports'] for r in local_trials]
        results='; '.join(f'{m["before_not_approved"]} → {m["after_not_approved"]} sin aprobar, {m["corrected"]} correcciones y {m["regressed"]} regresiones' for m in metrics)
        pieces.append('<h2>Modelo local alternativo · configuraciones descartadas</h2><p>'+results+'. Se cotejaron las 124 vistas y 228 fuentes OCR idénticas en cada ensayo, sin enviar respuestas humanas a la inferencia. Se conservan ambos resultados: ninguna configuración sustituyó al modelo de la app. La revisión mide contenido de vistas guardadas, con defectos de español adicionales; no certifica usos completos ni todas las palabras de los capítulos.</p>')
    normalized=diagnostic.get('normalized_llm8023')
    if normalized:
        m=normalized['cohorts']['all124_fixed_reading_viewports']
        pieces.append(f'<h2>Control con entrada normalizada · modelo alternativo descartado</h2><p>Se prepararon las mismas fuentes con la función nativa de la app: únicamente cambian mayúsculas y minúsculas. Se revisaron las 124 vistas y 228 bloques. Resultado: <b>{m["before_not_approved"]} → {m["after_not_approved"]} sin aprobar</b>, {m["corrected"]} correcciones completas y {m["regressed"]} regresiones completas. El modelo, el prompt y el muestreo del ensayo alternativo anterior permanecieron iguales. La normalización mejora ese ensayo, pero sigue empeorando el resultado frente al modelo actual y no se incorporó.</p>')
    specialist=diagnostic.get('specialist_hy8024')
    if specialist:
        m=specialist['cohorts']['all124_fixed_reading_viewports']
        pieces.append(f'<h2>Traductor local especializado · evaluación aislada</h2><p>Las mismas 124 vistas y 228 bloques OCR: <b>{m["before_not_approved"]} → {m["after_not_approved"]} sin aprobar</b>, {m["corrected"]} correcciones completas y {m["regressed"]} regresiones completas. Se cotejó todo el diálogo visible de las vistas guardadas; no todas las palabras de los capítulos. El ensayo no modifica la app, no certifica la captura, la superposición ni el movimiento y no acredita menos del 5 % de fallos por uso. El modelo tiene una licencia con restricciones y no se está distribuyendo.</p>')
    search=diagnostic.get('rejected_search8022')
    if search:
        m=search['cohorts']['all124_fixed_reading_viewports']
        pieces.append(f'<h2>Otra estrategia de búsqueda · ensayo descartado</h2><p>Se procesaron las mismas 124 vistas y 228 regiones con 215 inferencias nuevas de fuente única, conservando modelos y reconocimiento. Se cotejaron las {search["changed_viewports_reviewed"]} vistas cambiadas; las {search["identical_full_location_judgments_reused"]} salidas completas idénticas conservan su dictamen. Resultado: <b>{m["before_not_approved"]} → {m["after_not_approved"]} sin aprobar</b>, {m["corrected"]} correcciones completas, {m["regressed"]} regresiones completas y {m["already_failed_views_partially_worsened"]} empeoramientos parciales en vistas que ya fallaban. No se incorporó a la app ni modifica la mejora de la variante evaluada anterior.</p>')
    viewports=diagnostic.get('windows8020_full_viewports')
    if viewports:
        m=viewports['cohorts']['all124_fixed_reading_viewports'];uncut=viewports['cohorts']['no_visible_dialogue_clipped']
        pieces.append(f'<h2>124 vistas de lectura completas · significado revisado</h2><p><b>{m["before_not_approved"]} → {m["after_not_approved"]} vistas sin aprobar</b>, {m["corrected"]} correcciones completas y {m["regressed"]} regresión; reducción relativa del {m["relative_unapproved_reduction_percent"]:.2f} % en este mismo lote. Se inventarió todo el diálogo visible y se cotejaron todos los resultados, incluidos los que no cambiaron. En las {uncut["viewports"]} vistas sin diálogo cortado: {uncut["before_not_approved"]} → {uncut["after_not_approved"]} sin aprobar. Las onomatopeyas pueden permanecer sin traducir.</p><p>La revisión de significado está completa para estas vistas guardadas, una por capítulo. La revisión visual de toda la superposición sigue pendiente. <b>No equivale a revisar cada palabra de los capítulos ni a medir usos completos de la app.</b> La variante permanece desactivada en el uso normal; el objetivo inferior al 5 % no está acreditado. <a href="../windows8020-full-viewports-review/index.html">Originales, inventario y resultados completos</a>.</p>')
    integrated=diagnostic.get('windows8020_trial')
    if integrated:
        m=integrated['cohorts']['all_124_including_clipped_edges']
        pieces.append(f'<h2>Control anterior · 124 recortes de diálogo</h2><p>En los mismos 124 recortes: <b>{m["before_not_approved"]} → {m["after_not_approved"]} traducciones sin aprobar</b>, {m["corrected"]} correcciones completas y {m["regressed"]} regresiones observadas; reducción relativa del {m["relative_unapproved_reduction_percent"]:.2f} %. Se cotejaron los siete cambios; 117 salidas idénticas conservaron su dictamen de la misma ubicación. La compilación real mantuvo las 137 fuentes y geometrías antes de aplicar el consenso. El reconocimiento pasa de34 a27 errores de palabra, pero mantiene siete omisiones.</p><p>Este control sobre recortes tiene un alcance menor que las vistas completas mostradas arriba. Los lectores adicionales se activaron solo con configuración explícita del ensayo nativo; la barra normal todavía no los utiliza. <a href="../windows8020-consensus-heldout-pixels/visual-review/index.html">Cotejo de los cambios de integración</a>.</p>')
    broad=diagnostic.get('corpus_coverage8019')
    trial_broad=diagnostic.get('corpus_coverage8018')
    if broad:
        pieces.append(f'<h2>Validación amplia de recuperación · Windows en desarrollo</h2><p>Se recorrieron las 18.179 regiones del control OCR de 124 capítulos y se cotejaron visualmente los 119 cambios del ensayo inicial. Con las protecciones verificadas mediante {broad["fresh_native_validation_sources"]} inferencias nuevas: <b>{broad["before_not_approved"]} → {broad["after_not_approved"]} sin aprobar</b>, {broad["fully_corrected"]} correcciones completas y {broad["full_region_regressions"]} regresiones completas observadas. Reducción relativa del {broad["relative_unapproved_reduction_percent"]:.1f} % en esos cambios. El empeoramiento parcial del ensayo anterior también se rechazó. <a href="../full-corpus-coverage8019/index.html">Evidencia y alcance</a>.</p><p>Este control usa el mismo OCR anterior en ambas variantes. Las regiones sin cambios no quedan aprobadas por ello; no se ha terminado de revisar cada palabra de los capítulos. <b>La probabilidad de fallo por pantalla sigue sin establecerse y el objetivo inferior al 5 % no está acreditado.</b> La nueva compilación continúa en validación.</p>')
    elif trial_broad:
        pieces.append(f'<h2>Ensayo amplio · protección en corrección</h2><p>En el recorrido de 18.179 regiones de 124 capítulos se cotejaron los 119 cambios: <b>{trial_broad["before_not_approved"]} → {trial_broad["after_not_approved"]} sin aprobar</b>, {trial_broad["fully_corrected"]} correcciones completas, {trial_broad["full_region_regressions"]} regresión completa y un empeoramiento parcial en una región ya fallida. Este ensayo se conserva y no se publica como versión lista; se están verificando protecciones adicionales. <a href="../full-corpus-coverage8018/visual-review-compact/index.html">Originales y resultados del ensayo</a>.</p>')
    quant=diagnostic.get('int8_trial8018')
    if quant:
        pieces.append(f'<p><b>Variante de mayor precisión numérica descartada:</b> {quant["before_not_approved"]} → {quant["after_not_approved"]} sin aprobar en las mismas 124 ubicaciones; {quant["fully_corrected"]} correcciones y {quant["regressed"]} regresiones. Se cotejaron los 52 cambios y se rectificaron dos dictámenes por errores presentes en ambas variantes. No se cambiaron los modelos instalados. <a href="../int8-translation8018/visual-review/index.html">Cotejo de precisión numérica</a>.</p>')
    current=diagnostic.get('windows8019_trial')
    if current:
        m=current['cohorts']['all_124_including_clipped_edges']
        pieces.append(f'<p><b>Prueba real de Windows8019 sobre los mismos 124 recortes:</b> {m["before_not_approved"]} → {m["after_not_approved"]} sin aprobar, {m["corrected"]} correcciones completas y {m["regressed"]} regresiones completas observadas, con dos dictámenes corregidos aplicados a ambas variantes. Se conservaron exactamente las 137 regiones y su reconocimiento, incluidos 34 errores de palabra y siete omisiones. La app completó el lote sin errores de ejecución y superó 37 pruebas de geometría y las de superposición, barra y cancelación. Sigue en validación. <a href="../windows8019-heldout-pixels/index.html">Cotejo y alcance</a> · <a href="../windows8019-heldout-pixels/paint/index.html">Superposición real</a>.</p>')
    ocr_full=diagnostic.get('ocr_third_full8019')
    if ocr_full:
        m=ocr_full['metrics']['strict_apostrophes']
        pieces.append(f'<p><b>Otro lote OCR completo · 124 recortes y {ocr_full["words"]} palabras:</b> se revisaron las 108 lecturas sin cambios que faltaban. El candidato pasa de {m["before_word_errors"]} a {m["after_word_errors"]} errores de palabra y de {m["before_crops_with_word_errors"]} a {m["after_crops_with_word_errors"]} recortes con errores; {m["fully_corrected"]} correcciones completas y {m["regressed"]} regresiones. Conserva cinco omisiones. Incluye un control sin diálogo. La regla protege los apóstrofos y continúa aislada de la app; este inventario no aprueba traducciones españolas ni pantallas completas. <a href="../ocr-apostrophes8019/remaining-third/index.html">Inventario de las lecturas pendientes</a>.</p>')
    pieces.append('<details><summary>Ensayos y versiones anteriores conservados</summary>')
    native=diagnostic.get('windows_heldout')
    if native:
        m=native['cohorts']['all_124_including_clipped_edges']
        pieces.append(f'<h2>Cotejo nuevo de la app real · 124 ubicaciones</h2><p>Se revisaron las 124 salidas de Windows con los píxeles originales y Olympus, incluidas las que no cambiaron. Con el mismo criterio estricto, Windows8015 dejó <b>{m["before_not_approved"]}</b> traducciones sin aprobar y Windows8016 <b>{m["after_not_approved"]}</b>. El lote contiene 1.483 palabras visibles y una ubicación por capítulo. El motor real completó los 124 recortes sin errores de ejecución. Cuatro tienen texto cortado en un borde; se separan también las otras 120 ubicaciones. <a href="../windows8016-heldout-pixels/visual-review/index.html">Ver el cotejo completo del lote</a>.</p>')
    geometry=diagnostic.get('geometry_render') or diagnostic.get('geometry_final') or diagnostic.get('geometry_trial')
    if geometry:
        m=geometry['cohorts']['all_124_including_clipped_edges']
        folder='windows8017-render-heldout-pixels' if 'geometry_render' in diagnostic else 'windows8017-final-heldout-pixels' if 'geometry_final' in diagnostic else 'windows8017-preserve-heldout-pixels'
        pieces.append(f'<p><b>Unión de renglones en Windows8017: {m["before_not_approved"]} → {m["after_not_approved"]} traducciones sin aprobar</b>, {m["corrected"]} correcciones completas y {m["regressed"]} regresiones observadas. Reducción relativa de {m["relative_unapproved_reduction_percent"]:.1f} % sobre este mismo lote. Quedan {m["after_clear_errors"]} errores claros y {m["after_categories"].get("needs_improvement",0)} casos que requieren mejora. La lectura OCR permanece idéntica en las 124 ubicaciones. Los pesos no cambiaron; la corrección une renglones antes de traducir y conserva las palabras ya reconocidas. <a href="../{folder}/visual-review/index.html">Ver el cotejo</a> · <a href="../{folder}/paint/index.html">Superposición del motor real</a>.</p>')
        if (QA/'release8017.json').exists():pieces.append('<p><a href="../../releases/Luma-Windows-1.0.0+8017.zip">Descargar Windows8017 de prueba</a>.</p>')
    trial=diagnostic.get('windows8018_trial')
    if trial:
        m=trial['cohorts']['all_124_including_clipped_edges']
        pieces.append(f'<p><b>Windows8018 en validación · recuperación de frases cortas incorporada:</b> <b>{m["before_not_approved"]} → {m["after_not_approved"]} sin aprobar</b> en las mismas 124 ubicaciones, {m["corrected"]} correcciones completas y {m["regressed"]} regresiones observadas. El reconocimiento y las regiones permanecen idénticos. Quedan {m["after_clear_errors"]} errores claros y {m["after_categories"].get("needs_improvement",0)} casos que requieren mejora. Dos cambios recuperan una parte pero todavía no se aprueban. Continúa la comprobación sobre todas las fuentes guardadas de los 124 capítulos; este ensayo no acredita menos del 5 % de usos fallidos ni está publicado como versión lista. <a href="../windows8018-heldout-pixels/visual-review/index.html">Cotejo del lote</a> · <a href="../windows8018-heldout-pixels/paint/index.html">Dibujo de la app</a>.</p>')
    short=diagnostic.get('short_clause_candidate')
    if short:
        pieces.append(f'<p><b>Candidato adicional sin incorporar:</b> la recuperación de frases cortas cambió {short["reviewed_changed_locations"]} salidas y todas se cotejaron: <b>{short["before_not_approved"]} → {short["after_not_approved"]} sin aprobar</b>, {short["corrected"]} correcciones completas y {short["regressed"]} regresiones observadas. Se conservó el intento descartado por repeticiones y se añadieron guardas. Cinco casos siguen pendientes; requiere validación adicional antes de entrar en la app. <a href="../short-clause8017-guarded/visual-review/index.html">Ver las salidas modificadas</a>.</p>')
    third=diagnostic.get('ocr_coverage_heldout')
    if third:
        pieces.append(f'<p><b>Otro ensayo OCR independiente:</b> 124 ubicaciones excluidas de las 868 anteriores se procesaron con la regla congelada. Se cotejaron los {third["changed_locations_visually_reviewed"]} cambios: <b>{third["before_word_errors"]} → {third["after_word_errors"]} errores de palabra</b>, {third["changed_crops_fixed"]} recortes corregidos por completo y {third["changed_crops_regressed"]} regresiones. Dos conservan errores y las {third["unchanged_locations_without_meaning_approval"]} lecturas sin cambios siguen pendientes de inspección. Esta combinación todavía no está incorporada a la app. <a href="../ocr-coverage8017-holdout/coverage/index.html">Ver el cotejo independiente de cambios</a>.</p>')
    control=diagnostic.get('older_full_ocr_control')
    if control:
        m=control['metrics']
        pieces.append(f'<details><summary>Control anterior de OCR · cierre de las ubicaciones distribuidas</summary><p>En 744 ubicaciones de los 124 capítulos se cerraron las 51 inspecciones que faltaban: 48 cambios reutilizan cotejos anteriores y 645 salidas son idénticas. Sobre {m["comparable_regions"]} comparaciones válidas: <b>{m["before_not_approved"]} → {m["after_not_approved"]} sin aprobar</b>, {m["corrected"]} correcciones completas y {m["regressed"]} regresión observada. Se rectificó explícitamente un dictamen anterior de la misma frase incorrecta. Este es un control congelado anterior, no Windows8018, y se solapa con otros lotes: los recuentos no se suman. <a href="../full8012-review-checkpoint02/followup/index.html">Cotejo de las 51 ubicaciones nuevas</a>.</p></details>')
    pieces.append('</details>')
    return ''.join(pieces)


def publish():
    DEST.mkdir(exist_ok=True)
    all_current, paired_before, paired_after = [], [], []
    omission_regions = omission_chapters = 0
    for chapter in CHAPTERS:
        folder = next((name for name in COHORTS if complete(name, chapter)), None)
        assert folder, chapter
        latest = scan(chapter, folder)
        all_current.append(latest)
        atomic(DEST / (chapter + '.json'), json.dumps(latest, ensure_ascii=False, indent=2))
        if folder == CURRENT:
            paired_before.append(scan(chapter, BASELINE))
            paired_after.append(latest)
        comparison = QA / folder.replace('translated-en', 'comparison') / (chapter + '.words.jsonl')
        if not comparison.exists() and folder == BASELINE:
            comparison = QA / 'comparison' / (chapter + '.words.jsonl')
        # Distinct reference regions, not individual word flags. Artwork/OCR
        # alignment is automatic, so these remain unconfirmed omissions.
        metadata = comparison.with_name(chapter+'.json')
        if comparison.exists() and metadata.exists() and read(metadata).get('english_report_directory') == folder:
            omission_regions += len({r['reference_region'] for r in records(comparison)
                                     if r['state'] == 'no_luma_region_nearby'})
            omission_chapters += 1
    old_alerts = sum(r['alert_regions'] for r in paired_before)
    new_alerts = sum(r['alert_regions'] for r in paired_after)
    categories = collections.Counter()
    for report in all_current:
        categories.update(report['categories'])
    experiments={}
    for key,folder in [('improved_ocr','ocr-en8012-recovery'),('fixed_ocr_translation','translated-en8014-fixed-ocr'),('combined_recovery_translation','translated-en8014-recovery'),('current_windows8017','translated-en8017-geometry'),('current_windows8024_default','translated-en8024-short-default'),('current_windows8025_packaged','translated-en8025-packaged'),('current_windows8026_inflection','translated-en8026-inflection'),('current_windows8027_questions','postprocessed-en8027-questions'),('current_windows8028_openings','postprocessed-en8028-openings'),('current_windows8029_refinement','postprocessed-en8029-refinement'),('current_windows8030_tails','postprocessed-en8030-tails')]:
        finished=[read(p) for p in (QA/folder).glob('absolute-regression-*-en.done.json')]
        finished=[r for r in finished if r.get('all_files_traversed') and not r.get('runtime_errors')]
        experiments[key]=dict(chapters_complete=len(finished),chapters_expected=124,
            regions=sum(r['regions'] for r in finished),automatic_traversal_only=True,semantic_accuracy=None)
        if key=='current_windows8027_questions':experiments[key].update(execution_kind='derived_final_rule_on_immutable_native_results',fresh_ocr=False,new_decoder_inference=False)
        if key=='current_windows8028_openings':experiments[key].update(execution_kind='native_retranslation_of_eligible_openings_with_immutable_core_reports',fresh_ocr=False,fresh_translation_for_all_regions=False)
        if key=='current_windows8029_refinement':experiments[key].update(execution_kind='cached_pixel_reads_and_native_retranslation_of_refinement_candidates',fresh_ocr=False,fresh_translation_for_all_regions=False)
        if key=='current_windows8030_tails':experiments[key].update(execution_kind='cached_pixel_reads_and_native_retranslation_of_tail_candidates',fresh_ocr=False,fresh_translation_for_all_regions=False)
    summary = dict(schema=1, generated_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        chapters_expected=124, chapters_scanned=len(all_current),
        regions_scanned=sum(r['regions'] for r in all_current),
        automatic_alert_regions=sum(r['alert_regions'] for r in all_current),
        automatic_alert_categories=dict(categories),
        possible_omitted_reference_regions=omission_regions,
        omission_comparison_chapters=omission_chapters,
        omission_alignment_visually_verified=False,
        rule_version=RULE_VERSION, rule_sha256=digest(ROOT / 'tools/translation_quality_signals.py'),
        vocabulary_signal_source_sha256=digest(ROOT / 'assets/models/opus-en-es/tokenizer.json'),
        current_cohorts=dict(collections.Counter(r['report_directory'] for r in all_current)),
        current_fresh_pass_chapters=len(paired_after),
        automatic_matched_comparison=dict(chapters=len(paired_after),
            baseline=BASELINE, current=CURRENT, before_alert_regions=old_alerts, after_alert_regions=new_alerts,
            relative_alert_reduction_percent=reduction(old_alerts, new_alerts), semantic_error_metric=False,
            same_chapters_and_rule=True, matched_coverage_complete=len(paired_after)==124),
        confirmed_translation_errors=semantic_comparison(),
        distributed_semantic_comparison=distributed_semantic_comparison(),
        additional_semantic_comparison=distributed_semantic_comparison('corpus-semantic-review-b.json'),
        uniform_semantic_comparison=uniform_semantic_comparison(),
        expanded_semantic_comparison=expanded_semantic_comparison(),
        extended_semantic_comparison=extended_semantic_comparison(),
        coverage_semantic_comparison=coverage_semantic_comparison(),
        six_region_semantic_comparison=six_region_semantic_comparison(),
        six_region_coverage_comparison=six_region_coverage_comparison(),
        full_recovery_checkpoint_comparison=full_recovery_checkpoint_comparison(),
        paired_windows8012_sample=checked_diagnostic_review('paired8012-seed-semantic-review.json'),
        undetected_diagnostic_sample=checked_diagnostic_review('undetected-semantic-review8011.json'),
        ocr_word_errors=ocr_comparison(),
        all_chapter_words_visually_reviewed=False, corpus_semantic_error_rate=None,
        alerts_are_not_confirmed_errors=True,
        counts_overlap_across_categories=True)
    summary['experimental_traversal_progress']=experiments
    word_path=QA/'comparison8026-inflection/summary.json'
    word_state=read(word_path) if word_path.exists() else {}
    summary['word_comparison8026']=dict(chapter_pairs_requested=124,pairs_compared=word_state.get('pairs_compared',0),
        reference_ocr_tokens=word_state.get('reference_ocr_tokens',0),all_words_visually_reviewed=False,
        semantic_accuracy=None,automatic_proposals_only=True,
        source_summary_sha256=digest(word_path) if word_path.exists() else None)
    from full_native_delta8026 import publish as publish_full_delta
    summary['native_full_chapter_delta8026']=publish_full_delta()
    word7_path=QA/'comparison8027-question/summary.json';word7=read(word7_path) if word7_path.exists() else {}
    summary['word_comparison8027']=dict(chapter_pairs_requested=124,pairs_compared=word7.get('pairs_compared',0),
        reference_ocr_tokens=word7.get('reference_ocr_tokens',0),all_words_visually_reviewed=False,semantic_accuracy=None,
        automatic_proposals_only=True,derived_current_english_reports=True)
    summary['native_full_chapter_delta8027']=publish_full_delta('postprocessed-en8027-questions','full-native-delta8027')
    derived_path=QA/'postprocessed-en8027-questions/summary.json'
    summary['question_postprocess8027']=read(derived_path) if derived_path.exists() else None
    word8_path=QA/'comparison8028-opening/summary.json';word8=read(word8_path) if word8_path.exists() else {}
    summary['word_comparison8028']=dict(chapter_pairs_requested=124,pairs_compared=word8.get('pairs_compared',0),
        reference_ocr_tokens=word8.get('reference_ocr_tokens',0),all_words_visually_reviewed=False,semantic_accuracy=None,
        automatic_proposals_only=True,derived_english_reports_with_native_candidate_retranslation=True)
    summary['native_full_chapter_delta8028']=publish_full_delta('postprocessed-en8028-openings','full-native-delta8028')
    opening_path=QA/'postprocessed-en8028-openings/summary.json'
    summary['opening_postprocess8028']=read(opening_path) if opening_path.exists() else None
    word9_path=QA/'comparison8029-refinement/summary.json';word9=read(word9_path) if word9_path.exists() else {}
    summary['word_comparison8029']=dict(chapter_pairs_requested=124,pairs_compared=word9.get('pairs_compared',0),
        reference_ocr_tokens=word9.get('reference_ocr_tokens',0),all_words_visually_reviewed=False,semantic_accuracy=None,
        automatic_proposals_only=True,derived_pixel_evidence_with_native_candidate_mt=True)
    summary['native_full_chapter_delta8029']=publish_full_delta('postprocessed-en8029-refinement','full-native-delta8029')
    refinement_path=QA/'postprocessed-en8029-refinement/summary.json'
    summary['refinement_postprocess8029']=read(refinement_path) if refinement_path.exists() else None
    word10_path=QA/'comparison8030-tails/summary.json';word10=read(word10_path) if word10_path.exists() else {}
    summary['word_comparison8030']=dict(chapter_pairs_requested=124,pairs_compared=word10.get('pairs_compared',0),
        reference_ocr_tokens=word10.get('reference_ocr_tokens',0),all_words_visually_reviewed=False,semantic_accuracy=None,
        automatic_proposals_only=True,derived_pixel_evidence_with_native_candidate_mt=True)
    summary['native_full_chapter_delta8030']=publish_full_delta('postprocessed-en8030-tails','full-native-delta8030')
    tails_path=QA/'postprocessed-en8030-tails/summary.json'
    summary['tail_postprocess8030']=read(tails_path) if tails_path.exists() else None
    summary['windows_current_diagnostics']=latest_windows_diagnostics()
    full_translation=read(QA/'full-corpus-translation8014-validation.json')
    summary['full_translation_pass']={k:v for k,v in full_translation.items() if k not in ['reports','changes']}
    summary['full_translation_pass']['validation_sha256']=digest(QA/'full-corpus-translation8014-validation.json')
    gallery=read(QA/'photos8014-verification.json');summary['gallery_verification']=gallery
    background=read(QA/'background8015/summary.json');android_background=read(QA/'background8015/android-standalone/summary.json')
    summary['overlay_background_visual_trial']=dict(native_guards=background['native_guards'],actual_pixel_cases=background['cases'],
        changed_backgrounds=background['changed_backgrounds'],byte_identical_render_cases=7,translation_changes=0,
        android_pure_kotlin_tests=android_background['kotlin_unit_tests'],android_pixel_parity_cases=android_background['native_pixel_probe_parity_cases'],
        full_android_application_built=False,release_report_sha256=digest(QA/'release8015.json'))
    atomic(DEST / 'summary.json', json.dumps(summary, ensure_ascii=False, indent=2))
    paired = summary['automatic_matched_comparison']
    semantic = summary['distributed_semantic_comparison']
    additional = summary['additional_semantic_comparison']
    uniform = summary['uniform_semantic_comparison']
    six = summary['six_region_semantic_comparison']
    expanded = summary['six_region_coverage_comparison']['historical_baseline_comparison']
    paired_native = summary['paired_windows8012_sample']
    undetected = summary['undetected_diagnostic_sample']
    coverage = summary['six_region_coverage_comparison']
    recovered = summary['coverage_semantic_comparison']['selected_omission_diagnostic']
    checkpoint = summary['full_recovery_checkpoint_comparison']
    windows_diagnostic=summary['windows_current_diagnostics'];combined=windows_diagnostic['combined'];candidate=windows_diagnostic['omission_candidate']
    whole_omission=windows_diagnostic['full_omission'];consensus=windows_diagnostic['ocr_consensus_development'];heldout=windows_diagnostic['ocr_consensus_heldout']
    heldout_full=windows_diagnostic.get('ocr_consensus_heldout_full')
    expanded_ocr_html=''
    if heldout_full:
        checked=heldout_full['cohorts']['all_124_including_clipped_edges']['models'];base=checked['current'];new=checked['conservative_consensus']
        expanded_ocr_html=f'<p><b>Revisión ampliada terminada:</b> ya se cotejaron también las otras 112 lecturas, conservando el punto de control anterior. Las 124 ubicaciones nuevas contienen {heldout_full["words"]} palabras visibles: <b>{base["word_errors"]} → {new["word_errors"]} errores de palabra</b> y <b>{base["crops_with_word_error"]} → {new["crops_with_word_error"]} recortes con algún error</b>, {new["crops_fixed_vs_current"]} correcciones completas y {new["crops_regressed_vs_current"]} regresiones. Siguen presentes {new["edit_categories"].get("omitted_word",0)} palabras omitidas. Cuatro recortes tienen bordes de texto cortados; el informe separa los otros 120. Son medidas de reconocimiento de recortes, no de usos completos de la app. <a href="../ocr-reader-heldout8016/full-review/index.html">Ver las 124 lecturas cotejadas</a>.</p>'
    fmt = lambda n: 'Pendiente' if n is None else f'{n:.1f} %'
    category_rows = ''.join(f'<tr><td>{html.escape(LABELS[k])}</td><td>{n}</td></tr>' for k, n in categories.items())
    document = f'''<!doctype html><html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="60">
<title>Luma · Resultados globales</title><style>
body{{font:16px system-ui;background:#f2f5ef;color:#243b2b;margin:0}}main{{max-width:1050px;margin:auto;padding:24px}}
h1{{font-size:30px}}p{{line-height:1.6}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}}
article{{background:white;border:1px solid #d7e1d2;border-radius:14px;padding:20px}}strong.metric{{display:block;font-size:32px;margin:12px 0}}
.note{{padding:16px;background:#fff2d6;border-radius:10px}}table{{background:white;width:100%;border-collapse:collapse}}td,th{{padding:12px;text-align:left;border-bottom:1px solid #d7e1d2}}a{{color:#226045}}small{{color:#4b6554}}
</style><main><h1>Luma · resultados globales</h1>
<p class="note"><b>Objetivo de uso: menos del 5 % de intentos fallidos.</b> Un intento es una traducción de la pantalla completa. Omitir diálogo o narración, cambiar su significado, bloquearse, cerrarse o no completar la traducción cuenta como fallo. La prioridad es conservar todo el contenido del diálogo, incluso el que el OCR nunca detectó. Onomatopeyas como «sniff» pueden permanecer iguales; los nombres deben conservarse. <b>La probabilidad de fallo por pantalla todavía no está medida.</b> Revisar fragmentos, reducir alertas o completar archivos sin excepciones no acredita ese objetivo. El trabajo prioritario es Windows; el APK Android queda para el final.</p>
<p>Inventario histórico conservado: salidas guardadas de <b>{summary['chapters_scanned']} / 124 capítulos</b> · {summary['regions_scanned']} regiones examinadas. El avance de la configuración actual se indica por separado.</p>
<div class="cards"><article>Alertas automáticas pendientes<strong class="metric">{summary['automatic_alert_regions']}</strong>
Símbolos anómalos, inglés conservado, posibles pérdidas y repeticiones. Una región se cuenta una vez aunque tenga varias señales.</article>
<article>Errores por región · muestra histórica cotejada<strong class="metric">{expanded['before_errors']} → {expanded['after_errors']}</strong>
Reducción: <b>{fmt(expanded['relative_error_reduction_percent'])}</b>. {expanded['comparable_regions']} regiones comparables de {expanded['reviewed_regions']} inspeccionadas, distribuidas entre los 124 capítulos.</article>
<article>Pasada comparada de Windows · 8011<strong class="metric">{len(paired_after)} / 124</strong>
Archivos recorridos con una misma versión. Esta cobertura automática no equivale a aprobar cada palabra.</article>
<article>Cambios confirmados en la muestra<strong class="metric">{expanded['corrected_regions']} / {expanded['regressed_regions']}</strong>
Regiones corregidas / regiones que empeoraron. Las regresiones se incluyen en el total de errores restante.</article></div>
<p class="note">El total de errores semánticos de los 124 capítulos todavía no está establecido. Las alertas requieren cotejo: pueden incluir nombres, citas u OCR de referencia defectuoso. Una frase sin alerta puede seguir estando mal traducida. El porcentaje confirmado pertenece únicamente a la muestra cotejada; no representa la precisión global ni una revisión palabra por palabra de todos los capítulos.</p>
<h2>Pruebas actuales en Windows · prioridad a las omisiones</h2><p>El candidato nuevo ejecutó 744 inferencias nativas reales sobre las mismas ubicaciones. Siete salidas modificadas cotejadas contra los píxeles recuperan siete fragmentos omitidos. Cuatro globos modificados siguen teniendo otro error y no se aprueban. Se rectificaron explícitamente dos dictámenes históricos que habían permitido preguntas omitidas. Con el criterio revisado, el control tiene <b>{candidate['before_errors']} errores claros y el candidato {candidate['after_errors']}</b>, con {candidate['corrected_regions']} correcciones completas y {candidate['regressed_regions']} regresiones observadas en la muestra. Los pesos no cambiaron; es un ajuste de recuperación todavía en prueba. <a href="../sentence-coverage8016/visual-review/index.html">Ver el cotejo de las siete salidas</a>.</p>
<p>Separadamente, el punto de control del reconocimiento y traductor combinados incluye {combined['chapters_sampled']} capítulos disponibles y {combined['comparable_regions']} ubicaciones comparables: <b>{combined['before_errors']} → {combined['after_errors']} errores</b>, {combined['corrected_regions']} correcciones y {combined['regressed_regions']} regresiones. Estos recuentos se solapan con la muestra anterior y no se suman; tampoco son una probabilidad de fallo por pantalla. <a href="../combined-recovery8016-checkpoint01/index.html">Ver el punto de control combinado</a>.</p>
<p><b>Ajuste incorporado a Windows 8016:</b> se recorrieron las 18.179 regiones de los 124 capítulos para seleccionar reintentos. Se cotejaron las 37 salidas que cambiaron: <b>{whole_omission['before_errors']} → {whole_omission['after_errors']} errores claros</b>, {whole_omission['corrected_regions']} correcciones completas y {whole_omission['regressed_regions']} regresiones observadas. Las otras 18.142 salidas conservadas no quedan aprobadas por eso. La reducción de {whole_omission['relative_error_reduction_percent']:.1f} % pertenece al diagnóstico seleccionado de 37 cambios, no al conjunto completo ni a la probabilidad de fallo. La implementación de producción coincidió en 850 inferencias con el candidato cotejado y pasó 23 guardas de recuperación de frases. Dos procesos reales de la app evaluaron ocho vistas guardadas, cuatro por versión, sin errores de ejecución; la barra pasó las pruebas de animación, movimiento y cancelación. <a href="../full-omission-candidate8016/visual-review/index.html">Ver los 37 cambios cotejados</a> · <a href="../windows8016-real-pixels/index.html">Ver los renders de la app</a> · <a href="../../releases/Luma-Windows-1.0.0+8016.zip">Windows 8016 de prueba</a>.</p>
<h2>Lectores OCR · evaluación independiente del traductor</h2><p>Se cotejaron manualmente 124 recortes y 1.562 palabras contra tres lectores, con 372 ejecuciones nativas. El lector actual tuvo 44 errores de palabra distribuidos en 34 recortes; una tasa de 2,82 % por palabra sigue dejando 34 de 124 recortes defectuosos. La combinación conservadora en desarrollo obtuvo <b>{consensus['before_word_errors']} → {consensus['after_word_errors']} errores de palabra</b> y <b>{consensus['before_crops_with_error']} → {consensus['after_crops_with_error']} recortes con error</b>, con {consensus['crops_regressed']} regresiones y diez omisiones todavía presentes. Los lectores nuevos por sí solos introducen otros fallos y no sustituyen automáticamente al actual. <a href="../ocr-reader-comparison8016/index.html">Ver el cotejo completo de lectura</a>.</p>
<p>La regla se congeló y se probó en otras 124 ubicaciones, excluyendo las 744 anteriores. El primer punto de control cotejó sus {heldout['changed_locations_visually_reviewed']} recortes modificados: <b>{heldout['before_word_errors']} → {heldout['after_word_errors']} errores de palabra entre esos cambios</b>, {heldout['changed_crops_fixed']} recortes corregidos y {heldout['changed_crops_regressed']} regresiones. Dos conservan otro error. Esta combinación OCR todavía no está incorporada a Windows 8016 y requiere pruebas sobre capturas completas. <a href="../ocr-reader-heldout8016/consensus/index.html">Ver el punto de control inicial de doce cambios</a>.</p>{expanded_ocr_html}
<p>La comparación consolidada usa <b>seis regiones diferentes por capítulo</b>, seleccionadas sin usar el resultado de la traducción: cinco de texto largo y una de texto corto. Se cotejaron los píxeles del original inglés, la referencia española y la salida guardada de Luma. {expanded['excluded_unresolved_regions']} comparaciones se excluyeron por evidencia insuficiente o ausencia de texto real. La ampliación añade {six['newly_inspected_regions']} ubicaciones inspeccionadas por primera vez. La base histórica utiliza el reconocimiento anterior. Para aislar el último ajuste se mantiene fijo el OCR Windows 8011 con contexto y se ejecuta el traductor nativo 8014 sobre las fuentes guardadas. Los dictámenes se reutilizan únicamente si la salida es idéntica en la misma ubicación; las ocho traducciones modificadas se reinspeccionaron. El resultado histórico antes del último cambio era {six['before_errors']} → {six['after_errors']} errores ({fmt(six['relative_error_reduction_percent'])}) sobre estas mismas ubicaciones. La ampliación cambia la muestra y no es un entrenamiento nuevo.</p>
<p>Una región con varias palabras equivocadas cuenta como un único resultado defectuoso. Las diferencias menores de estilo se registran por separado. Esta selección exige una correspondencia propuesta y no mide los textos que el OCR nunca llegó a detectar. Las mejoras de reconocimiento en prueba para Windows 8012 todavía no están incluidas en este porcentaje.</p>
<p>Recorrido nativo de base: <b>Windows8026 {experiments['current_windows8026_inflection']['chapters_complete']} / 124</b>. Control congelado anterior: <b>Windows8017 {experiments['current_windows8017']['chapters_complete']} / 124</b>. El coordinador conserva el trabajo terminado y espera a disponer de memoria antes de otra inferencia. Controles intermedios conservados: <b>Windows8025 {experiments['current_windows8025_packaged']['chapters_complete']} / 124</b> · <b>Windows8024 {experiments['current_windows8024_default']['chapters_complete']} / 124</b>. Controles anteriores terminados: <b>OCR mejorado {experiments['improved_ocr']['chapters_complete']} / 124</b> · <b>retraducción con OCR fijo {experiments['fixed_ocr_translation']['chapters_complete']} / 124</b>. Estos contadores miden archivos procesados; no cuentan capítulos aprobados ni aumentan automáticamente los dictámenes semánticos.</p>
<p>Comparación anterior de las lecturas base: <b>{summary['word_comparison8026']['pairs_compared']} / 124</b> tablas y <b>{summary['word_comparison8026']['reference_ocr_tokens']}</b> palabras propuestas por el OCR de Olympus. La coincidencia literal no certifica el significado y la diferencia de redacción puede ser válida. La revisión humana de todas las palabras sigue pendiente. <a href="../review8026-inflection/index.html">Abrir comparación anterior por palabras</a>.</p>
<p>Control intermedio después de conservar preguntas: <b>Windows8027 {experiments['current_windows8027_questions']['chapters_complete']} / 124</b> capítulos. Se conservan las capturas, el OCR y las traducciones base del núcleo8026; solo se aplica la regla final de preguntas. Sus tablas anteriores con Olympus permanecen conservadas: <b>{summary['word_comparison8027']['pairs_compared']} / 124</b>. <a href="../review8027-question/index.html">Comparación intermedia por palabras</a>.</p>
<p>Control intermedio con aperturas: <b>Windows8028 {experiments['current_windows8028_openings']['chapters_complete']} / 124</b> capítulos. Sus <b>{summary['word_comparison8028']['pairs_compared']} / 124</b> tablas con Olympus permanecen conservadas. <a href="../review8028-opening/index.html">Comparación intermedia por palabras</a>.</p>
<p>Resultado actual con recuperación de frases finales: <b>Windows8030 {experiments['current_windows8030_tails']['chapters_complete']} / 124</b> capítulos. Se reutilizan lecturas de píxeles conservadas y se ejecuta traducción nativa en las regiones candidatas; no es un nuevo reconocimiento completo. Comparación actual con Olympus: <b>{summary['word_comparison8030']['pairs_compared']} / 124</b> tablas, <b>{summary['word_comparison8030']['reference_ocr_tokens']}</b> palabras propuestas por su OCR. Todas las palabras siguen conservadas; la lectura, alineación y significado requieren cotejo completo. <a href="../review8030-tails/index.html">Abrir comparación actual por palabras</a>.</p>
<p>Diferencias actuales: <b>{summary['native_full_chapter_delta8030']['matched_complete_chapters']} / 124</b> capítulos comparables y <b>{summary['native_full_chapter_delta8030']['changed_pairs']}</b> salidas modificadas en la misma posición. Las regiones sin pareja geométrica se conservan; no confirman por sí solas una omisión. <a href="../full-native-delta8030/summary.json">Datos actuales</a>.</p>
<p>Control anterior con selección de letras y preguntas breves: <b>Windows8029 {experiments['current_windows8029_refinement']['chapters_complete']} / 124</b> capítulos. Se reutilizan las lecturas de píxeles del núcleo conservado y se vuelve a ejecutar la traducción solo en las regiones candidatas. No es un reconocimiento nuevo de todos los capítulos. Comparación actual con Olympus: <b>{summary['word_comparison8029']['pairs_compared']} / 124</b> tablas, <b>{summary['word_comparison8029']['reference_ocr_tokens']}</b> palabras propuestas por su OCR. La lectura, la alineación y el significado siguen pendientes de cotejo completo. <a href="../review8029-refinement/index.html">Abrir comparación actual por palabras</a>.</p>
<p>Diferencias registradas para el resultado actual: <b>{summary['native_full_chapter_delta8029']['matched_complete_chapters']} / 124</b> capítulos comparables, <b>{summary['native_full_chapter_delta8029']['changed_pairs']}</b> salidas modificadas en la misma posición y <b>{summary['native_full_chapter_delta8029']['unmatched_old_regions'] + summary['native_full_chapter_delta8029']['unmatched_new_regions']}</b> regiones sin pareja geométrica exacta. Todas quedan conservadas para revisar; la falta de pareja no confirma una omisión. <a href="../full-native-delta8029/summary.json">Datos actuales</a>.</p>
<p>Comparación nativa de capítulos completos entre el control y la versión actual: <b>{summary['native_full_chapter_delta8026']['matched_complete_chapters']} / 124</b> capítulos comparables, <b>{summary['native_full_chapter_delta8026']['changed_pairs']}</b> salidas modificadas en la misma posición, <b>{summary['native_full_chapter_delta8026']['unmatched_old_regions']}</b> regiones anteriores y <b>{summary['native_full_chapter_delta8026']['unmatched_new_regions']}</b> nuevas sin pareja geométrica exacta. Todas quedan registradas para revisar, incluso sin alertas. Una región sin pareja puede deberse a división o agrupación y no confirma por sí sola una omisión. <a href="../full-native-delta8026/summary.json">Datos de diferencias completas</a>.</p>
<h2>Recorrido de traducción completo y galería actualizada</h2><p>La pasada del traductor nativo 8014 procesó <b>{full_translation['chapters_verified']} / 124 capítulos y {full_translation['regions_verified']} regiones</b> sobre el OCR guardado. Se conservaron fuente, imagen y coordenadas. Las {full_translation['changed_regions']} salidas modificadas coinciden con las mismas ubicaciones y traducciones del diagnóstico cotejado; las {full_translation['unchanged_regions']} restantes no cambiaron, lo que no implica que sean correctas. Hubo {full_translation['unexpected_inference_changes']} cambios inesperados de inferencia. La galería contiene <b>{gallery['images_verified']} imágenes completas verificadas</b>, incluidas zonas sin detección. <a href="../chapter-photos8014-fixed-ocr/index.html">Abrir galería de la traducción nueva</a> · <a href="../review8014-fixed-ocr/index.html">Abrir comparación por palabras con Olympus</a>.</p>
<h2>Recuperación de texto en prueba · Windows 8012</h2><p>Sobre las mismas 124 capturas, con una ubicación elegida previamente por capítulo: <b>{paired_native['before_errors']} → {paired_native['after_errors']} errores</b> en {paired_native['comparable_regions']} regiones comparables, reducción adicional de <b>{fmt(paired_native['relative_error_reduction_percent'])}</b>. {paired_native['corrected_regions']} correcciones y {paired_native['regressed_regions']} regresiones. Esta comparación corresponde a una muestra diferente de la principal y sus porcentajes no se suman. Las traducciones sin cambios conservan su evaluación anterior.</p>
<p>En un punto de control del recorrido de capítulos completos, se cotejaron seis ubicaciones por cada uno de los {checkpoint['chapters_sampled']} capítulos disponibles al congelar la comparación: <b>{checkpoint['before_errors']} → {checkpoint['after_errors']} errores claros</b>, reducción de <b>{fmt(checkpoint['relative_error_reduction_percent'])}</b> en {checkpoint['comparable_regions']} comparaciones válidas de {checkpoint['reviewed_regions']}. Se inspeccionaron las {checkpoint['changed_outputs_visually_reinspected']} salidas o fuentes modificadas y se conservaron {checkpoint['identical_output_judgments_reused']} dictámenes de salidas idénticas. {checkpoint['corrected_regions']} correcciones y {checkpoint['regressed_regions']} regresiones observadas. Es un subconjunto parcial que se solapa con el principal; no se suman sus cuentas. <a href="../full8012-review-checkpoint01/index.html">Ver las comparaciones del OCR mejorado</a>.</p>
<h2>Recuperación de frases omitidas · Windows 8014 en prueba</h2><p>Con el mismo OCR y las mismas {coverage['comparable_regions']} regiones comparables de la muestra principal: <b>{coverage['before_errors']} → {coverage['after_errors']} errores claros</b>, reducción adicional de <b>{fmt(coverage['relative_error_reduction_percent'])}</b>. Se revisaron visualmente las {coverage['changed_outputs_visually_reinspected']} salidas modificadas; las {coverage['identical_output_judgments_reused']} idénticas conservan sus dictámenes. Hubo {coverage['corrected_regions']} correcciones y {coverage['regressed_regions']} regresiones observadas. Son inferencias nativas nuevas sobre texto guardado, con los mismos pesos offline. Esta prueba aislada todavía no incorpora la nueva pasada completa de reconocimiento ni una validación nueva de Android.</p>
<p>En el diagnóstico seleccionado de salidas que recuperan frases: <b>{recovered['before_errors']} → {recovered['after_errors']} errores</b>, {recovered['corrected_regions']} correcciones y {recovered['regressed_regions']} regresiones. {recovered['newly_inspected_unaligned_regions']} regiones se cotejaron con el inglés visible por carecer de una referencia española alineada. Esta selección favorece casos de omisión y se solapa con la muestra principal; sus recuentos y porcentajes no se suman. <a href="../sentence-coverage8014/visual-review/index.html">Ver las salidas modificadas</a>.</p>
<h2>Fondo de superposición · Windows 8015 en prueba</h2><p>Se corrige el color de relleno cuando un borde oscuro no representa el fondo del globo. Diez guardas nativas y ocho pares de renders reales: un fondo corregido y siete imágenes idénticas, con cero cambios de texto. La lógica Kotlin pasa seis pruebas y coincide con C++ en los ocho recortes. No se ha generado un APK Android nuevo: Java/Gradle falla al establecer una conexión local antes de compilar. Esta corrección visual no aumenta el porcentaje semántico. <a href="../background8015/replay/index.html">Ver comparación visual</a> · <a href="../../releases/Luma-Windows-1.0.0+8015.zip">Windows 8015 de prueba</a>.</p>
<h2>Comprobación de posibles omisiones</h2><p>Se buscaron propuestas en los 124 capítulos y se inspeccionaron {undetected['reviewed_regions']} regiones candidatas de {undetected['candidate_chapters_reviewed']} capítulos. Se confirmaron <b>{undetected['complete_or_partial_english_detection_failures']} fallos de detección completa o parcial</b> y <b>{undetected['other_english_translation_defects']} defectos de traducción o fragmentación</b>. Además, {undetected['unsupported_source_script_regions']} región usa una escritura distinta del inglés y {undetected['spurious_nontext_detection_regions']} corresponden a dibujos reconocidos como caracteres. Anuncios, notas de edición y desalineaciones se registran por separado. Es una selección de diagnóstico: no determina la tasa de omisiones del conjunto y no se suma al total principal sin comprobar duplicados.</p>
<details><summary>Muestras históricas conservadas</summary><p>Primera muestra: {semantic['before_errors']} → {semantic['after_errors']} errores ({fmt(semantic['relative_error_reduction_percent'])}). Ampliación: {additional['before_errors']} → {additional['after_errors']} ({fmt(additional['relative_error_reduction_percent'])}). Esas instantáneas mezclaban versiones anteriores y se mantienen como historial; el indicador principal utiliza una sola pasada. En la primera muestra, {semantic['confirmed_errors_without_automatic_signal']} errores confirmados no activaron alertas automáticas.</p></details>
<h2>Comparación automática con el mismo criterio</h2><p>{paired['chapters']} capítulos presentes en ambas pasadas: <b>{old_alerts} → {new_alerts} regiones con alertas</b>, variación relativa <b>{fmt(paired['relative_alert_reduction_percent'])}</b>. Es una reducción de alertas detectables, no de todos los errores de traducción. La comparación se ampliará conforme termine la nueva pasada.</p>
<h2>Señales en el conjunto de 124 capítulos</h2><table><thead><tr><th>Motivo para revisar</th><th>Regiones</th></tr></thead><tbody>{category_rows}</tbody></table>
<p>Las categorías pueden coincidir en una región. En {omission_chapters} comparaciones de la misma pasada hay <b>{omission_regions}</b> regiones españolas sin correspondencia inglesa cercana propuesta; su alineación y posible omisión siguen pendientes de verificar.</p>
<p><a href="../chapter-photos8014-fixed-ocr/index.html">Galería actual de traducción</a> · <a href="../chapter-photos/index.html">Galería histórica conservada</a> · <a href="../corpus-review-sixth8011/index.html">Últimas 124 comparaciones inspeccionadas</a> · <a href="summary.json">Datos y alcance de las métricas</a></p>
<small>Actualizado {html.escape(summary['generated_at_utc'])}. Los textos esperados solo se usan en la evaluación. Las salidas de la aplicación se conservan sin editar.</small></main></html>'''
    document=document.replace('<div class="cards">',current_windows_review_html(windows_diagnostic)+'<details><summary>Indicadores históricos conservados</summary><div class="cards">',1)
    document=document.replace('</article></div>','</article></div></details>',1)
    atomic(DEST / 'index.html', document)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--track-experiments', action='store_true', help='Keep the report current while the isolated OCR/translation traversals finish')
    args = parser.parse_args()
    previous = None
    while True:
        watched = [p for folder in COHORTS for p in sorted((QA / folder).glob('*.done.json'))]
        watched.extend((ROOT / 'benchmarks/full-comics').glob('*semantic-review*.json'))
        watched.extend((ROOT / 'benchmarks/full-comics').glob('ocr*review*.json'))
        watched.extend((ROOT / 'benchmarks/full-comics').glob('*dialogue-ocr-review.json'))
        watched.extend([pathlib.Path(__file__), ROOT / 'tools/translation_quality_signals.py'])
        watched.extend(QA/name for name in ['full-corpus-translation8014-validation.json','photos8014-verification.json','release8015.json','release8016.json','release8017.json'])
        if args.track_experiments:
            for folder in ['ocr-en8012-recovery','translated-en8014-fixed-ocr','translated-en8014-recovery','translated-en8017-geometry','translated-en8024-short-default','translated-en8025-packaged','translated-en8026-inflection','postprocessed-en8027-questions','postprocessed-en8028-openings','postprocessed-en8029-refinement','postprocessed-en8030-tails']:
                watched.extend((QA/folder).glob('*.done.json'))
            watched.append(QA/'comparison8026-inflection/summary.json')
            watched.append(QA/'comparison8027-question/summary.json')
            watched.append(QA/'comparison8028-opening/summary.json')
            watched.append(QA/'comparison8029-refinement/summary.json')
        state = tuple((str(p), p.stat().st_mtime_ns) for p in watched if p.exists())
        if state != previous:
            summary = publish()
            print(json.dumps({k: summary[k] for k in ['chapters_scanned', 'automatic_alert_regions',
                  'current_fresh_pass_chapters', 'automatic_matched_comparison']}), flush=True)
            previous = state
        finished=summary['current_fresh_pass_chapters']==124
        if args.track_experiments:finished=finished and all(summary['experimental_traversal_progress'][key]['chapters_complete']==124 for key in ['current_windows8017','current_windows8026_inflection','current_windows8027_questions','current_windows8028_openings','current_windows8029_refinement','current_windows8030_tails']) and summary['word_comparison8030']['pairs_compared']==124
        if not args.watch or finished:
            break
        time.sleep(20)


if __name__ == '__main__':
    main()
