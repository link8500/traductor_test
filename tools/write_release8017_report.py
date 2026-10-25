"""Pin the tested geometry and painting changes to the packaged Windows build."""
import datetime
import hashlib
import json
import zipfile
from audit_corpus_quality import ROOT, QA, atomic, digest, read


def main():
    archive=ROOT/'build/releases/Luma-Windows-1.0.0+8017.zip'
    snapshot_path=QA/'windows-engine801704.json';snapshot=read(snapshot_path)
    old_snapshot=read(QA/'windows-engine801601.json')
    for name in ['native/local_translation.cpp','native/translation_coverage.h','native/ocr_recovery.h','assets/models/opus-en-es/manifest.json']:
        assert snapshot['source_sha256'][name]==old_snapshot['source_sha256'][name]
    checks_path=QA/'windows8017-render-runtime-checks.json';checks=read(checks_path)
    assert checks['success'] and checks['geometry_tests']==37 and checks['binary_sha256']==snapshot['binary_sha256']
    folder=QA/'windows8017-render-heldout-pixels';app=read(folder/'summary.json')
    assert app['pixel_crops']==124 and app['runtime_errors']==0 and app['crops_without_detected_text']==0
    semantic_path=ROOT/'benchmarks/full-comics/windows8017-render-geometry-semantic-review.json';semantic=read(semantic_path)
    assert semantic['after_build']=='801704' and semantic['all_124_original_source_strings_preserved']
    layout_path=folder/'paint/manual-review.json';layout=read(layout_path)
    assert layout['new_translated_text_not_overpainted'] and layout['viewports_visually_inspected']==semantic['changed_locations_reinspected']
    manifest=read(ROOT/'assets/models/opus-en-es/manifest.json')
    with zipfile.ZipFile(archive) as packaged:
        assert packaged.testzip() is None
        expected={'traductor.exe':snapshot['binary_sha256'],**{'data/flutter_assets/assets/models/opus-en-es/'+name:sha for name,sha in manifest['files'].items()}}
        for name,sha in expected.items():
            value=hashlib.sha256()
            with packaged.open(name) as source:
                for block in iter(lambda:source.read(1024*1024),b''):value.update(block)
            assert value.hexdigest()==sha,name
        assert not any('full-comics' in name or 'benchmarks' in name or 'ocr-candidates' in name for name in packaged.namelist())
    m=semantic['cohorts']['all_124_including_clipped_edges']
    value=dict(version='1.0.0+8017',platform='Windows x64',status='experimental',
        created_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        archive=str(archive),archive_sha256=digest(archive),binary_sha256=snapshot['binary_sha256'],
        frozen_snapshot_sha256=digest(snapshot_path),native_engine=snapshot['engine'],
        translation_policy_sha256=snapshot['source_sha256']['native/translation_coverage.h'],
        application_checks=checks,application_checks_sha256=digest(checks_path),
        actual_pixel_crops=124,actual_pixel_runtime_errors=0,actual_recognized_regions=app['recognized_regions'],
        all_124_original_source_strings_preserved=True,source_word_errors=app['crop_source_word_errors'],
        source_words=app['words'],source_omitted_words=app['source_edit_categories'].get('omitted_word',0),
        semantic_same_cohort=m,semantic_review_sha256=digest(semantic_path),
        native_pixel_proof_sha256=digest(folder/'summary.json'),render_visual_review_sha256=digest(layout_path),
        translated_text_overpaint_fixed=True,all_rendered_translations_semantically_correct=False,
        translation_weights_changed=False,ocr_weights_changed=False,
        experimental_ocr_consensus_bundled=False,experimental_short_clause_candidate_bundled=False,
        archive_offline_assets_verified=True,reference_material_packaged=False,
        android_application_built=False,android_device_tested=False,
        screen_attempt_failure_probability=None,target_failure_probability_below=.05,target_achieved=False,
        all_chapter_words_visually_reviewed=False,priority='Windows complete dialogue and narration; Android APK deferred')
    atomic(QA/'release8017.json',json.dumps(value,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in value.items() if k!='application_checks'}),flush=True)


if __name__=='__main__':main()
