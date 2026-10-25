"""Fresh 8014 inference for the next disjoint sample; source-only native input."""
import json
import subprocess
from audit_corpus_quality import ROOT, QA, read, records, digest, atomic


def main():
    sample_path=QA/'corpus-review-sixth8011/sample.json';sample=read(sample_path)
    previous_proof=read(QA/'sentence-coverage8014/provenance.json')
    binary=ROOT/'build/local-model8014/Release/luma_translate.exe';assets=ROOT/'assets/models/opus-en-es'
    assert digest(binary)==previous_proof['binary_sha256']
    assert digest(binary.parent/'onnxruntime.dll')==previous_proof['runtime_sha256']
    for name,sha in previous_proof['assets'].items():assert digest(assets/name)==sha
    out=QA/'sentence-coverage8014/additional-sample';out.mkdir(exist_ok=True)
    inputs=''.join(json.dumps(dict(source=c['source']))+'\n' for c in sample['cases'])
    atomic(out/'input.jsonl',inputs)
    proof=dict(sample_sha256=digest(sample_path),input_sha256=digest(out/'input.jsonl'),
        pinned_native_provenance_sha256=digest(QA/'sentence-coverage8014/provenance.json'),
        binary_sha256=digest(binary),reference_used_for_inference=False,translator_weights_changed=False)
    if (out/'provenance.json').exists():assert read(out/'provenance.json')==proof
    else:atomic(out/'provenance.json',json.dumps(proof,indent=2))
    completed=records(out/'output.jsonl') if (out/'output.jsonl').exists() else []
    assert all(row['source']==sample['cases'][i]['source'] for i,row in enumerate(completed))
    model=None
    try:
        for case in sample['cases'][len(completed):]:
            if model is None:model=subprocess.Popen([str(binary),str(assets)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
            model.stdin.write(json.dumps(dict(source=case['source']))+'\n');model.stdin.flush()
            line=model.stdout.readline();assert line,'Native translator stopped'
            row=json.loads(line);assert 'error' not in row and row['source']==case['source']
            with (out/'output.jsonl').open('a',encoding='utf-8') as handle:handle.write(json.dumps(row,ensure_ascii=False)+'\n')
            completed.append(row)
            if len(completed)%20==0:print('Additional native sample',len(completed),'/ 124',flush=True)
    finally:
        if model is not None:model.stdin.close();model.wait(timeout=30)
    changed=0
    for case,row in zip(sample['cases'],completed):
        if row.get('sentence_recovered'):assert row['whole_translation']==case['translation'];changed+=1
        else:assert row['translation']==case['translation'],'Unexpected inference change'
    summary=dict(cases=len(completed),all_inputs_fresh_native_inference=True,changed_outputs=changed,
        sample_sha256=digest(sample_path),output_sha256=digest(out/'output.jsonl'),
        all_chapter_words_visually_reviewed=False,semantic_accuracy=None)
    atomic(out/'summary.json',json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
