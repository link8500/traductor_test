"""Fresh native inferences verify safeguards on the union of both broad cohorts."""
import json
import subprocess
from audit_corpus_quality import ROOT,QA,atomic,digest,read,records


def main():
    out=QA/'production-coverage8019';out.mkdir(exist_ok=True)
    old=QA/'production-coverage8018/output.jsonl';paired=QA/'full-corpus-coverage8018/paired-inferences.jsonl'
    baseline={r['source']:r for r in records(old)}
    for row in records(paired):
        if row['variant']!='after':continue
        result=row['result'];source=result['source']
        if source in baseline:assert baseline[source]['translation']==result['translation']
        baseline[source]=result
    guard=ROOT/'build/coverage-guard8019/compiled/Release/luma_guard.exe'
    guard_pin=read(QA/'full-corpus-coverage8019/guard-provenance.json')
    assert digest(guard)==guard_pin['binary_sha256'] and digest(ROOT/'native/translation_coverage.h')==guard_pin['policy_sha256']
    manifest=out/'candidate-input.jsonl';atomic(manifest,''.join(json.dumps(r)+'\n' for r in baseline.values()))
    expected_path=out/'guarded-expectations.jsonl'
    with manifest.open('rb') as src,expected_path.open('wb') as dest:subprocess.run([str(guard)],stdin=src,stdout=dest,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    expected={r['source']:r for r in records(expected_path)}
    binary=ROOT/'build/local-model8019/Release/luma_translate.exe'
    guards=json.loads(subprocess.check_output([str(binary.with_name('luma_coverage_test.exe'))],text=True,creationflags=subprocess.CREATE_NO_WINDOW))
    pin=out/'provenance.json'
    proof=dict(binary_sha256=digest(binary),runtime_sha256=digest(binary.parent/'onnxruntime.dll'),
        source_sha256=digest(ROOT/'native/local_translation.cpp'),policy_sha256=digest(ROOT/'native/translation_coverage.h'),
        guard_executable_sha256=digest(guard),candidate_manifest_sha256=digest(manifest),expected_outputs_sha256=digest(expected_path),
        baseline_native_outputs_sha256=digest(old),broader_native_outputs_sha256=digest(paired),
        assets={name:digest(ROOT/'assets/models/opus-en-es'/name) for name in ['encoder.onnx','decoder.onnx','tokenizer.json','terminology.json']},
        reference_or_manual_answers_supplied=False,model_weights_changed=False)
    if pin.exists():assert read(pin)==proof
    else:atomic(pin,json.dumps(proof,indent=2))
    target=out/'output.jsonl';complete={r['source']:r for r in records(target)} if target.exists() else {}
    assert set(complete)<=set(expected);model=None
    try:
        for source in expected:
            if source in complete:continue
            if model is None:model=subprocess.Popen([str(binary),str(ROOT/'assets/models/opus-en-es')],stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
            model.stdin.write(json.dumps(dict(source=source))+'\n');model.stdin.flush();line=model.stdout.readline();assert line,'Native translator stopped'
            row=json.loads(line);assert row['source']==source and 'error' not in row
            with target.open('a',encoding='utf-8') as handle:handle.write(json.dumps(row,ensure_ascii=False)+'\n')
            complete[source]=row
            if len(complete)%50==0:print('Fresh guarded production:',len(complete),'/',len(expected),flush=True)
    finally:
        if model is not None:model.stdin.close();model.wait(timeout=30)
    disagreements=[dict(source=s,expected=e['guarded_translation'],actual=complete[s]['translation']) for s,e in expected.items()
        if complete[s]['translation']!=e['guarded_translation']]
    changes=[dict(source=s,before_translation=baseline[s]['translation'],translation=complete[s]['translation'],reason=expected[s]['guard_reason'])
        for s in expected if baseline[s]['translation']!=complete[s]['translation']]
    summary=dict(unique_source_inputs=len(expected),fresh_production_inferences=len(complete),
        safeguards_blocked_recoveries=sum(not r['recovery_accepted'] for r in expected.values()),
        outputs_changed_from_unguarded_trial=len(changes),changes=changes,guard_plan_disagreements=disagreements,
        native_guards=guards,provenance_sha256=digest(pin),output_sha256=digest(target),
        screen_attempt_failure_probability=None,all_chapter_words_visually_reviewed=False,model_weights_changed=False)
    atomic(out/'summary.json',json.dumps(summary,ensure_ascii=False,indent=2));assert not disagreements,'See recorded native disagreements'
    print(json.dumps({k:v for k,v in summary.items() if k!='changes'}),flush=True)


if __name__=='__main__':main()
