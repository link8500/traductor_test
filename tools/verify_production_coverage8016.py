"""Fresh production C++ inference must match every tested candidate source."""
import json
import subprocess
from audit_corpus_quality import ROOT,QA,read,records,digest,atomic


def main():
    out=QA/'production-coverage8016';out.mkdir(exist_ok=True)
    binary=ROOT/'build/local-model8016/Release/luma_translate.exe'
    guards=subprocess.run([str(binary.with_name('luma_coverage_test.exe'))],capture_output=True,text=True,check=True)
    expected={r['source']:r for r in records(QA/'sentence-coverage8016/output.jsonl')}
    for row in records(QA/'full-omission-candidate8016/inferences.jsonl'):
        if row['source'] in expected:assert expected[row['source']]['translation']==row['translation']
        expected[row['source']]=row
    manifest=out/'input.jsonl';target=out/'output.jsonl';atomic(manifest,''.join(json.dumps(dict(source=s))+'\n' for s in expected))
    proof=dict(binary_sha256=digest(binary),runtime_sha256=digest(binary.parent/'onnxruntime.dll'),source_sha256=digest(ROOT/'native/local_translation.cpp'),
        policy_sha256=digest(ROOT/'native/translation_coverage.h'),input_sha256=digest(manifest),candidate_sample_output_sha256=digest(QA/'sentence-coverage8016/output.jsonl'),
        full_candidate_fresh_output_sha256=digest(QA/'full-omission-candidate8016/inferences.jsonl'),assets={name:digest(ROOT/'assets/models/opus-en-es'/name) for name in ['encoder.onnx','decoder.onnx','tokenizer.json','terminology.json']},reference_supplied_to_inference=False)
    pin=out/'provenance.json'
    if pin.exists():assert read(pin)==proof
    else:atomic(pin,json.dumps(proof,indent=2))
    completed={r['source']:r for r in records(target)} if target.exists() else {};assert set(completed)<=set(expected)
    model=None
    try:
        for source in expected:
            if source in completed:continue
            if model is None:model=subprocess.Popen([str(binary),str(ROOT/'assets/models/opus-en-es')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
            model.stdin.write(json.dumps(dict(source=source))+'\n');model.stdin.flush();line=model.stdout.readline();assert line,'Native production stopped'
            row=json.loads(line);assert row['source']==source and 'error' not in row,row
            with target.open('a',encoding='utf-8') as handle:handle.write(json.dumps(row,ensure_ascii=False)+'\n')
            completed[source]=row
            if len(completed)%50==0:print('Fresh production parity inputs:',len(completed),'/',len(expected),flush=True)
    finally:
        if model is not None:model.stdin.close();model.wait(timeout=30)
    fields=['translation','prepared','raw_model','sentence_recovered','whole_translation','sentence_sources','sentence_translations','terminology','source_corrections','retained_original']
    differences=[dict(source=s,fields=[k for k in fields if completed[s].get(k)!=expected[s].get(k)]) for s in expected if any(completed[s].get(k)!=expected[s].get(k) for k in fields)]
    value=dict(inputs=len(expected),fresh_production_inferences=len(completed),production_candidate_differences=len(differences),differences=differences,
        native_guards=json.loads(guards.stdout),provenance_sha256=digest(pin),output_sha256=digest(target),all_chapter_words_visually_reviewed=False,
        screen_attempt_failure_probability=None,translator_weights_changed=False)
    atomic(out/'summary.json',json.dumps(value,ensure_ascii=False,indent=2));assert not differences,differences[:3]
    print(json.dumps(value),flush=True)


if __name__=='__main__':main()
