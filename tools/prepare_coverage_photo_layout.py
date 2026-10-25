"""Show the actual saved Windows replay for all eight changed sample outputs."""
import json
import pathlib
import textwrap
from PIL import Image,ImageDraw,ImageFont
from audit_corpus_quality import QA,read,digest,atomic


def main():
    sample=read(QA/'sentence-coverage8014/visual-review/sample.json');folder=QA/'sentence-coverage8014/photo-layout';folder.mkdir(exist_ok=True)
    cases=[]
    for case in sample['cases']:
        proof_path=QA/'chapter-photos8014-fixed-ocr'/case['chapter']/'provenance.json'
        assert proof_path.exists(),'The matching new gallery chapter is not ready yet'
        proof=read(proof_path);page=next(p for p in proof['pages'] if p['image']==case['source_image'])
        photo=proof_path.parent/page['file'];assert digest(photo)==page['output_sha256']
        cases.append(dict(**case,native_photo_path=str(photo),native_photo_sha256=page['output_sha256'],photo_provenance_sha256=digest(proof_path)))
    value=dict(cases=cases,regions=len(cases),source_sample_sha256=digest(QA/'sentence-coverage8014/visual-review/sample.json'),
        actual_saved_renderer_output=True,layout_visually_reviewed=False,all_chapter_words_visually_reviewed=False)
    atomic(folder/'sample.json',json.dumps(value,ensure_ascii=False,indent=2))
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',21);heading=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',23)
    for start in range(0,len(cases),4):
        sheet=Image.new('RGB',(1440,2240),'#f1f4ed');draw=ImageDraw.Draw(sheet)
        for position,case in enumerate(cases[start:start+4]):
            top=position*560;draw.text((16,top+8),f'Caso {case["id"]} · original EN / render nativo guardado / salida sin editar',font=heading,fill='#243b2b')
            bounds=case['bounds']
            for x,path in [(12,case['source_page']['path']),(485,case['native_photo_path'])]:
                with Image.open(path) as img:
                    box=(max(0,bounds[0]-90),max(0,bounds[1]-70),min(img.width,bounds[2]+90),min(img.height,bounds[3]+70))
                    crop=img.crop(box).convert('RGB');crop.thumbnail((460,480));sheet.paste(crop,(x+(460-crop.width)//2,top+48))
            y=top+48
            for line in textwrap.wrap(case['translation'],width=40):draw.text((965,y),line,font=font,fill='#222');y+=28
        sheet.save(folder/f'sheet-{start//4+1:02d}.jpg',quality=93)
    print(json.dumps(dict(regions=len(cases),sheets=(len(cases)+3)//4)))


if __name__=='__main__':main()
