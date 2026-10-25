"""Verify the unshipped protected Windows checkpoint and all paired evidence."""
import json
import urllib.request
from audit_corpus_quality import ROOT,QA,atomic,digest,read,records,latest_windows_diagnostics


def main():
    diagnostic=latest_windows_diagnostics();current=diagnostic['windows8019_trial'];broad=diagnostic['corpus_coverage8019']
    snapshot=QA/'windows-engine801901.json';engine=read(snapshot);binary=QA/'frozen-windows801901/traductor.exe'
    assert digest(binary)==engine['binary_sha256']
    native=QA/'production-coverage8019';proof=read(native/'provenance.json');validation=read(native/'summary.json')
    assert digest(ROOT/'build/local-model8019/Release/luma_translate.exe')==proof['binary_sha256']
    assert digest(ROOT/'build/local-model8019/Release/onnxruntime.dll')==proof['runtime_sha256']
    assert engine['source_sha256']['native/local_translation.cpp']==proof['source_sha256']
    assert engine['source_sha256']['native/translation_coverage.h']==proof['policy_sha256']
    for name,sha in proof['assets'].items():assert digest(ROOT/'assets/models/opus-en-es'/name)==sha
    assert validation['fresh_production_inferences']==1160 and not validation['guard_plan_disagreements']
    assert digest(native/'output.jsonl')==validation['output_sha256']==broad['production_output_sha256']
    assert digest(native/'summary.json')==broad['production_summary_sha256']
    assert validation['native_guards']['guards']==46
    runtime=read(QA/'windows8019-runtime-checks.json');assert runtime['success'] and runtime['geometry_tests']==37
    pixels=QA/'windows8019-heldout-pixels';summary=read(pixels/'summary.json')
    assert digest(pixels/'summary.json')==current['current_summary_sha256']
    assert digest(pixels/'output.jsonl')==current['native_output_sha256']==summary['native_output_sha256']
    assert summary['runtime_errors']==0 and summary['pixel_crops']==124 and summary['recognized_regions']==137
    assert current['baseline_judgment_revisions']==2 and current['original_pixel_source_strings_preserved']==124
    assert broad['full_region_regressions']==0 and broad['partial_content_worsening_from_rejected_trial_remaining']==0
    old=read(ROOT/'benchmarks/full-comics/full-corpus-coverage8018-semantic-review.json')
    assert digest(ROOT/'benchmarks/full-comics/full-corpus-coverage8018-semantic-review.json')==broad['original_trial_semantic_review_sha256']
    assert old['full_region_regressions']==1 and old['already_failed_regions_with_partial_content_worsening']==1
    quant=diagnostic['int8_trial8018'];assert quant['fully_corrected']==quant['regressed']==4
    assert not quant['quantization_variant_accepted_for_deployment']
    full=diagnostic['ocr_third_full8019'];assert full['additional_unchanged_crops_reviewed']==108
    assert full['metrics']['legacy']['after_edit_categories']['omitted_word']==5
    paint=read(pixels/'paint/manual-review.json');assert paint['images_visually_inspected']==4 and not paint['translation_text_overpaint_observed']
    assert not paint['all_meanings_approved']
    links=['metrics/index.html','full-corpus-coverage8019/index.html','full-corpus-coverage8018/visual-review-compact/index.html',
        'windows8019-heldout-pixels/index.html','windows8019-heldout-pixels/paint/index.html',
        'int8-translation8018/visual-review/index.html','ocr-apostrophes8019/remaining-third/index.html']
    for link in links:
        with urllib.request.urlopen('http://127.0.0.1:8765/full-comics/'+link,timeout=20) as response:
            page=response.read().decode('utf-8');assert response.status==200
            if link=='metrics/index.html':
                assert 'absolute-regression-' not in page and '1.160' not in page
                assert '1160' in page and 'probabilidad de fallo por pantalla' in page
                assert '41' in page and '8019' in page
    for report in [current,broad,quant,full]:
        assert report['screen_attempt_failure_probability'] is None and not report['all_chapter_words_visually_reviewed']
    result=dict(verified=True,checkpoint_build='801901',packaged_as_ready=False,actual_pixel_crops=124,
        fresh_translation_validation_sources=1160,translation_guards=46,geometry_guards=37,
        broad_changed_regions_reviewed=119,broad_before_not_approved=117,broad_after_not_approved=41,
        broad_relative_reduction_percent=broad['relative_unapproved_reduction_percent'],
        rejected_precision_variant_preserved=True,full_third_ocr_inventory_locations=124,
        screen_attempt_failure_probability=None,target_achieved=False,all_chapter_words_visually_reviewed=False,
        android_build_deferred=True,snapshot_sha256=digest(snapshot),current_review_sha256=current['review_sha256'])
    atomic(QA/'metrics/verification8019.json',json.dumps(result,indent=2));print(json.dumps(result),flush=True)


if __name__=='__main__':main()
