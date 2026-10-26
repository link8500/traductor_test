"""OCR and artwork-align bounded pages; every output is an unapproved proposal."""
import argparse
import collections
import json
import pathlib
import subprocess

import cv2
import numpy as np
from PIL import Image,ImageDraw,ImageFont

from prepare_finetune8031 import ROOT,OUT,META,sha,save
from quality_resources import wait_for_inference_memory


def read(p):return json.loads(pathlib.Path(p).read_text(encoding='utf-8'))
def records(p):return [json.loads(s) for s in pathlib.Path(p).read_text(encoding='utf-8').splitlines() if s.strip()]


def transcript_groups(rows):
    # Label-preparation proposals only. Close, aligned text lines can belong
    # to one balloon; every joined proposal must still be checked in pixels.
    parents=list(range(len(rows)))
    def find(i):
        while parents[i]!=i:parents[i]=parents[parents[i]];i=parents[i]
        return i
    for i,a in enumerate(rows):
        x=a['bounds'];ha=x[3]-x[1];wa=x[2]-x[0]
        for j in range(i):
            y=rows[j]['bounds'];hb=y[3]-y[1];wb=y[2]-y[0]
            if min(ha,hb)<8 or max(ha,hb)>2.2*min(ha,hb):continue
            overlap=max(0,min(x[2],y[2])-max(x[0],y[0]));gap=max(x[1]-y[3],y[1]-x[3])
            if -.2*min(ha,hb)<=gap<=1.3*max(ha,hb) and overlap>=.6*min(wa,wb) and abs((x[0]+x[2])-(y[0]+y[2]))<=.7*max(wa,wb):
                parents[find(i)]=find(j)
    groups=collections.defaultdict(list)
    for i,r in enumerate(rows):groups[find(i)].append(r)
    result=[]
    for members in groups.values():
        members.sort(key=lambda r:(r['bounds'][1],r['bounds'][0]));base=members[0]
        result.append(dict(base,source=' '.join(r['source'] for r in members),
            ocr_region_ids=[r['ocr_region_id'] for r in members],
            bounds=[min(r['bounds'][0] for r in members),min(r['bounds'][1] for r in members),max(r['bounds'][2] for r in members),max(r['bounds'][3] for r in members)]))
    return result


def ocr():
    pages=read(OUT/'images.json');binary=ROOT/'build/full-comics/frozen-windows803001/traductor.exe'
    snapshot=ROOT/'build/full-comics/windows-engine803001.json';assert sha(binary)==read(snapshot)['binary_sha256']
    jobs=OUT/'ocr';jobs.mkdir(exist_ok=True);all_rows=[]
    for start in range(0,len(pages),24):
        batch=start//24;selected=pages[start:start+24]
        profile='-transcript' if selected[0]['language']=='en' else ''
        manifest=jobs/f'part-{batch:02d}{profile}.input.jsonl';target=jobs/f'part-{batch:02d}{profile}.jsonl'
        inputs=[dict(path=p['path'],image=start+i,chapter=f"seventh-prince-{p['chapter']:03d}-{p['language']}",language=p['language'],ocr_only=True,
                     augment_detection=True,recover_paragraphs=True,complete_lines=True) for i,p in enumerate(selected)]
        for item in inputs:
            if item['language']=='en':
                # OCR is only a transcription aid here, not an app-quality
                # benchmark. Every accepted label still requires both pixels.
                item.update(augment_detection=False,reader_consensus=False,recover_paragraphs=False,
                            complete_lines=False,recover_short_dialogue=False)
        contents=''.join(json.dumps(r)+'\n' for r in inputs)
        if manifest.exists():assert manifest.read_text(encoding='utf-8')==contents
        else:manifest.write_text(contents,encoding='utf-8')
        done=pathlib.Path(str(target)+'.summary.json')
        if not done.exists():
            wait_for_inference_memory()
            with (jobs/f'part-{batch:02d}{profile}.log').open('ab') as log:
                subprocess.run([str(binary),'--comic-benchmark',str(manifest),str(target)],check=True,creationflags=subprocess.CREATE_NO_WINDOW,
                               stdout=log,stderr=log,timeout=1800)
        assert read(done)['runtime_errors']==0
        rows=records(target);assert not any('error' in r for r in rows);all_rows.extend(rows)
        print(json.dumps(dict(state='ocr',pages_completed=start+len(selected),pages_expected=len(pages),regions=len(all_rows))),flush=True)
    path=OUT/'ocr.jsonl';contents=''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in all_rows)
    if path.exists():assert path.read_text(encoding='utf-8')==contents
    else:path.write_text(contents,encoding='utf-8')
    save(OUT/'ocr-provenance.json',dict(binary_sha256=sha(binary),snapshot_sha256=sha(snapshot),pages_sha256=sha(OUT/'images.json'),
        output_sha256=sha(path),pages=len(pages),regions=len(all_rows),runtime_errors=0,ocr_only=True,model_answers_supplied=False,
        english_proposal_profile='system_ocr_with_line_reader_no_detector_augmentation_or_consensus',
        full_production_ocr_benchmark=False,all_text_visually_reviewed=False,usable_for_training_without_review=False))


def align():
    pages=read(OUT/'images.json');orb=cv2.ORB_create(nfeatures=2500,fastThreshold=12);features={}
    for i,p in enumerate(pages):
        assert sha(p['path'])==p['sha256']
        with Image.open(p['path']) as im:
            size=(round(im.width*min(900/im.width,900/im.height,1)),round(im.height*min(900/im.width,900/im.height,1)))
            image=np.asarray(im.convert('L').resize(size))
        key,desc=orb.detectAndCompute(image,None);features[i]=(key,desc,size[0]/p['width'],size[1]/p['height'])
    bf=cv2.BFMatcher(cv2.NORM_HAMMING);matches=[]
    for i,en in enumerate(pages):
        if en['language']!='en':continue
        a,ad,ax,ay=features[i];best=[]
        for j,es in enumerate(pages):
            if es['language']!='es' or en['chapter']!=es['chapter']:continue
            b,bd,bx,by=features[j]
            if ad is None or bd is None:continue
            good=[pair[0] for pair in bf.knnMatch(ad,bd,k=2) if len(pair)==2 and pair[0].distance<.72*pair[1].distance]
            if len(good)<8:continue
            src=np.float32([a[m.queryIdx].pt for m in good]);dst=np.float32([b[m.trainIdx].pt for m in good])
            hom,inliers=cv2.findHomography(src,dst,cv2.RANSAC,4.0)
            if hom is None:continue
            n=int(inliers.sum());scaled=np.diag([1/bx,1/by,1.0])@hom@np.diag([ax,ay,1.0])
            best.append(dict(english_image=i,spanish_image=j,inliers=n,homography=scaled.tolist()))
        best.sort(key=lambda x:x['inliers'],reverse=True)
        if best and best[0]['inliers']>=20:matches.append(dict(best[0],runner_up_inliers=best[1]['inliers'] if len(best)>1 else 0,visually_verified=False))
    save(OUT/'page-alignments.json',matches)
    print(json.dumps(dict(pages_proposed=len(matches),english_pages=sum(r['language']=='en' for r in pages),all_alignments_verified=False)),flush=True)


def pairs(partial=False):
    pages=read(OUT/'images.json');by_image=collections.defaultdict(list)
    if partial:
        rows=[]
        for n in range(6):
            p=OUT/'ocr'/f'part-{n:02d}{"-transcript" if n>=3 else ""}.jsonl'
            if not p.exists():continue
            for line in p.read_text(encoding='utf-8').splitlines():
                try:rows.append(json.loads(line))
                except json.JSONDecodeError:pass
    else:rows=records(OUT/'ocr.jsonl')
    for i,r in enumerate(rows):by_image[r['image']].append(dict(r,ocr_region_id=i))
    by_image={i:transcript_groups(rs) for i,rs in by_image.items()}
    proposals=[]
    for a in read(OUT/'page-alignments.json'):
        en=pages[a['english_image']];es=pages[a['spanish_image']];matrix=np.asarray(a['homography'])
        for source in by_image.get(a['english_image'],[]):
            b=source['bounds'];quad=np.float32([[[b[0],b[1]],[b[2],b[1]],[b[2],b[3]],[b[0],b[3]]]])
            transformed=cv2.perspectiveTransform(quad,matrix)[0];x1,y1=transformed.min(axis=0);x2,y2=transformed.max(axis=0)
            targets=[]
            for r in by_image.get(a['spanish_image'],[]):
                t=r['bounds'];cx=(t[0]+t[2])/2;cy=(t[1]+t[3])/2
                if x1-25<=cx<=x2+25 and y1-25<=cy<=y2+25:targets.append(r)
            if not targets:continue
            targets.sort(key=lambda r:(r['bounds'][1],-r['bounds'][0]))
            reference=' '.join(r['source'] for r in targets)
            if len(source['source'].split())<3 or len(reference.split())<2:continue
            box=[min(r['bounds'][0] for r in targets),min(r['bounds'][1] for r in targets),max(r['bounds'][2] for r in targets),max(r['bounds'][3] for r in targets)]
            proposals.append(dict(id=len(proposals)+1,chapter=en['chapter'],split=en['split'],english_page=en['page'],spanish_page=es['page'],
                source_ocr=source['source'],target_ocr=reference,source_image=en,reference_image=es,source_bounds=b,reference_bounds=box,
                source_regions=source['ocr_region_ids'],reference_regions=[i for r in targets for i in r['ocr_region_ids']],
                alignment_inliers=a['inliers'],visually_verified=False,approved_for_training=False))
    proposals.sort(key=lambda r:(r['chapter'],r['english_page'],r['source_bounds'][1],-r['source_bounds'][0]))
    for i,p in enumerate(proposals):p['id']=i+1
    suffix='-partial' if partial else ''
    save(OUT/f'pair-proposals{suffix}.json',proposals)
    # A deterministic first-page quota; no translation output is consulted.
    selected=[]
    for split,quota in [('train',60),('validation',16),('test',24)]:
        pool=[r for r in proposals if r['split']==split]
        chapters=sorted({r['chapter'] for r in pool}) if OUT.name=='expansion-v1' else read(META/'sources.json')['initial_pilot_chapters'][split]
        for i,chapter in enumerate(chapters):
            portion=quota//len(chapters)+(i<quota%len(chapters))
            selected.extend([r for r in pool if r['chapter']==chapter][:portion])
    save(OUT/f'review-selection{suffix}.json',selected)
    print(json.dumps(dict(proposals=len(proposals),selected=collections.Counter(p['split'] for p in selected),model_output_used_for_selection=False)),flush=True)
    review=OUT/f'review{suffix}';review.mkdir(exist_ok=True);font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',22)
    import textwrap
    for start in range(0,len(selected),4):
        sheet=Image.new('RGB',(1800,1600),'#f1f4ed');draw=ImageDraw.Draw(sheet)
        for slot,p in enumerate(selected[start:start+4]):
            top=slot*400;draw.text((12,top+5),f"{p['id']} · {p['split']} · página EN {p['english_page']+1} / ES {p['spanish_page']+1}",font=font,fill='#243b2b')
            for x,key,bounds in [(12,'source_image',p['source_bounds']),(610,'reference_image',p['reference_bounds'])]:
                page=p[key]
                with Image.open(page['path']) as im:
                    box=(max(0,bounds[0]-45),max(0,bounds[1]-55),min(im.width,bounds[2]+45),min(im.height,bounds[3]+55))
                    crop=im.crop(box).convert('RGB');crop.thumbnail((580,345));sheet.paste(crop,(x+(580-crop.width)//2,top+43))
            y=top+45
            for label,key in [('OCR inglés','source_ocr'),('OCR español','target_ocr')]:
                draw.text((1210,y),label,font=font,fill='#243b2b');y+=28
                for line in textwrap.wrap(p[key],width=43):draw.text((1210,y),line,font=font,fill='#202520');y+=26
                y+=12
        sheet.save(review/f'sheet-{start//4+1:02d}.jpg',quality=91)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['ocr','align','pairs']);parser.add_argument('--partial',action='store_true');parser.add_argument('--expansion',action='store_true');args=parser.parse_args()
    if args.expansion:OUT=OUT/'expansion-v1'
    {'ocr':ocr,'align':align,'pairs':lambda:pairs(args.partial)}[args.command]()
