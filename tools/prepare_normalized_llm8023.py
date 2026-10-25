"""Prepare the same native English inputs for a fair local-model comparison."""
import argparse
import json
import shutil
import subprocess
from audit_corpus_quality import ROOT, QA, atomic, digest, read, records
from prepare_local_llm8021 import download


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--restore-model',action='store_true');args=parser.parse_args()
    folder=QA/'local-llm8023-normalized';folder.mkdir(exist_ok=True)
    if args.restore_model:
        cache=ROOT/'build/llm-quality8021';model=read(cache/'download-provenance.json')['model']
        assert shutil.disk_usage(ROOT).free>model['size']+4*1024**3
        download(model['url'],cache/model['filename'],model['sha256'],model['size'])
        print(json.dumps(dict(cached=True,model_sha256=model['sha256'])),flush=True);return
    source=QA/'windows8021-full-viewports-full-agreement/output.jsonl';rows=records(source)
    assert len(rows)==228 and len({r['image'] for r in rows})==124
    unique=list(dict.fromkeys(r['source'] for r in rows))
    manifest=folder/'prepare-input.jsonl';atomic(manifest,''.join(json.dumps(dict(id=i,source=s,prepare=True))+'\n' for i,s in enumerate(unique)))
    binary=ROOT/'build/local-model8019/Release/luma_translate.exe'
    target=folder/'native-prepared.jsonl'
    if not target.exists():
        with manifest.open('rb') as src,target.open('wb') as out:
            subprocess.run([str(binary),str(ROOT/'assets/models/opus-en-es')],stdin=src,stdout=out,
                check=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=180)
    prepared=records(target)
    assert len(prepared)==len(unique)==215 and all('error' not in r for r in prepared)
    assert [r['source'] for r in prepared]==unique
    proof=dict(frozen_ocr_sha256=digest(source),prepare_input_sha256=digest(manifest),
        native_prepared_sha256=digest(target),native_binary_sha256=digest(binary),
        native_runtime_sha256=digest(binary.parent/'onnxruntime.dll'),
        native_source_sha256=digest(ROOT/'native/local_translation.cpp'),
        preprocessing='Exact existing LocalTranslationModel.PrepareInput; no human/reference text',
        model_assets={n:digest(ROOT/'assets/models/opus-en-es'/n) for n in ['encoder.onnx','decoder.onnx','tokenizer.json','terminology.json']},
        unique_sources=215,regions=228,viewports=124,translation_inferences_run_during_preparation=0,
        new_model_weights=False,application_modified=False,reference_text_supplied=False)
    pin=folder/'prepare-provenance.json'
    if pin.exists():assert read(pin)==proof
    else:atomic(pin,json.dumps(proof,indent=2))
    atomic(folder/'case-analysis.json',json.dumps(dict(native_prepared_sha256=digest(target),
        changed_prepared_sources=sum(r['source']!=r['prepared'] for r in prepared),
        preparation_only_changes_case=all(r['source'].casefold()==r['prepared'].casefold() for r in prepared)),indent=2))
    print(json.dumps(dict(prepared=215,regions=228,viewports=124,reference_text_supplied=False)),flush=True)


if __name__=='__main__':main()
