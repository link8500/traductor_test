"""Align chapter artwork before comparing EN app output with ES scanlation.

Geometric matches are proposals, not reviewed translation labels. Files from
the public reader stay in build/ and are not bundled with the application.
"""
import argparse,concurrent.futures,hashlib,json,pathlib,re,time
from urllib.parse import urljoin
import cv2
import numpy as np
import requests
from PIL import Image

ROOT=pathlib.Path(__file__).resolve().parents[1]
QA=ROOT/'build/bilingual-quality'


def reader_records():
    records=json.loads((ROOT/'benchmarks/bilingual-comics/spanish-reader.json').read_text())
    links=json.loads((ROOT/'benchmarks/bilingual-comics/sources.json').read_text())['records']
    expanded=[]
    for row in records:
        names=[]
        for part in row['f'].split('|'):
            match=re.fullmatch(r'(.*)\{(\d+)-(\d+)\}',part)
            if match:names.extend(match[1]+str(i).zfill(len(match[2]))+'.webp' for i in range(int(match[2]),int(match[3])+1))
            else:names.append(part+'.webp')
        value=2166136261
        for char in '|'.join(names):value=((value^ord(char))*16777619)&0xffffffff
        assert len(names)==row['n'] and f'{value:08x}'==row['h'],f'Reader list mismatch: {row}'
        series='absolute-regression' if row['s']=='a' else 'greatest-estate-developer'
        original=next(item for item in links if item['series']==series and item['chapter']==row['c'] and item['language']=='es')
        prefix=f"https://media.imagesolymp.xyz/comics/{1382 if row['s']=='a' else 463}/{row['d']}/"
        expanded.append({**original,'reader_source':'Rendered DOM in normal browser after reload, 2026-10-23',
            'images':[{'index':i,'url':urljoin(prefix,name),'path':f"references/{original['id']}/{i:03d}.webp"} for i,name in enumerate(names)]})
    (QA/'references.json').write_text(json.dumps(expanded,ensure_ascii=False,indent=2),encoding='utf-8')
    return expanded


def download(image):
    path=QA/image['path'];path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and path.stat().st_size:return
    for attempt in range(3):
        try:
            response=requests.get(image['url'],timeout=(15,40),headers={'User-Agent':'Luma local bilingual evaluation'})
            response.raise_for_status()
            partial=path.with_suffix('.partial');partial.write_bytes(response.content)
            with Image.open(partial) as bitmap:bitmap.verify()
            partial.replace(path);return
        except requests.RequestException as error:
            if getattr(error.response,'status_code',None) in [401,403] or attempt==2:raise
            time.sleep(attempt+1)


def panorama(record):
    path=QA/'aligned'/record['id']/'panorama.png';path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        try:
            with Image.open(path) as cached:cached.verify()
            return path
        except (OSError,SyntaxError):pass
    pages=[];height=0
    for entry in record['images']:
        with Image.open(QA/entry['path']) as bitmap:
            page=bitmap.convert('RGB');page=page.resize((390,round(page.height*390/page.width)),Image.Resampling.LANCZOS)
            pages.append(page);height+=page.height
    canvas=Image.new('RGB',(390,height),'white');top=0
    for page in pages:canvas.paste(page,(0,top));top+=page.height;page.close()
    partial=path.with_suffix('.partial')
    canvas.save(partial,format='PNG',compress_level=3);canvas.close();partial.replace(path);return path


def align(record):
    id_=record['id'];source_id=id_.removesuffix('-es')+'-en'
    source_path=QA/'samples'/source_id/'mobile.png'
    target_path=panorama(record)
    sample=next(row for row in json.loads((QA/'samples.json').read_text(encoding='utf-8'))['records'] if row['id']==source_id)
    with Image.open(source_path.parent/'original.webp') as original:
        resized=original.convert('RGB').resize((390,round(original.height*390/original.width)),Image.Resampling.LANCZOS)
        start=max(0,sample['mobile_crop_top']-800)
        stop=min(resized.height,sample['mobile_crop_top']+844+800)
        source=cv2.cvtColor(np.asarray(resized.crop((0,start,390,stop))),cv2.COLOR_RGB2GRAY)
    mobile_offset=sample['mobile_crop_top']-start
    target=cv2.imread(str(target_path),cv2.IMREAD_GRAYSCALE)
    result={'id':source_id,'reference_id':id_,'reference_url':record['url'],'alignment_reviewed':False,'reference_transcript_reviewed':False}
    # Editions use different image cuts, but much of the artwork remains the
    # same width. A coarse vertical correlation finds that artwork efficiently
    # even when ORB's global feature budget is dominated by other pages.
    small_source=cv2.resize(source,(195,source.shape[0]//2),interpolation=cv2.INTER_AREA)
    small_target=cv2.resize(target,(195,target.shape[0]//2),interpolation=cv2.INTER_AREA)
    scores=cv2.matchTemplate(small_target,small_source,cv2.TM_CCOEFF_NORMED)
    _,score,_,point=cv2.minMaxLoc(scores)
    if score>=.80 and float(small_source.std())>=12:
        top=max(0,min(point[1]*2+mobile_offset,target.shape[0]-844))
        with Image.open(target_path) as image:image.crop((0,top,390,top+844)).save(target_path.parent/'reference-mobile.png')
        return {**result,'state':'artwork_matched','method':'vertical_artwork_correlation','correlation':round(score,4),
            'reference_crop_top':top,'reference_image':str((target_path.parent/'reference-mobile.png').relative_to(QA))}
    detector=cv2.ORB_create(nfeatures=20000,fastThreshold=12)
    keys_a,desc_a=detector.detectAndCompute(source,None);keys_b,desc_b=detector.detectAndCompute(target,None)
    if desc_a is None or desc_b is None:return {**result,'state':'no_art_features'}
    pairs=cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(desc_a,desc_b,k=2)
    matches=[first for first,second in pairs if first.distance<.72*second.distance]
    if len(matches)<10:return {**result,'state':'insufficient_matches','matches':len(matches)}
    a=np.float32([keys_a[item.queryIdx].pt for item in matches]);b=np.float32([keys_b[item.trainIdx].pt for item in matches])
    # Uniform scale + translation is appropriate for vertically sliced artwork;
    # a general homography could wrongly fit an unrelated decorative pattern.
    matrix,inliers=cv2.estimateAffinePartial2D(a,b,method=cv2.RANSAC,ransacReprojThreshold=3,maxIters=4000,confidence=.995)
    if matrix is None:return {**result,'state':'no_transform','matches':len(matches)}
    count=int(inliers.sum());ratio=count/len(matches);scale=float(np.hypot(matrix[0,0],matrix[1,0]))
    result.update(matches=len(matches),inliers=count,inlier_ratio=round(ratio,3),scale=round(scale,4),transform=matrix.tolist())
    if count<12 or ratio<.45 or not .75<scale<1.3 or abs(matrix[1,0])>.03:
        return {**result,'state':'needs_alignment_review'}
    center=np.dot(matrix,np.array([195.,mobile_offset+422.,1.]));top=max(0,min(int(round(center[1]-422)),target.shape[0]-844))
    with Image.open(target_path) as image:image.crop((0,top,390,min(top+844,image.height))).save(target_path.parent/'reference-mobile.png')
    result.update(state='artwork_matched',reference_crop_top=top,reference_image=str((target_path.parent/'reference-mobile.png').relative_to(QA)))
    return result


def manual_alignment(record):
    manifest=ROOT/'benchmarks/bilingual-comics/visual-alignments.json'
    if not manifest.exists():return None
    id_=record['id'].removesuffix('-es')+'-en'
    item=next((row for row in json.loads(manifest.read_text(encoding='utf-8')) if row['id']==id_),None)
    if item is None:return None
    source=QA/'samples'/id_/'mobile.png';target=panorama(record)
    if hashlib.sha256(source.read_bytes()).hexdigest()!=item['source_mobile_sha256'] or hashlib.sha256(target.read_bytes()).hexdigest()!=item['target_panorama_sha256']:
        return None
    top=item['reference_crop_top']
    with Image.open(target) as image:image.crop((0,top,390,top+844)).save(target.parent/'reference-mobile.png')
    return {'id':id_,'reference_id':record['id'],'reference_url':record['url'],'state':'artwork_matched',
        'method':'full_page_color_correlation_and_visual_confirmation','alignment_reviewed':True,'reference_transcript_reviewed':False,
        'reference_crop_top':top,'reference_image':str((target.parent/'reference-mobile.png').relative_to(QA))}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download',action='store_true');parser.add_argument('--align',action='store_true')
    parser.add_argument('--retry-unmatched',action='store_true',help='Keep existing strong matches and retry uncertain alignments')
    args=parser.parse_args();records=reader_records();cv2.setNumThreads(2)
    if args.download:
        images=[image for record in records for image in record['images']];failures=[]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            pending={pool.submit(download,image):image for image in images}
            for index,future in enumerate(concurrent.futures.as_completed(pending),1):
                try:future.result()
                except Exception as error:failures.append({**pending[future],'error':str(error)})
                if index%100==0:print(f'Reference images {index}/{len(images)}, errors {len(failures)}',flush=True)
        (QA/'reference-download-errors.json').write_text(json.dumps(failures,indent=2),encoding='utf-8')
        if failures:raise SystemExit(f'{len(failures)} reference images unavailable; see report')
    if args.align:
        previous={row['id']:row for row in json.loads((QA/'alignments.json').read_text())} if args.retry_unmatched and (QA/'alignments.json').exists() else {}
        aligned=[]
        for index,record in enumerate(records,1):
            existing=previous.get(record['id'].removesuffix('-es')+'-en')
            result=existing if existing and existing['state']=='artwork_matched' else manual_alignment(record) or align(record)
            aligned.append(result)
            print(f"Alignment {index}/{len(records)}: {result['id']} {result['state']}",flush=True)
            (QA/'alignments.json').write_text(json.dumps(aligned,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
