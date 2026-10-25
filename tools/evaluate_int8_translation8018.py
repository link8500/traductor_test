"""Compare existing int8 weights on every source from124 actual Windows crops."""
import collections
import json
import subprocess
from audit_corpus_quality import ROOT,QA,atomic,digest,read,records


def main():
    folder=QA/'int8-translation8018';folder.mkdir(exist_ok=True)
    source_path=QA/'windows8018-heldout-pixels/output.jsonl';rows=records(source_path)
    assets=ROOT/'build/comic-quality/tc-big-int8-8018';lock=read(assets/'evaluation-manifest.json')
    for name,sha in lock['assets'].items():assert digest(assets/name)==sha
    for name in ['tokenizer.json','terminology.json']:assert digest(assets/name)==digest(ROOT/'assets/models/opus-en-es'/name)
    native=ROOT/'build/local-model8018/Release/luma_translate.exe';proof=read(QA/'production-coverage8018/provenance.json')
    assert digest(native)==proof['binary_sha256']
    inputs={r['source'] for r in rows};manifest=folder/'input.jsonl'
    atomic(manifest,''.join(json.dumps(dict(source=s))+'\n' for s in sorted(inputs)))
    identity=dict(binary_sha256=digest(native),source_pixel_outputs_sha256=digest(source_path),input_sha256=digest(manifest),
        assets=lock['assets'],upstream=lock['upstream'],variant=lock['variant'],original_answers_supplied=False,
        application_assets_modified=False,model_training_performed=False)
    pin=folder/'provenance.json'
    if pin.exists():assert read(pin)==identity
    else:atomic(pin,json.dumps(identity,indent=2))
    output=folder/'inferences.jsonl';done={r['source']:r for r in records(output)} if output.exists() else {}
    assert set(done)<=inputs;model=None
    try:
        for source in sorted(inputs):
            if source in done:continue
            if model is None:model=subprocess.Popen([str(native),str(assets)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
            model.stdin.write(json.dumps(dict(source=source))+'\n');model.stdin.flush();line=model.stdout.readline();assert line,'Native int8 translator stopped'
            row=json.loads(line);assert row['source']==source and 'error' not in row
            with output.open('a',encoding='utf-8') as handle:handle.write(json.dumps(row,ensure_ascii=False)+'\n')
            done[source]=row
            if len(done)%20==0:print('Int8 source inferences:',len(done),'/',len(inputs),flush=True)
    finally:
        if model is not None:model.stdin.close();model.wait(timeout=30)
    groups=collections.defaultdict(list)
    for row in rows:groups[row['image']].append(row)
    entries=[]
    for ident,values in sorted(groups.items()):
        ordered=sorted(values,key=lambda r:(r['bounds'][1],r['bounds'][0]))
        entries.append(dict(id=ident,source=' '.join(r['source'] for r in ordered),
            before_translations=[r['translation'] for r in ordered],translations=[done[r['source']]['translation'] for r in ordered],
            meaning_reviewed=False))
    report=dict(pixel_locations=124,unique_source_inferences=len(done),runtime_errors=0,
        changed_locations=sum(r['before_translations']!=r['translations'] for r in entries),
        native_milliseconds=sum(r['milliseconds'] for r in done.values()),
        application_assets_modified=False,model_training_performed=False,meanings_reviewed=False,
        screen_attempt_failure_probability=None,all_chapter_words_visually_reviewed=False,
        provenance_sha256=digest(pin),output_sha256=digest(output),entries=entries)
    atomic(folder/'summary.json',json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='entries'}),flush=True)


if __name__=='__main__':main()
