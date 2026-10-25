"""Apply the pinned 8014 native translator to every saved 8011 OCR region.

Only actual source strings are sent to inference. Reuse is limited to native
outputs from the exact 8014 binary, runtime, policy and assets. Reference
translations, annotations and expected answers are never loaded.
"""
import hashlib
import json
import subprocess
from audit_corpus_quality import ROOT, QA, CHAPTERS, read, records, digest, atomic


def main():
    seed=QA/'sentence-coverage8014';proof=read(seed/'provenance.json');seed_summary=read(seed/'summary.json')
    binary=ROOT/'build/local-model8014/Release/luma_translate.exe';assets=ROOT/'assets/models/opus-en-es'
    assert digest(binary)==proof['binary_sha256'] and digest(binary.parent/'onnxruntime.dll')==proof['runtime_sha256']
    for name,sha in proof['assets'].items():assert digest(assets/name)==sha
    assert digest(seed/'output.jsonl')==seed_summary['output_sha256']
    signature=hashlib.sha256(json.dumps({k:proof[k] for k in ['binary_sha256','runtime_sha256','source_sha256','header_sha256','coverage_policy_sha256','assets']},sort_keys=True).encode()).hexdigest()
    out=QA/'translated-en8014-fixed-ocr';out.mkdir(exist_ok=True)
    provenance=dict(translation_signature=signature,native=proof,seed_output_sha256=seed_summary['output_sha256'],
        capture_directory='ocr-en8011-context',reference_used_for_inference=False,translator_weights_changed=False,
        cache_condition='Exact source string and identical pinned 8014 inference implementation, runtime and model assets')
    pinned=out/'inference-provenance.json'
    if pinned.exists():assert read(pinned)==provenance,'Refuse mixing translation builds'
    else:atomic(pinned,json.dumps(provenance,indent=2))
    cache={r['source']:r for r in records(seed/'output.jsonl')};fresh_cache=out/'fresh-inference-cache.jsonl'
    if fresh_cache.exists():
        for r in records(fresh_cache):
            assert r['translation_signature']==signature
            cache[r['source']]=r['result']
    model=None
    def infer(source):
        nonlocal model
        if model is None:
            model=subprocess.Popen([str(binary),str(assets)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                text=True,encoding='utf-8',bufsize=1,creationflags=subprocess.CREATE_NO_WINDOW)
        model.stdin.write(json.dumps(dict(source=source))+'\n');model.stdin.flush()
        value=model.stdout.readline();assert value,'Native inference stopped'
        row=json.loads(value);assert 'error' not in row and row['source']==source,row
        with fresh_cache.open('a',encoding='utf-8') as handle:handle.write(json.dumps(dict(source=source,result=row,translation_signature=signature),ensure_ascii=False)+'\n')
        cache[source]=row;return row
    try:
        for chapter in CHAPTERS:
            chapter+='-en';capture=QA/'ocr-en8011-context'/(chapter+'.jsonl');status=read(capture.with_name(chapter+'.done.json'))
            assert status['all_files_traversed'] and status['runtime_errors']==0 and status['ocr_only']
            assert status['native_engine']=='59b87d53683e1193f3e34f0392ac892fad1d9b3dfa9ae89f05edbc9b1b853843'
            engine=hashlib.sha256((status['engine']+signature).encode()).hexdigest()
            report=out/(chapter+'.jsonl');done=out/(chapter+'.done.json')
            if done.exists():
                previous=read(done);assert previous['engine']==engine and previous['source_ocr_sha256']==digest(capture)
                assert digest(report)==previous['report_sha256'];continue
            result=[];fresh=reused=recovered=0
            for row in records(capture):
                known=row['source'] in cache;value=cache[row['source']] if known else infer(row['source'])
                result.append(dict(**{k:v for k,v in row.items() if k not in value},**value,
                    reused_identical_8014_source_inference=known,translation_signature=signature))
                reused+=int(known);fresh+=int(not known);recovered+=int(value.get('sentence_recovered',False))
            atomic(report,''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in result))
            final_status={**status,'engine':engine,'ocr_only':False,'translation_signature':signature,
                'capture_ocr_engine':status['engine'],'source_ocr_sha256':digest(capture),'report_sha256':digest(report),
                'fresh_inference_records':fresh,'reused_identical_source_records':reused,'sentence_recovered_regions':recovered,
                'translator_weights_changed':False,'semantic_accuracy':None}
            atomic(done,json.dumps(final_status,indent=2))
            reports=[read(p) for p in out.glob('*.done.json')]
            summary=dict(chapters=len(reports),chapters_expected=124,regions=sum(r['regions'] for r in reports),
                fresh_inference_records=sum(r['fresh_inference_records'] for r in reports),
                reused_identical_source_records=sum(r['reused_identical_source_records'] for r in reports),
                sentence_recovered_regions=sum(r['sentence_recovered_regions'] for r in reports),
                translation_signature=signature,ocr_held_fixed=True,all_chapter_words_visually_reviewed=False,semantic_accuracy=None)
            atomic(out/'summary.json',json.dumps(summary,indent=2))
            print('Translated',len(reports),'/ 124; fresh',fresh,'reused',reused,'recovered',recovered,flush=True)
    finally:
        if model is not None:model.stdin.close();model.wait(timeout=30)


if __name__=='__main__':main()
