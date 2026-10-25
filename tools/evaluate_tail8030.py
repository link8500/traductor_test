"""Scan124 complete controls, then test tail recovery with source-only native MT.

Planning uses captured English and prior app output, never reference answers.
All native batches are resumable and outputs remain unapproved until reviewed.
"""
import hashlib
import json
import pathlib
import shutil
import subprocess

from audit_corpus_quality import ROOT, QA, atomic, digest, read, records
from quality_resources import wait_for_inference_memory
from translation_quality_signals import PROMOTION, signals


def main():
    folder=QA/'tail8030';folder.mkdir(exist_ok=True)
    policy=ROOT/'build/local-model8030/Release/luma_translation_tail_candidate.exe'
    guards=json.loads(subprocess.check_output([str(policy),'--self-test'],text=True,creationflags=subprocess.CREATE_NO_WINDOW))
    sample=folder/'sample.json'
    if not sample.exists():
        inputs=[];reports={};paths=sorted((QA/'translated-en8017-geometry').glob('*.done.json'));assert len(paths)==124
        for done in paths:
            status=read(done);assert status['all_files_traversed'] and not status['runtime_errors']
            path=done.with_name(done.name.replace('.done.json','.jsonl'));reports[path.name]=digest(path)
            for index,r in enumerate(records(path)):
                if PROMOTION.search(r.get('source','')):continue
                inputs.append(dict(id=len(inputs)+1,report=path.name,report_row=index,image=r['image'],bounds=r['bounds'],
                                   source=r['source'],translation=r['translation'],retained_original=r.get('retained_original',False),
                                   automatic_alert=bool(signals(r))))
        text=''.join(json.dumps(r)+'\n' for r in inputs)
        planned=subprocess.run([str(policy),'--plan'],input=text,text=True,encoding='utf-8',capture_output=True,
                               check=True,creationflags=subprocess.CREATE_NO_WINDOW)
        actual=[json.loads(s) for s in planned.stdout.splitlines() if s.strip()];assert len(actual)==len(inputs)
        eligible=[r for r in actual if r['eligible']]
        for i,r in enumerate(eligible):r['global_source_id']=r['id'];r['id']=i+1
        value=dict(chapters_scanned=124,meaningful_or_nonpromotional_rows_scanned=len(inputs),cases=eligible,reports=reports,
                   planning_input_sha256=hashlib.sha256(text.encode()).hexdigest(),
                   planning_output_sha256=hashlib.sha256(planned.stdout.encode()).hexdigest(),
                   policy_sha256=digest(policy),policy_header_sha256=digest(ROOT/'native/translation_tail_candidate.h'),
                   selection='Question deficit or short fewer-sentence output with a captured complete final clause',
                   sample_is_diagnostic_not_population_estimate=True,all_chapter_words_visually_reviewed=False)
        atomic(sample,json.dumps(value,ensure_ascii=False,indent=2))
    frozen=read(sample);assert frozen['policy_sha256']==digest(policy)
    for name,expected in frozen['reports'].items():assert digest(QA/'translated-en8017-geometry'/name)==expected
    inputs=[];ids={}
    for case in frozen['cases']:
        for key in ['source','head_source','tail_source']:
            source=case[key]
            if source not in ids:ids[source]=len(inputs)+1;inputs.append(dict(id=ids[source],image=0,bounds=[0,0,1,1],source=source))
    binary=QA/'frozen-windows802901/traductor.exe';snapshot=QA/'windows-engine802901.json'
    assert digest(binary)==read(snapshot)['binary_sha256']
    proof=dict(binary_sha256=digest(binary),snapshot_sha256=digest(snapshot),sample_sha256=digest(sample),
               policy_sha256=digest(policy),source_only_model_input=True,manual_or_reference_answers_supplied=False,
               model_weights_changed=False,new_ocr_inference=False,fresh_capture=False,production_modified=False)
    pin=folder/'provenance.json'
    if pin.exists():assert read(pin)==proof
    else:atomic(pin,json.dumps(proof,indent=2))
    actual=[]
    for start in range(0,len(inputs),64):
        n=start//64;part=inputs[start:start+64];manifest=folder/f'batch-{n:02d}.input.jsonl';target=folder/f'batch-{n:02d}.jsonl'
        contents=''.join(json.dumps(r)+'\n' for r in part)
        if manifest.exists():assert manifest.read_text(encoding='utf-8')==contents
        else:atomic(manifest,contents)
        status=pathlib.Path(str(target)+'.summary.json')
        if not status.exists():
            assert shutil.disk_usage(folder).free>=4*1024**3
            wait_for_inference_memory(minimum_free_bytes=5*1024**3//2)
            with (folder/f'batch-{n:02d}.log').open('ab') as log:
                subprocess.run([str(binary),'--translation-replay',str(manifest),str(target)],check=True,
                               creationflags=subprocess.CREATE_NO_WINDOW,stdout=log,stderr=log,timeout=1800)
        rows=records(target);assert len(rows)==len(part) and all('error' not in r for r in rows)
        assert read(status)['runtime_errors']==0
        assert [(r['id'],r['source']) for r in rows]==[(r['id'],r['source']) for r in part]
        actual.extend(rows)
        print(json.dumps(dict(state='native_mt',records_completed=len(actual),records_expected=len(inputs),candidates=len(frozen['cases']))),flush=True)
    by_source={r['source']:r for r in actual};policy_inputs=[]
    for c in frozen['cases']:
        whole,head,tail=[by_source[c[k]] for k in ['source','head_source','tail_source']]
        policy_inputs.append(dict(id=c['id'],source=c['source'],translation=whole['translation'],
                                  head_translation=head['translation'],tail_translation=tail['translation'],
                                  retained_original=whole['retained_original'],head_retained=head['retained_original'],tail_retained=tail['retained_original']))
    contents=''.join(json.dumps(r)+'\n' for r in policy_inputs);atomic(folder/'policy-input.jsonl',contents)
    result=subprocess.run([str(policy)],input=contents,text=True,encoding='utf-8',capture_output=True,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    atomic(folder/'policy-output.jsonl',result.stdout)
    selected=[json.loads(s) for s in result.stdout.splitlines() if s.strip()]
    changes=[dict(c,policy=r,native={k:by_source[c[k]] for k in ['source','head_source','tail_source']},meaning_reviewed=False)
             for c,r in zip(frozen['cases'],selected) if r['tail_recovered']]
    atomic(folder/'changes.json',json.dumps(changes,ensure_ascii=False,indent=2))
    value=dict(chapters_scanned=124,candidates=len(frozen['cases']),candidates_without_automatic_alert=sum(not c['automatic_alert'] for c in frozen['cases']),
               actual_native_output_records=len(actual),changed_regions=len(changes),runtime_errors=0,native_guards=guards,
               policy_output_sha256=digest(folder/'policy-output.jsonl'),changes_sha256=digest(folder/'changes.json'),
               provenance_sha256=digest(pin),production_modified=False,all_changed_meanings_reviewed=False,
               all_chapter_words_visually_reviewed=False,screen_attempt_failure_probability=None,target_achieved=False)
    atomic(folder/'summary.json',json.dumps(value,indent=2));print(json.dumps(value),flush=True)


if __name__=='__main__':main()
