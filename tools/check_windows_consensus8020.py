"""Run the real Windows OCR-consensus path on all124 untouched pixel crops.

Additional readers are explicitly configured for this isolated native test.
The default application and its installed model files are not switched.
"""
import collections
import json
import pathlib
import subprocess
import time
from audit_corpus_quality import ROOT,QA,atomic,digest,read,records
from evaluate_ocr_reader_comparison import compare
from evaluate_ocr_apostrophes8019 import strict_compare


def main():
    out=QA/'windows8020-consensus-heldout-pixels';out.mkdir(exist_ok=True)
    baseline=QA/'windows8019-heldout-pixels';old=records(baseline/'output.jsonl')
    binary=QA/'frozen-windows802001/traductor.exe';snapshot=QA/'windows-engine802001.json'
    assert digest(binary)==read(snapshot)['binary_sha256']
    first=QA/'ocr-candidates8016/english-v5';second=QA/'ocr-candidates8016/multilingual-v6-small'
    assets={name:{part:digest(folder/part) for part in ['english-ocr.onnx','ocr-characters.json','english-ocr-fallback.onnx','ocr-characters-fallback.json']}
        for name,folder in [('first',first),('second',second)]}
    inputs=[]
    for row in records(baseline/'input.jsonl'):
        inputs.append(dict(row,consensus_first_directory=str(first),consensus_second_directory=str(second)))
    manifest=out/'input.jsonl';atomic(manifest,''.join(json.dumps(r)+'\n' for r in inputs))
    proof=dict(binary_sha256=digest(binary),snapshot_sha256=digest(snapshot),input_sha256=digest(manifest),
        baseline_native_output_sha256=digest(baseline/'output.jsonl'),additional_reader_assets=assets,
        production_models_manifest_sha256=digest(ROOT/'assets/models/opus-en-es/manifest.json'),
        original_pixels_only=True,transcriptions_or_reference_answers_supplied=False,
        installed_application_model_assets_modified=False,production_default_unchanged=True,
        actual_windows_native_consensus_path=True,benchmark_configuration_explicit=True)
    pin=out/'provenance.json'
    if pin.exists():assert read(pin)==proof
    else:atomic(pin,json.dumps(proof,indent=2))
    output=out/'output.jsonl';done=pathlib.Path(str(output)+'.summary.json')
    if not done.exists():
        start=time.monotonic()
        subprocess.run([str(binary),'--comic-benchmark',str(manifest),str(output)],check=True,
            creationflags=subprocess.CREATE_NO_WINDOW,timeout=2400)
        atomic(out/'timing.json',json.dumps(dict(elapsed_seconds=time.monotonic()-start)))
    raw=read(done);rows=records(output)
    assert raw['images']==124 and raw['runtime_errors']==0 and len(rows)==len(old)==137
    before={};after={}
    for a,b in zip(old,rows):
        assert a['image']==b['image'] and a['bounds']==b['bounds']
        assert a['source']==b['before_consensus'],'Baseline recognition changed before the new policy'
        before.setdefault(a['image'],[]).append(a);after.setdefault(b['image'],[]).append(b)
    manual_path=ROOT/'benchmarks/full-comics/ocr8016-heldout-full-manual-transcriptions.json';truth={r[0]:r[1] for r in read(manual_path)}
    entries=[]
    for ident in sorted(before):
        a=sorted(before[ident],key=lambda r:(r['bounds'][1],r['bounds'][0]));b=sorted(after[ident],key=lambda r:(r['bounds'][1],r['bounds'][0]))
        old_source=' '.join(r['source'] for r in a);source=' '.join(r['source'] for r in b)
        entries.append(dict(id=ident,expected_visible_english=truth[ident],before_source=old_source,source=source,
            before_translations=[r['translation'] for r in a],translations=[r['translation'] for r in b],
            before_ocr=compare(truth[ident],old_source),after_ocr=compare(truth[ident],source),
            before_strict_ocr=strict_compare(truth[ident],old_source),after_strict_ocr=strict_compare(truth[ident],source),
            meaning_reviewed=False))
    metrics={}
    for label in ['before_ocr','after_ocr']:
        counts=collections.Counter()
        for e in entries:counts.update(e[label]['edit_categories'])
        metrics[label]=dict(word_errors=sum(e[label]['word_errors'] for e in entries),
            crops_with_word_errors=sum(e[label]['word_errors']>0 for e in entries),edit_categories=dict(counts))
    value=dict(actual_windows_pixel_crops=124,regions=137,runtime_errors=0,baseline_sources_preserved_before_policy=True,
        changed_source_locations=sum(e['before_source']!=e['source'] for e in entries),
        changed_translation_locations=sum(e['before_translations']!=e['translations'] for e in entries),
        metrics=metrics,entries=entries,summary_sha256=digest(done),native_output_sha256=digest(output),
        manual_sha256=digest(manual_path),provenance_sha256=digest(pin),
        all_changed_meanings_reviewed=False,default_application_enabled=False,
        installed_application_model_assets_modified=False,all_chapter_words_visually_reviewed=False,
        screen_attempt_failure_probability=None,target_achieved=False)
    atomic(out/'summary.json',json.dumps(value,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in value.items() if k!='entries'}),flush=True)


if __name__=='__main__':main()
