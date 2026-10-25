"""Render every change selected across the complete124-source corpus."""
import argparse
import collections
import json
import pathlib
import textwrap
from PIL import Image,ImageDraw,ImageFont
from audit_corpus_quality import QA,atomic,digest,read,records


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--compact',action='store_true');args=parser.parse_args()
    folder=QA/'full-corpus-coverage8018';changes=read(folder/'changed.json')['cases']
    out=folder/('visual-review-compact' if args.compact else 'visual-review');out.mkdir(exist_ok=True)
    pages={lang:{(r['chapter'].removesuffix('-'+lang),r['image']):r for r in read(QA/f'images-{lang}.json')} for lang in ['en','es']}
    refs={};ledgers={};cases=[]
    for row in changes:
        chapter=row['chapter']
        if chapter not in refs:refs[chapter]=records(QA/'ocr-es'/(chapter+'-es.jsonl'))
        if chapter not in ledgers:ledgers[chapter]=records(QA/'comparison8014-recovery'/(chapter+'.words.jsonl'))
        proposed=collections.Counter(r['reference_region'] for r in ledgers[chapter] if r['luma_region']==row['region'])
        ref=refs[chapter][proposed.most_common(1)[0][0]] if proposed else None
        cases.append(dict(row,id=len(cases)+1,source_page=pages['en'][(chapter,row['image'])],
            reference_page=pages['es'][(chapter,ref['image'])] if ref else None,reference_bounds=ref['bounds'] if ref else None,
            reference_alignment_requires_visual_check=True,meaning_reviewed=False))
    value=dict(cases=cases,changed_regions=len(changes),changed_output_sha256=digest(folder/'changed.json'),
        corpus_summary_sha256=digest(folder/'summary.json'),all_chapter_words_visually_reviewed=False)
    path=out/'sample.json'
    if path.exists():assert read(path)==value
    else:atomic(path,json.dumps(value,ensure_ascii=False,indent=2))
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',19);head=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',22)
    per_sheet=4 if args.compact else 2
    for start in range(0,len(cases),per_sheet):
        selected=cases[start:start+per_sheet]
        heights=[max(520 if args.compact else 1000,180+24*sum(len(textwrap.wrap(c[k],width=43)) for k in ['before_translation','translation','source'])) for c in selected]
        sheet=Image.new('RGB',(1440,sum(heights)),'#f1f4ed');draw=ImageDraw.Draw(sheet);top=0
        for case,height in zip(selected,heights):
            draw.text((12,top+8),f'Caso {case["id"]} · original / referencia propuesta / traductores reales',font=head,fill='#243b2b')
            for x,key,bounds in [(12,'source_page',case['bounds']),(485,'reference_page',case['reference_bounds'])]:
                page=case[key]
                if not page:draw.text((x,top+60),'Referencia sin alinear',font=font,fill='#243b2b');continue
                assert digest(pathlib.Path(page['path']))==page['sha256']
                with Image.open(page['path']) as image:
                    crop=image.crop([max(0,bounds[0]-65),max(0,bounds[1]-65),min(image.width,bounds[2]+65),min(image.height,bounds[3]+65)]).convert('RGB')
                    crop.thumbnail((460,height-90));sheet.paste(crop,(x+(460-crop.width)//2,top+50))
            y=top+50
            for label,key in [('Anterior','before_translation'),('Actual','translation'),('OCR idéntico','source')]:
                draw.text((965,y),label,font=head,fill='#243b2b');y+=30
                for line in textwrap.wrap(case[key],width=43):draw.text((965,y),line,font=font,fill='#222');y+=24
                y+=16
            assert y<top+height;top+=height
        sheet.save(out/f'sheet-{start//per_sheet+1:02d}.jpg',quality=94)
    print(json.dumps(dict(changed_regions=len(cases),sheets=(len(cases)+per_sheet-1)//per_sheet)),flush=True)


if __name__=='__main__':main()
