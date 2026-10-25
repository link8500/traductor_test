"""Fresh native trial on the fixed, previously inspected 744 OCR locations.

Only English source strings enter the executable. Spanish pixels, old output
and semantic judgments are used afterwards to prepare a pending review.
"""
import json
import pathlib
import subprocess
import time
import prepare_corpus_review_sample as sheets
from audit_corpus_quality import ROOT,QA,read,records,digest,atomic


def main():
    out=QA/'sentence-coverage8016';out.mkdir(exist_ok=True)
    build_path=ROOT/'build/coverage8016/build.json';build=read(build_path)
    binary=ROOT/'build/coverage8016/compiled/Release/luma_translate.exe'
    assert digest(binary)==build['binary_sha256']
    base_path=ROOT/'benchmarks/full-comics/coverage8014-six-regions-semantic-review.json';base=read(base_path)
    location_path=ROOT/'benchmarks/full-comics/current8011-six-regions-semantic-review.json';locations={r['id']:r for r in read(location_path)['entries']}
    sources={}
    for row in base['entries']:
        if row['source'] in sources:assert sources[row['source']]==row['translation']
        sources[row['source']]=row['translation']
    manifest=out/'input.jsonl';output=out/'output.jsonl'
    atomic(manifest,''.join(json.dumps(dict(source=source))+'\n' for source in sources))
    proof=dict(build_sha256=digest(build_path),**build,base_review_sha256=digest(base_path),location_review_sha256=digest(location_path),
        input_sha256=digest(manifest),assets={name:digest(ROOT/'assets/models/opus-en-es'/name) for name in ['encoder.onnx','decoder.onnx','tokenizer.json','terminology.json']})
    proof_path=out/'provenance.json'
    if proof_path.exists():assert read(proof_path)==proof,'Refuse mixing trial versions'
    else:atomic(proof_path,json.dumps(proof,indent=2))
    completed={r['source']:r for r in records(output)} if output.exists() else {}
    assert set(completed)<=set(sources)
    model=None;started=time.monotonic()
    try:
        for source in sources:
            if source in completed:continue
            if model is None:model=subprocess.Popen([str(binary),str(ROOT/'assets/models/opus-en-es')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
            model.stdin.write(json.dumps(dict(source=source))+'\n');model.stdin.flush()
            line=model.stdout.readline();assert line,'Missing native output'
            row=json.loads(line);assert row['source']==source
            with output.open('a',encoding='utf-8') as handle:handle.write(json.dumps(row,ensure_ascii=False)+'\n')
            completed[source]=row
            if len(completed)%25==0:print('Fresh trial inputs:',len(completed),'/',len(sources),flush=True)
    finally:
        if model is not None:model.stdin.close();model.wait(timeout=30)
    templates={}
    for group,name in [('a','current8011-full-a'),('b','current8011-full-b'),('short','corpus-review-short8011'),('next','corpus-review-next8011'),('sixth','corpus-review-sixth8011')]:
        for case in read(QA/name/'sample.json')['cases']:templates[(group,case['id'])]=case
    changed=[]
    for old in base['entries']:
        row=completed[old['source']]
        if row.get('translation')==old['translation']:continue
        location=locations[old['id']];template=templates[(location['group'],location['original_id'])]
        changed.append(dict(template,id=len(changed)+1,original_id=old['id'],source=old['source'],before_translation=old['translation'],translation=row.get('translation',''),
            before_judgment=old['after'],native_error=row.get('error'),candidate_inference=row,meaning_reviewed=False))
    review=out/'visual-review';review.mkdir(exist_ok=True)
    sample=dict(cases=changed,chapters=len({c['chapter'] for c in changed}),reviewed_locations=len(base['entries']),unique_inferences=len(sources),
        changed_outputs=len(changed),base_review_sha256=digest(base_path),native_output_sha256=digest(output),all_chapter_words_visually_reviewed=False)
    atomic(review/'sample.json',json.dumps(sample,ensure_ascii=False,indent=2));sheets.OUT=review;sheets.render(sample,100,90)
    value=dict(locations=len(base['entries']),unique_fresh_native_inferences=len(sources),changed_outputs=len(changed),
        native_errors=sum('error' in r for r in completed.values()),retained_original=sum(r.get('retained_original',False) for r in completed.values()),
        application_modified=False,translator_weights_changed=False,reference_used_for_inference=False,
        semantic_accuracy=None,all_chapter_words_visually_reviewed=False,base_review_sha256=digest(base_path),input_sha256=digest(manifest),
        output_sha256=digest(output),provenance_sha256=digest(proof_path),seconds_this_run=round(time.monotonic()-started,2))
    atomic(out/'summary.json',json.dumps(value,indent=2));print(json.dumps(value),flush=True)


if __name__=='__main__':main()
