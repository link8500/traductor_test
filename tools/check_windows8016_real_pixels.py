"""Compare both Windows app binaries on four unedited comic viewports."""
import json
import pathlib
import subprocess
from PIL import Image
from audit_corpus_quality import ROOT,QA,read,records,digest,atomic


def main():
    folder=QA/'windows8016-real-pixels';folder.mkdir(exist_ok=True)
    examples={c['id']:c for c in read(QA/'full-omission-candidate8016/visual-review/sample.json')['cases']}
    # This is a targeted implementation check, not an unbiased accuracy sample.
    inputs=[];proof=[]
    for i,selected in enumerate([1,2,13,32],1):
        case=examples[selected];page=case['source_page'];source=pathlib.Path(page['path']);assert digest(source)==page['sha256']
        with Image.open(source) as image:
            top=max(0,case['bounds'][1]-260);bottom=min(image.height,case['bounds'][3]+260)
            path=folder/f'{i:03d}.png';image.crop((0,top,image.width,bottom)).convert('RGB').save(path)
        inputs.append(dict(chapter=f'implementation-viewport-{i:03d}',image=i,path=str(path.resolve()),language='en',ocr_only=False,augment_detection=True,all_candidates=True,recover_paragraphs=True,complete_lines=True))
        proof.append(dict(id=i,source_sha256=page['sha256'],source_crop=[0,top,page['width'],bottom],viewport_sha256=digest(path)))
    manifest=folder/'input.jsonl';atomic(manifest,''.join(json.dumps(r)+'\n' for r in inputs))
    values={};binaries={}
    for label,build in [('before','801501'),('after','801601')]:
        binary=QA/f'frozen-windows{build}/traductor.exe';target=folder/(label+'.jsonl');binaries[label]=digest(binary)
        if not pathlib.Path(str(target)+'.summary.json').exists():
            subprocess.run([str(binary),'--comic-benchmark',str(manifest),str(target)],check=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=600)
        report=read(pathlib.Path(str(target)+'.summary.json'));assert report['images']==4 and report['runtime_errors']==0
        values[label]=records(target)
    a,b=values['before'],values['after'];assert len(a)==len(b)
    for x,y in zip(a,b):assert all(x[k]==y[k] for k in ['image','source','bounds'])
    changed=[dict(image=x['image'],source=x['source'],before=x['translation'],after=y['translation']) for x,y in zip(a,b) if x['translation']!=y['translation']]
    result=dict(viewports=4,native_windows_app_processes=2,native_windows_viewport_attempts=8,regions=len(b),runtime_errors=0,source_and_geometry_identical=True,
        changed_translations=len(changed),binaries=binaries,input_sha256=digest(manifest),original_pixel_proofs=proof,
        before_sha256=digest(folder/'before.jsonl'),after_sha256=digest(folder/'after.jsonl'),changes=changed,
        targeted_implementation_check=True,full_screen_semantic_review_complete=False,screen_attempt_failure_probability=None)
    atomic(folder/'summary.json',json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ['changes','original_pixel_proofs']}),flush=True)


if __name__=='__main__':main()
