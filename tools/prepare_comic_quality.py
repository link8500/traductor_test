"""Download the user-selected regression pages and pinned local model artifacts.

Comic images stay under build/ and are never included in the application.
"""
from __future__ import annotations
import argparse, concurrent.futures, hashlib, html, json, pathlib, re, time
import requests

ROOT = pathlib.Path(__file__).resolve().parents[1]
QA = ROOT / 'build/comic-quality'
MODEL = ROOT / 'assets/models/opus-en-es'
REVISION = '4b002a4c7edd54a7ced58877258b87f7efd3f892'
BASE = f'https://huggingface.co/Xenova/opus-mt-en-es/resolve/{REVISION}/'

def download(url: str, path: pathlib.Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return
    for attempt in range(3):
        try:
            with requests.get(url, stream=True, timeout=(20, 120), headers={'User-Agent':'Luma local translation evaluation'}) as response:
                response.raise_for_status()
                with path.with_suffix(path.suffix + '.part').open('wb') as output:
                    for chunk in response.iter_content(1024 * 1024): output.write(chunk)
            path.with_suffix(path.suffix + '.part').replace(path)
            return
        except Exception:
            if attempt == 2: raise
            time.sleep(1 + attempt)

def chapters():
    manifest = json.loads((QA/'manifest.json').read_text(encoding='utf-8'))
    jobs=[]
    for chapter in manifest:
        source=html.unescape((QA/f"{chapter['id']}.html").read_text(encoding='utf-8'))
        urls=list(dict.fromkeys(re.findall(r'https://cdn\.asurascans\.com/asura-images/chapters/[^"\s<>\\]+?\.webp(?:\?v=\d+)?', source)))
        chapter['images']=[{'index':i, 'url':url, 'path':f"images/{chapter['id']}/{i:03d}.webp"} for i,url in enumerate(urls)]
        for image in chapter['images']: jobs.append((image['url'],QA/image['path']))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(download,*job):job[1] for job in jobs}
        done=0
        for future in concurrent.futures.as_completed(futures):
            future.result(); done+=1
            if done%15==0: print(f'comic images {done}/{len(jobs)}',flush=True)
    from PIL import Image
    for chapter in manifest:
        for image in chapter['images']:
            with Image.open(QA/image['path']) as bitmap: image['width'],image['height']=bitmap.size
        print(chapter['id'],len(chapter['images']),'images',flush=True)
    (QA/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')

def model():
    # The final app uses the larger checkpoint selected in the comic comparison.
    import sys
    from prepare_larger_model import main
    sys.argv=[sys.argv[0],'--bundle']
    main()
    return

def compact_reference_model():
    files={'encoder.onnx':'onnx/encoder_model_quantized.onnx', 'decoder.onnx':'onnx/decoder_model_merged_quantized.onnx',
           'source.spm':'source.spm','vocab.json':'vocab.json','config.json':'config.json','README.upstream.md':'README.md'}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        jobs={pool.submit(download,BASE+remote,MODEL/local):local for local,remote in files.items()}
        for job in concurrent.futures.as_completed(jobs): job.result(); print('model',jobs[job],'ready',flush=True)
    import sentencepiece as sp
    processor=sp.SentencePieceProcessor(model_file=str(MODEL/'source.spm'))
    vocab=json.loads((MODEL/'vocab.json').read_text(encoding='utf-8'))
    tokens=[None]*len(vocab)
    for token,index in vocab.items(): tokens[index]=token
    pieces=[[processor.id_to_piece(i),processor.get_score(i),vocab[processor.id_to_piece(i)]] for i in range(processor.get_piece_size())
            if processor.id_to_piece(i) in vocab and not processor.is_control(i) and not processor.is_unknown(i)]
    (MODEL/'tokenizer.json').write_text(json.dumps({'pieces':pieces,'tokens':tokens,'unk':vocab['<unk>'],'eos':vocab['</s>'],'pad':vocab['<pad>']},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    lock={'repository':'Xenova/opus-mt-en-es','upstream':'Helsinki-NLP/opus-mt-en-es','revision':REVISION,'license':'Apache-2.0',
          'files':{path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in MODEL.iterdir() if path.is_file() and path.name!='manifest.json'}}
    (MODEL/'manifest.json').write_text(json.dumps(lock,indent=2),encoding='utf-8')
    print('model bytes',sum(path.stat().st_size for path in MODEL.iterdir() if path.is_file()),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('target',choices=['chapters','model']);args=parser.parse_args()
    globals()[args.target]()
