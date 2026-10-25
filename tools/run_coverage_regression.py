"""Run real offline inference for the reviewed sample and omission candidates.

Only source strings enter the native process. Old outputs and judgments are
retained outside its input for comparisons after inference.
"""
import collections
import json
import pathlib
import subprocess
import time

from audit_corpus_quality import ROOT, QA, CURRENT, read, records, digest, atomic


def main():
    out=QA/'sentence-coverage8014';out.mkdir(exist_ok=True)
    binary=ROOT/'build/local-model8014/Release/luma_translate.exe'
    review_path=ROOT/'benchmarks/full-comics/current8011-extended-semantic-review.json'
    sources={};cases=[]
    def add(source,control,metadata):
        if source in sources:assert sources[source]==control,('Ambiguous old inference',source)
        sources[source]=control;cases.append(dict(source=source,control_translation=control,**metadata))
    for entry in read(review_path)['entries']:
        path=QA/CURRENT/(entry['chapter']+'-en.jsonl')
        assert digest(path)==entry['current_report_sha256']
        add(entry['source'],entry['translation'],dict(group='reviewed',id=entry['id'],before_judgment=entry['after']))
    probes=sorted((QA/'sentence-coverage-probe8011').glob('absolute-regression-*-en.json'))
    for path in probes:
        report=read(path)
        assert digest(QA/CURRENT/(report['chapter']+'.jsonl'))==report['source_report_sha256']
        for case in report['cases']:
            add(case['source'],case['control_translation'],dict(group='omission-candidate',chapter=report['chapter'],region_index=case['region_index'],probe_sha256=digest(path)))
    manifest=out/'input.jsonl';target=out/'output.jsonl';metadata=out/'cases.json'
    atomic(manifest,''.join(json.dumps(dict(source=source))+'\n' for source in sources))
    atomic(metadata,json.dumps(dict(cases=cases,review_sha256=digest(review_path)),ensure_ascii=False,indent=2))
    proof=dict(binary_sha256=digest(binary),runtime_sha256=digest(binary.parent/'onnxruntime.dll'),
        source_sha256=digest(ROOT/'native/local_translation.cpp'),header_sha256=digest(ROOT/'native/local_translation.h'),
        coverage_policy_sha256=digest(ROOT/'native/translation_coverage.h'),input_sha256=digest(manifest),cases_sha256=digest(metadata),
        assets={name:digest(ROOT/'assets/models/opus-en-es'/name) for name in ['encoder.onnx','decoder.onnx','tokenizer.json','terminology.json']},
        reference_used_for_inference=False,translator_weights_changed=False)
    proof_path=out/'provenance.json'
    if proof_path.exists():assert read(proof_path)==proof,'Refuse mixing builds within a regression run'
    else:atomic(proof_path,json.dumps(proof,indent=2))
    completed={r['source']:r for r in records(target)} if target.exists() else {}
    assert set(completed)<=set(sources)
    model=None;started=time.monotonic()
    try:
        for source in sources:
            if source in completed:continue
            if model is None:
                model=subprocess.Popen([str(binary),str(ROOT/'assets/models/opus-en-es')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                    text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
            model.stdin.write(json.dumps(dict(source=source))+'\n');model.stdin.flush()
            line=model.stdout.readline();assert line,'Missing native output'
            row=json.loads(line);assert 'error' not in row,row
            assert row['source']==source
            with target.open('a',encoding='utf-8') as handle:handle.write(json.dumps(row,ensure_ascii=False)+'\n')
            completed[source]=row
            if len(completed)%25==0:print('Fresh offline inferences:',len(completed),'/',len(sources),flush=True)
    finally:
        if model is not None:model.stdin.close();model.wait(timeout=30)
    pairs=[dict(**case,current=completed[case['source']]) for case in cases]
    for pair in pairs:
        row=pair['current']
        if row.get('sentence_recovered'):
            assert row['whole_translation']==pair['control_translation'],'Whole-paragraph inference drifted'
        else:assert row['translation']==pair['control_translation'],'Unexpected change outside recovery'
    for group in ['reviewed','omission-candidate']:
        selected=[p for p in pairs if p['group']==group]
        atomic(out/(group+'.json'),json.dumps(dict(cases=selected),ensure_ascii=False,indent=2))
    summary=dict(inputs=len(sources),comparisons=len(cases),group_sizes=dict(collections.Counter(c['group'] for c in cases)),
        all_inputs_fresh_native_inference=True,changed_outputs=sum(p['current']['translation']!=p['control_translation'] for p in pairs),
        unique_recovered_sources=sum(r.get('sentence_recovered',False) for r in completed.values()),
        unreviewed_current_semantic_accuracy=None,all_chapter_words_visually_reviewed=False,
        seconds_this_run=round(time.monotonic()-started,2),input_sha256=digest(manifest),output_sha256=digest(target),provenance_sha256=digest(proof_path))
    atomic(out/'summary.json',json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
