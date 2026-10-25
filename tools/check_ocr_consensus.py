"""Regression: recover a real stylized U without copying an unverified hint."""
import hashlib,json,pathlib,re,subprocess
import numpy as np
from PIL import Image

ROOT=pathlib.Path(__file__).resolve().parents[1];CASE=ROOT/'build/full-comics/poco8008-underwater'
build=re.search(r'^version:.*\+(\d+)',(ROOT/'pubspec.yaml').read_text(),re.M)[1]
source=CASE/'exact-geometry-source.png';image=Image.open(source).convert('RGBA');raw=CASE/'exact-geometry-source.bgra'
np.array(image)[:,:,[2,1,0,3]].tofile(raw)
probe=json.loads((CASE/'exact-geometry-probe.log').read_text(encoding='utf-8-sig').strip());regions=[]
for line in probe['lines']:
    left,top,right,bottom=line['bounds'];padding=int((bottom-top)*1.1)
    regions.append(dict(bounds=[max(0,left-padding),top-3,min(image.width,right+padding),bottom+3],hint=line['system']))
positive=len(regions);incorrect='A MEAL THUNDERWATER'
index=next(i for i,line in enumerate(probe['lines']) if 'UNDERWATER' in line['system'])
regions.append({**regions[index],'hint':incorrect})
request=dict(width=image.width,height=image.height,path=str(raw),regions=regions)
models=ROOT/'assets/models/opus-en-es';process=subprocess.run([str(ROOT/'build/local-model/Release/luma_ocr.exe'),str(models),str(models)],input=json.dumps(request)+'\n',text=True,encoding='utf-8',capture_output=True,check=True,timeout=120)
result=json.loads(process.stdout)
key=lambda text:''.join(c for c in text.upper() if c.isalnum())
for region,reading in zip(regions[:positive],result['region_reads']):
    assert key(region['hint'])==key(reading['text']),(region,reading)
    assert reading['system_agreement'] and reading['confidence']>=.9,reading
assert key(result['region_reads'][-1]['text'])!=key(incorrect),'An unsupported hint was copied'
report=dict(success=True,verified_real_lines=positive,unverified_hint_rejected=True,source_fixture_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    source_sha256=hashlib.sha256((ROOT/'native/local_translation.cpp').read_bytes()).hexdigest(),readings=result['region_reads'])

# Windows supplies different line geometry. Exercise that recorded crop too.
windows_raw=CASE/'windows-source.bgra'
if windows_raw.exists():
    request=dict(width=900,height=2000,path=str(windows_raw),regions=[dict(bounds=[105,326,795,377],hint='A MEAL UNDERWATER')])
    process=subprocess.run([str(ROOT/'build/local-model/Release/luma_ocr.exe'),str(models),str(models)],input=json.dumps(request)+'\n',text=True,encoding='utf-8',capture_output=True,check=True,timeout=120)
    reading=json.loads(process.stdout)['region_reads'][0]
    assert key(reading['text'])==key('A MEAL UNDERWATER') and reading['system_agreement'],reading
    report['windows_recorded_line']=reading
    print('Windows recorded crop passed:',reading)
(CASE/f'consensus{build}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report))
