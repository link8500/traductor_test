"""Verify and record the release and its actual, bounded QA evidence."""
import collections,datetime,hashlib,json,pathlib,re,zipfile
from PIL import Image

ROOT=pathlib.Path(__file__).resolve().parents[1];QA=ROOT/'build/full-comics'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def log_json(path):
    value=path.read_text(encoding='utf-8-sig');match=re.search(r'(\{.*\})',value,re.S)
    assert match,(path,'No successful JSON report');return json.loads(match[1])

snapshot=read(QA/'windows-engine8010.json')
for name,sha in snapshot['source_sha256'].items():assert digest(ROOT/name)==sha,(name,'Source changed after freezing')
assert digest(QA/'frozen-windows8010/traductor.exe')==snapshot['binary_sha256']
core=(ROOT/'native/local_translation.cpp').read_text(encoding='utf-8')
old=(QA/'recognizer-before-8009.cpp').read_text(encoding='utf-8')
translation=lambda text:text[:text.index('struct LocalTextDetector::Impl')]+text[text.index('struct LocalTranslationModel::Impl'):]
assert translation(core)==translation(old),'Translation implementation changed'
photos=read(QA/'chapter-photos/summary.json');assert photos['chapters_exported']==124 and photos['source_images_rendered']==1854,photos['chapters_exported']
inputs={p['chapter'].removesuffix('-en')+'#'+str(p['image']):p for p in read(QA/'images-en.json') if p['series']=='absolute-regression'}
photo_count=0;cohorts=collections.Counter()
for number in range(1,125):
    chapter=f'absolute-regression-{number:02d}';folder=QA/'chapter-photos'/chapter;proof=read(folder/'provenance.json')
    report=QA/proof['report_directory']/(chapter+'-en.jsonl');assert digest(report)==proof['report_sha256']
    cohorts[proof['report_directory']]+=1
    for page in proof['pages']:
        source=inputs[chapter+'#'+str(page['image'])];path=folder/page['file']
        assert page['original_sha256']==source['sha256'] and digest(path)==page['output_sha256'],path
        with Image.open(path) as image:assert image.size==(source['width'],source['height']);image.verify()
        photo_count+=1
assert photo_count==1854
ocr=read(QA/'ocr-en8010/absolute-regression-124-en.done.json');nmt=read(QA/'translated-en8010/absolute-regression-124-en.done.json')
assert ocr['images']==22 and ocr['viewports']==152 and not ocr['runtime_errors']
assert nmt['images']==22 and not nmt['runtime_errors']
dialogue=next(r for r in map(json.loads,(QA/'translated-en8010/absolute-regression-124-en.jsonl').read_text(encoding='utf-8').splitlines()) if r['image']==2 and 'MEAL' in r['source'])
assert 'A MEAL UNDERWATER' in dialogue['source'] and 'bajo el agua' in dialogue['translation'] and 'fantasmas' in dialogue['translation']
phone=log_json(QA/'poco8008-underwater/android8010-probe-retry.log');handwriting=log_json(QA/'handwriting8010-test.log');suite=log_json(QA/'android8010-release-suite.log')
assert phone['success'] and handwriting['success'] and suite['success'] and suite['version_code']==8010
assert all(read(QA/'windows8010-toolbar-test.json').values()) and read(QA/'windows8010-self-test.json')['success']
assert read(QA/'poco8008-underwater/consensus8010.json')['success']
sources=['native/local_translation.cpp','native/local_translation.h','windows/runner/screen_translator.cpp','windows/runner/screen_translator.h',
    'windows/runner/review_export.cpp','windows/runner/main.cpp','android/app/src/main/kotlin/com/example/traductor/ScreenTranslatorService.kt',
    'android/app/src/main/kotlin/com/example/traductor/ComicOcr.kt','android/app/src/main/kotlin/com/example/traductor/LocalMarian.kt',
    'android/app/src/main/cpp/local_translation_jni.cpp','assets/models/opus-en-es/manifest.json']
apk=ROOT/'build/app/outputs/flutter-apk/app-release.apk';archive=ROOT/'build/releases/Luma-Windows-1.0.0+8010.zip'
with zipfile.ZipFile(apk) as zipped:abis=sorted({n.split('/')[1] for n in zipped.namelist() if n.startswith('lib/')})
report=dict(build=8010,generated_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),offline=True,translator_weights_changed=False,
    answer_lookup_added=False,translation_implementation_unchanged=True,translation_signature=read(QA/'translated-en8010/summary.json')['translation_signature'],
    sources={name:digest(ROOT/name) for name in sources},windows_engine=snapshot,
    artifacts=dict(android=dict(path=str(apk),sha256=digest(apk),bytes=apk.stat().st_size,abis=abis),windows=dict(path=str(archive),sha256=digest(archive),bytes=archive.stat().st_size)),
    tested_devices=dict(android_phone='YPGIZDMN995DLZMF',android_abi=suite['abi'],emulator_build8010_tested=False),
    phone_production_pipeline=phone['production_pipeline'],phone_handwriting_passed=handwriting['success'],android_release_suite=suite,
    windows_self_test=read(QA/'windows8010-self-test.json'),windows_toolbar_test=read(QA/'windows8010-toolbar-test.json'),
    native_consensus_test=read(QA/'poco8008-underwater/consensus8010.json'),chapter124=dict(images=22,viewports=152,regions=nmt['regions'],runtime_errors=0,dialogue=dialogue),
    photo_export=dict(chapters=124,images=1854,all_image_hashes_and_dimensions_verified=True,cohorts=dict(cohorts),
        physical_phone_screenshots=False,scope='Saved model output rendered with the production Windows painter and reconstructed placement style; all source pages remain visible'),
    mechanical_review=read(QA/'chapter-audit/summary.json'),keep_awake=read(QA/'android-keep-awake-state.json'),
    all_words_visually_reviewed=False,semantic_accuracy=None,
    known_limits=['Full visual and semantic word review is not complete. Photo exports preserve baseline and newer cohorts explicitly.',
        'THEN FOLLOW ME in chapter 124 remains split across separate recognized regions.',
        'Other viewport sizes, stylized lettering and background masks still need review; older Sniff/SKIRMISH/FOR REVENGE failures are not all certified fixed.',
        'Initial Android instrumentation launch during the installation sequence failed; the retry after installation passed. This is not counted as a passing first attempt.'])
(QA/'release8010.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Verified release8010:',photo_count,'images in 124 chapters; target paragraph passed in Windows and Android; semantic review remains open')
