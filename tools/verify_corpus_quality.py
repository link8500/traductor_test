"""Verify the aggregate report against frozen inference and inspected pixels."""
import datetime
import json
import pathlib
import urllib.request

from PIL import Image

from audit_corpus_quality import ROOT, QA, DEST, read, records, digest, atomic


def main():
    review_path = ROOT / 'benchmarks/full-comics/corpus-semantic-review.json'
    review = read(review_path)
    sample_path = ROOT / review['sample_path']
    assert digest(sample_path) == review['sample_sha256']
    sample = read(sample_path)
    assert len(sample['cases']) == len(review['entries']) == 124
    assert len({c['chapter'] for c in sample['cases']}) == 124
    assert {c['id'] for c in sample['cases']} == {c['id'] for c in review['entries']}
    evidence = {}
    for path in sorted(sample_path.parent.glob('sheet-*.jpg')):
        with Image.open(path) as image:
            assert image.size == (1440, 2240)
            image.verify()
        evidence[path.name] = digest(path)
    assert len(evidence) == 31
    original_paths = {}
    for case in sample['cases']:
        for key in ['source_page', 'reference_page']:
            page = case[key]
            path = pathlib.Path(page['path'])
            if str(path) not in original_paths:
                assert digest(path) == page['sha256'], str(path)
                original_paths[str(path)] = page['sha256']
        current = QA / case['current_folder'] / (case['chapter']+'-en.jsonl')
        baseline = QA / case['baseline_folder'] / (case['chapter']+'-en.jsonl')
        assert digest(current) == case['current_report_sha256']
        assert digest(baseline) == case['baseline_report_sha256']
        recorded = records(current)[case['current_region']]
        assert recorded['source'] == case['source'] and recorded.get('translation', '') == case['translation']
    for review_name,expected_sheets in [('corpus-semantic-review-b.json',62),('corpus-semantic-review-short.json',31),('corpus-semantic-review-next.json',31),('corpus-semantic-review-sixth.json',31)]:
        other_review=read(ROOT/'benchmarks/full-comics'/review_name)
        other_sample_path=ROOT/other_review['sample_path']
        assert digest(other_sample_path)==other_review['sample_sha256']
        other_sample=read(other_sample_path)
        assert {c['id'] for c in other_sample['cases']}=={e['id'] for e in other_review['entries']}
        sheets=sorted(other_sample_path.parent.glob('sheet-*.jpg'))
        assert len(sheets)==expected_sheets
        for path in sheets:
            with Image.open(path) as image:
                assert image.size==(1440,2240)
                image.verify()
            evidence[other_sample_path.parent.name+'/'+path.name]=digest(path)
        for case in other_sample['cases']:
            for key in ['source_page','reference_page']:
                page=case[key];path=pathlib.Path(page['path'])
                if str(path) not in original_paths:
                    assert digest(path)==page['sha256']
                    original_paths[str(path)]=page['sha256']
            current=QA/case['current_folder']/(case['chapter']+'-en.jsonl')
            assert digest(current)==case['current_report_sha256']
            assert digest(QA/case['baseline_folder']/(case['chapter']+'-en.jsonl'))==case['baseline_report_sha256']
            actual=records(current)[case['current_region']]
            assert actual['source']==case['source'] and actual['translation']==case['translation']
    summary = read(DEST / 'summary.json')
    semantic = summary['distributed_semantic_comparison']
    assert summary['chapters_scanned'] == 124
    assert semantic['reviewed_regions'] == 124 and semantic['comparable_regions'] == 122
    assert semantic['before_errors'] == 84 and semantic['after_errors'] == 51
    assert semantic['corrected_regions'] == 36 and semantic['regressed_regions'] == 3
    assert not semantic['population_accuracy_estimate']
    assert not summary['all_chapter_words_visually_reviewed']
    assert summary['corpus_semantic_error_rate'] is None
    assert summary['alerts_are_not_confirmed_errors']
    assert semantic['confirmed_errors_with_automatic_signal'] + semantic['confirmed_errors_without_automatic_signal'] == 51
    uniform = summary['uniform_semantic_comparison']
    assert uniform['chapters_sampled'] == 124 and uniform['reviewed_regions'] == 372
    assert uniform['comparable_regions'] == 365 and uniform['excluded_unresolved_regions'] == 7
    assert uniform['before_errors'] == 253 and uniform['after_errors'] == 107
    assert uniform['corrected_regions'] == 162 and uniform['regressed_regions'] == 16
    assert uniform['single_build_comparison'] and not uniform['population_accuracy_estimate']
    assert uniform['changed_outputs_visually_reinspected'] == 91
    expanded=summary['expanded_semantic_comparison']
    assert expanded['reviewed_regions']==496 and expanded['comparable_regions']==488
    assert expanded['before_errors']==329 and expanded['after_errors']==141
    assert expanded['corrected_regions']==207 and expanded['regressed_regions']==19
    assert expanded['single_build_comparison'] and not expanded['population_accuracy_estimate']
    extended=summary['extended_semantic_comparison']
    assert extended['reviewed_regions']==620 and extended['comparable_regions']==612
    assert extended['before_errors']==406 and extended['after_errors']==170
    assert extended['corrected_regions']==260 and extended['regressed_regions']==24
    assert extended['excluded_unresolved_regions']==8
    assert extended['single_build_comparison'] and not extended['population_accuracy_estimate']
    coverage=summary['coverage_semantic_comparison'];native_folder=QA/'sentence-coverage8014'
    assert coverage['reviewed_regions']==620 and coverage['comparable_regions']==612 and coverage['excluded_unresolved_regions']==8
    assert coverage['before_errors']==170 and coverage['after_errors']==164
    assert coverage['corrected_regions']==6 and coverage['regressed_regions']==0
    assert coverage['changed_outputs_visually_reinspected']==8 and coverage['identical_output_judgments_reused']==612
    native_proof=read(native_folder/'provenance.json');native_summary=read(native_folder/'summary.json')
    native_outputs=records(native_folder/'output.jsonl')
    assert len(native_outputs)==native_summary['inputs']==723 and len({r['source'] for r in native_outputs})==723
    assert digest(native_folder/'output.jsonl')==native_summary['output_sha256']==coverage['native_output_sha256']
    assert digest(ROOT/'build/local-model8014/Release/luma_translate.exe')==native_proof['binary_sha256']
    frozen=read(QA/'windows-engine801401.json')
    assert frozen['source_sha256']['native/local_translation.cpp']==native_proof['source_sha256']
    assert frozen['source_sha256']['native/translation_coverage.h']==native_proof['coverage_policy_sha256']
    assert digest(QA/'frozen-windows801401/traductor.exe')==frozen['binary_sha256']
    assert not native_proof['translator_weights_changed'] and not native_proof['reference_used_for_inference']
    for name,sha in native_proof['assets'].items():assert digest(ROOT/'assets/models/opus-en-es'/name)==sha
    diagnostic=coverage['selected_omission_diagnostic']
    assert diagnostic['reviewed_regions']==68 and diagnostic['before_errors']==68 and diagnostic['after_errors']==16
    assert diagnostic['corrected_regions']==52 and diagnostic['regressed_regions']==0
    six=summary['six_region_semantic_comparison'];current=summary['six_region_coverage_comparison']
    assert six['reviewed_regions']==744 and six['comparable_regions']==735 and six['excluded_unresolved_regions']==9
    assert six['before_errors']==491 and six['after_errors']==203 and six['corrected_regions']==314 and six['regressed_regions']==26
    assert current['reviewed_regions']==744 and current['comparable_regions']==735 and current['excluded_unresolved_regions']==9
    assert current['before_errors']==203 and current['after_errors']==197 and current['corrected_regions']==6 and current['regressed_regions']==0
    assert current['historical_baseline_comparison']['before_errors']==491
    assert current['historical_baseline_comparison']['after_errors']==197
    added=QA/'sentence-coverage8014/additional-sample';added_status=read(added/'summary.json')
    added_sample=read(QA/'corpus-review-sixth8011/sample.json');added_rows=records(added/'output.jsonl')
    assert added_status['all_inputs_fresh_native_inference'] and added_status['cases']==124 and added_status['changed_outputs']==0
    assert digest(added/'output.jsonl')==added_status['output_sha256']==current['additional_native_output_sha256']
    for case,row in zip(added_sample['cases'],added_rows):
        assert case['source']==row['source'] and case['translation']==row['translation']
    for name,expected in [('visual-review',2),('unaligned-review',4)]:
        folder=native_folder/name;paths=sorted(folder.glob('sheet-*.jpg'));assert len(paths)==expected
        for path in paths:
            with Image.open(path) as image:
                assert image.size==(1440,2240);image.verify()
            evidence['sentence-coverage8014/'+name+'/'+path.name]=digest(path)
        for case in read(folder/'sample.json')['cases']:
            for key in ['source_page','reference_page']:
                if key not in case:continue
                page=case[key];path=pathlib.Path(page['path'])
                assert digest(path)==page['sha256'];original_paths[str(path)]=page['sha256']
    checkpoint=summary['full_recovery_checkpoint_comparison']
    checkpoint_folder=QA/'full8012-review-checkpoint01';checkpoint_sample=read(checkpoint_folder/'sample.json')
    assert checkpoint['reviewed_regions']==318 and checkpoint['comparable_regions']==314
    assert checkpoint['before_errors']==92 and checkpoint['after_errors']==72
    assert checkpoint['corrected_regions']==20 and checkpoint['regressed_regions']==0
    assert checkpoint['sample_sha256']==digest(checkpoint_folder/'sample.json')
    checkpoint_sheets=sorted(checkpoint_folder.glob('sheet-*.jpg'));assert len(checkpoint_sheets)==12
    for path in checkpoint_sheets:
        with Image.open(path) as image:
            assert image.size==(1440,2240);image.verify()
        evidence['full8012-review-checkpoint01/'+path.name]=digest(path)
    for case in checkpoint_sample['cases']:
        for key in ['source_page','reference_page']:
            page=case[key];path=pathlib.Path(page['path'])
            assert digest(path)==page['sha256'];original_paths[str(path)]=page['sha256']
    full=summary['full_translation_pass'];gallery=summary['gallery_verification'];visual=summary['overlay_background_visual_trial']
    assert full['chapters_verified']==124 and full['regions_verified']==18179 and full['all_requested_chapters_processed']
    assert full['changed_regions']==68 and full['unchanged_regions']==18111 and full['unexpected_inference_changes']==0
    assert full['changed_regions_with_same_location_diagnostic']==68 and full['changed_regions_awaiting_semantic_review']==0
    assert full['fresh_inference_records']+full['reused_identical_8014_source_records']==18179
    assert not full['all_chapter_words_visually_reviewed'] and full['semantic_accuracy'] is None
    assert digest(QA/'full-corpus-translation8014-validation.json')==full['validation_sha256']
    assert gallery['chapters_verified']==124 and gallery['images_verified']==1854 and gallery['all_source_images_present']
    assert gallery['reused_identical_painter_inputs']==1786 and gallery['fresh_native_replay_images']==68
    assert digest(QA/'chapter-photos8014-fixed-ocr/index.html')==gallery['index_sha256']
    assert visual['native_guards']==10 and visual['actual_pixel_cases']==8 and visual['changed_backgrounds']==1 and visual['translation_changes']==0
    assert visual['android_pure_kotlin_tests']==6 and visual['android_pixel_parity_cases']==8 and not visual['full_android_application_built']
    release=read(QA/'release8015.json')
    assert digest(QA/'release8015.json')==visual['release_report_sha256']
    assert release['archive_offline_assets_verified'] and not release['translation_weights_changed']
    assert digest(pathlib.Path(release['archive']))==release['archive_sha256']
    for folder, expected in [('current8011-full-a',10),('current8011-full-b',13)]:
        paths = sorted((QA/folder).glob('sheet-*.jpg'))
        assert len(paths) == expected
        for path in paths:
            with Image.open(path) as image:
                assert image.size == (1440,2240)
                image.verify()
            evidence[folder+'/'+path.name] = digest(path)
    response = urllib.request.urlopen('http://127.0.0.1:8765/full-comics/metrics/index.html', timeout=20)
    document = response.read().decode('utf-8')
    assert response.status == 200 and '59.9 %' in document and '491' in document and '197' in document
    assert '203 → 197' in document and '3.0 %' in document and '68 → 16' in document
    assert '92 → 72' in document and '21.7 %' in document
    assert '1854 imágenes completas verificadas' in document and '18179 regiones' in document
    assert 'Luma-Windows-1.0.0+8015.zip' in document
    assert 'absolute-regression-' not in document
    result = dict(verified_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        inspected_review_entries=744, comparable_regions=735, source_images_verified=len(original_paths),
        before_errors=491, after_errors=197, corpus_semantic_error_rate=None,
        all_chapter_words_visually_reviewed=False, app_or_model_changes_in_this_qa_step=False,
        initial_sample_sha256=digest(sample_path), initial_manual_review_sha256=digest(review_path),
        expanded_review_sha256=digest(ROOT/'benchmarks/full-comics/current8011-expanded-semantic-review.json'),
        extended_review_sha256=digest(ROOT/'benchmarks/full-comics/current8011-extended-semantic-review.json'),
        coverage_review_sha256=coverage['adjudications_sha256'],native_translation_inputs_verified=847,
        six_region_review_sha256=six['adjudications_sha256'],six_region_native_review_sha256=current['adjudications_sha256'],
        fixed_ocr_trial_before_errors=203,fixed_ocr_trial_after_errors=197,fixed_ocr_trial_regressions=0,
        full_ocr_checkpoint_review_sha256=checkpoint['adjudications_sha256'],
        full_ocr_checkpoint_comparable_regions=314,full_ocr_checkpoint_before_errors=92,full_ocr_checkpoint_after_errors=72,
        full_native_translation_chapters_verified=124,full_native_translation_regions_verified=18179,
        complete_gallery_images_verified=1854,background_native_guards=10,android_pure_kotlin_unit_tests=6,
        windows_trial_version='1.0.0+8015',android_new_application_built=False,
        evidence_sheets=evidence, source_images=original_paths,
        aggregate_page_http_status=200, aggregate_page_contains_chapter_examples=False,
        verification_source_sha256=digest(pathlib.Path(__file__)))
    atomic(DEST / 'verification.json', json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k not in ['source_images', 'evidence_sheets']}))


if __name__ == '__main__':
    main()
