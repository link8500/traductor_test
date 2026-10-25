"""Plan all source/output pairs, then infer only newly affected policy branches."""
import argparse
import json
import subprocess
from audit_corpus_quality import ROOT,QA,atomic,digest,read,records


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--guard-repetitions',action='store_true')
    args=parser.parse_args()
    out=QA/('short-clause8017-guarded' if args.guard_repetitions else 'short-clause8017');out.mkdir(exist_ok=True)
    build=ROOT/('build/coverage8017-guarded' if args.guard_repetitions else 'build/coverage8017');proof=read(build/'build.json')
    binary=build/'compiled/Release/luma_translate.exe';plan=binary.with_name('luma_short_clause_plan.exe')
    assert digest(binary)==proof['binary_sha256'] and digest(plan)==proof['plan_binary_sha256']
    sources={};inputs=[]
    input_files=[QA/'production-coverage8016/output.jsonl',QA/'windows8016-heldout-pixels/output.jsonl']
    for cohort,path in zip(['fixed_prior_sample','actual_windows_heldout'],input_files):
        for index,row in enumerate(records(path)):
            key=f'{cohort}:{index}'
            inputs.append(dict(id=key,cohort=cohort,source=row['source'],translation=row.get('whole_translation',row['translation'])))
            sources[key]=row
    manifest=out/'plan-input.jsonl';target=out/'plan-output.jsonl'
    atomic(manifest,''.join(json.dumps(r)+'\n' for r in inputs))
    with manifest.open('rb') as src,target.open('wb') as dest:
        subprocess.run([str(plan)],stdin=src,stdout=dest,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    plans=records(target);assert len(plans)==1008
    selected=[r for r in plans if r['policy_changed'] and r['candidate_retry']]
    unique=sorted({r['source'] for r in selected});output=out/'inferences.jsonl'
    identity=dict(build_sha256=digest(build/'build.json'),binary_sha256=digest(binary),
        plan_input_sha256=digest(manifest),plan_output_sha256=digest(target),
        actual_source_files_sha256={p.relative_to(ROOT).as_posix():digest(p) for p in input_files},
        reference_or_manual_answers_supplied=False,model_weights_changed=False,application_modified=False)
    identity_path=out/'provenance.json'
    if identity_path.exists():assert read(identity_path)==identity
    else:atomic(identity_path,json.dumps(identity,indent=2))
    cache={r['source']:r for r in records(output)} if output.exists() else {}
    assert set(cache)<=set(unique);model=None
    try:
        for source in unique:
            if source in cache:continue
            if model is None:model=subprocess.Popen([str(binary),str(ROOT/'assets/models/opus-en-es')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
            model.stdin.write(json.dumps(dict(source=source))+'\n');model.stdin.flush()
            line=model.stdout.readline();assert line,'Native candidate stopped'
            result=json.loads(line);assert result['source']==source and 'error' not in result
            with output.open('a',encoding='utf-8') as handle:handle.write(json.dumps(result,ensure_ascii=False)+'\n')
            cache[source]=result
            print('Fresh short-clause candidates:',len(cache),'/',len(unique),flush=True)
    finally:
        if model is not None:model.stdin.close();model.wait(timeout=30)
    changed=[]
    for row in selected:
        old=sources[row['id']];new=cache[row['source']]
        if old['translation']==new['translation']:continue
        changed.append(dict(id=row['id'],cohort=row['cohort'],image=old.get('image'),
            source=old['source'],before_translation=old['translation'],translation=new['translation'],
            native_candidate=new,meaning_reviewed=False))
    value=dict(input_locations_planned=len(inputs),newly_affected_locations=len(selected),
        unique_fresh_native_inferences=len(unique),changed_outputs=len(changed),
        application_modified=False,weights_changed=False,reference_used_for_inference=False,
        screen_attempt_failure_probability=None,all_changed_outputs_semantically_reviewed=False,
        provenance_sha256=digest(identity_path),output_sha256=digest(output),changes=changed)
    atomic(out/'summary.json',json.dumps(value,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in value.items() if k!='changes'}),flush=True)


if __name__=='__main__':main()
