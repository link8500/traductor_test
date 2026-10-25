"""Compare both native Windows painters on the same eight actual inputs."""
import json
import pathlib
import subprocess
import textwrap
from PIL import Image,ImageDraw,ImageFont
from audit_corpus_quality import ROOT,QA,read,records,digest,atomic


def main():
    out=QA/'background8015/replay';out.mkdir(exist_ok=True);sample=read(QA/'sentence-coverage8014/photo-layout/sample.json');cases=[]
    for case in sample['cases']:
        source=pathlib.Path(case['source_page']['path']);assert digest(source)==case['source_page']['sha256']
        with Image.open(source) as image:
            bounds=case['bounds'];box=(max(0,bounds[0]-90),max(0,bounds[1]-70),min(image.width,bounds[2]+90),min(image.height,bounds[3]+70))
            path=out/f'{case["id"]:03d}-input.png';image.crop(box).convert('RGB').save(path)
        row=dict(bounds=[bounds[0]-box[0],bounds[1]-box[1],bounds[2]-box[0],bounds[3]-box[1]],translation=case['translation'])
        cases.append(dict(id=case['id'],path=str(path.resolve()),rows=[row],input_sha256=digest(path)))
    binaries={}
    for name,build in [('before','801401'),('after','801501')]:
        folder=out/name;folder.mkdir(exist_ok=True);inputs=[]
        for case in cases:inputs.append(dict(path=case['path'],rows=case['rows'],output=str((folder/f'{case["id"]:03d}.jpg').resolve())))
        manifest=folder/'input.jsonl';atomic(manifest,''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in inputs));target=folder/'native.json'
        binary=QA/f'frozen-windows{build}/traductor.exe';binaries[name]=digest(binary)
        subprocess.run([str(binary.resolve()),'--review-export',str(manifest.resolve()),str(target.resolve())],check=True,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
        assert read(target)['success'] and read(target)['images']==8
    changed=[];proof=[]
    for case in cases:
        before=out/'before'/f'{case["id"]:03d}.jpg';after=out/'after'/f'{case["id"]:03d}.jpg'
        if digest(before)!=digest(after):changed.append(case['id'])
        proof.append(dict(**case,before_sha256=digest(before),after_sha256=digest(after),translation_unchanged=True))
    assert len(changed)==1,('Unexpected visual changes',changed)
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',21);heading=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',23)
    for start in range(0,len(cases),4):
        sheet=Image.new('RGB',(1440,2240),'#f1f4ed');draw=ImageDraw.Draw(sheet)
        for position,case in enumerate(cases[start:start+4]):
            top=position*560;draw.text((16,top+8),f'Caso {case["id"]} · pintor anterior / pintor corregido / mismo texto',font=heading,fill='#243b2b')
            for x,name in [(12,'before'),(485,'after')]:
                with Image.open(out/name/f'{case["id"]:03d}.jpg') as image:
                    crop=image.copy();crop.thumbnail((460,480));sheet.paste(crop,(x+(460-crop.width)//2,top+48))
            y=top+48
            for line in textwrap.wrap(case['rows'][0]['translation'],width=40):draw.text((965,y),line,font=font,fill='#222');y+=28
        sheet.save(out/f'sheet-{start//4+1:02d}.jpg',quality=93)
    value=dict(cases=8,background_changed_cases=changed,byte_identical_render_cases=7,translation_changes=0,
        native_binaries=binaries,inputs=proof,layout_visually_reviewed=False,all_chapter_words_visually_reviewed=False)
    atomic(out/'summary.json',json.dumps(value,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in value.items() if k!='inputs'}))


if __name__=='__main__':main()
