"""Freeze artwork-mapped possible OCR omissions across all requested chapters.

Candidates are diagnostics, not confirmed errors. The inference files already
exist and are never modified or given reference text by this review tool.
"""
import bisect
import collections
import hashlib
import json
import pathlib
import textwrap

from PIL import Image, ImageDraw, ImageFont
from audit_corpus_quality import ROOT, QA, CHAPTERS, CURRENT, records, read, digest, atomic
from translation_quality_signals import PROMOTION, tokens

OUT=QA/'undetected-review8011'


def prepare():
    OUT.mkdir(exist_ok=True)
    target=OUT/'sample.json'
    if target.exists():return read(target)
    pages={lang:collections.defaultdict(dict) for lang in ['en','es']}
    for lang in pages:
        for page in read(QA/f'images-{lang}.json'):
            pages[lang][page['chapter'].removesuffix('-'+lang)][str(page['image'])]=page
    cases=[];coverage=[]
    for chapter in CHAPTERS:
        comparison_path=QA/'comparison8011-context'/(chapter+'.json')
        comparison=read(comparison_path)
        assert comparison['english_report_directory']==CURRENT
        en_path=QA/CURRENT/(chapter+'-en.jsonl');en=records(en_path)
        es_path=QA/'ocr-es'/(chapter+'-es.jsonl');es=records(es_path)
        ledger_path=comparison_path.with_name(chapter+'.words.jsonl')
        candidates={r['reference_region'] for r in records(ledger_path) if r['state']=='no_luma_region_nearby'}
        eligible=[i for i in candidates if 4<=len(tokens(es[i]['source']))<=45 and not PROMOTION.search(es[i]['source'])]
        coverage.append(dict(chapter=chapter,automatic_missing_region_candidates=len(candidates),eligible_regions=len(eligible)))
        if not eligible:continue
        index=min(eligible,key=lambda i:hashlib.sha256(f'omission:{chapter}:{i}'.encode()).hexdigest())
        ref=es[index];anchors=comparison['anchors']
        en_map=read(QA/'artwork'/(chapter+'-en.json'));es_map=read(QA/'artwork'/(chapter+'-es.json'))
        em=es_map[str(ref['image'])];sy=em['offset']+(ref['bounds'][1]+ref['bounds'][3])*em['scale']/2
        at=bisect.bisect_left([a['es'] for a in anchors],sy)
        assert 0<at<len(anchors)
        left,right=anchors[at-1],anchors[at]
        slope=(right['en']-left['en'])/(right['es']-left['es'])
        assert right['es']-left['es']<=1000 and .75<slope<1.33
        mapped=left['en']+(sy-left['es'])*slope
        source_key=max((k for k,v in en_map.items() if v['offset']<=mapped),key=lambda k:en_map[k]['offset'])
        page=pages['en'][chapter][source_key];loc=en_map[source_key]
        y=(mapped-loc['offset'])/loc['scale']
        height=max(320,(ref['bounds'][3]-ref['bounds'][1])*em['scale']*slope/loc['scale']+240)
        box=[0,max(0,round(y-height/2)),page['width'],min(page['height'],round(y+height/2))]
        nearby=[dict(index=i,**r) for i,r in enumerate(en) if r['image']==int(source_key) and
                r['bounds'][1]<box[3] and r['bounds'][3]>box[1]]
        cases.append(dict(id=len(cases)+1,chapter=chapter,reference_region=index,reference_source=ref['source'],
            reference_bounds=ref['bounds'],reference_page=pages['es'][chapter][str(ref['image'])],
            source_bounds=box,source_page=page,nearby_luma_regions=nearby,
            proposed_artwork_alignment_human_verified=False,source_pixels_inspected=False,meaning_reviewed=False,
            current_report_sha256=digest(en_path),reference_report_sha256=digest(es_path),
            comparison_sha256=digest(comparison_path),ledger_sha256=digest(ledger_path)))
    value=dict(schema=1,engine=CURRENT,chapters_checked=124,review_cases=len(cases),selection='One hashed eligible missing-region proposal per chapter where available; diagnostic selection.',
        all_chapter_words_reviewed=False,reference_used_by_application=False,coverage=coverage,cases=cases)
    atomic(target,json.dumps(value,ensure_ascii=False,indent=2));return value


def render(sample):
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)
    title=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',22)
    for start in range(0,len(sample['cases']),4):
        sheet=Image.new('RGB',(1440,2240),'#f1f4ed');draw=ImageDraw.Draw(sheet)
        for position,case in enumerate(sample['cases'][start:start+4]):
            top=position*560
            draw.text((12,top+8),f'Caso {case["id"]} · omisión propuesta: contexto EN / referencia ES / regiones de Luma',font=title,fill='#243b2b')
            for x,page,box in [(12,case['source_page'],case['source_bounds']), (485,case['reference_page'],case['reference_bounds'])]:
                assert digest(pathlib.Path(page['path']))==page['sha256']
                with Image.open(page['path']) as image:
                    crop=image.crop((max(0,box[0]-25),max(0,box[1]-25),min(image.width,box[2]+25),min(image.height,box[3]+25))).convert('RGB')
                    crop.thumbnail((460,465));sheet.paste(crop,(x+(460-crop.width)//2,top+50))
            y=top+48
            values=case['nearby_luma_regions']
            if not values:
                draw.text((965,y),'Sin región de Luma en este recorte.',font=font,fill='#222222')
            for row in values:
                for label,text in [('OCR',row['source']),('Luma',row.get('translation',''))]:
                    for line in textwrap.wrap(label+': '+text,width=43):
                        draw.text((965,y),line,font=font,fill='#222222');y+=23
                y+=12
        sheet.save(OUT/f'sheet-{start//4+1:02d}.jpg',quality=94)
    print(json.dumps(dict(chapters_checked=124,cases=len(sample['cases']),sheets=(len(sample['cases'])+3)//4),ensure_ascii=True))


if __name__=='__main__':render(prepare())
