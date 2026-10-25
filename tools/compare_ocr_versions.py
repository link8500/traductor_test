"""Development probes for English line models, not a semantic quality score."""
import json,math,pathlib
import numpy as np
import onnxruntime as ort
from PIL import Image,ImageOps

qa=pathlib.Path(__file__).resolve().parents[1]/'build/comic-quality'
sessions=[]
for name in ['english-rec.onnx','english-v5.onnx']:
    options=ort.SessionOptions();options.intra_op_num_threads=2
    model=ort.InferenceSession(str(qa/'ocr-candidate'/name),sess_options=options)
    sessions.append((model,['blank']+model.get_modelmeta().custom_metadata_map['character'].splitlines()+[' ']))

def read(image,model,characters):
    width=min(2048,max(8,math.ceil(48*image.width/image.height)))
    resized=image.resize((width,48),Image.Resampling.BILINEAR)
    data=np.zeros((1,3,48,max(320,width)),dtype=np.float32)
    data[0,:,:,:width]=(np.asarray(resized.convert('RGB'),dtype=np.float32)/127.5-1).transpose(2,0,1)
    values=model.run(None,{model.get_inputs()[0].name:data})[0][0]
    text=[];scores=[];previous=-1
    for row,index in zip(values,values.argmax(axis=-1)):
        if index and index!=previous:text.append(characters[index]);scores.append(float(row[index]))
        previous=index
    return ''.join(text).strip(),sum(scores)/max(1,len(scores))

rows=[json.loads(line) for line in (qa/'ocr-baseline.jsonl').read_text(encoding='utf-8').splitlines()]
chapters={chapter['id']:chapter for chapter in json.loads((qa/'manifest.json').read_text())}
selected=[]
for chapter in chapters:
    candidates=[r for r in rows if r['chapter']==chapter and r['image']>0 and len(r['source'])>60]
    selected+=candidates[:3]
    selected+=next(([r] for r in candidates if 'REGRESSOR' in r['source'] or 'CULTVATOR' in r['source']),[])
results=[]
for row in selected:
    with Image.open(qa/chapters[row['chapter']]['images'][row['image']]['path']) as original:
        left,top,right,bottom=row['bounds']
        image=original.convert('RGB').crop((max(0,left-8),max(0,top-6),min(original.width,right+8),min(original.height,bottom+6)))
    gray=np.asarray(image.convert('L'));border=np.concatenate((gray[0],gray[-1],gray[:,0],gray[:,-1]))
    if np.median(border)<128:image=ImageOps.invert(image)
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
    result={**row}
    for version,(model,characters) in enumerate(sessions,start=4):
        lines=[read(image.crop((0,max(0,a-2),image.width,min(image.height,b+2))),model,characters) for a,b in merged if b-a>7]
        result['v'+str(version)]=' '.join(text for text,_ in lines)
        result['v'+str(version)+'_confidence']=sum(score for _,score in lines)/max(1,len(lines))
    results.append(result)
    print(row['chapter'],'\nNative:',row['source'],'\nV4:',result['v4'],'\nV5:',result['v5'],flush=True)
(qa/'ocr-candidate/version-comparison.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
