"""Measure known-fixture ink coverage; this is not comic OCR accuracy."""
import json,pathlib
import numpy as np
from PIL import Image,ImageDraw,ImageFont

ROOT=pathlib.Path(__file__).resolve().parents[1];QA=ROOT/'build/full-comics'
read=lambda name:[json.loads(s) for s in (QA/name).read_text(encoding='utf-8').splitlines()]
before=read('colour-baseline.jsonl');after=read('colour-new.jsonl');results=[]
for name in [r['chapter'] for r in before]:
    image=Image.open(QA/'colour-fixtures'/(name+'.png')).convert('RGB');pixels=np.asarray(image).astype(np.int16)
    ink=np.max(np.abs(pixels-pixels[0,0]),axis=2)>40
    def coverage(records):
        mask=np.zeros(ink.shape,dtype=bool);boxes=[]
        for row in records:
            if row['chapter']!=name:continue
            a,b,c,d=row['bounds'];mask[max(0,b):d,max(0,a):c]=True;boxes.append(row['bounds'])
        return round(float((mask&ink).sum()/max(1,ink.sum())),4),boxes
    first,first_boxes=coverage(before);last,last_boxes=coverage(after)
    recognized=' '.join(r['source'] for r in after if r['chapter']==name)
    results.append(dict(case=name,before_ink_coverage=first,after_ink_coverage=last,before_boxes=first_boxes,after_boxes=last_boxes,
        text_correct=recognized.casefold()=='the ancient sword',meaning_reviewed=False))
assert all(r['text_correct'] for r in results)
assert all(r['after_ink_coverage']>.85 for r in results)
(QA/'colour-summary.json').write_text(json.dumps({'scope':'Synthetic known text, not real-comic recall. Baseline already reads the nine phrases; the comparison also checks geometry.',
    'cases':results},ensure_ascii=False,indent=2),encoding='utf-8')
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',20)
canvas=Image.new('RGB',(1120,760),'#f1f5ef');draw=ImageDraw.Draw(canvas)
draw.text((24,16),'Luma · Coordenadas del texto inclinado',font=font,fill='#24372c')
draw.text((24,50),'Antes',font=font,fill='#a24822');draw.text((580,50),'Ahora',font=font,fill='#265b33')
for index,name in enumerate(['slanted-red','slanted-blue']):
    row=next(r for r in results if r['case']==name)
    for side,key,colour in [(0,'before_boxes','#cc5522'),(1,'after_boxes','#228844')]:
        image=Image.open(QA/'colour-fixtures'/(name+'.png')).convert('RGB');annotate=ImageDraw.Draw(image)
        for box in row[key]:annotate.rectangle(box,outline=colour,width=3)
        image=image.resize((520,267));canvas.paste(image,(24+side*556,90+index*300))
draw.text((24,700),'Prueba de posición con texto conocido. Los errores del cómic se revisan por separado.',font=font,fill='#34483a')
canvas.save(QA/'colour-geometry-comparison.png')
print(json.dumps(results,ensure_ascii=False,indent=2))
