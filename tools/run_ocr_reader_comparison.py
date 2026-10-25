"""Compare three real readers on fixed original pixels, no answer input."""
import json
import argparse
import pathlib
import re
import shutil
import subprocess
import time
from PIL import Image,ImageDraw,ImageFont
from audit_corpus_quality import ROOT,QA,read,records,digest,atomic


def summarize(row):
    lines=[]
    for r in row['lines']:
        q=r['quad'];left=min(q[::2]);top=min(q[1::2]);bottom=max(q[1::2]);height=max(1,bottom-top)
        if r['confidence']<.8:continue
        lines.append(dict(text=r['text'],left=left,top=top,bottom=bottom,height=height,confidence=r['confidence']))
    groups=[]
    for line in sorted(lines,key=lambda r:(r['top'],r['left'])):
        match=next((g for g in groups if abs(g['top']-line['top'])<.35*max(g['height'],line['height'])),None)
        if match is None:groups.append(dict(top=line['top'],height=line['height'],lines=[line]))
        else:match['lines'].append(line)
    return ' '.join(r['text'] for group in groups for r in sorted(group['lines'],key=lambda r:r['left']))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed-path',default='build/full-comics/corpus-review-sample/sample.json')
    parser.add_argument('--output-name',default='ocr-reader-comparison8016')
    args=parser.parse_args();assert re.fullmatch('[a-z][a-z0-9-]+',args.output_name)
    out=QA/args.output_name;out.mkdir(exist_ok=True)
    binary=ROOT/'build/ocr8016/Release/luma_ocr.exe';assert binary.exists()
    runtime=binary.parent/'onnxruntime.dll'
    if not runtime.exists():shutil.copy2(ROOT/'windows/third_party/onnxruntime/onnxruntime.dll',runtime)
    original=ROOT/args.seed_path;seeds=read(original)['cases'];assert len(seeds)==124
    models={'current':ROOT/'assets/models/opus-en-es',**{name:QA/'ocr-candidates8016'/name for name in ['english-v5','multilingual-v6-small']}}
    proof=dict(binary_sha256=digest(binary),runtime_sha256=digest(binary.parent/'onnxruntime.dll'),source_sha256=digest(ROOT/'native/local_translation.cpp'),
        seed_sha256=digest(original),model_files={name:{part:digest(path/part) for part in ['english-ocr.onnx','ocr-characters.json','english-ocr-fallback.onnx','ocr-characters-fallback.json']} for name,path in models.items()},
        source_pixels_only=True,transcription_supplied=False,reference_supplied=False,application_modified=False)
    proof_path=out/'provenance.json'
    if proof_path.exists():assert read(proof_path)==proof
    else:atomic(proof_path,json.dumps(proof,indent=2))
    manifest=[];cases=[]
    for seed in seeds:
        ident=seed['id'];page=seed['source_page'];source=pathlib.Path(page['path']);assert digest(source)==page['sha256']
        with Image.open(source) as bitmap:
            b=seed['bounds'];bounds=[max(0,b[0]-50),max(0,b[1]-45),min(bitmap.width,b[2]+50),min(bitmap.height,b[3]+45)]
            crop=bitmap.crop(bounds).convert('RGB');pixels=out/f'{ident:03d}.bgra';preview=out/f'{ident:03d}.png'
            if not pixels.exists():pixels.write_bytes(crop.convert('RGBA').tobytes('raw','BGRA'));crop.save(preview)
            assert pixels.stat().st_size==crop.width*crop.height*4
            manifest.append(dict(id=ident,path=str(pixels.resolve()),width=crop.width,height=crop.height))
        cases.append(dict(id=ident,chapter=seed['chapter'],source_image=seed['source_image'],source_page=page,crop_bounds=bounds,
            pixels_sha256=digest(pixels),preview_sha256=digest(preview),preview=str(preview.resolve())))
    atomic(out/'input.jsonl',''.join(json.dumps(row)+'\n' for row in manifest))
    for name,directory in models.items():
        target=out/(name+'.jsonl');completed={r['id']:r for r in records(target)} if target.exists() else {};model=None
        try:
            for row in manifest:
                if row['id'] in completed:continue
                if model is None:model=subprocess.Popen([str(binary),str(directory),str(ROOT/'assets/models/opus-en-es')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
                model.stdin.write(json.dumps(row)+'\n');model.stdin.flush();line=model.stdout.readline();assert line,'Missing reader output'
                result=json.loads(line);assert 'error' not in result,result;result['grouped_reading']=summarize(result)
                with target.open('a',encoding='utf-8') as handle:handle.write(json.dumps(result,ensure_ascii=False)+'\n')
                completed[row['id']]=result
                if len(completed)%25==0:print(name,'native pixel crops:',len(completed),'/124',flush=True)
        finally:
            if model is not None:model.stdin.close();model.wait(timeout=30)
    rows={name:{r['id']:r for r in records(out/(name+'.jsonl'))} for name in models}
    for case in cases:case['readings']={name:rows[name][case['id']]['grouped_reading'] for name in models}
    sample=dict(cases=cases,chapters=124,selection='One previously frozen pixel location per chapter, independent of these model outputs',
        source_seed_sha256=digest(original),provenance_sha256=digest(proof_path),native_outputs_sha256={name:digest(out/(name+'.jsonl')) for name in models},
        all_words_reviewed=False,model_accuracy=None,application_modified=False)
    atomic(out/'sample.json',json.dumps(sample,ensure_ascii=False,indent=2))
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18);small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',17)
    import textwrap
    for start in range(0,len(cases),4):
        sheet=Image.new('RGB',(1600,2200),'#f1f4ed');draw=ImageDraw.Draw(sheet)
        for offset,case in enumerate(cases[start:start+4]):
            y=offset*550;draw.text((12,y+8),f'Caso {case["id"]} · Píxeles originales / Lecturas reales sin respuestas',font=font,fill='#243b2b')
            with Image.open(case['preview']) as bitmap:
                crop=bitmap.convert('RGB');crop.thumbnail((505,490));sheet.paste(crop,(12+(505-crop.width)//2,y+44))
            for x,name in [(535,'current'),(890,'english-v5'),(1245,'multilingual-v6-small')]:
                draw.text((x,y+44),name,font=font,fill='#243b2b');line_y=y+78
                for line in textwrap.wrap(case['readings'][name],width=30):draw.text((x,line_y),line,font=small,fill='#222');line_y+=23
        sheet.save(out/f'sheet-{start//4+1:02d}.jpg',quality=93)
    print(json.dumps(dict(crops=124,readers=3,real_native_executions=372,changed_from_current={name:sum(c['readings'][name]!=c['readings']['current'] for c in cases) for name in models if name!='current'},pixel_review_pending=True,application_modified=False)),flush=True)


if __name__=='__main__':main()
