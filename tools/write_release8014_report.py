"""Pin the tested Windows archive and its bounded quality evidence."""
import datetime
import hashlib
import json
import zipfile
from audit_corpus_quality import ROOT, QA, read, digest, atomic, coverage_semantic_comparison


def main():
    archive_path=ROOT/'build/releases/Luma-Windows-1.0.0+8014.zip';engine=read(QA/'windows-engine801401.json')
    folder=ROOT/'build/windows/x64/runner/Release'
    assert digest(folder/'traductor.exe')==engine['binary_sha256']
    manifest=read(ROOT/'assets/models/opus-en-es/manifest.json')
    with zipfile.ZipFile(archive_path) as archive:
        expected={'traductor.exe':engine['binary_sha256'],'onnxruntime.dll':digest(folder/'onnxruntime.dll')}
        expected.update({'data/flutter_assets/assets/models/opus-en-es/'+name:sha for name,sha in manifest['files'].items()})
        for name,sha in expected.items():
            hashed=hashlib.sha256()
            with archive.open(name) as source:
                for block in iter(lambda:source.read(1024*1024),b''):hashed.update(block)
            assert hashed.hexdigest()==sha,name
        assert not any('full-comics' in name or 'benchmarks' in name for name in archive.namelist())
    checks={}
    for name in ['recovery','layout','overlay','toolbar']:
        path=QA/f'windows8014-{name}-test.json';value=read(path)
        if name=='toolbar':assert value and all(v is True for v in value.values())
        else:assert value['success']
        checks[name]=dict(sha256=digest(path),result=value)
    quality=coverage_semantic_comparison()
    value=dict(version='1.0.0+8014',platform='Windows x64',status='experimental',
        created_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        archive=str(archive_path),archive_sha256=digest(archive_path),archive_bytes=archive_path.stat().st_size,
        frozen_windows_snapshot_sha256=digest(QA/'windows-engine801401.json'),native_engine=engine['engine'],
        native_sentence_policy_guards=17,execution_checks=checks,
        fixed_ocr_sample_review_sha256=quality['adjudications_sha256'],fixed_ocr_comparable_regions=quality['comparable_regions'],
        fixed_ocr_before_errors=quality['before_errors'],fixed_ocr_after_errors=quality['after_errors'],
        fixed_ocr_regressed_regions=quality['regressed_regions'],translator_weights_changed=False,
        offline_assets_verified_inside_archive=True,reference_material_in_application=False,
        all_chapter_words_visually_reviewed=False,android_updated=False)
    atomic(QA/'release8014.json',json.dumps(value,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in value.items() if k!='execution_checks'}))


if __name__=='__main__':main()
