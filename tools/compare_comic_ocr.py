"""Evaluate a small local line recognizer on pixels where native OCR failed."""
import json,pathlib,math
import numpy as np
import onnxruntime as ort
from PIL import Image,ImageOps
root=pathlib.Path(__file__).resolve().parents[1]/'build/comic-quality'
settings=ort.SessionOptions();settings.intra_op_num_threads=2
session=ort.InferenceSession(str(root/'ocr-candidate/english-rec.onnx'),sess_options=settings)
characters=['blank']+session.get_modelmeta().custom_metadata_map['character'].splitlines()+[' ']
def recognize(image):
    width=max(320,math.ceil(48*image.width/image.height));width=min(2048,width)
    resized=image.resize((width,48),Image.Resampling.BILINEAR)
    data=(np.asarray(resized.convert('RGB'),dtype=np.float32)/255-.5)/.5
    probabilities=session.run(None,{'x':data.transpose(2,0,1)[None]})[0][0]
    ids=probabilities.argmax(axis=-1);text=[];scores=[];previous=-1
    for step,index in enumerate(ids):
        if index and index!=previous:text.append(characters[index]);scores.append(float(probabilities[step,index]))
        previous=index
    return ''.join(text),sum(scores)/max(1,len(scores))
rows=[json.loads(line) for line in (root/'ocr-baseline.jsonl').read_text(encoding='utf-8').splitlines()]
chapters={chapter['id']:chapter for chapter in json.loads((root/'manifest.json').read_text())}
selected=[]
for chapter in chapters:
    candidates=[row for row in rows if row['chapter']==chapter and row['image']>0 and len(row['source'])>60]
    selected+=candidates[:3]
selected += [row for row in rows if 'CULTVATOR' in row['source']][:1]
report=[]
for row in selected:
    with Image.open(root/chapters[row['chapter']]['images'][row['image']]['path']) as original:
        left,top,right,bottom=row['bounds'];image=original.convert('RGB').crop((max(0,left-8),max(0,top-6),min(original.width,right+8),min(original.height,bottom+6)))
    gray=np.asarray(image.convert('L'));perimeter=np.concatenate((gray[0],gray[-1],gray[:,0],gray[:,-1]))
    if np.median(perimeter)<128:image=ImageOps.invert(image)
    gray=np.asarray(image.convert('L'));ink=(gray<128).sum(axis=1)>max(3,image.width*.015)
    spans=[];start=None
    for y,value in enumerate(ink):
        if value and start is None:start=y
        if not value and start is not None:spans.append([start,y]);start=None
    if start is not None:spans.append([start,image.height])
    merged=[]
    for span in spans:
        if merged and span[0]-merged[-1][1]<5:merged[-1][1]=span[1]
        else:merged.append(span)
    lines=[recognize(image.crop((0,max(0,a-2),image.width,min(image.height,b+2)))) for a,b in merged if b-a>7]
    item={**row,'candidate':' '.join(t for t,_ in lines),'confidence':sum(s for _,s in lines)/max(1,len(lines))};report.append(item)
    print(row['chapter'],row['source'],'=>',item['candidate'],flush=True)
(root/'ocr-candidate/comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
