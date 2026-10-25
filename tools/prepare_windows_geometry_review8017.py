"""Compare unchanged Windows NMT across the complete124-crop geometry trial."""
import argparse
import json
import pathlib
import textwrap
import time
from PIL import Image,ImageDraw,ImageFont
from audit_corpus_quality import ROOT,QA,atomic,digest,read


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--wait',action='store_true');parser.add_argument('--final',action='store_true');parser.add_argument('--render',action='store_true');args=parser.parse_args()
    folder=QA/('windows8017-render-heldout-pixels' if args.render else 'windows8017-final-heldout-pixels' if args.final else 'windows8017-preserve-heldout-pixels');path=folder/'summary.json'
    deadline=time.monotonic()+1800
    while args.wait and not path.exists() and time.monotonic()<deadline:time.sleep(20)
    current=read(path);before_path=QA/'windows8016-heldout-pixels/summary.json';before=read(before_path)
    semantic_path=ROOT/'benchmarks/full-comics/windows8016-heldout-semantic-review.json'
    judgments={e['id']:e for e in read(semantic_path)['entries']}
    originals={e['id']:e for e in read(QA/'windows8016-heldout-pixels/visual-review/sample.json')['cases']}
    out=folder/'visual-review';out.mkdir(exist_ok=True)
    cases=[];reused=[]
    assert len(current['entries'])==len(before['entries'])==124
    for old,new in zip(before['entries'],current['entries']):
        assert old['id']==new['id'] and old['source']==new['source'],'Geometry change must retain all original OCR words and punctuation'
        if old['translations']==new['translations']:
            reused.append(dict(id=old['id'],judgment=judgments[old['id']]['after'],source=old['source'],translations=old['translations']))
            continue
        seed=originals[old['id']]
        cases.append(dict(seed,id=len(cases)+1,location_id=old['id'],before_translation=' '.join(old['translations']),
            translation=' '.join(new['translations']),before_judgment=judgments[old['id']]['after'],meaning_reviewed=False))
    value=dict(cases=cases,reused_identical_location_outputs=reused,locations=124,
        source_strings_identical=True,changed_locations=len(cases),
        baseline_summary_sha256=digest(before_path),current_summary_sha256=digest(path),
        previous_semantic_review_sha256=digest(semantic_path),all_chapter_words_visually_reviewed=False)
    atomic(out/'sample.json',json.dumps(value,ensure_ascii=False,indent=2))
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',19);head=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',22)
    for start in range(0,len(cases),2):
        sheet=Image.new('RGB',(1600,2100),'#f1f4ed');draw=ImageDraw.Draw(sheet)
        for offset,case in enumerate(cases[start:start+2]):
            top=offset*1050;draw.text((12,top+8),f'Caso {case["id"]} · EN original / referencia propuesta / Windows anterior y unión nueva',font=head,fill='#243b2b')
            for x,key,bounds in [(12,'source_page',case['bounds']),(535,'reference_page',case['reference_bounds'])]:
                page=case[key];assert digest(pathlib.Path(page['path']))==page['sha256']
                with Image.open(page['path']) as bitmap:
                    crop=bitmap.crop([max(0,bounds[0]-50),max(0,bounds[1]-45),min(bitmap.width,bounds[2]+50),min(bitmap.height,bounds[3]+45)]).convert('RGB')
                    crop.thumbnail((505,950));sheet.paste(crop,(x+(505-crop.width)//2,top+50))
            y=top+50
            for label,key in [('Windows8016','before_translation'),('Unión con lectura conservada','translation'),('Reconocimiento idéntico','source')]:
                if key=='source':text=case['actual_windows']['source']
                else:text=case[key]
                draw.text((1065,y),label,font=head,fill='#243b2b');y+=31
                for line in textwrap.wrap(text,width=42):draw.text((1065,y),line,font=font,fill='#222');y+=25
                y+=20
            assert y<=top+1050
        sheet.save(out/f'sheet-{start//2+1:02d}.jpg',quality=94)
    print(json.dumps({k:v for k,v in value.items() if k not in ['cases','reused_identical_location_outputs']}),flush=True)


if __name__=='__main__':main()
