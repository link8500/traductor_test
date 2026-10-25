"""Artwork alignment and an explicit, unverified ledger of each ES OCR token.

Literal word overlap is never presented as semantic accuracy. Scanlation OCR,
artwork matches, and proposed region links each retain their review status.
"""
import argparse,bisect,collections,hashlib,json,pathlib,re,subprocess,sys,time,unicodedata
import cv2
import numpy as np
from PIL import Image

ROOT=pathlib.Path(__file__).resolve().parents[1];QA=ROOT/'build/full-comics';WIDTH=240
cv2.setNumThreads(1)
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def lines(path):return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines() if s.strip()]
def write_atomic(path,value):
    pending=path.with_name(path.name+'.pending');pending.write_text(value,encoding='utf-8');pending.replace(path)
def compact_ledger_row(row):
    return {k:row[k] for k in ['reference_word','reference_region','word_index','luma_region','state','meaning_approved','word_reviewed']}
def normal(word):return ''.join(c for c in unicodedata.normalize('NFD',word.casefold()) if c.isalnum())
def words(text):return re.findall(r"[^\W_]+(?:['’\-][^\W_]+)*",text,flags=re.UNICODE)

def panorama(chapter,images,directory):
    path=directory/(chapter+'.png');meta=path.with_suffix('.json')
    if path.exists() and meta.exists():return cv2.imread(str(path),cv2.IMREAD_GRAYSCALE),read(meta)
    pages=[];offset=0;mapping={}
    for row in images:
        with Image.open(row['path']) as image:
            scaled=image.convert('L').resize((WIDTH,max(1,round(image.height*WIDTH/image.width))),Image.Resampling.LANCZOS)
            pages.append(np.asarray(scaled));mapping[str(row['image'])]={'offset':offset,'scale':WIDTH/row['width']}
            offset+=scaled.height
    data=np.concatenate(pages,axis=0);cv2.imwrite(str(path),data,[cv2.IMWRITE_PNG_COMPRESSION,3]);meta.write_text(json.dumps(mapping),encoding='utf-8')
    return data,mapping

def features(image):
    budget=max(60,min(300,30000//max(1,image.shape[0]//500)))
    detector=cv2.ORB_create(nfeatures=budget,fastThreshold=12,edgeThreshold=16)
    points=[];descriptors=[]
    for top in range(0,image.shape[0],480):
        tile=image[top:top+512]
        if tile.shape[0]<40 or tile.std()<10:continue
        keys,desc=detector.detectAndCompute(tile,None)
        if desc is None:continue
        points.extend((k.pt[0],k.pt[1]+top) for k in keys);descriptors.append(desc)
    return np.asarray(points,dtype=np.float32),np.concatenate(descriptors) if descriptors else None

def artwork_anchors(en,es):
    a,da=features(en);b,db=features(es)
    if da is None or db is None:return [],dict(reason='No stable artwork features')
    matches=cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(da,db,k=2);bins=collections.defaultdict(list)
    for pair in matches:
        if len(pair)!=2:continue
        first,second=pair
        if first.distance>=min(45,.68*second.distance):continue
        p=a[first.queryIdx];q=b[first.trainIdx]
        if abs(float(p[0]-q[0]))>12:continue
        bins[int(p[1]//200)].append((float(p[1]),float(q[1])))
    proposals=[]
    for values in bins.values():
        offsets=[y-x for x,y in values];hist=collections.Counter(round(d/20) for d in offsets)
        centre=hist.most_common(1)[0][0]*20
        consistent=[(x,y) for x,y in values if abs(y-x-centre)<20]
        if len(consistent)<6:continue
        median=float(np.median([y-x for x,y in consistent]));residual=float(np.median([abs(y-x-median) for x,y in consistent]))
        if residual>7:continue
        ey=float(np.median([x for x,y in consistent]));proposals.append(dict(en=ey,es=ey+median,matches=len(consistent),residual=residual))
    proposals.sort(key=lambda r:r['en'])
    # A maximum-weight monotonic chain rejects backwards/repeated artwork.
    score=[];parent=[]
    for i,row in enumerate(proposals):
        value=min(row['matches'],30);best=value;previous=-1
        for j,old in enumerate(proposals[:i]):
            de=row['en']-old['en'];ds=row['es']-old['es']
            if de>20 and ds>20 and .5<ds/de<2 and score[j]+value>best:best=score[j]+value;previous=j
        score.append(best);parent.append(previous)
    if not score:return [],dict(reason='No reliable local artwork matches',features_en=len(a),features_es=len(b))
    index=int(np.argmax(score));anchors=[]
    while index>=0:anchors.append(proposals[index]);index=parent[index]
    anchors.reverse();return anchors,dict(features_en=len(a),features_es=len(b),anchor_count=len(anchors),alignment_human_verified=False)

def compare(chapter,images_en,images_es,directory,english_reports=None,compact=False):
    en_id=chapter+'-en';es_id=chapter+'-es'
    en_directory=QA/(english_reports or ('translated-en-final' if (QA/'translated-en-final'/(en_id+'.done.json')).exists() else 'translated-en'))
    en_done=en_directory/(en_id+'.done.json');es_done=QA/'ocr-es'/(es_id+'.done.json')
    signature=hashlib.sha256(en_done.read_bytes()+es_done.read_bytes()+pathlib.Path(__file__).read_bytes()+str(compact).encode()).hexdigest()
    image_signature=hashlib.sha256(''.join(r['sha256'] for r in images_en+images_es).encode()).hexdigest()
    output=directory/(chapter+'.json');ledger=directory/(chapter+'.words.jsonl')
    if output.exists() and ledger.exists() and read(output).get('signature')==signature:return read(output)
    pan=QA/'artwork';pan.mkdir(exist_ok=True)
    en,en_map=panorama(en_id,images_en,pan);es,es_map=panorama(es_id,images_es,pan)
    previous=read(output) if output.exists() else {}
    baseline=QA/'comparison'/(chapter+'.json')
    if not previous and directory!=QA/'comparison' and baseline.exists():previous=read(baseline)
    if previous.get('image_signature')==image_signature and previous.get('alignment_version')==1:
        anchors,alignment=previous['anchors'],previous['artwork_alignment']
    else:anchors,alignment=artwork_anchors(en,es)
    english=lines(en_directory/(en_id+'.jsonl'));spanish=lines(QA/'ocr-es'/(es_id+'.jsonl'))
    for index,row in enumerate(english):
        location=en_map[str(row['image'])];scale=location['scale'];a,b,c,d=row['bounds']
        row['_box']=[a*scale,location['offset']+b*scale,c*scale,location['offset']+d*scale];row['_id']=index
        row['_tokens']={normal(w) for w in words(row.get('translation',''))}
    yvalues=[a['es'] for a in anchors];ledger_rows=[];counts=collections.Counter()
    for region_index,reference in enumerate(spanish):
        a,b,c,d=reference['bounds'];location=es_map[str(reference['image'])];scale=location['scale'];sx=(a+c)*scale/2;sy=location['offset']+(b+d)*scale/2
        i=bisect.bisect_left(yvalues,sy);mapped=None
        if 0<i<len(anchors):
            first,second=anchors[i-1],anchors[i];gap=second['es']-first['es'];slope=(second['en']-first['en'])/gap
            if gap<=1000 and .75<slope<1.33:mapped=first['en']+(sy-first['es'])*slope
        best=None;best_score=1e9
        if mapped is not None:
            for row in english:
                x1,y1,x2,y2=row['_box'];gap=max(y1-mapped,mapped-y2,0);horizontal=abs((x1+x2)/2-sx)
                if gap>25 or horizontal>max(45,(x2-x1)/2):continue
                score=gap*2+abs((y1+y2)/2-mapped)*.35+horizontal*.15
                if score<best_score:best=row;best_score=score
        for index,word in enumerate(words(reference['source'])):
            state='alignment_pending' if mapped is None else 'no_luma_region_nearby' if best is None else 'literal_token_present' if normal(word) in best['_tokens'] else 'different_wording'
            counts[state]+=1
            ledger_rows.append(dict(reference_word=word,reference_region=region_index,word_index=index,reference_image=reference['image'],reference_bounds=reference['bounds'],
                reference_text=reference['source'],reference_native_text=reference['native_source'],
                reference_reading_human_verified=False,artwork_alignment_human_verified=False,
                luma_region=best['_id'] if best else None,luma_image=best['image'] if best else None,luma_bounds=best['bounds'] if best else None,
                source=best['source'] if best else None,translation=best.get('translation') if best else None,
                state=state,meaning_approved=False,word_reviewed=False))
    result=dict(chapter=chapter,signature=signature,image_signature=image_signature,alignment_version=1,english_report_directory=en_directory.name,
        english_execution_kind=read(en_done).get('execution_kind','native_traversal'),
        display_build=read(en_done).get('display_build'),native_core_build=read(en_done).get('native_core_build'),
        ledger_format='region-indices-v1' if compact else 'explicit-words-v1',
        english_report_sha256=hashlib.sha256((en_directory/(en_id+'.jsonl')).read_bytes()).hexdigest(),
        reference_report_sha256=hashlib.sha256((QA/'ocr-es'/(es_id+'.jsonl')).read_bytes()).hexdigest(),
        english_files=len(images_en),spanish_files=len(images_es),english_regions=len(english),spanish_regions=len(spanish),
        reference_ocr_tokens=len(ledger_rows),token_states=dict(counts),artwork_alignment=alignment,anchors=anchors,
        word_review_complete=False,semantic_accuracy=None,comparison='Automatic proposals. Different wording can be correct; a literal token match can still be wrong.')
    write_atomic(ledger,''.join(json.dumps(compact_ledger_row(row) if compact else row,ensure_ascii=False)+'\n' for row in ledger_rows));write_atomic(output,json.dumps(result,ensure_ascii=False,indent=2))
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--watch',action='store_true')
    parser.add_argument('--update-review',action='store_true',help='Refresh the local review pages when comparisons change')
    parser.add_argument('--english-reports',help='Explicit English engine report directory')
    parser.add_argument('--output-name',default='comparison')
    parser.add_argument('--review-name',default='review')
    parser.add_argument('--expected-chapters',type=int,default=154)
    parser.add_argument('--series',choices=['all','absolute-regression'],default='all')
    parser.add_argument('--compact-ledger',action='store_true',help='Reference the existing EN/ES region reports instead of repeating full paragraphs per word')
    args=parser.parse_args()
    if not 1<=args.expected_chapters<=154:parser.error('Expected chapters must be between 1 and 154')
    for name in [args.english_reports,args.output_name,args.review_name]:
        if name and not re.fullmatch(r'[a-z][a-z0-9-]+',name):parser.error('Invalid QA directory name')
    grouped={}
    for language in ['en','es']:
        groups=collections.defaultdict(list)
        for row in read(QA/f'images-{language}.json'):
            if args.series=='all' or row['series']==args.series:groups[row['chapter'].removesuffix('-'+language)].append(row)
        grouped[language]=groups
    directory=QA/args.output_name;directory.mkdir(exist_ok=True)
    first_pass=True
    while True:
        changed=False
        for chapter in sorted(grouped['en']):
            en_done=QA/(args.english_reports or 'translated-en')/(chapter+'-en.done.json');es_done=QA/'ocr-es'/(chapter+'-es.done.json')
            if not en_done.exists() or not es_done.exists():continue
            if any(not read(p).get('all_files_traversed') or read(p).get('runtime_errors') for p in [en_done,es_done]):continue
            target=directory/(chapter+'.json');before=target.stat().st_mtime if target.exists() else 0
            result=compare(chapter,grouped['en'][chapter],grouped['es'][chapter],directory,args.english_reports,args.compact_ledger)
            if target.stat().st_mtime!=before:
                changed=True;print('Compared',chapter,result['reference_ocr_tokens'],'reference tokens',len(result['anchors']),'artwork anchors',flush=True)
        all_reports=[read(path) for path in directory.glob('*.json') if path.name!='summary.json']
        summary=dict(chapter_pairs_requested=args.expected_chapters,pairs_compared=len(all_reports),reference_ocr_tokens=sum(r['reference_ocr_tokens'] for r in all_reports),
            ledger_format='region-indices-v1' if args.compact_ledger else 'explicit-words-v1',
            all_words_visually_reviewed=False,semantic_accuracy=None,chapters=all_reports)
        summary_path=directory/'summary.json';summary_text=json.dumps(summary,ensure_ascii=False,indent=2)
        if not summary_path.exists() or summary_path.read_text(encoding='utf-8')!=summary_text:write_atomic(summary_path,summary_text)
        if args.update_review and (changed or first_pass):
            command=[sys.executable,str(ROOT/'tools/create_full_comic_review.py'),'--comparisons',args.output_name,'--output-name',args.review_name]
            if args.english_reports:command.extend(['--english-reports',args.english_reports])
            command.extend(['--series',args.series])
            subprocess.run(command,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
        first_pass=False
        all_final=len(all_reports)>=args.expected_chapters and all(r.get('english_report_directory')==(args.english_reports or 'translated-en-final') for r in all_reports)
        if not args.watch or all_final:break
        time.sleep(15)

if __name__=='__main__':main()
