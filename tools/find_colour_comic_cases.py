"""Propose real-colour cases for visual review; colour is not an accuracy label."""
import json,pathlib,re
import numpy as np
from PIL import Image,ImageDraw,ImageFont

ROOT=pathlib.Path(__file__).resolve().parents[1];QA=ROOT/'build/full-comics';directory=QA/'style-review';directory.mkdir(exist_ok=True)
images={(r['chapter'],r['image']):r for r in json.loads((QA/'images-en.json').read_text(encoding='utf-8'))}
candidates=[]
for done in (QA/'translated-en').glob('*.done.json'):
    chapter=json.loads(done.read_text(encoding='utf-8'))['chapter']
    for line in (QA/'translated-en'/(chapter+'.jsonl')).read_text(encoding='utf-8').splitlines():
        row=json.loads(line)
        if not row.get('additional_detection') or row.get('native_words') or len(row['source'])<5 or re.search(r'asura|https?|discord|\.com|\.net',row['source'],re.I):continue
        entry=images[(row['chapter'],row['image'])];a,b,c,d=row['bounds']
        if row['image']==0 or c-a<30 or d-b<15 or d-b>650:continue
        with Image.open(entry['path']) as image:
            crop=image.convert('RGB').crop((max(0,a-5),max(0,b-5),min(image.width,c+5),min(image.height,d+5)))
        pixels=np.asarray(crop,dtype=np.float32);border=np.concatenate((pixels[0],pixels[-1],pixels[:,0],pixels[:,-1]));bg=np.median(border,axis=0)
        ink=np.max(abs(pixels-bg),axis=2)>65;saturation=pixels.max(axis=2)-pixels.min(axis=2)
        ratio=float(((saturation>75)&ink).sum()/max(1,ink.sum()))
        if ratio<.12:continue
        candidates.append(dict(**row,path=entry['path'],colour_proposal=ratio,word_reviewed=False))
candidates.sort(key=lambda r:-r['colour_proposal']);selected=candidates[:12]
(directory/'candidates.json').write_text(json.dumps(selected,ensure_ascii=False,indent=2),encoding='utf-8')
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',15)
for start in range(0,len(selected),6):
    canvas=Image.new('RGB',(1200,1000),'#f2f5ef');draw=ImageDraw.Draw(canvas)
    for i,row in enumerate(selected[start:start+6]):
        x=(i%2)*600;y=(i//2)*330;a,b,c,d=row['bounds']
        with Image.open(row['path']) as image:crop=image.convert('RGB').crop((max(0,a-20),max(0,b-20),min(image.width,c+20),min(image.height,d+20)))
        crop.thumbnail((570,245));canvas.paste(crop,(x+12,y+38))
        draw.text((x+12,y+10),f"{start+i}: {row['chapter']} · imagen {row['image']}",font=font,fill='#233729')
        draw.text((x+12,y+288),row['source'][:73],font=font,fill='#233729')
    canvas.save(directory/f'contact-{start//6}.png')
print('Candidate colour regions',len(candidates),'selected',len(selected))
for i,row in enumerate(selected):print(i,row['chapter'],row['image'],repr(row['source']))
