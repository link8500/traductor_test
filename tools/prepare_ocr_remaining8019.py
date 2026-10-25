"""Expose all108 previously unchanged, uninspected third-cohort locations."""
import json
import pathlib
import textwrap
from PIL import Image,ImageDraw,ImageFont
from audit_corpus_quality import ROOT,QA,atomic,digest,read,records


def main():
    folder=QA/'ocr-coverage8017-holdout';sample=read(folder/'sample.json')
    changed_path=ROOT/'benchmarks/full-comics/ocr8017-coverage-heldout-review.json'
    changed=read(changed_path);known={r['location_id'] for r in changed['entries']}
    old={r['id']:r for r in records(folder/'coverage/output.jsonl')}
    output_path=QA/'ocr-apostrophes8019/ocr-coverage8017-holdout-output.jsonl';new={r['id']:r for r in records(output_path)}
    assert all(new[i]['selected']==old[i]['selected'] for i in old)
    out=QA/'ocr-apostrophes8019/remaining-third';out.mkdir(exist_ok=True)
    cases=[dict(c,review_id=len([x for x in sample['cases'][:i] if x['id'] not in known])+1,
        candidate=new[c['id']]['selected']) for i,c in enumerate(sample['cases']) if c['id'] not in known]
    assert len(cases)==108
    value=dict(cases=cases,previous_changed_review_sha256=digest(changed_path),native_output_sha256=digest(output_path),
        original_sample_sha256=digest(folder/'sample.json'),all108_meanings_reviewed=False)
    atomic(out/'sample.json',json.dumps(value,ensure_ascii=False,indent=2))
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',20);head=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',23)
    for start in range(0,len(cases),4):
        selected=cases[start:start+4];heights=[max(550,160+26*(len(textwrap.wrap(c['readings']['current'],width=65))+len(textwrap.wrap(c['candidate'],width=65)))) for c in selected]
        sheet=Image.new('RGB',(1600,sum(heights)),'#f1f4ed');draw=ImageDraw.Draw(sheet);top=0
        for case,height in zip(selected,heights):
            draw.text((12,top+8),f'Lectura {case["review_id"]} · original completo del recorte / base y candidato',font=head,fill='#243b2b')
            assert digest(pathlib.Path(case['preview']))==case['preview_sha256']
            with Image.open(case['preview']) as original:
                crop=original.convert('RGB');crop.thumbnail((760,height-75));sheet.paste(crop,(12+(760-crop.width)//2,top+50))
            y=top+50
            for label,text in [('OCR actual',case['readings']['current']),('Candidato protegido',case['candidate'])]:
                draw.text((810,y),label,font=head,fill='#243b2b');y+=32
                for line in textwrap.wrap(text,width=65):draw.text((810,y),line,font=font,fill='#222');y+=26
                y+=20
            assert y<top+height;top+=height
        sheet.save(out/f'sheet-{start//4+1:02d}.jpg',quality=95)
    print(json.dumps(dict(locations=108,sheets=27)),flush=True)


if __name__=='__main__':main()
