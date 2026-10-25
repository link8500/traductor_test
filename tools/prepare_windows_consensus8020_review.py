"""Show every actual Windows reader-integration change for visual meaning review."""
import json
import pathlib
import textwrap
from PIL import Image,ImageDraw,ImageFont
from audit_corpus_quality import ROOT,QA,atomic,digest,read


def main():
    folder=QA/'windows8020-consensus-heldout-pixels';summary=read(folder/'summary.json')
    previous=ROOT/'benchmarks/full-comics/windows8019-heldout-semantic-review.json';old={r['id']:r for r in read(previous)['entries']}
    templates={r['id']:r for r in read(QA/'windows8016-heldout-pixels/visual-review/sample.json')['cases']}
    cases=[];identical=[]
    for row in summary['entries']:
        ident=row['id'];before=' '.join(row['before_translations']);after=' '.join(row['translations'])
        assert old[ident]['translation']==before
        if row['before_source']==row['source'] and before==after:
            identical.append(dict(id=ident,source=row['source'],translation=after,judgment=old[ident]['after']));continue
        cases.append(dict(templates[ident],id=len(cases)+1,location_id=ident,before_source=row['before_source'],source=row['source'],
            before_translation=before,translation=after,before_judgment=old[ident]['after'],meaning_reviewed=False))
    out=folder/'visual-review';out.mkdir(exist_ok=True)
    sample=dict(cases=cases,identical_location_outputs=identical,previous_review_sha256=digest(previous),
        inference_summary_sha256=digest(folder/'summary.json'),application_default_enabled=False,all_chapter_words_visually_reviewed=False)
    atomic(out/'sample.json',json.dumps(sample,ensure_ascii=False,indent=2))
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',19);head=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',23)
    for start in range(0,len(cases),2):
        selected=cases[start:start+2];heights=[max(900,220+24*sum(len(textwrap.wrap(c[k],width=40)) for k in ['before_source','source','before_translation','translation'])) for c in selected]
        sheet=Image.new('RGB',(1600,sum(heights)),'#f1f4ed');draw=ImageDraw.Draw(sheet);top=0
        for case,height in zip(selected,heights):
            draw.text((12,top+8),f'Caso {case["id"]} · original / referencia / Windows anterior y consenso',font=head,fill='#243b2b')
            for x,key,bounds in [(12,'source_page',case['bounds']),(535,'reference_page',case['reference_bounds'])]:
                page=case[key];assert digest(pathlib.Path(page['path']))==page['sha256']
                with Image.open(page['path']) as original:
                    crop=original.crop([max(0,bounds[0]-50),max(0,bounds[1]-45),min(original.width,bounds[2]+50),min(original.height,bounds[3]+45)]).convert('RGB')
                    crop.thumbnail((505,height-85));sheet.paste(crop,(x+(505-crop.width)//2,top+50))
            y=top+50
            for label,key in [('OCR anterior','before_source'),('OCR con consenso','source'),('Traducción anterior','before_translation'),('Traducción con consenso','translation')]:
                draw.text((1065,y),label,font=head,fill='#243b2b');y+=32
                for line in textwrap.wrap(case[key],width=40):draw.text((1065,y),line,font=font,fill='#222');y+=24
                y+=14
            assert y<top+height;top+=height
        sheet.save(out/f'sheet-{start//2+1:02d}.jpg',quality=95)
    print(json.dumps(dict(changed_locations=len(cases),identical_locations=len(identical),sheets=(len(cases)+1)//2)),flush=True)


if __name__=='__main__':main()
