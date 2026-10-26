"""Prepare bounded, provenance-pinned data for an isolated OPUS LoRA pilot."""
import argparse
import concurrent.futures
import hashlib
import html
from html.parser import HTMLParser
import json
import pathlib
import re
import shutil
import time
from urllib.parse import urlsplit

import requests
from PIL import Image

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'build/finetune8031'
META=ROOT/'benchmarks/finetune8031'
MODEL='Helsinki-NLP/opus-mt-tc-big-en-es'
REVISION='8f4d4924189681076e9c642b2fd85278d793fd4d'
SEED='luma-opus-domain-pilot8031-v1'


def sha(p):
    h=hashlib.sha256()
    with pathlib.Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def save(p,value):
    p=pathlib.Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    text=json.dumps(value,ensure_ascii=False,indent=2)
    if p.exists():assert p.read_text(encoding='utf-8')==text,('Frozen input changed',str(p))
    else:p.write_text(text,encoding='utf-8')


def split(n):
    bucket=int(hashlib.sha256(f'{SEED}|{n}'.encode()).hexdigest()[:8],16)%100
    return 'train' if bucket<70 else 'validation' if bucket<85 else 'test'


def inventory(source):
    data=source.read_bytes();text=data.decode('utf-8-sig');rows=[]
    for u in re.findall(r'https?://[^\s<>]+',text):
        p=urlsplit(u);lang={'www.leercapitulo.co':'es','mangakatana.com':'en'}.get(p.hostname)
        assert lang and p.scheme=='https',u
        m=re.search(r'(?:/c|/)(\d+)/?$',p.path);assert m,u
        n=int(m[1]);rows.append(dict(id=f'seventh-prince-{n:03d}-{lang}',series='seventh-prince',chapter=n,language=lang,url=u,split=split(n)))
    assert len(rows)==434 and len({r['id'] for r in rows})==434
    for lang in ['en','es']:assert sorted(r['chapter'] for r in rows if r['language']==lang)==list(range(1,218))
    groups={s:[n for n in range(1,218) if split(n)==s] for s in ['train','validation','test']}
    pilot={'train':groups['train'][:2],'validation':groups['validation'][:1],'test':groups['test'][:1]}
    value=dict(schema=1,source_path=str(source),source_sha256=hashlib.sha256(data).hexdigest(),chapter_pairs=217,
               seed=SEED,split_unit='complete_chapter',assignments=groups,initial_pilot_chapters=pilot,
               initial_pilot_max_pages_per_language_and_chapter=18,records=rows,
               previous_absolute_regression_corpus_role='regression_test_only_never_training',
               test_answers_allowed_for_training=False,chapter_links_are_not_approved_training_pairs=True)
    save(META/'sources.json',value)
    print(json.dumps(dict(chapter_pairs=217,splits={k:len(v) for k,v in groups.items()},pilot=pilot)),flush=True)


class Images(HTMLParser):
    def __init__(self):super().__init__();self.rows=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='img' and a.get('alt','').startswith('Capitulo ') and a.get('data-index','').isdigit():
            self.rows.append((int(a['data-index']),html.unescape(a['data-src'])))


def request(url,referer=None):
    response=requests.get(url,timeout=(15,60),headers={'User-Agent':'Mozilla/5.0','Referer':referer or url})
    response.raise_for_status();return response


def pages(expansion=False):
    source=json.loads((META/'sources.json').read_text(encoding='utf-8'))
    selected=set(source['assignments']['train'][2:4]) if expansion else {n for ns in source['initial_pilot_chapters'].values() for n in ns}
    folder=OUT/'expansion-v1' if expansion else OUT
    work=[];readers=[]
    for r in source['records']:
        if r['chapter'] not in selected:continue
        p=folder/'readers'/(r['id']+'.html');p.parent.mkdir(parents=True,exist_ok=True)
        if not p.exists():p.write_text(request(r['url']).text,encoding='utf-8')
        text=p.read_text(encoding='utf-8')
        if r['language']=='es':parser=Images();parser.feed(text);images=[u for _,u in sorted(parser.rows)]
        else:
            m=re.search(r'\bvar\s+thzq\s*=\s*\[(.*?)\]\s*;',text,re.S);assert m,r['id']
            images=re.findall(r"['\"](https://[^'\"]+)['\"]",m[1])
        assert 5<=len(images)<=150,(r['id'],len(images));assert len(images)==len(set(images))
        readers.append(dict(r,html_sha256=sha(p),all_page_urls=images,pages_available=len(images)))
        for i,url in enumerate(images[:source['initial_pilot_max_pages_per_language_and_chapter']]):
            assert urlsplit(url).scheme=='https'
            ext='.webp' if r['language']=='es' else '.jpg'
            work.append(dict(chapter=r['chapter'],language=r['language'],split=r['split'],page=i,url=url,
                             chapter_url=r['url'],path=str(folder/'images'/r['id']/(f'{i:03d}'+ext))))
    save(folder/'readers.json',readers)
    def one(r):
        p=pathlib.Path(r['path']);p.parent.mkdir(parents=True,exist_ok=True)
        if not p.exists():
            assert shutil.disk_usage(OUT).free>4*1024**3+10*1024**2
            value=request(r['url'],r['chapter_url']).content
            temporary=p.with_name(p.name+'.part');temporary.write_bytes(value)
            with Image.open(temporary) as image:assert image.width>=200 and image.height>=200;image.verify()
            temporary.replace(p)
        with Image.open(p) as image:width,height=image.size
        return dict(r,sha256=sha(p),width=width,height=height,bytes=p.stat().st_size)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results=[]
        for r in pool.map(one,work):
            results.append(r)
            if len(results)%12==0:print(json.dumps(dict(state='images',completed=len(results),expected=len(work))),flush=True)
    save(folder/'images.json',results)
    if expansion:save(folder/'scope.json',dict(role='additional_training_proposals_only',chapters=sorted(selected),all_splits=['train'],
        previous_test_chapter_retired_from_blind_final_evaluation=source['initial_pilot_chapters']['test'],
        future_unseen_test_chapters=[n for n in source['assignments']['test'] if n not in source['initial_pilot_chapters']['test']],
        source_inventory_sha256=sha(META/'sources.json'),automatically_approved_for_training=False))
    print(json.dumps(dict(chapter_pairs=len(selected),images=len(results),bytes=sum(r['bytes'] for r in results),all217_downloaded=False)),flush=True)


def model():
    folder=OUT/'base-model';folder.mkdir(parents=True,exist_ok=True)
    tree=request(f'https://huggingface.co/api/models/{MODEL}/tree/{REVISION}').json()
    selected={r['path']:r for r in tree if r['path'] in ['config.json','generation_config.json','model.safetensors','source.spm','target.spm','special_tokens_map.json','tokenizer_config.json','vocab.json','README.md']}
    assert len(selected)==9
    records=[]
    for name,entry in selected.items():
        path=folder/name;expected=entry.get('lfs',{}).get('oid')
        if not path.exists():
            assert shutil.disk_usage(folder).free>4*1024**3+entry['size']
            url=f'https://huggingface.co/{MODEL}/resolve/{REVISION}/{name}'
            response=requests.get(url,stream=True,timeout=(15,120));response.raise_for_status()
            temporary=path.with_name(path.name+'.part')
            with temporary.open('wb') as f:
                for b in response.iter_content(1024*1024):
                    f.write(b)
                    if f.tell()%(64*1024*1024)==0:print(json.dumps(dict(state='base_download',file=name,bytes=f.tell())),flush=True)
            assert temporary.stat().st_size==entry['size'];temporary.replace(path)
        assert path.stat().st_size==entry['size']
        actual=sha(path)
        if expected:assert actual==expected,(name,actual,expected)
        records.append(dict(path=name,bytes=path.stat().st_size,sha256=actual,upstream_lfs_sha256=expected))
        print(json.dumps(dict(state='base_verified',file=name,bytes=path.stat().st_size)),flush=True)
    save(OUT/'base-model-provenance.json',dict(model=MODEL,revision=REVISION,files=records,license='CC-BY-4.0',model_weights_unmodified=True))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['inventory','pages','model','expansion']);p.add_argument('--source',type=pathlib.Path);args=p.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    if args.command=='inventory':assert args.source;inventory(args.source)
    elif args.command in ['pages','expansion']:pages(args.command=='expansion')
    else:model()


if __name__=='__main__':main()
