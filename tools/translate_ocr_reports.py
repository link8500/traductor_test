"""Translate a new full OCR traversal, preserving exact inference provenance.

Only identical source strings from the previous *model outputs* can be reused.
The shared translation source and all four translation assets must be identical.
No Spanish reference, transcription, or expected answer is read by this tool.
"""
import argparse,hashlib,json,pathlib,re,subprocess,time

ROOT=pathlib.Path(__file__).resolve().parents[1];QA=ROOT/'build/full-comics'
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def records(path):return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines() if s.strip()]
def digest(value):return hashlib.sha256(value).hexdigest()
def translation_code(value):
    text=value.decode('utf-8')
    return (text[:text.index('struct LocalTextDetector::Impl')]+text[text.index('struct LocalTranslationModel::Impl'):]).encode('utf-8')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ocr-reports',required=True);parser.add_argument('--output-name',required=True)
    parser.add_argument('--watch',action='store_true');parser.add_argument('--expected-chapters',type=int,default=154)
    parser.add_argument('--translation-snapshot',type=pathlib.Path,help='Explicit immutable old translation binary/source; permits resuming an old OCR cohort while a newer translator is developed')
    args=parser.parse_args()
    if not 1<=args.expected_chapters<=154:parser.error('Expected chapters must be between 1 and 154')
    for name in [args.ocr_reports,args.output_name]:
        if not re.fullmatch(r'[a-z][a-z0-9-]+',name):parser.error('Invalid QA directory name')
    source_path=ROOT/'native/local_translation.cpp'
    binary=ROOT/'build/local-model/Release/luma_translate.exe'
    runtime=ROOT/'build/local-model/Release/onnxruntime.dll'
    if args.translation_snapshot:
        pinned=args.translation_snapshot.resolve();proof=read(pinned/'snapshot.json')
        source_path=pinned/'source.cpp';binary=pinned/'luma_translate.exe';runtime=pinned/'onnxruntime.dll'
        assert digest(source_path.read_bytes())==proof['source_sha256']
        assert digest(binary.read_bytes())==proof['binary_sha256']
        assert digest(runtime.read_bytes())==proof['runtime_sha256']
        assert digest(translation_code(source_path.read_bytes()))==proof['translation_code_sha256']
    cpp=source_path.read_bytes()
    old_cpp=(QA/'shared-before-ocr8006.cpp').read_bytes()
    assert digest(old_cpp)==read(QA/'release8004.json')['sources']['native/local_translation.cpp'],'Baseline shared source snapshot changed'
    assert translation_code(cpp)==translation_code(old_cpp),'Shared translation implementation changed'
    runtime_sha=digest(runtime.read_bytes())
    assert runtime_sha==digest((QA/'baseline-engine/onnxruntime.dll').read_bytes()),'Inference runtime changed'
    current=read(ROOT/'assets/models/opus-en-es/manifest.json');baseline=read(QA/'baseline-engine/manifest.json')
    assets={name:current['files'][name] for name in ['encoder.onnx','decoder.onnx','tokenizer.json','terminology.json']}
    for name,sha in assets.items():
        assert baseline['files'][name]==sha and digest((ROOT/'assets/models/opus-en-es'/name).read_bytes())==sha,('Translation asset changed',name)
    signature=digest(translation_code(cpp)+json.dumps(assets,sort_keys=True).encode())
    expected_baseline=digest(old_cpp+(QA/'baseline-engine/manifest.json').read_bytes())
    baseline_directory=QA/'translated-en-final';cache={};ambiguous=set()
    fields=['prepared','translation','raw_model','terminology','source_corrections','retained_original','reason']
    for status in sorted(baseline_directory.glob('*.done.json')):
        assert read(status)['engine']==expected_baseline,'Baseline output does not use the expected shared translation implementation'
        for row in records(status.with_name(read(status)['chapter']+'.jsonl')):
            if 'error' in row or 'translation' not in row:continue
            source=row['source'];value={k:row[k] for k in fields if k in row}
            if source in cache and cache[source]['translation']!=value['translation']:ambiguous.add(source)
            cache[source]=value
    for source in ambiguous:cache.pop(source,None)
    output=QA/args.output_name;output.mkdir(exist_ok=True)
    proof={'translation_signature':signature,'shared_source_sha256':digest(cpp),'translation_code_sha256':digest(translation_code(cpp)),
        'baseline_shared_source_sha256':digest(old_cpp),'runtime_sha256':runtime_sha,'translation_assets':assets,
        'baseline_engine':expected_baseline,'baseline_directory':baseline_directory.name,'ambiguous_baseline_sources_excluded':len(ambiguous),
        'reuse_condition':'Exact source string; identical shared translation implementation and translation assets; actual previous inference only',
        'spanish_reference_used_for_translation':False,'translator_weights_changed':False,
        'binary_sha256':digest(binary.read_bytes()),'translation_source_path':str(source_path.resolve())}
    (output/'inference-provenance.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
    fresh_cache=output/'fresh-inference-cache.jsonl'
    if fresh_cache.exists():
        for line in fresh_cache.read_text(encoding='utf-8').splitlines():
            if not line.strip():continue
            try:row=json.loads(line)
            except ValueError:continue  # An interrupted append is re-inferred.
            if row.get('translation_signature')==signature:cache[row['source']]=row['result']
    model=None
    def close():
        nonlocal model
        if model is not None:model.stdin.close();model.wait(timeout=30);model=None
    def translate(source):
        nonlocal model
        if model is None:
            model=subprocess.Popen([str(binary),str(ROOT/'assets/models/opus-en-es')],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',bufsize=1,creationflags=subprocess.CREATE_NO_WINDOW)
        model.stdin.write(json.dumps({'source':source})+'\n');model.stdin.flush();line=model.stdout.readline()
        if not line:raise RuntimeError(model.stderr.read())
        result=json.loads(line)
        if 'error' in result:raise RuntimeError(result['error'])
        value={k:result[k] for k in fields if k in result}
        with fresh_cache.open('a',encoding='utf-8') as handle:handle.write('\n'+json.dumps(dict(source=source,result=value,translation_signature=signature),ensure_ascii=False)+'\n')
        cache[source]=value
        return value
    try:
        while True:
            for status in sorted((QA/args.ocr_reports).glob('*.done.json')):
                capture=read(status);chapter=capture['chapter'];engine=digest(capture['engine'].encode()+signature.encode())
                done=output/(chapter+'.done.json');report=output/(chapter+'.jsonl')
                if done.exists() and report.exists() and read(done)['engine']==engine:continue
                rows=records(status.with_name(chapter+'.jsonl'));final=[];fresh=0;reused=0
                for row in rows:
                    source=row['source'];known=source in cache
                    result=cache[source] if known else translate(source)
                    reused+=int(known);fresh+=int(not known)
                    final.append({**row,**result,'reused_identical_source_inference':known,'translation_signature':signature})
                temporary=report.with_suffix('.pending');temporary.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in final),encoding='utf-8');temporary.replace(report)
                summary={**capture,'engine':engine,'capture_ocr_engine':capture['engine'],'translation_signature':signature,'ocr_only':False,
                    'fresh_inference_records':fresh,'reused_identical_source_records':reused,'translator_weights_changed':False,
                    'all_files_traversed_by_new_ocr_binary':True,'word_review_complete':False,'semantic_accuracy':None}
                temporary=done.with_suffix('.pending');temporary.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(done)
                print('Translated',chapter,'fresh',fresh,'reused',reused,flush=True)
            close()
            reports=[read(p) for p in output.glob('*.done.json')]
            summary={'chapters':len(reports),'chapters_expected':args.expected_chapters,'fresh_inference_records':sum(r['fresh_inference_records'] for r in reports),
                'reused_identical_source_records':sum(r['reused_identical_source_records'] for r in reports),
                'word_review_complete':False,'semantic_accuracy':None,'translation_signature':signature}
            (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
            if not args.watch or len(reports)>=args.expected_chapters:break
            time.sleep(15)
    finally:close()

if __name__=='__main__':main()
