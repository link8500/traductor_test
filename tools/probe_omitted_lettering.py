"""Compare blind preprocessing on original screen pixels with both bundled OCRs.

Diagnostic only: no expected strings or Spanish inputs are supplied to either
OCR. Nontext controls are retained to expose confident false detections.
"""
import json
import pathlib
import shutil
import subprocess

import cv2
import numpy as np
from PIL import Image
from audit_corpus_quality import ROOT, QA, read, digest, atomic


def main():
    out=QA/'omitted-lettering-probe8012';out.mkdir(exist_ok=True)
    cases={c['id']:c for c in read(QA/'undetected-review8011/sample.json')['cases']}
    manifest=read(ROOT/'assets/models/opus-en-es/manifest.json')
    requests=[];proof=[]
    for case_id in [11,12,17,21,27,31,32,34]:
        case=cases[case_id];page=case['source_page'];path=pathlib.Path(page['path'])
        assert digest(path)==page['sha256']
        with Image.open(path) as original:
            center=(case['source_bounds'][1]+case['source_bounds'][3])//2
            top=max(0,min(center-1000,original.height-2000));bottom=min(original.height,top+2000)
            rgb=np.asarray(original.crop((0,top,original.width,bottom)).convert('RGB'))
        gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
        clahe=cv2.createCLAHE(clipLimit=2.0,tileGridSize=(8,8)).apply(gray)
        color_span=np.max(rgb,axis=2)-np.min(rgb,axis=2)
        def contrast(a):
            lo,hi=np.percentile(a,(1,99))
            return np.clip((a.astype(np.float32)-lo)*255/max(1,hi-lo),0,255).astype(np.uint8)
        variants={'original':rgb,'gray-contrast':contrast(gray),'local-gray':clahe,
            'max-channel':contrast(np.max(rgb,axis=2)),'color-span':contrast(color_span),
            'rotated-left':np.rot90(rgb,1),'rotated-right':np.rot90(rgb,3)}
        for name,array in variants.items():
            if array.ndim==2:array=cv2.cvtColor(array,cv2.COLOR_GRAY2RGB)
            image=Image.fromarray(np.ascontiguousarray(array)).convert('RGBA')
            path=out/f'{case_id:03d}-{name}.bgra';path.write_bytes(image.tobytes('raw','BGRA'))
            request=dict(chapter=f'probe-{case_id:03d}-{name}',path=str(path.resolve()),width=image.width,height=image.height)
            requests.append(request)
            proof.append(dict(case_id=case_id,variant=name,source_sha256=page['sha256'],crop_top=top,crop_bottom=bottom,
                raw_pixels_sha256=digest(path),request=request))
    atomic(out/'inputs.json',json.dumps(dict(source_review_sample_sha256=digest(QA/'undetected-review8011/sample.json'),
        reference_used_for_inference=False,app_code_modified=False,cases=proof),indent=2))
    binary=ROOT/'build/local-model/Release/luma_ocr.exe'
    for family,model,dictionary in [('latin-v5','english-ocr.onnx','ocr-characters.json'),
                                    ('english-v4','english-ocr-fallback.onnx','ocr-characters-fallback.json')]:
        target=out/(family+'.jsonl')
        if target.exists() and len(target.read_text(encoding='utf-8').splitlines())==len(requests):continue
        model_dir=out/family;model_dir.mkdir(exist_ok=True)
        for source,name in [(model,'english-ocr.onnx'),(dictionary,'ocr-characters.json')]:
            src=ROOT/'assets/models/opus-en-es'/source
            assert digest(src)==manifest['files'][source]
            shutil.copy2(src,model_dir/name)
        process=subprocess.Popen([str(binary),str(model_dir),str(ROOT/'assets/models/opus-en-es')],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
        data,error=process.communicate(''.join(json.dumps(r)+'\n' for r in requests),timeout=1800)
        assert process.returncode==0,error
        rows=[json.loads(line) for line in data.splitlines() if line.strip()]
        assert len(rows)==len(requests) and all('error' not in row for row in rows)
        atomic(target,data)
        atomic(out/(family+'-provenance.json'),json.dumps(dict(binary_sha256=digest(binary),model_sha256=manifest['files'][model],
            dictionary_sha256=manifest['files'][dictionary],input_manifest_sha256=digest(out/'inputs.json'),
            output_sha256=digest(target),reference_used_for_inference=False),indent=2))
        print('Diagnostic OCR family completed:',family,len(rows),'actual image variants',flush=True)


if __name__=='__main__':main()
