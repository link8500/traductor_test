"""Show all52 quantization changes against the same original/reference pixels."""
import json
import pathlib
import textwrap
from PIL import Image,ImageDraw,ImageFont
from audit_corpus_quality import ROOT,QA,atomic,digest,read


def main():
    folder=QA/'int8-translation8018';summary=read(folder/'summary.json')
    previous=ROOT/'benchmarks/full-comics/windows8018-heldout-semantic-review.json'
    judgments={r['id']:r for r in read(previous)['entries']}
    templates={r['id']:r for r in read(QA/'windows8016-heldout-pixels/visual-review/sample.json')['cases']}
    cases=[];identical=[]
    for r in summary['entries']:
        ident=r['id'];assert ' '.join(r['before_translations'])==judgments[ident]['translation']
        if r['before_translations']==r['translations']:
            identical.append(dict(id=ident,source=r['source'],translation=' '.join(r['translations']),judgment=judgments[ident]['after']));continue
        cases.append(dict(templates[ident],id=len(cases)+1,location_id=ident,source=r['source'],before_judgment=judgments[ident]['after'],
            before_translation=' '.join(r['before_translations']),translation=' '.join(r['translations']),meaning_reviewed=False))
    assert len(cases)==52 and len(identical)==72
    out=folder/'visual-review';out.mkdir(exist_ok=True)
    sample=dict(cases=cases,identical_location_judgments=identical,previous_semantic_review_sha256=digest(previous),
        inference_summary_sha256=digest(folder/'summary.json'),all_chapter_words_visually_reviewed=False)
    atomic(out/'sample.json',json.dumps(sample,ensure_ascii=False,indent=2))
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',19);head=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',22)
    for start in range(0,len(cases),4):
        selected=cases[start:start+4]
        heights=[max(540,180+24*sum(len(textwrap.wrap(c[k],width=36)) for k in ['before_translation','translation','source'])) for c in selected]
        sheet=Image.new('RGB',(1440,sum(heights)),'#f1f4ed');draw=ImageDraw.Draw(sheet);top=0
        for case,height in zip(selected,heights):
            draw.text((12,top+8),f'Caso {case["id"]} · original / referencia / int4 e int8',font=head,fill='#243b2b')
            for x,key,bounds in [(12,'source_page',case['bounds']),(485,'reference_page',case['reference_bounds'])]:
                page=case[key];assert digest(pathlib.Path(page['path']))==page['sha256']
                with Image.open(page['path']) as image:
                    crop=image.crop([max(0,bounds[0]-50),max(0,bounds[1]-45),min(image.width,bounds[2]+50),min(image.height,bounds[3]+45)]).convert('RGB')
                    crop.thumbnail((460,height-90));sheet.paste(crop,(x+(460-crop.width)//2,top+50))
            y=top+50
            for label,key in [('Int4 actual','before_translation'),('Int8 experimental','translation'),('OCR idéntico','source')]:
                draw.text((965,y),label,font=head,fill='#243b2b');y+=30
                for line in textwrap.wrap(case[key],width=36):draw.text((965,y),line,font=font,fill='#222');y+=24
                y+=16
            assert y<top+height;top+=height
        sheet.save(out/f'sheet-{start//4+1:02d}.jpg',quality=94)
    print(json.dumps(dict(changed_locations=len(cases),identical_locations=len(identical),sheets=13)),flush=True)


if __name__=='__main__':main()
