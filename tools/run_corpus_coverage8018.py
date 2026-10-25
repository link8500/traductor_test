"""Compare both production policies over all124 completed frozen OCR reports.

Only the retry branch changed. Sources where neither policy retries retain
the real common whole-model inference. All other sources use both actual
native translators, with exact-source model-output reuse pinned separately.
"""
import argparse
import hashlib
import json
import subprocess
from audit_corpus_quality import ROOT,QA,CHAPTERS,atomic,digest,read,records


def complete_records(path):
    if not path.exists():return []
    raw=path.read_bytes();raw=raw[:raw.rfind(b'\n')+1]
    return [json.loads(line) for line in raw.decode('utf-8').splitlines() if line.strip()]


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan-only',action='store_true');args=parser.parse_args()
    out=QA/'full-corpus-coverage8018';out.mkdir(exist_ok=True)
    plan_root=ROOT/'build/coverage-plan8018';plan=plan_root/'compiled/Release/luma_plan.exe';plan_proof=read(plan_root/'proof.json')
    assert digest(plan)==plan_proof['binary_sha256']
    before_binary=ROOT/'build/local-model8016/Release/luma_translate.exe';after_binary=ROOT/'build/local-model8018/Release/luma_translate.exe'
    before_proof=read(QA/'production-coverage8016/provenance.json');after_proof=read(QA/'production-coverage8018/provenance.json')
    assert digest(before_binary)==before_proof['binary_sha256'] and digest(after_binary)==after_proof['binary_sha256']
    assert before_proof['assets']==after_proof['assets'] and before_proof['runtime_sha256']==after_proof['runtime_sha256']
    original=(ROOT/'native/local_translation.cpp').read_text(encoding='utf-8').replace('    if(!coverage::Plausible(part,translated.text))return result;\n','')
    assert hashlib.sha256(original.replace('\n','\r\n').encode()).hexdigest()==before_proof['source_sha256']
    assert digest(ROOT/'native/translation_coverage.h')==plan_proof['after_policy_sha256']==after_proof['policy_sha256']
    inputs=[];old_rows={};chapters={}
    for chapter in CHAPTERS:
        path=QA/'translated-en8014-recovery'/(chapter+'-en.jsonl');status_path=path.with_name(path.stem+'.done.json');status=read(status_path)
        assert status['all_files_traversed'] and not status['runtime_errors']
        chapters[chapter]=dict(report_sha256=digest(path),status_sha256=digest(status_path))
        for index,row in enumerate(records(path)):
            old_rows[(chapter,index)]=row
            inputs.append(dict(chapter=chapter,region=index,source=row['source'],whole_translation=row.get('whole_translation',row['translation'])))
    manifest=out/'plan-input.jsonl';atomic(manifest,''.join(json.dumps(r)+'\n' for r in inputs));target=out/'plan-output.jsonl'
    if not target.exists():
        with manifest.open('rb') as src,target.open('wb') as dest:subprocess.run([str(plan)],stdin=src,stdout=dest,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    planned=records(target);assert len(planned)==len(inputs)==18179
    assert all(all(a[k]==b[k] for k in ['chapter','region','source','whole_translation']) for a,b in zip(planned,inputs))
    selected={r['source'] for r in planned if r['selected']}
    proof=dict(plan_proof_sha256=digest(plan_root/'proof.json'),plan_input_sha256=digest(manifest),plan_output_sha256=digest(target),
        before_native_proof_sha256=digest(QA/'production-coverage8016/provenance.json'),after_native_proof_sha256=digest(QA/'production-coverage8018/provenance.json'),
        before_binary_sha256=digest(before_binary),after_binary_sha256=digest(after_binary),chapters=chapters,
        reference_or_manual_answers_supplied=False,model_weights_changed=False,
        unchanged_reuse_condition='Exact source, identical whole-model implementation/runtime/assets; neither old nor new coverage policy retries')
    pin=out/'provenance.json'
    if pin.exists():assert read(pin)==proof
    else:atomic(pin,json.dumps(proof,indent=2))
    print(json.dumps(dict(chapters=124,source_locations=len(inputs),selected_regions=sum(r['selected'] for r in planned),unique_selected_sources=len(selected))),flush=True)
    if args.plan_only:return
    output=out/'paired-inferences.jsonl';done={(r['variant'],r['result']['source']):r for r in records(output)} if output.exists() else {}
    before_cache={r['source']:r for r in records(QA/'production-coverage8016/output.jsonl')}
    after_cache={r['source']:r for r in complete_records(QA/'production-coverage8018/output.jsonl')}
    fresh=0
    for variant,binary,cache in [('before',before_binary,before_cache),('after',after_binary,after_cache)]:
        model=None
        try:
            for source in sorted(selected):
                if (variant,source) in done:continue
                reused=source in cache
                if reused:result=cache[source]
                else:
                    if model is None:model=subprocess.Popen([str(binary),str(ROOT/'assets/models/opus-en-es')],stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
                    model.stdin.write(json.dumps(dict(source=source))+'\n');model.stdin.flush();line=model.stdout.readline();assert line,'Native translator stopped'
                    result=json.loads(line);assert 'error' not in result and result['source']==source;fresh+=1
                row=dict(variant=variant,result=result,reused_identical_native_source=reused,binary_sha256=digest(binary))
                with output.open('a',encoding='utf-8') as handle:handle.write(json.dumps(row,ensure_ascii=False)+'\n')
                done[(variant,source)]=row
                if len(done)%25==0:print('Paired native results:',len(done),'/',len(selected)*2,flush=True)
        finally:
            if model is not None:model.stdin.close();model.wait(timeout=30)
    changes=[];retained=0
    for row in planned:
        if not row['selected']:retained+=1;continue
        before=done[('before',row['source'])]['result'];after=done[('after',row['source'])]['result']
        if before['translation']==after['translation']:continue
        old=old_rows[(row['chapter'],row['region'])]
        changes.append(dict(chapter=row['chapter'],region=row['region'],image=old['image'],bounds=old['bounds'],source=row['source'],
            before_translation=before['translation'],translation=after['translation'],meaning_reviewed=False))
    atomic(out/'changed.json',json.dumps(dict(cases=changes),ensure_ascii=False,indent=2))
    value=dict(chapters_scanned=124,source_locations=18179,native_plan_selected_regions=sum(r['selected'] for r in planned),
        unique_selected_sources=len(selected),paired_source_results=len(done),fresh_native_inferences=sum(not r['reused_identical_native_source'] for r in done.values()),
        reused_identical_native_results=sum(r['reused_identical_native_source'] for r in done.values()),
        whole_model_results_retained_without_retry=retained,changed_regions=len(changes),
        changed_meanings_reviewed=False,screen_attempt_failure_probability=None,all_chapter_words_visually_reviewed=False,
        provenance_sha256=digest(pin),paired_inferences_sha256=digest(output),changed_sha256=digest(out/'changed.json'))
    atomic(out/'summary.json',json.dumps(value,indent=2));print(json.dumps(value),flush=True)


if __name__=='__main__':main()
