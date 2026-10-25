"""Combine the pinned 8012 OCR traversal with the pinned 8014 translator.

Reuse comes exclusively from real 8014 native inference with identical source,
binary, runtime and assets. No human/reference translation is loaded.
"""
import hashlib
import json
import subprocess
import time
from audit_corpus_quality import ROOT, QA, CHAPTERS, read, records, digest, atomic


def main():
    control=QA/'translated-en8014-fixed-ocr';identity=read(control/'inference-provenance.json');native=identity['native']
    binary=ROOT/'build/local-model8014/Release/luma_translate.exe';assets=ROOT/'assets/models/opus-en-es'
    assert digest(binary)==native['binary_sha256'] and digest(binary.parent/'onnxruntime.dll')==native['runtime_sha256']
    for name,sha in native['assets'].items():assert digest(assets/name)==sha
    signature=identity['translation_signature'];source=QA/'ocr-en8012-recovery';out=QA/'translated-en8014-recovery';out.mkdir(exist_ok=True)
    proof=dict(translation_signature=signature,native=native,capture_directory=source.name,
        capture_snapshot_sha256=digest(QA/'windows-engine801201.json'),reuse_condition='Exact source; same pinned 8014 native inference, runtime and assets',
        reference_used_for_inference=False,translator_weights_changed=False)
    pinned=out/'inference-provenance.json'
    if pinned.exists():assert read(pinned)==proof
    else:atomic(pinned,json.dumps(proof,indent=2))
    cache={};fresh_cache=out/'fresh-inference-cache.jsonl';model=None
    def remember(source,row):
        assert row['source']==source and 'error' not in row
        if source in cache:assert cache[source]['translation']==row['translation'],'Ambiguous cached native output'
        cache[source]=row
    def warm():
        for row in records(QA/'sentence-coverage8014/output.jsonl'):remember(row['source'],row)
        for path in [control/'fresh-inference-cache.jsonl',fresh_cache]:
            if not path.exists():continue
            # Another native worker can be appending its final line. Only use
            # newline-terminated cache records, and retry the tail next pass.
            raw=path.read_bytes()
            if b'\n' not in raw:continue
            complete=raw.rsplit(b'\n',1)[0].decode('utf-8')
            for line in complete.splitlines():
                if not line.strip():continue
                row=json.loads(line);assert row['translation_signature']==signature
                remember(row['source'],row['result'])
    def close():
        nonlocal model
        if model is not None:model.stdin.close();model.wait(timeout=30);model=None
    def infer(text):
        nonlocal model
        if model is None:model=subprocess.Popen([str(binary),str(assets)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
        model.stdin.write(json.dumps(dict(source=text))+'\n');model.stdin.flush()
        line=model.stdout.readline();assert line,'Native translator stopped'
        row=json.loads(line);remember(text,row)
        with fresh_cache.open('a',encoding='utf-8') as handle:handle.write(json.dumps(dict(source=text,result=row,translation_signature=signature),ensure_ascii=False)+'\n')
        return row
    try:
        while True:
            warm()
            for chapter in CHAPTERS:
                chapter+='-en';capture=source/(chapter+'.jsonl');status_path=source/(chapter+'.done.json')
                if not status_path.exists():continue
                status=read(status_path);assert status['all_files_traversed'] and not status['runtime_errors'] and status['ocr_only']
                assert status['native_engine']=='769e45816118cc1a494071584fde5a90ef9a73cb78366dec52760502d3cc1101'
                engine=hashlib.sha256((status['engine']+signature).encode()).hexdigest();report=out/(chapter+'.jsonl');done=out/(chapter+'.done.json')
                if done.exists():
                    previous=read(done);assert previous['engine']==engine and previous['source_ocr_sha256']==digest(capture)
                    assert digest(report)==previous['report_sha256'];continue
                rows=[];fresh=reused=recovered=0
                for row in records(capture):
                    known=row['source'] in cache;result=cache[row['source']] if known else infer(row['source'])
                    rows.append({**row,**result,'reused_identical_8014_source_inference':known,'translation_signature':signature})
                    fresh+=int(not known);reused+=int(known);recovered+=int(result.get('sentence_recovered',False))
                atomic(report,''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
                result_status={**status,'engine':engine,'ocr_only':False,'translation_signature':signature,'capture_ocr_engine':status['engine'],
                    'source_ocr_sha256':digest(capture),'report_sha256':digest(report),'fresh_inference_records':fresh,'reused_identical_source_records':reused,
                    'sentence_recovered_regions':recovered,'translator_weights_changed':False,'word_review_complete':False,'semantic_accuracy':None}
                atomic(done,json.dumps(result_status,indent=2));print('Combined OCR and NMT:',len(list(out.glob('*.done.json'))),'/ 124;',fresh,'fresh,',reused,'reused',flush=True)
            close();reports=[read(p) for p in out.glob('*.done.json')]
            summary=dict(chapters=len(reports),chapters_expected=124,regions=sum(r['regions'] for r in reports),
                fresh_inference_records=sum(r['fresh_inference_records'] for r in reports),reused_identical_source_records=sum(r['reused_identical_source_records'] for r in reports),
                translation_signature=signature,capture_snapshot_sha256=proof['capture_snapshot_sha256'],
                all_chapter_words_visually_reviewed=False,semantic_accuracy=None)
            atomic(out/'summary.json',json.dumps(summary,indent=2))
            if len(reports)==124:break
            time.sleep(20)
    finally:close()


if __name__=='__main__':main()
