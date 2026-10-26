"""Prepare broader frozen train/validation proposals, without opening test chapters."""
import concurrent.futures
import json
import pathlib
import re
import shutil
import textwrap
import time
import cv2
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import prepare_finetune8031 as data
import prepare_finetune8031_pairs as prior

ROOT=data.ROOT;META=ROOT/'benchmarks/finetune8034';OUT=ROOT/'build/finetune8034'
read=prior.read;save=data.save;sha=data.sha


def fetch(url,referer=None):
    for attempt in range(3):
        try:return data.request(url,referer)
        except Exception:
            if attempt==2:raise
            time.sleep(2*(attempt+1))


def pages():
    protocol=read(META/'data-protocol.json');source=read(data.META/'sources.json')
    assert protocol['source_inventory_sha256']==sha(data.META/'sources.json')
    selected={n:s for s,ns in protocol['selected_chapters'].items() for n in ns};assert 'test' not in selected.values()
    work=[];readers=[]
    for r in source['records']:
        if r['chapter'] not in selected:continue
        assert r['split']==selected[r['chapter']] and r['split']!='test'
        p=OUT/'readers'/(r['id']+'.html');p.parent.mkdir(parents=True,exist_ok=True)
        if not p.exists():p.write_text(fetch(r['url']).text,encoding='utf-8')
        text=p.read_text(encoding='utf-8')
        if r['language']=='es':parser=data.Images();parser.feed(text);images=[u for _,u in sorted(parser.rows)]
        else:
            m=re.search(r'\bvar\s+thzq\s*=\s*\[(.*?)\]\s*;',text,re.S);assert m,r['id']
            images=re.findall(r"['\"](https://[^'\"]+)['\"]",m[1])
        assert 5<=len(images)<=150 and len(images)==len(set(images))
        readers.append(dict(r,html_sha256=sha(p),all_page_urls=images,pages_available=len(images)))
        for i,url in enumerate(images[:protocol['maximum_pages_per_language']]):
            work.append(dict(chapter=r['chapter'],language=r['language'],split=r['split'],page=i,url=url,chapter_url=r['url'],
                path=str(OUT/'images'/r['id']/(f'{i:03d}'+('.webp' if r['language']=='es' else '.jpg')))))
    save(OUT/'readers.json',readers)
    def one(r):
        p=pathlib.Path(r['path']);p.parent.mkdir(parents=True,exist_ok=True)
        if not p.exists():
            assert shutil.disk_usage(OUT).free>4*1024**3+10*1024**2
            temp=p.with_name(p.name+'.part');temp.write_bytes(fetch(r['url'],r['chapter_url']).content)
            with Image.open(temp) as im:assert im.width>=200 and im.height>=200;im.verify()
            temp.replace(p)
        with Image.open(p) as im:width,height=im.size
        return dict(r,width=width,height=height,bytes=p.stat().st_size,sha256=sha(p))
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results=[]
        for r in pool.map(one,work):
            results.append(r)
            if len(results)%24==0:print(json.dumps(dict(state='pages',completed=len(results),expected=len(work))),flush=True)
    save(OUT/'images.json',results)
    print(json.dumps(dict(state='pages_complete',images=len(results),bytes=sum(r['bytes'] for r in results))),flush=True)


def proposals():
    pages=read(OUT/'images.json');by={}
    for i,r in enumerate(prior.records(OUT/'ocr.jsonl')):by.setdefault(r['image'],[]).append(dict(r,ocr_region_id=i))
    by={i:prior.transcript_groups(rs) for i,rs in by.items()};rows=[]
    for a in read(OUT/'page-alignments.json'):
        en=pages[a['english_image']];es=pages[a['spanish_image']]
        assert en['chapter']==es['chapter'] and en['split']==es['split'] and en['split']!='test'
        for r in by.get(a['english_image'],[]):
            b=r['bounds'];quad=np.float32([[[b[0],b[1]],[b[2],b[1]],[b[2],b[3]],[b[0],b[3]]]])
            q=cv2.perspectiveTransform(quad,np.asarray(a['homography']))[0];x1,y1=q.min(axis=0);x2,y2=q.max(axis=0)
            targets=[t for t in by.get(a['spanish_image'],[]) if x1-25<=(t['bounds'][0]+t['bounds'][2])/2<=x2+25 and y1-25<=(t['bounds'][1]+t['bounds'][3])/2<=y2+25]
            targets.sort(key=lambda t:(t['bounds'][1],-t['bounds'][0]));reference=' '.join(t['source'] for t in targets)
            if len(r['source'].split())<3 or len(reference.split())<2:continue
            box=[min(t['bounds'][0] for t in targets),min(t['bounds'][1] for t in targets),max(t['bounds'][2] for t in targets),max(t['bounds'][3] for t in targets)]
            rows.append(dict(chapter=en['chapter'],split=en['split'],english_page=en['page'],spanish_page=es['page'],source_ocr=r['source'],target_ocr=reference,
                source_image=en,reference_image=es,source_bounds=b,reference_bounds=box,source_regions=r['ocr_region_ids'],reference_regions=[i for t in targets for i in t['ocr_region_ids']],
                alignment_inliers=a['inliers'],visually_verified=False,approved_for_training=False))
    rows.sort(key=lambda r:(r['chapter'],r['english_page'],r['source_bounds'][1],-r['source_bounds'][0]))
    for i,r in enumerate(rows):r['id']=i+1
    protocol=read(META/'data-protocol.json');selected=[]
    for split,chapters in protocol['selected_chapters'].items():
        if split=='test':assert not chapters;continue
        quota=protocol['proposal_quota_per_training_chapter' if split=='train' else 'proposal_quota_per_validation_chapter']
        for chapter in chapters:selected.extend([r for r in rows if r['chapter']==chapter][:quota])
    save(OUT/'pair-proposals.json',rows);save(OUT/'review-selection.json',selected)
    review=OUT/'review';review.mkdir(exist_ok=True);font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',22)
    for start in range(0,len(selected),4):
        sheet=Image.new('RGB',(1800,1600),'#f1f4ed');draw=ImageDraw.Draw(sheet)
        for slot,p in enumerate(selected[start:start+4]):
            top=slot*400;draw.text((12,top+5),f"{p['id']} | {p['split']} | EN {p['english_page']+1} / ES {p['spanish_page']+1}",font=font,fill='#243b2b')
            for x,key,bounds in [(12,'source_image',p['source_bounds']),(610,'reference_image',p['reference_bounds'])]:
                with Image.open(p[key]['path']) as im:
                    box=(max(0,bounds[0]-100),max(0,bounds[1]-100),min(im.width,bounds[2]+100),min(im.height,bounds[3]+100))
                    crop=im.crop(box).convert('RGB');crop.thumbnail((580,345));sheet.paste(crop,(x+(580-crop.width)//2,top+43))
            y=top+45
            for label,key in [('English OCR','source_ocr'),('Spanish OCR','target_ocr')]:
                draw.text((1210,y),label,font=font,fill='#243b2b');y+=28
                for line in textwrap.wrap(p[key],43):
                    if y>top+370:break
                    draw.text((1210,y),line,font=font,fill='#202520');y+=26
                y+=12
        sheet.save(review/f'sheet-{start//4+1:02d}.jpg',quality=91)
    save(OUT/'preparation-provenance.json',dict(data_protocol_sha256=sha(META/'data-protocol.json'),script_sha256=sha(__file__),
        original_helpers_sha256=sha(prior.__file__),images_sha256=sha(OUT/'images.json'),selection_sha256=sha(OUT/'review-selection.json'),
        no_model_translations_consulted=True,no_test_chapters_opened=True,labels_approved=False))
    print(json.dumps(dict(state='proposals_ready',proposals=len(rows),selected=len(selected),training=sum(r['split']=='train' for r in selected),validation=sum(r['split']=='validation' for r in selected))),flush=True)


if __name__=='__main__':
    OUT.mkdir(exist_ok=True);pages();prior.OUT=OUT;prior.ocr();prior.align();proposals()
