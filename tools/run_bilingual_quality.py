"""Run the Windows app's real OCR/translation on the bilingual sample set."""
import argparse,concurrent.futures,hashlib,json,pathlib,subprocess,time

ROOT=pathlib.Path(__file__).resolve().parents[1]
QA=ROOT/'build/bilingual-quality'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--size',choices=['mobile','desktop'],default='mobile')
    parser.add_argument('--workers',type=int,default=2)
    args=parser.parse_args()
    executable=ROOT/'build/windows/x64/runner/Release/traductor.exe'
    rows=[json.loads(line) for line in (QA/f'windows-{args.size}-input.jsonl').read_text().splitlines()]
    model_manifest=ROOT/'assets/models/opus-en-es/manifest.json'
    signature=hashlib.sha256(model_manifest.read_bytes()+(ROOT/'native/local_translation.cpp').read_bytes()+
        (ROOT/'windows/runner/screen_translator.cpp').read_bytes()).hexdigest()
    started=time.monotonic()
    shards=[]
    for index in range(args.workers):
        input_=QA/f'{args.size}-input-{index}.jsonl';output=QA/f'{args.size}-output-{index}.jsonl'
        input_.write_text(''.join(json.dumps(row)+'\n' for row in rows[index::args.workers]),encoding='utf-8')
        shards.append((input_,output))

    def run(shard):
        input_,output=shard
        result=subprocess.run([str(executable),'--comic-benchmark',str(input_),str(output)],
            creationflags=subprocess.CREATE_NO_WINDOW,check=False)
        if result.returncode:
            error=pathlib.Path(str(output)+'.error.txt')
            raise RuntimeError(error.read_text() if error.exists() else f'Native benchmark exit {result.returncode}')
        return output

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for output in pool.map(run,shards):print('Completed',output.name,flush=True)
    results=[];summaries=[]
    for _,output in shards:
        results.extend(json.loads(line) for line in output.read_text(encoding='utf-8').splitlines())
        summaries.append(json.loads(pathlib.Path(str(output)+'.summary.json').read_text()))
    results.sort(key=lambda row:(row['chapter'],row['cropTop'],row['bounds'][1],row['bounds'][0]))
    (QA/f'{args.size}-translations.jsonl').write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in results),encoding='utf-8')
    by_chapter={row['chapter']:sum(item['chapter']==row['chapter'] for item in results) for row in rows}
    summary={'engine':signature,'size':args.size,'input_images':len(rows),'chapters_sampled':len(by_chapter),
        'selection':'one middle image per chapter; mobile uses only its middle 390x844 crop',
        'full_chapter_coverage':False,'regions':len(results),'viewports':sum(row['viewports'] for row in summaries),
        'runtime_errors':sum('error' in row for row in results),'retained_original':sum(row.get('retained_original',False) for row in results),
        'unchanged':sum(row.get('translation','').casefold()==row['source'].casefold() for row in results),
        'empty_samples':[chapter for chapter,count in by_chapter.items() if count==0],
        'regions_by_chapter':by_chapter,'semantic_accuracy':None,
        'semantic_accuracy_reason':'Needs visually aligned and reviewed reference segments; zero runtime errors does not mean correct translation.',
        'elapsed_seconds':round(time.monotonic()-started,2)}
    (QA/f'{args.size}-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
