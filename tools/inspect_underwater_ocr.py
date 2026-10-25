"""Inspect actual recognizer responses to crop geometry; no answer substitution."""
import json,pathlib,subprocess
import numpy as np
from PIL import Image

ROOT=pathlib.Path(__file__).resolve().parents[1]
case=ROOT/'build/full-comics/poco8008-underwater'
im=Image.open(case/'exact-geometry-source.png').convert('RGBA')
a=np.array(im)[:,:,[2,1,0,3]];raw=case/'exact-geometry-source.bgra';a.tofile(raw)
probe=json.loads((case/'exact-geometry-probe.log').read_text(encoding='utf-8-sig').strip())
regions=[]
for row in probe['lines']:
    if 'UNDERWATER' not in row['system']:continue
    l,t,r,b=row['bounds']
    for horizontal in [0,.3,.6,1.1]:
        for vertical in [3,1,0,-1,-2,-3,-4,-5,-6]:
            regions.append({'bounds':[max(0,l-int((b-t)*horizontal)),t-vertical,min(im.width,r+int((b-t)*horizontal)),b+vertical],
                'hint':row['system'],'horizontal':horizontal,'vertical':vertical})
value=dict(width=im.width,height=im.height,path=str(raw),regions=regions)
exe=ROOT/'build/local-model/Release/luma_ocr.exe';models=ROOT/'assets/models/opus-en-es'
process=subprocess.run([str(exe),str(models),str(models)],input=json.dumps(value)+'\n',text=True,encoding='utf-8',capture_output=True,timeout=90)
result=json.loads(process.stdout);(case/'padding-diagnosis.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
for region,reading in zip(regions,result['region_reads']):print(region['horizontal'],region['vertical'],reading)
