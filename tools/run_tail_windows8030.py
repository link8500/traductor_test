"""Validate integrated tail recovery with actual native source-only MT.

Pixel OCR is reused unchanged. Existing fixed views and prior changed-location
controls stay fixed; the omission diagnostic is reported as a separate cohort.
"""
import json
import pathlib
import shutil
import subprocess

from audit_corpus_quality import ROOT, QA, atomic, digest, read, records
from quality_resources import wait_for_inference_memory


def main():
    folder=QA/'windows8030-tail-translation-replay';folder.mkdir(exist_ok=True)
    trial=QA/'tail8030';policy=ROOT/'build/local-model8030/Release/luma_translation_tail.exe'
    guards=json.loads(subprocess.check_output([str(policy),'--self-test'],text=True,creationflags=subprocess.CREATE_NO_WINDOW))
    assert guards['success'] and guards['guards']==18
    planned=subprocess.run([str(policy)],input=(trial/'policy-input.jsonl').read_text(encoding='utf-8'),text=True,
                           encoding='utf-8',capture_output=True,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    atomic(folder/'predicted.jsonl',planned.stdout);predicted=[json.loads(s) for s in planned.stdout.splitlines() if s.strip()]
    cases=read(trial/'sample.json')['cases'];assert [c['id'] for c in cases]==[r['id'] for r in predicted]
    fixed_path=QA/'windows8029-refinement-full-viewports/output.jsonl';fixed=records(fixed_path)
    broad_path=QA/'windows8029-refinement-full-viewports/broad-selected.json';broad=read(broad_path)
    inputs=[];scopes=[]
    for scope,rows in [('fixed',fixed),('prior_diagnostic',[r['after'] for r in broad]),('tail',cases)]:
        for row in rows:
            inputs.append(dict(id=len(inputs)+1,image=row['image'],bounds=row['bounds'],source=row['source']))
            scopes.append(dict(scope=scope,case_id=row.get('id')))
    binary=QA/'frozen-windows803001/traductor.exe';snapshot=QA/'windows-engine803001.json';assert digest(binary)==read(snapshot)['binary_sha256']
    provenance=dict(binary_sha256=digest(binary),snapshot_sha256=digest(snapshot),
                    previous_fixed_output_sha256=digest(fixed_path),previous_diagnostic_sha256=digest(broad_path),
                    trial_sample_sha256=digest(trial/'sample.json'),policy_sha256=digest(policy),
                    policy_header_sha256=digest(ROOT/'native/translation_tail.h'),prediction_sha256=digest(folder/'predicted.jsonl'),
                    actual_native_translation=True,source_only_model_input=True,manual_or_reference_answers_supplied=False,
                    fresh_ocr_inference=False,fresh_screen_capture=False,model_weights_changed=False,
                    fixed_scope_unchanged=True,diagnostic_not_population_estimate=True)
    pin=folder/'provenance.json'
    if pin.exists():assert read(pin)==provenance
    else:atomic(pin,json.dumps(provenance,indent=2))
    outputs=[]
    for start in range(0,len(inputs),64):
        n=start//64;part=inputs[start:start+64];manifest=folder/f'part-{n:02d}.input.jsonl';target=folder/f'part-{n:02d}.jsonl'
        contents=''.join(json.dumps(r)+'\n' for r in part)
        if manifest.exists():assert manifest.read_text(encoding='utf-8')==contents
        else:atomic(manifest,contents)
        if not pathlib.Path(str(target)+'.summary.json').exists():
            assert shutil.disk_usage(folder).free>=4*1024**3
            wait_for_inference_memory(minimum_free_bytes=5*1024**3//2)
            with (folder/f'part-{n:02d}.log').open('ab') as log:
                subprocess.run([str(binary),'--translation-replay',str(manifest),str(target)],check=True,
                               creationflags=subprocess.CREATE_NO_WINDOW,stdout=log,stderr=log,timeout=1800)
        actual=records(target);assert len(actual)==len(part) and all('error' not in r for r in actual)
        assert read(pathlib.Path(str(target)+'.summary.json'))['runtime_errors']==0
        assert [(r['id'],r['source'],r['image'],r['bounds']) for r in actual]==[(r['id'],r['source'],r['image'],r['bounds']) for r in part]
        outputs.extend(actual);print(json.dumps(dict(state='native_mt',completed=len(outputs),expected=len(inputs))),flush=True)
    fixed_new=outputs[:len(fixed)];broad_new=outputs[len(fixed):len(fixed)+len(broad)];tail_new=outputs[len(fixed)+len(broad):]
    fixed_changes=[dict(id=i+1,before=a,after=b) for i,(a,b) in enumerate(zip(fixed,fixed_new)) if a['translation']!=b['translation']]
    broad_changes=[dict(id=a['case_id'],before=a['after'],after=b) for a,b in zip(broad,broad_new) if a['after']['translation']!=b['translation']]
    assert len(tail_new)==len(predicted)
    assert [r['translation'] for r in tail_new]==[r['candidate_translation'] for r in predicted]
    assert [r['tail_recovered'] for r in tail_new]==[r['tail_recovered'] for r in predicted]
    changed=[dict(c,policy=p,actual_native=r,meaning_reviewed=False) for c,p,r in zip(cases,predicted,tail_new) if r['tail_recovered']]
    for name,rows in [('fixed-output.jsonl',fixed_new),('prior-diagnostic-output.jsonl',broad_new),('tail-output.jsonl',tail_new)]:
        atomic(folder/name,''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
    for name,rows in [('fixed-changes.json',fixed_changes),('prior-diagnostic-changes.json',broad_changes),('changes.json',changed)]:
        atomic(folder/name,json.dumps(rows,ensure_ascii=False,indent=2))
    summary=dict(actual_native_output_records=len(outputs),fixed_regions=len(fixed_new),fixed_changed_regions=len(fixed_changes),
                 previous_diagnostic_regions=len(broad_new),previous_diagnostic_changed_regions=len(broad_changes),
                 tail_candidates=len(tail_new),tail_changed_regions=len(changed),runtime_errors=0,native_guards=guards,
                 all_candidate_outputs_match_pure_policy=True,source_only_inference=True,fresh_ocr_inference=False,
                 fresh_screen_capture=False,all_chapter_words_visually_reviewed=False,
                 screen_attempt_failure_probability=None,target_achieved=False)
    atomic(folder/'summary.json',json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
