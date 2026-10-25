"""Verify the exact packaged Windows trial and aggregate evidence boundaries."""
import json
import pathlib
import urllib.request
from audit_corpus_quality import ROOT, QA, atomic, digest, read, latest_windows_diagnostics


def main():
    diagnostic=latest_windows_diagnostics();release=diagnostic['windows_release']
    assert release['version']=='1.0.0+8017'
    assert digest(pathlib.Path(release['archive']))==release['archive_sha256']
    assert digest(QA/'frozen-windows801704/traductor.exe')==release['binary_sha256']
    assert digest(QA/'windows-engine801704.json')==release['frozen_snapshot_sha256']
    checks=read(QA/'windows8017-render-runtime-checks.json')
    assert checks['success'] and checks['geometry_tests']==37
    assert all(t['result'].get('success',all(v for v in t['result'].values() if isinstance(v,bool))) for t in checks['tests'].values())
    folder=QA/'windows8017-render-heldout-pixels'
    before=read(QA/'windows8016-heldout-pixels/summary.json');current=read(folder/'summary.json')
    assert len(before['entries'])==len(current['entries'])==124
    assert all(a['id']==b['id'] and a['source']==b['source'] for a,b in zip(before['entries'],current['entries']))
    assert current['runtime_errors']==0 and current['crop_source_word_errors']==34 and current['words']==1483
    geometry=diagnostic['geometry_render'];sample=read(folder/'visual-review/sample.json')
    assert geometry['changed_locations_reinspected']==len(sample['cases'])
    assert geometry['identical_location_judgments_reused']==len(sample['reused_identical_location_outputs'])
    assert digest(folder/'visual-review/manual-decisions.json')==geometry['manual_sha256']
    assert digest(folder/'output.jsonl')==geometry['native_output_sha256']
    assert digest(folder/'summary.json')==geometry['current_summary_sha256']
    assert digest(ROOT/'benchmarks/full-comics/windows8016-heldout-semantic-review.json')==geometry['original_semantic_review_sha256']
    for case in sample['cases']:
        for key in ['source_page','reference_page']:
            page=case[key];assert digest(pathlib.Path(page['path']))==page['sha256']
    paint=read(folder/'paint/manual-review.json')
    assert paint['viewports_visually_inspected']==len(sample['cases']) and paint['new_translated_text_not_overpainted']
    assert not paint['all_rendered_translations_semantically_correct']
    for entry in paint['rendered_images']:assert digest(pathlib.Path(entry['path']))==entry['sha256']
    full=diagnostic['ocr_consensus_heldout_full'];third=diagnostic['ocr_coverage_heldout'];short=diagnostic['short_clause_candidate']
    assert full['crops_visually_reviewed']==124 and full['words']==1483
    assert third['changed_locations_visually_reviewed']==16 and third['unchanged_locations_without_meaning_approval']==108
    assert short['reviewed_changed_locations']==14 and short['corrected']==8 and short['after_not_approved']==5
    assert not short['included_in_application'] and not third['application_modified']
    assert not release['experimental_ocr_consensus_bundled'] and not release['experimental_short_clause_candidate_bundled']
    assert not release['translation_weights_changed'] and not release['ocr_weights_changed']
    assert not release['target_achieved'] and release['screen_attempt_failure_probability'] is None
    assert not release['all_chapter_words_visually_reviewed'] and not release['android_application_built']
    links=['metrics/index.html','windows8016-heldout-pixels/visual-review/index.html',
        'windows8017-render-heldout-pixels/visual-review/index.html','windows8017-render-heldout-pixels/paint/index.html',
        'short-clause8017-guarded/visual-review/index.html','ocr-coverage8017-holdout/coverage/index.html']
    for path in links:
        with urllib.request.urlopen('http://127.0.0.1:8765/full-comics/'+path,timeout=20) as response:
            page=response.read().decode('utf-8');assert response.status==200
            if path=='metrics/index.html':
                assert 'probabilidad de fallo por pantalla todavía no está medida' in page
                assert 'absolute-regression-' not in page and 'Luma-Windows-1.0.0+8017.zip' in page
                assert 'sin incorporar' in page and '124 ubicaciones' in page
    result=dict(verified=True,windows_version='1.0.0+8017',actual_pixel_crops=124,
        actual_pixel_runtime_errors=0,original_source_strings_preserved=124,
        geometry_and_paint_guards=37,semantic_cohort=geometry['cohorts']['all_124_including_clipped_edges'],
        release_sha256=digest(QA/'release8017.json'),all_chapter_words_visually_reviewed=False,
        screen_attempt_failure_probability=None,target_achieved=False,android_build_deferred=True)
    atomic(QA/'metrics/verification8017.json',json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
