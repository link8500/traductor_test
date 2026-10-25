"""Verify the actual 8015 Windows package and preserve its bounded evidence."""
import datetime
import hashlib
import json
import zipfile
from audit_corpus_quality import ROOT,QA,read,digest,atomic,six_region_coverage_comparison


def main():
    archive=ROOT/'build/releases/Luma-Windows-1.0.0+8015.zip';snapshot=read(QA/'windows-engine801501.json')
    manifest=read(ROOT/'assets/models/opus-en-es/manifest.json');model=read(QA/'sentence-coverage8014/provenance.json')
    assert snapshot['source_sha256']['native/local_translation.cpp']==model['source_sha256']
    assert snapshot['source_sha256']['native/local_translation.h']==model['header_sha256']
    assert snapshot['source_sha256']['native/translation_coverage.h']==model['coverage_policy_sha256']
    with zipfile.ZipFile(archive) as packaged:
        expected={'traductor.exe':snapshot['binary_sha256']}
        expected.update({'data/flutter_assets/assets/models/opus-en-es/'+name:sha for name,sha in manifest['files'].items()})
        for name,sha in expected.items():
            actual=hashlib.sha256()
            with packaged.open(name) as source:
                for block in iter(lambda:source.read(1024*1024),b''):actual.update(block)
            assert actual.hexdigest()==sha,name
        assert not any('full-comics' in name or 'benchmarks' in name for name in packaged.namelist())
    checks={}
    for name in ['recovery','layout','overlay','toolbar']:
        path=QA/f'windows8015-{name}-test.json';result=read(path)
        assert all(v is True for v in result.values()) if name=='toolbar' else result['success']
        checks[name]=dict(sha256=digest(path),result=result)
    background=read(QA/'background8015/summary.json');replay=read(QA/'background8015/replay/summary.json')
    manual=read(QA/'background8015/replay/manual-review.json');android=read(QA/'background8015/android-standalone/summary.json')
    assert background['native_guards']==10 and background['changed_backgrounds']==1
    assert replay['cases']==8 and replay['byte_identical_render_cases']==7 and replay['translation_changes']==0
    assert replay['native_binaries']['after']==snapshot['binary_sha256']
    assert manual['visually_inspected_cases']==8 and manual['text_fits_reviewed_bounds']
    assert android['kotlin_unit_tests']==6 and android['native_pixel_probe_parity_cases']==8
    semantic=six_region_coverage_comparison()
    value=dict(version='1.0.0+8015',platform='Windows x64',status='experimental',
        created_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),archive=str(archive),archive_sha256=digest(archive),
        frozen_snapshot_sha256=digest(QA/'windows-engine801501.json'),native_engine=snapshot['engine'],
        application_checks=checks,background_native_guards=10,background_real_pixel_cases=8,
        background_changed_cases=1,unchanged_render_cases=7,android_pure_kotlin_unit_tests=6,android_native_pixel_parity_cases=8,
        android_full_application_built=False,android_device_tested=False,
        kotlin_source_sha256=android['kotlin_source_sha256'],background_policy_sha256=background['policy_sha256'],
        visual_review_sha256=digest(QA/'background8015/replay/manual-review.json'),
        semantic_review_sha256=semantic['adjudications_sha256'],semantic_comparable_regions=735,
        historical_before_errors=491,semantic_after_errors=197,translation_weights_changed=False,
        background_fix_changes_translation_or_ocr_source=False,all_chapter_words_visually_reviewed=False,
        archive_offline_assets_verified=True,reference_material_packaged=False)
    atomic(QA/'release8015.json',json.dumps(value,ensure_ascii=False,indent=2))
    pictures=''.join(f'<img loading="lazy" src="sheet-{i:02d}.jpg" alt="Comparación visual {i}">' for i in range(1,3))
    atomic(QA/'background8015/replay/index.html','<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luma · Fondo de superposición</title><style>body{font:17px system-ui;background:#f1f4ed;color:#243b2b;margin:24px}img{display:block;width:100%;max-width:1440px;margin:24px auto}p{line-height:1.6;max-width:950px}</style><h1>Fondo de superposición · comparación visual</h1><p>Ocho pares dibujados con los binarios reales anterior y corregido. Se conserva exactamente el mismo texto: se corrige un fondo erróneo y siete renders permanecen idénticos. Los errores de traducción siguen visibles. Esta corrección no incrementa la precisión semántica ni aprueba todos los fondos de los capítulos.</p><p><a href="../../metrics/index.html">Resultados agregados</a></p>'+pictures+'</html>')
    print(json.dumps({k:v for k,v in value.items() if k!='application_checks'}))


if __name__=='__main__':main()
