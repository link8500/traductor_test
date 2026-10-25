"""Confirm disabling the new recovery stage preserves previous full-frame OCR."""
import json
import pathlib
import subprocess
from audit_corpus_quality import QA, read, records, digest, atomic


def main():
    folder=QA/'recovery-viewports801201'
    out=folder/'control-check';out.mkdir(exist_ok=True)
    results=[]
    for case_id in [7,32,65,71]:
        source=folder/f'{case_id:03d}.input.jsonl'
        if not source.exists():continue
        item=records(source)[0];item['recover_paragraphs']=False
        manifest=out/f'{case_id:03d}.input.jsonl';atomic(manifest,json.dumps(item)+'\n')
        outputs=[]
        for build in ['801101','801201']:
            target=out/f'{case_id:03d}-{build}.jsonl'
            binary=QA/f'frozen-windows{build}/traductor.exe'
            snapshot=read(QA/f'windows-engine{build}.json')
            assert digest(binary)==snapshot['binary_sha256']
            if not target.exists():
                run=subprocess.run([str(binary),'--comic-benchmark',str(manifest),str(target)],creationflags=subprocess.CREATE_NO_WINDOW)
                assert run.returncode==0
            summary=read(pathlib.Path(str(target)+'.summary.json'))
            assert summary['images']==1 and summary['runtime_errors']==0
            keys=['source','bounds','native_source','native_words','additional_detection','cropTop']
            outputs.append([{k:r.get(k) for k in keys} for r in records(target)])
        equal=outputs[0]==outputs[1]
        results.append(dict(viewport_id=case_id,unchanged=equal,before_regions=len(outputs[0]),after_regions=len(outputs[1])))
        print('Baseline preservation check:',len(results),'passed:',equal,flush=True)
    proof=dict(cases=results,all_passed=all(r['unchanged'] for r in results),full_corpus_equivalence=False)
    atomic(out/'summary.json',json.dumps(proof,indent=2))
    assert len(results)==4 and proof['all_passed'],proof


if __name__=='__main__':main()
