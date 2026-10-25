"""Audit user-provided EN/ES chapters and prepare reproducible local samples.

Chapter HTML, images and recognized text stay in build/. A successful HTTP
response is not proof that a chapter contains usable reference translations.
"""
from __future__ import annotations
import argparse,concurrent.futures,hashlib,json,pathlib,re
from html.parser import HTMLParser
from urllib.parse import urljoin,urlparse
import requests

ROOT=pathlib.Path(__file__).resolve().parents[1]
QA=ROOT/'build/bilingual-quality'
SERIES={
    'absolute-regression':{'en':'absolute-regression-11fe7da3','es':'comic-geom-mugeuk-20261023-080026034'},
    'greatest-estate-developer':{'en':'the-greatest-estate-developer-11fe7da3','es':'comic-loco-frontera-20261023-080055819'},
}


class ChapterHTML(HTMLParser):
    def __init__(self,url):
        super().__init__();self.url=url;self.images=[];self.title='';self.in_title=False
    def handle_starttag(self,tag,attrs):
        values=dict(attrs)
        if tag=='title':self.in_title=True
        if tag=='img':
            alt=values.get('alt','')
            # Exclude covers, ads, avatars and recommendations.
            if ('data-page-index' in values or re.search(r'capítulo \d+, página \d+',alt)) and values.get('src'):
                self.images.append({'url':urljoin(self.url,values['src']),'alt':alt})
    def handle_endtag(self,tag):
        if tag=='title':self.in_title=False
    def handle_data(self,text):
        if self.in_title:self.title+=text


def inventory(source):
    data=source.read_bytes();urls=re.findall(r'https://[^\s<>]+',data.decode('utf-8-sig'))
    records=[];seen=set()
    for url in urls:
        parsed=urlparse(url);parts=parsed.path.strip('/').split('/')
        language='es' if parsed.hostname=='olympusxyz.com' else 'en' if parsed.hostname=='asurascans.com' else None
        if language is None or len(parts)!=4 or not parts[3].isdigit():
            raise ValueError(f'Unrecognized chapter URL: {url}')
        series=next((key for key,value in SERIES.items() if value[language]==parts[1]),None)
        if series is None:raise ValueError(f'Unknown series: {url}')
        number=int(parts[3]);key=(series,number,language)
        if key in seen:raise ValueError(f'Duplicate chapter: {key}')
        seen.add(key)
        records.append({'id':f'{series}-{number:02d}-{language}','series':series,'chapter':number,'language':language,'url':url})
    pairs=[]
    for series in SERIES:
        numbers=sorted({row['chapter'] for row in records if row['series']==series})
        for number in numbers:
            links={row['language']:row['url'] for row in records if row['series']==series and row['chapter']==number}
            if set(links)!={'en','es'}:raise ValueError(f'Missing language: {series} {number}')
            pairs.append({'series':series,'chapter':number,**links,'alignment':'unverified; inspect matching artwork before treating as a reference'})
    result={'source_sha256':hashlib.sha256(data).hexdigest(),'chapters':len(pairs),'links':len(records),'series':SERIES,'pairs':pairs,'records':records}
    destination=ROOT/'benchmarks/bilingual-comics/sources.json';destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result


def audit(record):
    path=QA/'pages'/f"{record['id']}.html";path.parent.mkdir(parents=True,exist_ok=True)
    result=dict(record)
    try:
        text=path.read_text(encoding='utf-8') if path.exists() else ''
        cached=ChapterHTML(record['url']);cached.feed(text)
        usable=bool(cached.images) and not any(urlparse(image['url']).path.startswith('/cp/') for image in cached.images)
        if usable:
            result.update(http_status=200,cached=True)
        else:
            response=requests.get(record['url'],timeout=(15,35),headers={'User-Agent':'Luma local bilingual evaluation'})
            result.update(http_status=response.status_code,final_url=response.url)
            response.raise_for_status();text=response.text;path.write_text(text,encoding='utf-8')
        parser=ChapterHTML(record['url']);parser.feed(text)
        result.update(title=parser.title,images=parser.images,html_sha256=hashlib.sha256(text.encode()).hexdigest())
        placeholders=[image for image in parser.images if urlparse(image['url']).path.startswith('/cp/')]
        result['reader_state']='placeholder_images' if placeholders else 'image_links_present' if parser.images else 'no_chapter_images'
    except requests.RequestException as error:result.update(reader_state='http_error',error=str(error))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=pathlib.Path)
    parser.add_argument('--audit',action='store_true')
    parser.add_argument('--samples',action='store_true',help='Download one deterministic middle image per available chapter')
    args=parser.parse_args();QA.mkdir(parents=True,exist_ok=True)
    source=inventory(args.source)
    print(f"Indexed {source['chapters']} chapter pairs / {source['links']} links",flush=True)
    if not args.audit:return
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows=[]
        for row in pool.map(audit,source['records']):
            rows.append(row)
            if len(rows)%10==0:print(f"Audited {len(rows)}/{len(source['records'])}",flush=True)
    # Probe each unique placeholder once; avoid reporting 200 HTML as a usable
    # Spanish translation when its actual images return 404.
    placeholders={image['url'] for row in rows for image in row.get('images',[]) if urlparse(image['url']).path.startswith('/cp/')}
    probes=[]
    for url in sorted(placeholders):
        try:
            response=requests.get(url,timeout=(10,20),headers={'User-Agent':'Luma local bilingual evaluation'})
            probes.append({'url':url,'status':response.status_code,'content_type':response.headers.get('content-type')})
        except requests.RequestException as error:probes.append({'url':url,'error':str(error)})
    summary={'chapter_pairs':source['chapters'],'links_audited':len(rows),'by_language':{},'placeholder_probes':probes,
        'semantic_accuracy':None,'semantic_accuracy_reason':'Requires accessible, visually aligned and reviewed Spanish references; automatic OCR is not ground truth.'}
    for language in ['en','es']:
        group=[row for row in rows if row['language']==language]
        summary['by_language'][language]={state:sum(row['reader_state']==state for row in group) for state in ['image_links_present','placeholder_images','no_chapter_images','http_error']}
        summary['by_language'][language]['image_links']=sum(len(row.get('images',[])) for row in group)
    (QA/'audit.json').write_text(json.dumps({'summary':summary,'records':rows},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
    if args.samples:prepare_samples(rows)


def prepare_samples(records):
    from PIL import Image
    candidates=[row for row in records if row['reader_state']=='image_links_present']
    def sample(row):
        index=len(row['images'])//2;image=row['images'][index]
        directory=QA/'samples'/row['id'];directory.mkdir(parents=True,exist_ok=True)
        raw=directory/'original.webp'
        if not raw.exists():
            response=requests.get(image['url'],timeout=(15,60),headers={'User-Agent':'Luma local bilingual evaluation'})
            response.raise_for_status();raw.write_bytes(response.content)
        with Image.open(raw) as bitmap:
            bitmap=bitmap.convert('RGB');width,height=bitmap.size
            # Fixed 390 x 844 view, sampled from the middle of the page. This
            # simulates layout only; it is not an Android permission/UI test.
            resized=bitmap.resize((390,round(height*390/width)),Image.Resampling.LANCZOS)
            top=max(0,(resized.height-844)//2)
            viewport=resized.crop((0,top,390,min(top+844,resized.height)))
            canvas=Image.new('RGB',(390,844),'white');canvas.paste(viewport,(0,0));canvas.save(directory/'mobile.png')
            bitmap.save(directory/'desktop.png',compress_level=1)
        return {**{key:row[key] for key in ['id','series','chapter','language','url']},'source_image':image['url'],
            'source_index':index,'width':width,'height':height,'mobile_crop_top':top,'source_sha256':hashlib.sha256(raw.read_bytes()).hexdigest()}
    sampled=[];errors=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        pending={pool.submit(sample,row):row for row in candidates}
        for future in concurrent.futures.as_completed(pending):
            try:sampled.append(future.result())
            except Exception as error:errors.append({'id':pending[future]['id'],'error':str(error)})
            if (len(sampled)+len(errors))%10==0:print(f'Samples {len(sampled)}/{len(candidates)}, errors {len(errors)}',flush=True)
    sampled.sort(key=lambda row:row['id'])
    (QA/'samples.json').write_text(json.dumps({'selection':'one middle image and its middle 390x844 viewport per chapter; not full chapter coverage',
        'records':sampled,'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
    for size in ['mobile','desktop']:
        rows=[{'chapter':row['id'],'image':row['source_index'],'path':str((QA/'samples'/row['id']/f'{size}.png').resolve())}
            for row in sampled if row['language']=='en']
        (QA/f'windows-{size}-input.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows),encoding='utf-8')
    print('Prepared sample images:',len(sampled),flush=True)


if __name__=='__main__':main()
