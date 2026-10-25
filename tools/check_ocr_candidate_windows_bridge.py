"""Evaluate pixel-reader proposals against actual frozen Windows OCR sources.

Only single-block crops can change; multiple unrelated geometries are never
merged by a text-only postprocessor. This remains an integration experiment.
"""
import collections
import json
import subprocess
from audit_corpus_quality import ROOT,QA,atomic,digest,read,records
from evaluate_ocr_reader_comparison import compare


def main():
    out=QA/'ocr-coverage8017-windows-bridge';out.mkdir(exist_ok=True)
    app=read(QA/'windows8016-heldout-pixels/summary.json')
    readers=read(QA/'ocr-reader-heldout8016/sample.json')
    samples={r['id']:r for r in readers['cases']}
    frozen=QA/'ocr-coverage8017-development';binary=frozen/'native.exe'
    identity=read(frozen/'summary.json');assert digest(binary)==identity['binary_sha256']
    rows=[]
    for entry in app['entries']:
        readings=samples[entry['id']]['readings']
        rows.append(dict(id=entry['id'],base=entry['source'],
            first=readings['english-v5'] if entry['regions']==1 else entry['source'],
            second=readings['multilingual-v6-small'] if entry['regions']==1 else entry['source']))
    manifest=out/'input.jsonl';target=out/'output.jsonl'
    atomic(manifest,''.join(json.dumps(r)+'\n' for r in rows))
    with manifest.open('rb') as src,target.open('wb') as dest:
        subprocess.run([str(binary),str(ROOT/'assets/models/opus-en-es/tokenizer.json')],stdin=src,stdout=dest,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    actual={r['id']:r for r in records(target)}
    # Original pixels were transcribed before this diagnostic; these answers
    # enter only the scoring step after the native process has exited.
    manual_path=ROOT/'benchmarks/full-comics/ocr8016-heldout-full-manual-transcriptions.json'
    truth={r[0]:r[1] for r in read(manual_path)}
    entries=[]
    for entry in app['entries']:
        row=actual[entry['id']];assert row['base']==entry['source']
        before=compare(truth[row['id']],row['base']);after=compare(truth[row['id']],row['selected'])
        entries.append(dict(id=row['id'],before=before,after=after,base=row['base'],selected=row['selected'],
            regions=entry['regions'],insertions=row['insertions'],replacements=row['replacements']))
    metrics={}
    for name in ['before','after']:
        counts=collections.Counter()
        for entry in entries:counts.update(entry[name]['edit_categories'])
        metrics[name]=dict(word_errors=sum(r[name]['word_errors'] for r in entries),
            crops_with_word_errors=sum(r[name]['word_errors']>0 for r in entries),edit_categories=dict(counts))
    value=dict(crops=124,metrics=metrics,
        eligible_single_block_crops=sum(r['regions']==1 for r in entries),
        changed_crops=sum(r['base']!=r['selected'] for r in entries),
        crops_fixed=sum(r['before']['word_errors']>0 and r['after']['word_errors']==0 for r in entries),
        crops_regressed=sum(r['before']['word_errors']==0 and r['after']['word_errors']>0 for r in entries),
        actual_windows_sources_used=True,experimental_reader_outputs_on_same_pixels=True,
        single_block_geometry_guard=True,application_modified=False,
        reference_or_transcription_supplied_to_native_policy=False,
        independent_validation=False,screen_attempt_failure_probability=None,
        all_chapter_words_visually_reviewed=False,production_source_summary_sha256=digest(QA/'windows8016-heldout-pixels/summary.json'),
        reader_sample_sha256=digest(QA/'ocr-reader-heldout8016/sample.json'),
        manual_sha256=digest(manual_path),binary_sha256=digest(binary),
        input_sha256=digest(manifest),output_sha256=digest(target),entries=entries)
    atomic(out/'summary.json',json.dumps(value,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in value.items() if k!='entries'}),flush=True)
    print(json.dumps([r for r in entries if r['base']!=r['selected']],ensure_ascii=True),flush=True)


if __name__=='__main__':main()
