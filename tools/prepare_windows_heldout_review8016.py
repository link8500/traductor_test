"""Show each actual Windows translation beside original and proposed ES pixels."""
import json
import pathlib
import textwrap
from PIL import Image,ImageDraw,ImageFont
from audit_corpus_quality import QA,atomic,digest,read


def main():
    folder=QA/'windows8016-heldout-pixels';out=folder/'visual-review';out.mkdir(exist_ok=True)
    source=read(QA/'ocr-reader-heldout8016-source/sample.json')
    app=read(folder/'summary.json');entries={e['id']:e for e in app['entries']}
    cases=[]
    for seed in source['cases']:
        row=entries[seed['id']]
        cases.append(dict(seed,actual_windows=row,reference_alignment_visually_verified=False,meaning_reviewed=False))
    atomic(out/'sample.json',json.dumps(dict(cases=cases,source_sample_sha256=digest(QA/'ocr-reader-heldout8016-source/sample.json'),
        windows_summary_sha256=digest(folder/'summary.json'),all_chapter_words_visually_reviewed=False),ensure_ascii=False,indent=2))
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18);head=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',20)
    for start in range(0,len(cases),4):
        sheet=Image.new('RGB',(1600,2400),'#f1f4ed');draw=ImageDraw.Draw(sheet)
        for offset,case in enumerate(cases[start:start+4]):
            top=offset*600;draw.text((12,top+8),f'Caso {case["id"]} · EN original / Olympus propuesta / salida real Windows8016',font=head,fill='#243b2b')
            for x,key,bounds in [(12,'source_page',case['bounds']),(535,'reference_page',case['reference_bounds'])]:
                page=case[key];assert digest(pathlib.Path(page['path']))==page['sha256']
                with Image.open(page['path']) as bitmap:
                    crop=bitmap.crop([max(0,bounds[0]-50),max(0,bounds[1]-45),min(bitmap.width,bounds[2]+50),min(bitmap.height,bounds[3]+45)]).convert('RGB')
                    crop.thumbnail((505,520));sheet.paste(crop,(x+(505-crop.width)//2,top+50))
            y=top+50
            for label,value in [('Traducción Windows',' '.join(case['actual_windows']['translations'])),('Reconocimiento Windows',case['actual_windows']['source'])]:
                draw.text((1065,y),label,font=head,fill='#243b2b');y+=28
                for line in textwrap.wrap(value,width=43):draw.text((1065,y),line,font=font,fill='#222');y+=23
                y+=14
            assert y<=top+600,(case['id'],y-top)
        sheet.save(out/f'sheet-{start//4+1:02d}.jpg',quality=93)
    print(json.dumps(dict(cases=len(cases),sheets=31,meaning_review_pending=True)),flush=True)


if __name__=='__main__':main()
