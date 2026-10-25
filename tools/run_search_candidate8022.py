"""Fresh wider-search translations of all same OCR sources across 124 views."""
import json
import subprocess
from audit_corpus_quality import ROOT, QA, atomic, digest, read, records


def main():
    folder=QA/'translation-search8022';source=QA/'windows8021-full-viewports-full-agreement/output.jsonl'
    rows=records(source);assert len(rows)==228 and len({r['image'] for r in rows})==124
    binary=ROOT/'build/local-search8022/Release/luma_translate_search.exe'
    proof=read(folder/'build-provenance.json');assert digest(binary)==proof['binary_sha256']
    unique=list(dict.fromkeys(r['source'] for r in rows))
    manifest=folder/'input.jsonl';atomic(manifest,''.join(json.dumps(dict(id=i,source=s))+'\n' for i,s in enumerate(unique)))
    target=folder/'unique-output.jsonl'
    previous={r['source']:r for r in records(target)} if target.exists() else {}
    assert set(previous)<=set(unique)
    provenance=dict(build_provenance_sha256=digest(folder/'build-provenance.json'),
        frozen_baseline_outputs_sha256=digest(source),input_sha256=digest(manifest),
        source_regions=228,reading_viewports=124,unique_inferences=len(unique),
        reference_or_original_inventory_supplied=False,offline_only=True)
    pin=folder/'inference-provenance.json'
    if pin.exists():assert read(pin)==provenance
    else:atomic(pin,json.dumps(provenance,indent=2))
    worker=None
    try:
        for i,s in enumerate(unique):
            if s in previous:continue
            if worker is None:
                worker=subprocess.Popen([str(binary),str(ROOT/'assets/models/opus-en-es')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                    stderr=(folder/'stderr.log').open('w'),text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
            worker.stdin.write(json.dumps(dict(id=i,source=s))+'\n');worker.stdin.flush()
            line=worker.stdout.readline();assert line,'Native search process stopped'
            row=json.loads(line);assert row['source']==s and 'error' not in row
            with target.open('a',encoding='utf-8') as out:out.write(json.dumps(row,ensure_ascii=False)+'\n')
            previous[s]=row
            print(json.dumps(dict(completed=len(previous),requested=len(unique))),flush=True)
    finally:
        if worker is not None:worker.stdin.close();worker.wait(timeout=60)
    updated=[]
    for row in rows:
        result=previous[row['source']]
        exported=dict(row,translation=result['translation'],retained_original=result['retained_original'],
            sentence_recovered=result['sentence_recovered'])
        for key in ['reason','whole_translation','sentence_sources','sentence_translations']:
            exported.pop(key,None)
            if key in result:exported[key]=result[key]
        updated.append(exported)
    atomic(folder/'output.jsonl',''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in updated))
    changes=[dict(id=i,image=a['image'],source=a['source'],before=a['translation'],after=b['translation'])
        for i,(a,b) in enumerate(zip(rows,updated)) if a['translation']!=b['translation']]
    atomic(folder/'changes.json',json.dumps(changes,ensure_ascii=False,indent=2))
    summary=dict(viewports=124,regions=228,fresh_unique_native_inferences=len(unique),
        changed_regions=len(changes),changed_viewports=len({r['image'] for r in changes}),runtime_errors=0,
        inference_provenance_sha256=digest(pin),output_sha256=digest(folder/'output.jsonl'),
        all_changed_meanings_reviewed=False,screen_attempt_failure_probability=None,target_achieved=False,
        application_modified=False,ready_for_release=False)
    atomic(folder/'summary.json',json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
