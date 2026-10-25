"""Prove that capture/UI changes do not invalidate the running OCR corpus."""
import hashlib,json,pathlib,re

ROOT=pathlib.Path(__file__).resolve().parents[1];QA=ROOT/'build/full-comics'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
read=lambda path:json.loads(path.read_text(encoding='utf-8'))
snapshot=read(QA/'windows-engine8007.json');previous=read(QA/'release8007.json')
before_path=QA/'screen-translator-before-capture8008.cpp';before_header=QA/'screen-translator-before-capture8008.h'
assert digest(before_path)==snapshot['source_sha256']['windows/runner/screen_translator.cpp']
assert digest(before_header)==snapshot['source_sha256']['windows/runner/screen_translator.h']
old=before_path.read_text(encoding='utf-8');current=(ROOT/'windows/runner/screen_translator.cpp').read_text(encoding='utf-8')
proof={}
for name,start,end in [
    ('screen_recognition','std::vector<ScreenTranslator::Block> ScreenTranslator::Recognize(', 'std::wstring ScreenTranslator::Translate('),
    ('full_chapter_benchmark','int ScreenTranslator::ComicBenchmark(', 'int ScreenTranslator::ToolbarTest(')]:
    extract=lambda text:text[text.index(start):text.index(end)]
    assert extract(old)==extract(current),(name,'implementation changed')
    proof[name]=hashlib.sha256(extract(current).encode()).hexdigest()
for name in ['Frame','Block']:
    pattern=rf'struct {name} \{{[^}}]+\}};'
    a=re.search(pattern,before_header.read_text(encoding='utf-8'))[0]
    b=re.search(pattern,(ROOT/'windows/runner/screen_translator.h').read_text(encoding='utf-8'))[0]
    assert a==b,(name,'input layout changed')
unchanged=['native/local_translation.cpp','native/local_translation.h','assets/models/opus-en-es/manifest.json',
    'android/app/src/main/cpp/local_translation_jni.cpp','android/app/src/main/kotlin/com/example/traductor/LocalMarian.kt',
    'android/app/src/main/kotlin/com/example/traductor/ComicOcr.kt','android/app/src/main/kotlin/com/example/traductor/ComicText.kt']
for path in unchanged:assert digest(ROOT/path)==previous['sources'][path],(path,'recognition or translation changed')
for row in read(QA/'real-chapter-fixtures8008.json'):
    images=read(QA/'images-en.json');image=next(r for r in images if r['chapter']==row['chapter'] and r['image']==row['image'])
    assert digest(pathlib.Path(image['path']))==row['sha256'],('Live fixture image changed',row['chapter'])
report={'capture_build':8008,'corpus_engine':snapshot['engine'],'corpus_binary':'frozen-windows8007/traductor.exe',
    'unchanged_functions':proof,'unchanged_core_files':{p:digest(ROOT/p) for p in unchanged},
    'source_image_signatures_verified':True,
    'scope':'The running Windows corpus still uses the same file OCR and translation implementation. Live Android capture is validated separately; this does not certify every Android viewport or word.'}
(QA/'capture8008-core-proof.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('Corpus recognition/translation unchanged; source fixtures verified; capture changes tested separately')
