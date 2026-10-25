"""Checkpointed inventory/downloads for every supplied bilingual chapter.

Raw public pages remain in build/. Nothing here is an approved transcript.
"""
import argparse,concurrent.futures,hashlib,json,pathlib,re,time
from urllib.parse import urlparse
import requests
from PIL import Image
import prepare_bilingual_quality as previous
import align_bilingual_samples as alignment

ROOT=pathlib.Path(__file__).resolve().parents[1]
QA=ROOT/'build/full-comics'

def inventory():
    old=json.loads((ROOT/'benchmarks/bilingual-comics/sources.json').read_text(encoding='utf-8'))
    source=ROOT/'texo.text';data=source.read_bytes();records=list(old['records'])
    for url in re.findall(r'https://[^\s<>]+',data.decode('utf-8-sig')):
        host=urlparse(url).hostname;parts=urlparse(url).path.strip('/').split('/')
        language='en' if host=='asurascans.com' else 'es' if host=='olympusxyz.com' else None
        assert language and len(parts)==4 and parts[3].isdigit(),url
        assert parts[1]==old['series']['absolute-regression'][language],url
        chapter=int(parts[3]);assert 31<=chapter<=124,url
        records.append(dict(id=f'absolute-regression-{chapter:02d}-{language}',series='absolute-regression',chapter=chapter,language=language,url=url))
    assert len(records)==308 and len({r['id'] for r in records})==308
    for series,count in [('absolute-regression',124),('greatest-estate-developer',30)]:
        for lang in ['en','es']:
            assert sorted(r['chapter'] for r in records if r['series']==series and r['language']==lang)==list(range(1,count+1))
    result={'chapter_pairs':154,'new_chapter_pairs':94,'records':records,
        'sources':[{'path':'benchmarks/bilingual-comics/sources.json','sha256':hashlib.sha256((ROOT/'benchmarks/bilingual-comics/sources.json').read_bytes()).hexdigest()},
                   {'path':'texo.text','sha256':hashlib.sha256(data).hexdigest()}]}
    path=ROOT/'benchmarks/full-comics/sources.json';path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');QA.mkdir(parents=True,exist_ok=True)
    return result

def audit_english(source):
    previous.QA=QA
    cached={r['id']:r for r in json.loads((ROOT/'build/bilingual-quality/audit.json').read_text(encoding='utf-8'))['records']}
    def audit(row):
        old=cached.get(row['id'])
        if old and old.get('reader_state')=='image_links_present':return old
        return previous.audit(row)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows=[]
        for row in pool.map(audit,[r for r in source['records'] if r['language']=='en']):
            rows.append(row)
            if len(rows)%10==0:print('English chapter lists',len(rows),'/154',flush=True)
    (QA/'english-reader.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    assert all(r['reader_state']=='image_links_present' for r in rows),'Some English chapters unavailable; see inventory'
    return rows

def spanish_records(source):
    rows=alignment.reader_records()
    extra=ROOT/'benchmarks/full-comics/spanish-reader-extra.json'
    if extra.exists():
        links={r['chapter']:r for r in source['records'] if r['series']=='absolute-regression' and r['language']=='es'}
        data=json.loads(extra.read_text(encoding='utf-8'))
        for chapter,directory,pattern,count,check in data['records']:
            row=dict(c=chapter,d=directory,f=data['patterns'][pattern],n=count,h=check)
            names=[]
            for part in row['f'].split('|'):
                match=re.fullmatch(r'(.*)\{(\d+)-(\d+)\}',part)
                names.extend([match[1]+str(n).zfill(len(match[2]))+'.webp' for n in range(int(match[2]),int(match[3])+1)] if match else [part+'.webp'])
            value=2166136261
            for char in '|'.join(names):value=((value^ord(char))*16777619)&0xffffffff
            assert len(names)==row['n'] and f'{value:08x}'==row['h'],row
            record=links[row['c']]
            rows.append({**record,'reader_source':'Rendered DOM, 2026-10-23','images':[dict(index=i,url=f"https://media.imagesolymp.xyz/comics/1382/{row['d']}/{name}") for i,name in enumerate(names)]})
    return rows

def download_all(readers):
    work=[]
    for row in readers:
        for index,item in enumerate(row['images']):
            url=item['url'];path=QA/'images'/row['id']/f'{index:03d}.webp'
            if row['language']=='es':
                old=ROOT/'build/bilingual-quality/references'/row['id']/f'{index:03d}.webp'
                if old.exists():path=old
            work.append(dict(chapter=row['id'],series=row['series'],number=row['chapter'],language=row['language'],image=index,url=url,path=str(path.resolve())))
    def download(row):
        path=pathlib.Path(row['path']);path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():
            for attempt in range(4):
                try:
                    response=requests.get(row['url'],timeout=(15,60),headers={'User-Agent':'Luma local bilingual evaluation'})
                    response.raise_for_status();partial=path.with_suffix('.partial');partial.write_bytes(response.content)
                    with Image.open(partial) as bitmap:bitmap.verify()
                    partial.replace(path);break
                except (requests.RequestException,OSError) as error:
                    if attempt==3 or getattr(getattr(error,'response',None),'status_code',None) in [401,403]:raise
                    time.sleep(attempt+1)
        with Image.open(path) as bitmap:width,height=bitmap.size
        return {**row,'width':width,'height':height,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    results=[];errors=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        pending={pool.submit(download,row):row for row in work}
        for future in concurrent.futures.as_completed(pending):
            try:results.append(future.result())
            except Exception as error:errors.append({**pending[future],'error':str(error)})
            if (len(results)+len(errors))%100==0:print('Images verified',len(results),'/',len(work),'errors',len(errors),flush=True)
    results.sort(key=lambda r:(r['chapter'],r['image']))
    suffix='-en' if all(r['language']=='en' for r in work) else '-es' if all(r['language']=='es' for r in work) else ''
    (QA/f'images{suffix}.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    (QA/f'download-errors{suffix}.json').write_text(json.dumps(errors,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Images',len(results),'errors',len(errors),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--english',action='store_true');parser.add_argument('--download',choices=['en','es','all'])
    args=parser.parse_args();source=inventory();print('Indexed 154 chapter pairs; 94 new',flush=True)
    en=audit_english(source) if args.english else json.loads((QA/'english-reader.json').read_text(encoding='utf-8')) if (QA/'english-reader.json').exists() else []
    if args.download:
        es=spanish_records(source) if args.download in ['es','all'] else []
        download_all((en if args.download in ['en','all'] else [])+es)
