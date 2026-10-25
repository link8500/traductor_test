"""Show original pixels for changed diagnostic outputs without an ES alignment.

These cases are kept separate from the comparison sample. A missing alignment
must never be replaced by an unrelated Spanish balloon.
"""
import json
import pathlib
import textwrap
from PIL import Image, ImageDraw, ImageFont
from audit_corpus_quality import QA, CURRENT, read, records, digest, atomic


def main():
    folder=QA/'sentence-coverage8014';out=folder/'unaligned-review';out.mkdir(exist_ok=True)
    reviewed=read(QA/'omission-review8011/sample.json')
    known={(c['chapter']+'-en',c['region_index']) for c in reviewed['cases']}
    pages={(r['chapter'],r['image']):r for r in read(QA/'images-en.json')}
    cases=[]
    for pair in read(folder/'omission-candidate.json')['cases']:
        if not pair['current']['sentence_recovered'] or (pair['chapter'],pair['region_index']) in known:continue
        report=QA/CURRENT/(pair['chapter']+'.jsonl');row=records(report)[pair['region_index']]
        assert row['source']==pair['source'] and row['translation']==pair['control_translation']
        cases.append(dict(id=len(cases)+1,chapter=pair['chapter'],region_index=pair['region_index'],source=pair['source'],
            before_translation=pair['control_translation'],translation=pair['current']['translation'],bounds=row['bounds'],
            source_page=pages[(pair['chapter'],row['image'])],source_report_sha256=digest(report),
            spanish_reference_alignment_available=False,meaning_reviewed=False))
    sample=dict(cases=cases,chapters=len({c['chapter'] for c in cases}),native_output_sha256=digest(folder/'output.jsonl'),
        automatic_candidate_selection=True,population_accuracy_estimate=False,all_chapter_words_visually_reviewed=False)
    atomic(out/'sample.json',json.dumps(sample,ensure_ascii=False,indent=2))
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',22)
    heading=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',25)
    for start in range(0,len(cases),4):
        sheet=Image.new('RGB',(1440,2240),'#f1f4ed');draw=ImageDraw.Draw(sheet)
        for offset,case in enumerate(cases[start:start+4]):
            top=offset*560;page=case['source_page'];bounds=case['bounds']
            draw.text((16,top+8),f'Caso {case["id"]} · EN original / salida anterior y actual',font=heading,fill='#243b2b')
            assert digest(pathlib.Path(page['path']))==page['sha256']
            with Image.open(page['path']) as img:
                crop=img.crop((max(0,bounds[0]-80),max(0,bounds[1]-100),min(img.width,bounds[2]+80),min(img.height,bounds[3]+100))).convert('RGB')
                crop.thumbnail((650,480));sheet.paste(crop,(12+(650-crop.width)//2,top+48))
            y=top+48
            for label,value in [('Referencia ES','Sin correspondencia alineada: se evalúa contra el inglés visible.'),('Antes',case['before_translation']),('Actual',case['translation']),('OCR',case['source'])]:
                draw.text((695,y),label,font=heading,fill='#243b2b');y+=30
                for line in textwrap.wrap(value,width=62):draw.text((695,y),line,font=font,fill='#222');y+=26
                y+=12
        sheet.save(out/f'sheet-{start//4+1:02d}.jpg',quality=93)
    print(json.dumps(dict(cases=len(cases),sheets=(len(cases)+3)//4)))


if __name__=='__main__':main()
