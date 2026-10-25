"""Run app-produced OCR through the identical native offline translation core.

This is a regression/execution report, not an automatic semantic accuracy score.
The copyrighted chapter text stays in build/ and is never shipped with Luma.
"""
from __future__ import annotations
import argparse, concurrent.futures, hashlib, json, pathlib, subprocess, threading, time

ROOT = pathlib.Path(__file__).resolve().parents[1]
QA = ROOT / 'build/comic-quality'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--workers',type=int,default=3)
    parser.add_argument('--input',type=pathlib.Path,default=QA/'ocr.jsonl')
    parser.add_argument('--prefix',default='')
    parser.add_argument('--output-directory',type=pathlib.Path,default=QA)
    args=parser.parse_args()
    destination=args.output_directory;destination.mkdir(parents=True,exist_ok=True)
    rows=[json.loads(line) for line in args.input.read_text(encoding='utf-8').splitlines() if line.strip()]
    model=ROOT/'assets/models/opus-en-es'
    signature=hashlib.sha256((model/'manifest.json').read_bytes()+(ROOT/'native/local_translation.cpp').read_bytes()).hexdigest()
    if '/' in args.prefix or '\\' in args.prefix:raise ValueError('The report prefix must be a filename prefix')
    output=destination/(args.prefix+'translations.jsonl')
    cached={}
    if output.exists():
        for line in output.read_text(encoding='utf-8').splitlines():
            try:
                row=json.loads(line)
                if row.get('engine')==signature and 'translation' in row: cached[row['source']]=row
            except ValueError: pass
    unique=list(dict.fromkeys(row['source'] for row in rows))
    pending=[source for source in unique if source not in cached]
    groups=[pending[i::args.workers] for i in range(args.workers)]
    lock=threading.Lock();start=time.monotonic();done=0
    with output.open('a',encoding='utf-8',buffering=1) as stream:
        def worker(sources):
            nonlocal done
            process=subprocess.Popen([str(ROOT/'build/local-model/Release/luma_translate.exe'),str(model)],
                                     stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',bufsize=1)
            try:
                for source in sources:
                    process.stdin.write(json.dumps({'source':source},ensure_ascii=False)+'\n');process.stdin.flush()
                    response=process.stdout.readline()
                    if not response: raise RuntimeError(process.stderr.read())
                    record=json.loads(response);record['engine']=signature
                    with lock:
                        cached[source]=record;stream.write(json.dumps(record,ensure_ascii=False)+'\n');done+=1
                        if done%20==0: print(f'{done}/{len(pending)} new translations · {time.monotonic()-start:.0f}s',flush=True)
            finally:
                process.stdin.close();process.wait()
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            for result in pool.map(worker,groups): pass
    chapters={}
    joined=[]
    for row in rows:
        translated=cached[row['source']]
        result={**row,**translated}
        if 'error' not in translated:result.pop('error',None)
        joined.append(result)
        chapter=chapters.setdefault(row['chapter'],{'regions':0,'runtime_errors':0,'unchanged':0,'retained_original':0,'terminology_adjustments':0})
        chapter['regions']+=1
        chapter['runtime_errors']+=int('error' in translated)
        chapter['unchanged']+=int(translated.get('translation','').casefold()==row['source'].casefold())
        chapter['retained_original']+=int(bool(translated.get('retained_original')))
        chapter['terminology_adjustments']+=int(bool(translated.get('terminology')))
    (destination/(args.prefix+'translated-regions.jsonl')).write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in joined),encoding='utf-8')
    summary={'engine':signature,'unique_sources':len(unique),'regions':len(rows),'chapters':chapters,
             'semantic_accuracy':'Not automatically established: requires reviewed reference translations.',
             'elapsed_seconds':time.monotonic()-start}
    (destination/(args.prefix+'translation-summary.json')).write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
