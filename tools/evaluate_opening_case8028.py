"""Check sentence casing of isolated openings using actual native inference."""
import json
import pathlib
import subprocess

from audit_corpus_quality import ROOT, QA, atomic, digest, read, records
from quality_resources import wait_for_inference_memory


def main():
    folder=QA/'opening8028';cases=read(folder/'evaluated.json')
    forms={case['opening']:case['opening'][:1].upper()+case['opening'][1:].lower() for case in cases}
    inputs=[dict(id=i+1,image=0,bounds=[0,0,1,1],source=text) for i,text in enumerate(sorted(set(forms.values())))]
    path=folder/'normalized-opening-input.jsonl';target=folder/'normalized-opening-output.jsonl'
    contents=''.join(json.dumps(r)+'\n' for r in inputs)
    if path.exists():assert path.read_text(encoding='utf-8')==contents
    else:atomic(path,contents)
    binary=QA/'frozen-windows802701/traductor.exe'
    proof=dict(binary_sha256=digest(binary),source_sample_sha256=digest(folder/'sample.json'),
               input_sha256=digest(path),normalization='Uppercase first letter; lowercase remaining opening letters',
               manual_translation_supplied=False,production_modified=False)
    pin=folder/'normalized-opening-provenance.json'
    if pin.exists():assert read(pin)==proof
    else:atomic(pin,json.dumps(proof,indent=2))
    if not pathlib.Path(str(target)+'.summary.json').exists():
        wait_for_inference_memory(minimum_free_bytes=5*1024**3//2)
        with (folder/'normalized-opening-runtime.log').open('ab') as log:
            subprocess.run([str(binary),'--translation-replay',str(path),str(target)],check=True,
                           creationflags=subprocess.CREATE_NO_WINDOW,stdout=log,stderr=log,timeout=900)
    actual=records(target);assert len(actual)==len(inputs) and all('error' not in r for r in actual)
    by_text={r['source']:r for r in actual};policy=[]
    for c in cases:
        whole,rest=c['native']['source'],c['native']['rest'];first=by_text[forms[c['opening']]]
        policy.append(dict(id=c['id'],source=c['source'],translation=whole['translation'],
                           opening_translation=first['translation'],rest_translation=rest['translation'],
                           retained_original=whole['retained_original'],opening_retained=first['retained_original'],
                           rest_retained=rest['retained_original']))
    binary_policy=ROOT/'build/local-model8028/Release/luma_translation_opening.exe'
    guards=json.loads(subprocess.check_output([str(binary_policy),'--self-test'],text=True,creationflags=subprocess.CREATE_NO_WINDOW))
    contents=''.join(json.dumps(r)+'\n' for r in policy)
    atomic(folder/'normalized-policy-input.jsonl',contents)
    out=subprocess.run([str(binary_policy)],input=contents,text=True,encoding='utf-8',capture_output=True,check=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    atomic(folder/'normalized-policy-output.jsonl',out.stdout)
    results=[json.loads(line) for line in out.stdout.splitlines() if line.strip()]
    changes=[dict(c,policy=r) for c,r in zip(cases,results) if r['opening_recovered']]
    atomic(folder/'normalized-changes.json',json.dumps(changes,ensure_ascii=False,indent=2))
    summary=dict(candidates=len(cases),changes=len(changes),additional_actual_native_inferences=len(actual),guards=guards,
                 output_sha256=digest(target),policy_output_sha256=digest(folder/'normalized-policy-output.jsonl'),
                 policy_binary_sha256=digest(binary_policy),reference_or_manual_answers_supplied=False,
                 production_modified=False,all_changed_meanings_reviewed=False,screen_attempt_failure_probability=None,target_achieved=False)
    atomic(folder/'normalized-summary.json',json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
