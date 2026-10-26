"""Prepare a frozen, previously unread test slice without using model answers."""
import concurrent.futures
import json
import pathlib
import re
import shutil
from PIL import Image,ImageDraw,ImageFont
import numpy as np
import cv2
import prepare_finetune8031 as source
import prepare_finetune8031_pairs as pairs

ROOT=source.ROOT
OUT=ROOT/'build/finetune8032/fresh-test'
META=ROOT/'benchmarks/finetune8032'


def pages():
    protocol=pairs.read(META/'fresh-test-protocol.json')
    inventory=pairs.read(source.META/'sources.json')
    assert source.sha(source.META/'sources.json')==protocol['source_inventory_sha256']
    work=[];readers=[]
    for r in inventory['records']:
        if r['chapter'] not in protocol['selected_chapters']:continue
        assert r['split']=='test'
        p=OUT/'readers'/(r['id']+'.html');p.parent.mkdir(parents=True,exist_ok=True)
        if not p.exists():p.write_text(source.request(r['url']).text,encoding='utf-8')
        text=p.read_text(encoding='utf-8')
        if r['language']=='es':
            parser=source.Images();parser.feed(text);images=[u for _,u in sorted(parser.rows)]
        else:
            m=re.search(r'\bvar\s+thzq\s*=\s*\[(.*?)\]\s*;',text,re.S);assert m
            images=re.findall(r"['\"](https://[^'\"]+)['\"]",m[1])
        assert 5<=len(images)<=150 and len(set(images))==len(images)
        readers.append(dict(r,html_sha256=source.sha(p),all_page_urls=images,pages_available=len(images)))
        for i,u in enumerate(images[:protocol['maximum_pages_per_language']]):
            work.append(dict(chapter=r['chapter'],language=r['language'],split='test',page=i,url=u,
                chapter_url=r['url'],path=str(OUT/'images'/r['id']/(f'{i:03d}'+('.webp' if r['language']=='es' else '.jpg')))))
    source.save(OUT/'readers.json',readers)
    def one(r):
        p=pathlib.Path(r['path']);p.parent.mkdir(parents=True,exist_ok=True)
        if not p.exists():
            assert shutil.disk_usage(OUT).free>4*1024**3+10*1024**2
            temp=p.with_name(p.name+'.part');temp.write_bytes(source.request(r['url'],r['chapter_url']).content)
            with Image.open(temp) as im:assert im.width>=200 and im.height>=200;im.verify()
            temp.replace(p)
        with Image.open(p) as im:w,h=im.size
        return dict(r,width=w,height=h,bytes=p.stat().st_size,sha256=source.sha(p))
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:records=list(pool.map(one,work))
    source.save(OUT/'images.json',records)
    print(json.dumps(dict(state='fresh_test_pages',images=len(records),bytes=sum(r['bytes'] for r in records))),flush=True)


def proposals():
    images=pairs.read(OUT/'images.json');by={}
    for i,r in enumerate(pairs.records(OUT/'ocr.jsonl')):by.setdefault(r['image'],[]).append(dict(r,ocr_region_id=i))
    by={i:pairs.transcript_groups(rs) for i,rs in by.items()};rows=[]
    for a in pairs.read(OUT/'page-alignments.json'):
        en=images[a['english_image']];es=images[a['spanish_image']]
        for r in by.get(a['english_image'],[]):
            b=r['bounds'];quad=np.float32([[[b[0],b[1]],[b[2],b[1]],[b[2],b[3]],[b[0],b[3]]]])
            q=cv2.perspectiveTransform(quad,np.asarray(a['homography']))[0];x1,y1=q.min(axis=0);x2,y2=q.max(axis=0)
            targets=[t for t in by.get(a['spanish_image'],[]) if x1-25<=(t['bounds'][0]+t['bounds'][2])/2<=x2+25 and y1-25<=(t['bounds'][1]+t['bounds'][3])/2<=y2+25]
            targets.sort(key=lambda t:(t['bounds'][1],-t['bounds'][0]));reference=' '.join(t['source'] for t in targets)
            if len(r['source'].split())<3 or len(reference.split())<2:continue
            box=[min(t['bounds'][0] for t in targets),min(t['bounds'][1] for t in targets),max(t['bounds'][2] for t in targets),max(t['bounds'][3] for t in targets)]
            rows.append(dict(chapter=en['chapter'],split='test',english_page=en['page'],spanish_page=es['page'],source_ocr=r['source'],target_ocr=reference,
                source_image=en,reference_image=es,source_bounds=b,reference_bounds=box,source_regions=r['ocr_region_ids'],reference_regions=[i for t in targets for i in t['ocr_region_ids']],
                alignment_inliers=a['inliers'],visually_verified=False,approved_for_training=False))
    rows.sort(key=lambda r:(r['chapter'],r['english_page'],r['source_bounds'][1],-r['source_bounds'][0]))
    for i,r in enumerate(rows):r['id']=i+1
    selected=rows[:pairs.read(META/'fresh-test-protocol.json')['maximum_review_proposals']]
    source.save(OUT/'pair-proposals.json',rows);source.save(OUT/'review-selection.json',selected)
    review=OUT/'review';review.mkdir(exist_ok=True);font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',22)
    import textwrap
    for start in range(0,len(selected),4):
        sheet=Image.new('RGB',(1800,1600),'#f1f4ed');draw=ImageDraw.Draw(sheet)
        for slot,p in enumerate(selected[start:start+4]):
            top=slot*400;draw.text((12,top+5),f"{p['id']} | test | EN {p['english_page']+1} / ES {p['spanish_page']+1}",font=font,fill='#243b2b')
            for x,key,bounds in [(12,'source_image',p['source_bounds']),(610,'reference_image',p['reference_bounds'])]:
                with Image.open(p[key]['path']) as im:
                    box=(max(0,bounds[0]-45),max(0,bounds[1]-55),min(im.width,bounds[2]+45),min(im.height,bounds[3]+55))
                    crop=im.crop(box).convert('RGB');crop.thumbnail((580,345));sheet.paste(crop,(x+(580-crop.width)//2,top+43))
            y=top+45
            for label,key in [('English OCR','source_ocr'),('Spanish OCR','target_ocr')]:
                draw.text((1210,y),label,font=font,fill='#243b2b');y+=28
                for line in textwrap.wrap(p[key],43):draw.text((1210,y),line,font=font,fill='#202520');y+=26
                y+=12
        sheet.save(review/f'sheet-{start//4+1:02d}.jpg',quality=91)
    source.save(OUT/'preparation-provenance.json',dict(protocol_sha256=source.sha(META/'fresh-test-protocol.json'),script_sha256=source.sha(__file__),
        proposal_helper_sha256=source.sha(pairs.__file__),images_sha256=source.sha(OUT/'images.json'),selection_sha256=source.sha(OUT/'review-selection.json'),
        candidate_answers_used=False,approved_for_training=False,review_complete=False))
    print(json.dumps(dict(state='fresh_test_proposals',proposals=len(rows),selected=len(selected),model_answers_used=False)),flush=True)


if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True);pages();pairs.OUT=OUT;pairs.ocr();pairs.align();proposals()
