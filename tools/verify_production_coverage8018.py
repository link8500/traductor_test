"""Fresh production inference on all prior sources, including unchanged ones.

Expected output is used only after inference. Original pixels/reference text
and manual answers never enter the translator's input stream.
"""
import json
import subprocess
from audit_corpus_quality import ROOT,QA,atomic,digest,read,records


def main():
    out=QA/'production-coverage8018';out.mkdir(exist_ok=True)
    binary=ROOT/'build/local-model8018/Release/luma_translate.exe'
    files=[QA/'production-coverage8016/output.jsonl',QA/'windows8016-heldout-pixels/output.jsonl',
           QA/'windows8017-render-heldout-pixels/output.jsonl']
    baseline={};locations=0
    for path in files:
        for row in records(path):
            locations+=1
            if row['source'] in baseline:assert baseline[row['source']]['translation']==row['translation']
            baseline[row['source']]=row
    candidate_path=QA/'short-clause8017-guarded/inferences.jsonl'
    candidate={r['source']:r for r in records(candidate_path)}
    assert set(candidate)<=set(baseline)
    inputs=out/'input.jsonl';target=out/'output.jsonl'
    atomic(inputs,''.join(json.dumps(dict(source=s))+'\n' for s in baseline))
    guards=json.loads(subprocess.check_output([str(binary.with_name('luma_coverage_test.exe'))],text=True))
    proof=dict(binary_sha256=digest(binary),runtime_sha256=digest(binary.parent/'onnxruntime.dll'),
        source_sha256=digest(ROOT/'native/local_translation.cpp'),policy_sha256=digest(ROOT/'native/translation_coverage.h'),
        input_sha256=digest(inputs),baseline_source_files_sha256={p.relative_to(ROOT).as_posix():digest(p) for p in files},
        frozen_candidate_output_sha256=digest(candidate_path),
        assets={name:digest(ROOT/'assets/models/opus-en-es'/name) for name in ['encoder.onnx','decoder.onnx','tokenizer.json','terminology.json']},
        original_pixels_or_reference_answers_supplied=False,model_weights_changed=False)
    pin=out/'provenance.json'
    if pin.exists():assert read(pin)==proof
    else:atomic(pin,json.dumps(proof,indent=2))
    complete={r['source']:r for r in records(target)} if target.exists() else {}
    assert set(complete)<=set(baseline)
    model=None
    try:
        for source in baseline:
            if source in complete:continue
            if model is None:model=subprocess.Popen([str(binary),str(ROOT/'assets/models/opus-en-es')],stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
            model.stdin.write(json.dumps(dict(source=source))+'\n');model.stdin.flush()
            line=model.stdout.readline();assert line,'Production translator stopped'
            row=json.loads(line);assert row['source']==source and 'error' not in row
            with target.open('a',encoding='utf-8') as handle:handle.write(json.dumps(row,ensure_ascii=False)+'\n')
            complete[source]=row
            if len(complete)%50==0:print('Fresh production coverage:',len(complete),'/',len(baseline),flush=True)
    finally:
        if model is not None:model.stdin.close();model.wait(timeout=30)
    expected_fields=['translation','prepared','raw_model','sentence_recovered','whole_translation','sentence_sources',
        'sentence_translations','terminology','source_corrections','retained_original']
    disagreements=[dict(source=s,fields=[k for k in expected_fields if complete[s].get(k)!=row.get(k)])
        for s,row in candidate.items() if any(complete[s].get(k)!=row.get(k) for k in expected_fields)]
    changes=[dict(source=s,before_translation=row['translation'],translation=complete[s]['translation'],
        covered_by_frozen_candidate=s in candidate,meaning_reviewed=False) for s,row in baseline.items()
        if row['translation']!=complete[s]['translation']]
    report=dict(source_locations=locations,unique_source_inputs=len(baseline),fresh_production_inferences=len(complete),
        frozen_candidate_inputs=len(candidate),frozen_candidate_output_differences=len(disagreements),differences=disagreements,
        changed_sources=len(changes),additional_changed_sources_not_in_previous_candidate=sum(not r['covered_by_frozen_candidate'] for r in changes),
        changes=changes,native_guards=guards,provenance_sha256=digest(pin),output_sha256=digest(target),
        all_changed_outputs_semantically_reviewed=False,screen_attempt_failure_probability=None,
        model_weights_changed=False,all_chapter_words_visually_reviewed=False)
    atomic(out/'summary.json',json.dumps(report,ensure_ascii=False,indent=2))
    assert not disagreements,'Production differs from the frozen guarded candidate; investigate saved differences'
    print(json.dumps({k:v for k,v in report.items() if k!='changes'}),flush=True)


if __name__=='__main__':main()
