"""Translate every changed source with the current offline native translator."""
import json
import subprocess
from audit_corpus_quality import ROOT, QA, atomic, digest, read, records
from quality_resources import wait_for_inference_memory


def main():
    folder=QA/'ocr-morph-consensus8026';summary=read(folder/'summary.json')
    assert summary['native_guards']['success']
    assert all(not r['worsened'] for r in summary['cohorts'].values())
    changes=read(folder/'full-viewports-changes.json')
    binary=ROOT/'build/local-model8026/Release/luma_translate.exe'
    manifest=folder/'translation-input.jsonl';target=folder/'translation-output.jsonl'
    inputs=[dict(id=r['id'],image=r['image'],source=r['after_source']) for r in changes]
    atomic(manifest,''.join(json.dumps(r)+'\n' for r in inputs))
    proof=dict(binary_sha256=digest(binary),runtime_sha256=digest(binary.parent/'onnxruntime.dll'),
        selection_summary_sha256=digest(folder/'summary.json'),input_sha256=digest(manifest),
        sources={n:digest(ROOT/n) for n in ['native/translate_cli.cpp','native/local_translation.cpp','native/local_translation.h','native/translation_coverage.h']},
        assets={n:digest(ROOT/'assets/models/opus-en-es'/n) for n in ['encoder.onnx','decoder.onnx','tokenizer.json','terminology.json']},
        reference_or_manual_answers_supplied=False,new_model_weights=False,actual_app_integrated=False)
    pin=folder/'translation-provenance.json'
    if pin.exists():assert read(pin)==proof
    else:atomic(pin,json.dumps(proof,indent=2))
    if not target.exists():
        wait_for_inference_memory()
        work=folder/'translation-work.jsonl'
        with manifest.open('rb') as src,work.open('wb') as dest:
            subprocess.run([str(binary),str(ROOT/'assets/models/opus-en-es')],stdin=src,stdout=dest,
                check=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=300)
        output=records(work);assert len(output)==len(inputs) and all('error' not in r for r in output)
        atomic(target,work.read_text(encoding='utf-8'))
    output=records(target);assert len(output)==len(inputs) and all('error' not in r for r in output)
    print(json.dumps(dict(fresh_native_translations=len(output),output_sha256=digest(target),all_meanings_reviewed=False)),flush=True)


if __name__=='__main__':main()
