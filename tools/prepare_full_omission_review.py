"""Prepare every changed corpus output; never approve it from the retry flag."""
import collections
import json
import math
import pathlib
import textwrap
from PIL import Image,ImageDraw,ImageFont
from audit_corpus_quality import ROOT,QA,read,records,digest,atomic


def main():
    folder=QA/'full-omission-candidate8016';out=folder/'visual-review';out.mkdir(exist_ok=True)
    changes=read(folder/'changed.json')['cases'];known=read(QA/'sentence-coverage8016/visual-review/sample.json')['cases']
    known_decisions={r[0]:r for r in read(QA/'sentence-coverage8016/visual-review/manual-decisions.json')}
    pages={lang:{(r['chapter'].removesuffix('-'+lang),r['image']):r for r in read(QA/f'images-{lang}.json')} for lang in ['en','es']}
    references={};ledgers={};cases=[];reused=[]
    for change in changes:
        original=pages['en'][(change['chapter'],change['image'])]
        match=next((c for c in known if c['chapter']==change['chapter'] and c['source_image']==change['image'] and c['bounds']==change['bounds'] and all(c[k]==change[k] for k in ['source','before_translation','translation'])),None)
        if match:
            reused.append(dict(**change,decision=known_decisions[match['id']],known_case_id=match['id'],source_page=original));continue
        chapter=change['chapter']
        if chapter not in references:references[chapter]=records(QA/'ocr-es'/(chapter+'-es.jsonl'))
        if chapter not in ledgers:ledgers[chapter]=records(QA/'comparison8014-fixed-ocr'/(chapter+'.words.jsonl'))
        proposed=collections.Counter(r['reference_region'] for r in ledgers[chapter] if r['luma_region']==change['region'])
        ref=references[chapter][proposed.most_common(1)[0][0]] if proposed else None
        cases.append(dict(**change,id=len(cases)+1,source_image=change['image'],source_page=original,
            reference_page=pages['es'][(chapter,ref['image'])] if ref else None,reference_bounds=ref['bounds'] if ref else None,
            reference_proposal_requires_visual_check=True))
    sample=dict(cases=cases,reused_pixel_judgments=reused,changed_regions=len(changes),pending_cases=len(cases),
        candidate_output_sha256=digest(folder/'changed.json'),previous_sample_sha256=digest(QA/'sentence-coverage8016/visual-review/sample.json'),
        previous_manual_sha256=digest(QA/'sentence-coverage8016/visual-review/manual-decisions.json'),all_chapter_words_visually_reviewed=False)
    path=out/'sample.json'
    if path.exists():assert read(path)==sample
    else:atomic(path,json.dumps(sample,ensure_ascii=False,indent=2))
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',19);head=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',22)
    for start in range(0,len(cases),2):
        selected=cases[start:start+2];heights=[max(1050,180+24*sum(len(textwrap.wrap(c[k],width=43)) for k in ['before_translation','translation','source'])) for c in selected]
        sheet=Image.new('RGB',(1440,sum(heights)),'#f1f4ed');draw=ImageDraw.Draw(sheet);top=0
        for case,height in zip(selected,heights):
            draw.text((12,top+8),f'Caso {case["id"]} · EN original / ES propuesta / inferencias reales',font=head,fill='#243b2b')
            for x,key,bounds in [(12,'source_page',case['bounds']),(485,'reference_page',case['reference_bounds'])]:
                page=case[key]
                if page is None:draw.text((x,top+60),'Sin referencia alineada',font=font,fill='#243b2b');continue
                assert digest(pathlib.Path(page['path']))==page['sha256']
                with Image.open(page['path']) as bitmap:
                    box=[max(0,bounds[0]-70),max(0,bounds[1]-70),min(bitmap.width,bounds[2]+70),min(bitmap.height,bounds[3]+70)]
                    crop=bitmap.crop(box).convert('RGB');crop.thumbnail((460,height-85));sheet.paste(crop,(x+(460-crop.width)//2,top+50))
            y=top+50
            for label,key in [('Antes','before_translation'),('Candidato','translation'),('OCR fijo','source')]:
                draw.text((965,y),label,font=head,fill='#243b2b');y+=30
                for line in textwrap.wrap(case[key],width=43):draw.text((965,y),line,font=font,fill='#222');y+=24
                y+=16
            assert y<=top+height
            top+=height
        sheet.save(out/f'sheet-{start//2+1:02d}.jpg',quality=93)
    print(json.dumps(dict(changed_regions=len(changes),reused_same_pixel_judgments=len(reused),new_cases_pending=len(cases),sheets=math.ceil(len(cases)/2))),flush=True)


if __name__=='__main__':main()
