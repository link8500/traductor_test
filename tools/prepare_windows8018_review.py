"""Inspect every actual Windows8018 change on the complete124 heldout cohort."""
import json
import pathlib
import textwrap
from PIL import Image,ImageDraw,ImageFont
from audit_corpus_quality import ROOT,QA,atomic,digest,read


def main():
    folder=QA/'windows8018-heldout-pixels';before_folder=QA/'windows8017-render-heldout-pixels'
    old=read(before_folder/'summary.json');new=read(folder/'summary.json')
    report_path=ROOT/'benchmarks/full-comics/windows8017-render-geometry-semantic-review.json'
    judgments={e['id']:e for e in read(report_path)['entries']}
    templates={c['id']:c for c in read(QA/'windows8016-heldout-pixels/visual-review/sample.json')['cases']}
    assert len(old['entries'])==len(new['entries'])==124
    cases=[];identical=[]
    for a,b in zip(old['entries'],new['entries']):
        assert a['id']==b['id'] and a['source']==b['source'] and a['regions']==b['regions']
        ident=a['id']
        if a['translations']==b['translations']:
            identical.append(dict(id=ident,judgment=judgments[ident]['after'],source=b['source'],translations=b['translations']));continue
        cases.append(dict(templates[ident],id=len(cases)+1,location_id=ident,actual_windows=b,
            before_judgment=judgments[ident]['after'],before_translation=' '.join(a['translations']),translation=' '.join(b['translations']),meaning_reviewed=False))
    value=dict(cases=cases,identical_location_judgments=identical,all_124_source_strings_preserved=True,
        before_summary_sha256=digest(before_folder/'summary.json'),after_summary_sha256=digest(folder/'summary.json'),
        previous_semantic_review_sha256=digest(report_path),all_chapter_words_visually_reviewed=False)
    out=folder/'visual-review';out.mkdir(exist_ok=True);atomic(out/'sample.json',json.dumps(value,ensure_ascii=False,indent=2))
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',19);head=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',22)
    for start in range(0,len(cases),2):
        sheet=Image.new('RGB',(1600,2100),'#f1f4ed');draw=ImageDraw.Draw(sheet)
        for offset,case in enumerate(cases[start:start+2]):
            top=offset*1050;draw.text((12,top+8),f'Caso {case["id"]} · original / referencia / app real anterior y actual',font=head,fill='#243b2b')
            for x,key,bounds in [(12,'source_page',case['bounds']),(535,'reference_page',case['reference_bounds'])]:
                page=case[key];assert digest(pathlib.Path(page['path']))==page['sha256']
                with Image.open(page['path']) as image:
                    crop=image.crop([max(0,bounds[0]-50),max(0,bounds[1]-45),min(image.width,bounds[2]+50),min(image.height,bounds[3]+45)]).convert('RGB')
                    crop.thumbnail((505,950));sheet.paste(crop,(x+(505-crop.width)//2,top+50))
            y=top+50
            for label,key in [('Anterior','before_translation'),('Actual','translation'),('Reconocimiento idéntico','source')]:
                text=case['actual_windows']['source'] if key=='source' else case[key]
                draw.text((1065,y),label,font=head,fill='#243b2b');y+=31
                for line in textwrap.wrap(text,width=42):draw.text((1065,y),line,font=font,fill='#222');y+=25
                y+=20
            assert y<top+1050
        sheet.save(out/f'sheet-{start//2+1:02d}.jpg',quality=94)
    print(json.dumps(dict(actual_pixel_locations=124,changed_locations=len(cases),identical_outputs=len(identical),source_strings_preserved=True)),flush=True)


if __name__=='__main__':main()
