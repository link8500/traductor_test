"""Visual review samples: original pixels paired with app OCR, kept in build/."""
import json,pathlib,textwrap
from PIL import Image,ImageDraw,ImageOps
root=pathlib.Path(__file__).resolve().parents[1]/'build/comic-quality'
rows=[json.loads(line) for line in (root/'ocr-baseline.jsonl').read_text(encoding='utf-8').splitlines()]
chapters={chapter['id']:chapter for chapter in json.loads((root/'manifest.json').read_text())}
selected=[]
for chapter in chapters:
    candidates=[row for row in rows if row['chapter']==chapter and row['image']>0 and len(row['source'])>70]
    preferred=[row for row in candidates if any(term in row['source'] for term in ['MUSCIES','CULTVATOR','D1SCIPLES'])]
    selected.append((preferred or candidates)[0])
cards=[]
for row in selected:
    image=Image.open(root/chapters[row['chapter']]['images'][row['image']]['path']).convert('RGB')
    left,top,right,bottom=row['bounds'];crop=image.crop((max(0,left-30),max(0,top-25),min(image.width,right+30),min(image.height,bottom+25)))
    crop=ImageOps.contain(crop,(800,330));card=Image.new('RGB',(840,crop.height+100),'#f3f4ef');card.paste(crop,((840-crop.width)//2,30))
    draw=ImageDraw.Draw(card);draw.text((12,8),row['chapter']+' / image '+str(row['image']),fill='black')
    draw.text((12,crop.height+40),'OCR: '+textwrap.fill(row['source'],100),fill='black');cards.append(card)
sheet=Image.new('RGB',(840,sum(card.height for card in cards)), 'white');y=0
for card in cards:sheet.paste(card,(0,y));y+=card.height
sheet.save(root/'review-original-ocr.png')
print(root/'review-original-ocr.png')
