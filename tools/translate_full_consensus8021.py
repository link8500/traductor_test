"""Fresh offline native translations of every new full-viewport OCR proposal."""
import json
import subprocess
from audit_corpus_quality import ROOT, QA, atomic, digest, read, records


def main():
    folder=QA/'ocr-full-consensus8021'
    changes=read(folder/'full-viewports-changes.json')
    binary=ROOT/'build/local-model8019/Release/luma_translate.exe'
    manifest=folder/'translation-input.jsonl'
    inputs=[dict(id=r['id'],image=r['image'],source=r['selected']) for r in changes]
    atomic(manifest,''.join(json.dumps(r)+'\n' for r in inputs))
    proof=dict(binary_sha256=digest(binary),runtime_sha256=digest(binary.parent/'onnxruntime.dll'),
        selection_sha256=digest(folder/'summary.json'),input_sha256=digest(manifest),
        assets={n:digest(ROOT/'assets/models/opus-en-es'/n) for n in ['encoder.onnx','decoder.onnx','tokenizer.json','terminology.json']},
        reference_or_manual_answers_supplied=False,new_model_weights=False,actual_app_integrated=False)
    pin=folder/'translation-provenance.json'
    if pin.exists():assert read(pin)==proof
    else:atomic(pin,json.dumps(proof,indent=2))
    target=folder/'translation-output.jsonl'
    if not target.exists():
        with manifest.open('rb') as src,target.open('wb') as dest:
            subprocess.run([str(binary),str(ROOT/'assets/models/opus-en-es')],stdin=src,stdout=dest,
                check=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=900)
    outputs=records(target)
    assert len(outputs)==len(inputs) and all('error' not in r for r in outputs)
    print(json.dumps(dict(fresh_native_translations=len(outputs),output_sha256=digest(target),all_meanings_reviewed=False)),flush=True)


if __name__=='__main__':main()
