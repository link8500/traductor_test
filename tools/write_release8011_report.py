"""Verify the shipped 8011 changes without claiming full corpus word approval."""
import datetime,hashlib,json,pathlib,xml.etree.ElementTree as ET
from PIL import Image

ROOT=pathlib.Path(__file__).resolve().parents[1];QA=ROOT/'build/full-comics'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    snapshot=read(QA/'windows-engine801101.json')
    for name,sha in snapshot['source_sha256'].items():assert digest(ROOT/name)==sha,name
    assert digest(QA/'frozen-windows801101/traductor.exe')==snapshot['binary_sha256']
    def phone_log(name):
        result=json.loads((QA/name).read_text(encoding='utf-8-sig').strip());assert result['success'];return result
    follow=phone_log('android8011-follow-test.log');underwater=phone_log('android8011-underwater-test.log');suite=phone_log('android8011-release-suite.log')
    assert suite['version_code']==8011 and suite['samples']==29 and suite['colour_and_rotation_cases']==9
    assert follow['production_pipeline'][0]['text'].replace('\n',' ')=='THEN FOLLOW ME.'
    assert follow['production_pipeline'][0]['translation']=='Entonces sígueme.'
    assert any('bajo el agua' in r.get('translation','') for r in underwater['production_pipeline'])
    layout=read(QA/'windows8011-layout-test.json');assert layout['success'] and all(r['passed'] for r in layout['cases'])
    units=[]
    for path in (ROOT/'build/app/test-results/testReleaseUnitTest').glob('TEST-*.xml'):
        root=ET.parse(path).getroot();assert int(root.get('failures','0'))==0 and int(root.get('errors','0'))==0
        units.append(dict(name=root.get('name'),tests=int(root.get('tests','0'))))
    assert sum(r['tests'] for r in units)==16
    chapter='absolute-regression-124';capture=read(QA/'ocr-en8011-context'/f'{chapter}-en.done.json')
    assert capture['all_files_traversed'] and capture['images']==22 and capture['capture_selection']=='overlap-context-v2' and not capture['runtime_errors']
    proof=read(QA/'chapter-photos'/chapter/'provenance.json');assert proof['report_directory']=='translated-en8011-context'
    assert proof['report_sha256']==digest(QA/proof['report_directory']/f'{chapter}-en.jsonl')
    for page in proof['pages']:
        photo=QA/'chapter-photos'/chapter/page['file'];assert digest(photo)==page['output_sha256']
        with Image.open(photo) as image:assert image.size==(page['width'],page['height']);image.verify()
    baseline=read(QA/'visual-evaluation8010'/f'{chapter}.json');current=read(QA/'visual-evaluation8011-context'/f'{chapter}.json')
    assert baseline['expected_english_words']==current['expected_english_words']==724
    assert baseline['ocr_word_edits']==77 and current['ocr_word_edits']==46
    truth=read(ROOT/'benchmarks/full-comics/visual-reviews'/f'{chapter}.json')
    assert len(truth['entries'])==67 and truth['evaluated_english_report_sha256']==current['report_sha256']
    artifacts={}
    for name,path in [('android',ROOT/'build/app/outputs/flutter-apk/app-release.apk'),('windows',ROOT/'build/releases/Luma-Windows-1.0.0+8011.zip')]:
        artifacts[name]=dict(path=str(path),bytes=path.stat().st_size,sha256=digest(path))
    sources=['native/local_translation.cpp','native/local_translation.h','windows/runner/screen_translator.cpp','windows/runner/screen_translator.h',
        'windows/runner/main.cpp','android/app/src/main/kotlin/com/example/traductor/ComicText.kt','android/app/src/main/kotlin/com/example/traductor/ComicLineLayout.kt']
    report=dict(build=8011,generated_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),sources={name:digest(ROOT/name) for name in sources},
        translator_weights_changed=False,production_answer_lookup_added=False,windows_corpus_engine=snapshot,artifacts=artifacts,
        tested_android_phone='YPGIZDMN995DLZMF',phone_disconnect_announced_by_user=True,emulator_build8011_tested=False,
        phone_grouped_dialogue=follow,phone_underwater_regression=underwater,android_release_suite=suite,jvm_tests=units,windows_layout=layout,
        full_chapter_capture=capture,chapter124_photo_hashes_and_dimensions_verified=len(proof['pages']),
        inspected_ocr_comparison=dict(dialogue_pairs=67,expected_english_words=724,before_word_edits=77,after_word_edits=46,
            semantic_accuracy=None,scope='Inspected dialogues of chapter124 only; not a corpus-wide quality percentage'),
        full_corpus_pass_in_progress='ocr-en8011-context → translated-en8011-context → comparison8011-context → chapter-photos',
        obsolete_workers_retired=['8007','8010'],historical_reports_and_checkpoints_preserved=True,
        all_124_chapters_visually_word_reviewed=False,
        known_remaining_issues=['Narrow lettering in WHAT DO YOU MEAN THERE’S NO PROOF still loses NO',
            'UNFORTUNATE → LNFORTUNATE can invert the Spanish meaning','FOUNDATION → FOLNDATION can change the meaning',
            'Outlined narration remains fragmented','Some names and titles require better translation'],
        diagnostic_reader_probe=dict(paragraph_crops=10,readers=['latin-v5','english-v4'],source='ocr-reader-probe8011',
            app_pipeline_changed_by_probe=False,reference_answers_passed_to_ocr=False),
        discarded_generic_test_runner_attempt=dict(log='android8011-generic-runner-failed.log',
            reason='Generic Kotlin instrumentation references a stdlib facade removed by R8; the release-model probe was used successfully instead'))
    (QA/'release8011.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Verified 8011: grouped dialogue, phone OCR regressions, 16 JVM cases, 15 Windows layout cases, chapter124 capture selection and 22 review images. Full visual word review remains incomplete.')

if __name__=='__main__':main()
