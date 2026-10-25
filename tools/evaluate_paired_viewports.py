"""Translate the actual old/new OCR for the exact same 124 screen captures.

Only byte-identical source inference from an identical NMT implementation can
be reused. No expected text, reference images, or judgments enter inference.
"""
import collections
import hashlib
import json
import subprocess
from pathlib import Path
from audit_corpus_quality import ROOT, QA, CURRENT, read, records, digest, atomic
from translate_ocr_reports import translation_code


def main():
    folder=QA/'recovery-viewports801201';out=folder/'paired-evaluation';out.mkdir(exist_ok=True)
    control=folder/'paired-control801101'
    proof=read(control/'done.json')
    assert digest(control/'output.jsonl')==proof['output_sha256']
    provenance=read(QA/CURRENT/'inference-provenance.json')
    assert hashlib.sha256(translation_code((ROOT/'native/local_translation.cpp').read_bytes())).hexdigest()==provenance['translation_code_sha256']
    assert digest(ROOT/'build/local-model/Release/onnxruntime.dll')==provenance['runtime_sha256']
    for name,sha in provenance['translation_assets'].items():assert digest(ROOT/'assets/models/opus-en-es'/name)==sha
    signature=provenance['translation_signature'];cache={};ambiguous=set()
    def remember(source,translation):
        if source in cache and cache[source]!=translation:ambiguous.add(source)
        cache[source]=translation
    for path in sorted((QA/CURRENT).glob('*-en.jsonl')):
        for row in records(path):
            assert row['translation_signature']==signature
            remember(row['source'],row['translation'])
    for path in sorted((folder/'evaluation').glob('[0-9][0-9][0-9].json')):
        report=read(path);assert report['translation_signature']==signature
        for case in report['cases']:remember(case['source'],case['inference']['translation'])
    cache_path=out/'fresh-inference.jsonl'
    if cache_path.exists():
        for row in records(cache_path):
            assert row['translation_signature']==signature
            remember(row['source'],row['inference']['translation'])
    for source in ambiguous:cache.pop(source,None)
    by_image=collections.defaultdict(list)
    for row in records(control/'output.jsonl'):by_image[row['image']].append(row)
    model=None;fresh=0;reused=0
    def translate(source):
        nonlocal model,fresh,reused
        if source in cache:reused+=1;return cache[source]
        if model is None:
            model=subprocess.Popen([str(ROOT/'build/local-model/Release/luma_translate.exe'),str(ROOT/'assets/models/opus-en-es')],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
        model.stdin.write(json.dumps(dict(source=source))+'\n');model.stdin.flush()
        line=model.stdout.readline();assert line,'Missing native translation'
        result=json.loads(line);assert 'error' not in result,result
        with cache_path.open('a',encoding='utf-8') as handle:
            handle.write(json.dumps(dict(source=source,inference=result,translation_signature=signature),ensure_ascii=False)+'\n')
        cache[source]=result['translation'];fresh+=1;return result['translation']
    cases=[]
    try:
        for index in range(1,125):
            old=by_image[index];new_path=folder/f'{index:03d}.jsonl';new=records(new_path)
            status=read(folder/f'{index:03d}.done.json')
            assert digest(new_path)==status['source_output_sha256']
            assert len(old)==len(new),(index,len(old),len(new))
            result_path=out/f'{index:03d}.json';pairs=[]
            for n,(before,after) in enumerate(zip(old,new)):
                assert all(before.get(k)==after.get(k) for k in ['native_source','native_words','additional_detection','cropTop'])
                changed=before['source']!=after['source'] or before['bounds']!=after['bounds']
                assert not changed or after.get('paragraph_recovered'),(index,n)
                pairs.append(dict(region_index=n,before=dict(before,translation=translate(before['source'])),
                    after=dict(after,translation=translate(after['source'])),source_or_bounds_changed=changed))
            value=dict(viewport_id=index,status=status,old_full_control_sha256=proof['output_sha256'],
                new_output_sha256=digest(new_path),translation_signature=signature,reference_used_for_inference=False,
                full_chapter_review=False,cases=pairs)
            atomic(result_path,json.dumps(value,ensure_ascii=False,indent=2));cases.extend(pairs)
            print('Paired screens translated:',index,'/124;',len(pairs),'regions',flush=True)
    finally:
        if model is not None:model.stdin.close();model.wait(timeout=30)
    summary=dict(viewports=124,regions=len(cases),changed_source_or_bounds=sum(c['source_or_bounds_changed'] for c in cases),
        changed_translations=sum(c['before']['translation']!=c['after']['translation'] for c in cases),
        fresh_inferences_this_run=fresh,reused_identical_source_inferences_this_run=reused,
        translation_signature=signature,root_nmt_binary_sha256=digest(ROOT/'build/local-model/Release/luma_translate.exe'),
        all_words_visually_reviewed=False,semantic_accuracy=None,full_chapter_traversal=False)
    atomic(out/'summary.json',json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
