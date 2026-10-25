"""Replay only changed preparations after full native OCR/translation passes.

Unchanged prepared text reuses actual baseline inference only with identical
decoder code and assets. This is not another screenshot/OCR traversal.
"""
import argparse,hashlib,json,pathlib,subprocess,time

ROOT=pathlib.Path(__file__).resolve().parents[1];QA=ROOT/'build/full-comics'
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def records(path):return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines() if s.strip()]
def decoder(text):return text[text.index('  std::string Generate('):text.index('LocalTranslationModel::LocalTranslationModel')]

def without_source_case_preparation(text):
    start=text.index('std::string LocalTranslationModel::PrepareSource(')
    end=text.index('std::string LocalTranslationModel::Translate(',start)
    return text[:start]+text[end:]
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--watch',action='store_true')
    parser.add_argument('--release-idle-models',action='store_true',help='Unload inference processes while waiting for another completed chapter');args=parser.parse_args()
    previous=(QA/'baseline-engine/local_translation.cpp').read_text(encoding='utf-8');current=(ROOT/'native/local_translation.cpp').read_text(encoding='utf-8')
    assert decoder(previous)==decoder(current),'Decoder changed; inference must be repeated for all texts'
    assert without_source_case_preparation(previous)==without_source_case_preparation(current),\
        'Changes outside PrepareSource need a separate inference/postprocessing audit before reuse'
    manifest=(ROOT/'assets/models/opus-en-es/manifest.json').read_bytes()
    assert json.loads(manifest)['files']==read(QA/'baseline-engine/manifest.json')['files'],'Model assets changed'
    engine=hashlib.sha256(current.encode()+manifest).hexdigest();directory=QA/'translated-en-final';directory.mkdir(exist_ok=True)
    processes=[]
    def start_models():
        processes.extend(subprocess.Popen([str(binary),str(ROOT/'assets/models/opus-en-es')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            text=True,encoding='utf-8',bufsize=1) for binary in [QA/'baseline-engine/luma_translate.exe',ROOT/'build/local-model/Release/luma_translate.exe'])
    def close_models():
        for process in processes:
            process.stdin.close();process.wait(timeout=30)
        processes.clear()
    def call(process,source,prepare=True):
        process.stdin.write(json.dumps(dict(source=source,prepare=prepare))+'\n');process.stdin.flush();line=process.stdout.readline()
        if not line:raise RuntimeError(process.stderr.read())
        result=json.loads(line)
        if 'error' in result:raise RuntimeError(result)
        return result
    old_cache={};new_cache={};translation_cache={}
    try:
        while True:
            for status in sorted((QA/'translated-en').glob('*.done.json')):
                baseline=read(status);chapter=baseline['chapter'];done=directory/(chapter+'.done.json');output=directory/(chapter+'.jsonl')
                if done.exists() and output.exists() and read(done).get('engine')==engine:continue
                if not processes:start_models()
                rows=records(status.with_name(chapter+'.jsonl'));final=[];fresh=0;reused=0;changed=[]
                for row in rows:
                    source=row['source']
                    if source not in old_cache:old_cache[source]=call(processes[0],source)
                    if source not in new_cache:new_cache[source]=call(processes[1],source)
                    old=old_cache[source];new=new_cache[source]
                    same=old['prepared']==new['prepared'] and old['source_corrections']==new['source_corrections'] and 'error' not in row
                    result={**row,'prepared':new['prepared'],'source_corrections':new['source_corrections'],'translation_engine':engine,'reused_identical_prepared_input':same}
                    if same:reused+=1
                    else:
                        if source not in translation_cache:translation_cache[source]=call(processes[1],source,False)
                        result.update(translation_cache[source]);fresh+=1
                    if row.get('translation')!=result.get('translation'):changed.append({'source':source,'before':row.get('translation'),'after':result.get('translation')})
                    final.append(result)
                temporary=output.with_suffix('.partial');temporary.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in final),encoding='utf-8');temporary.replace(output)
                report={**baseline,'engine':engine,'capture_ocr_engine':baseline['engine'],'replay_type':'Preparation audit over saved complete native traversal; reuse only for identical preparation with unchanged decoder and weights.',
                    'fresh_inference_records':fresh,'reused_identical_prepared_inputs':reused,'changed_translations':changed,'decoder_sha256':hashlib.sha256(decoder(current).encode()).hexdigest(),
                    'all_files_traversed_by_final_binary':False,'all_words_visually_reviewed':False,'translator_weights_changed':False}
                temporary=done.with_suffix('.partial');temporary.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(done)
                print('Replayed',chapter,'fresh',fresh,'reused',reused,'changed',len(changed),flush=True)
            if args.release_idle_models:close_models()
            reports=[read(p) for p in directory.glob('*.done.json')]
            summary={'engine':engine,'chapters':len(reports),'fresh_inference_records':sum(r['fresh_inference_records'] for r in reports),
                'reused_identical_prepared_inputs':sum(r['reused_identical_prepared_inputs'] for r in reports),'semantic_accuracy':None,'word_review_complete':False}
            (directory/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
            if not args.watch or len(reports)==154:break
            time.sleep(15)
    finally:
        close_models()

if __name__=='__main__':main()
