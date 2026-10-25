"""Pin the real Windows-only omission fix and its limits, no Android build."""
import datetime
import hashlib
import json
import pathlib
import zipfile
from audit_corpus_quality import ROOT,QA,read,digest,atomic


def main():
    archive=ROOT/'build/releases/Luma-Windows-1.0.0+8016.zip';snapshot_path=QA/'windows-engine801601.json';snapshot=read(snapshot_path)
    parity=read(QA/'production-coverage8016/summary.json');native=read(QA/'production-coverage8016/provenance.json')
    assert parity['fresh_production_inferences']==850 and parity['production_candidate_differences']==0 and parity['native_guards']['guards']==23
    assert snapshot['source_sha256']['native/local_translation.cpp']==native['source_sha256']
    assert snapshot['source_sha256']['native/translation_coverage.h']==native['policy_sha256']
    manifest=read(ROOT/'assets/models/opus-en-es/manifest.json')
    with zipfile.ZipFile(archive) as packaged:
        expected={'traductor.exe':snapshot['binary_sha256'],**{'data/flutter_assets/assets/models/opus-en-es/'+name:sha for name,sha in manifest['files'].items()}}
        for name,sha in expected.items():
            actual=hashlib.sha256()
            with packaged.open(name) as source:
                for block in iter(lambda:source.read(1024*1024),b''):actual.update(block)
            assert actual.hexdigest()==sha,name
        assert not any('full-comics' in name or 'benchmarks' in name or 'ocr-candidates8016' in name for name in packaged.namelist())
    checks={}
    for name in ['recovery','layout','overlay','toolbar']:
        path=QA/f'windows8016-{name}-test.json';r=read(path)
        assert all(v is True for v in r.values()) if name=='toolbar' else r['success']
        checks[name]=dict(sha256=digest(path),result=r)
    full_path=ROOT/'benchmarks/full-comics/full-omission8016-semantic-review.json';full=read(full_path)
    sample_path=ROOT/'benchmarks/full-comics/coverage8016-candidate-semantic-review.json';sample=read(sample_path)
    pixels=read(QA/'windows8016-real-pixels/summary.json')
    visual_path=QA/'windows8016-real-pixels/manual-review.json';visual=read(visual_path)
    assert visual['viewports_visually_inspected']==4 and visual['new_translation_text_fits_recognized_area']
    assert full['reviewed_regions']==37 and full['before_errors']==36 and full['after_errors']==10 and full['regressed_regions']==0
    assert sample['comparable_regions']==735 and sample['before_errors']==199 and sample['after_errors']==196 and sample['regressed_regions']==0
    assert pixels['binaries']['after']==snapshot['binary_sha256'] and pixels['runtime_errors']==0 and pixels['source_and_geometry_identical']
    value=dict(version='1.0.0+8016',platform='Windows x64',created_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        status='experimental',archive=str(archive),archive_sha256=digest(archive),frozen_snapshot_sha256=digest(snapshot_path),binary_sha256=snapshot['binary_sha256'],
        native_engine=snapshot['engine'],translation_policy_sha256=native['policy_sha256'],application_checks=checks,
        native_policy_guards=23,fresh_native_production_parity_inputs=850,production_candidate_output_differences=0,
        real_pixel_windows_app_processes=2,real_pixel_windows_viewport_attempts=8,real_pixel_viewports=4,real_pixel_runtime_errors=0,real_pixel_changed_translations=4,
        semantic_fixed_ocr_sample_comparable_regions=735,semantic_fixed_ocr_sample_before_errors=199,semantic_fixed_ocr_sample_after_errors=196,
        semantic_control_judgments_explicitly_revised=2,full_corpus_candidate_changed_regions=37,full_corpus_changed_regions_before_errors=36,
        full_corpus_changed_regions_after_errors=10,full_corpus_changed_regions_corrected=26,full_corpus_changed_regions_regressed=0,
        full_corpus_changes_selected_not_population_rate=True,semantic_sample_review_sha256=digest(sample_path),full_candidate_review_sha256=digest(full_path),
        production_parity_sha256=digest(QA/'production-coverage8016/summary.json'),real_pixel_proof_sha256=digest(QA/'windows8016-real-pixels/summary.json'),
        real_pixel_visual_review_sha256=digest(visual_path),real_pixel_render_text_fits=True,
        screen_attempt_failure_probability=None,target_failure_probability_below=.05,target_achieved=False,
        priority='Windows dialogue/narration completeness; Android APK deferred',translation_weights_changed=False,ocr_weights_changed=False,
        experimental_ocr_consensus_bundled=False,all_chapter_words_visually_reviewed=False,archive_offline_assets_verified=True,reference_material_packaged=False,
        android_application_built=False,android_device_tested=False)
    atomic(QA/'release8016.json',json.dumps(value,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in value.items() if k!='application_checks'}),flush=True)


if __name__=='__main__':main()
