"""Validate contraction protection using frozen pixel-reader sets and Windows sources.

These are native policy evaluations over real cached OCR, not new OCR runs.
Strict scoring preserves internal apostrophes so ILL cannot equal I'LL.
"""
import json
import re
import shutil
import subprocess
from audit_corpus_quality import ROOT,QA,atomic,digest,read,records
from evaluate_ocr_reader_comparison import compare
from paragraph_recovery import alignment


def strict_compare(expected,actual):
    def words(s):return [x.casefold().replace('’',"'") for x in re.findall(r"[^\W_]+(?:['’][^\W_]+)*",s,re.UNICODE)]
    before,after=words(expected),words(actual);distance,trace=alignment(before,after)
    return dict(expected_words=len(before),word_errors=distance,edits=[dict(expected=before[i] if i is not None else None,
        actual=after[j] if j is not None else None) for i,j in trace if i is None or j is None or before[i]!=after[j]])


def main():
    out=QA/'ocr-apostrophes8019';out.mkdir(exist_ok=True);binary=ROOT/'build/local-model8019/Release/luma_ocr_coverage_candidate.exe'
    guards=json.loads(subprocess.check_output([str(binary),'--self-test'],text=True,creationflags=subprocess.CREATE_NO_WINDOW))
    tokenizer=ROOT/'assets/models/opus-en-es/tokenizer.json';sets={};changes=[]
    bridge='ocr-coverage8017-windows-bridge'
    for name in ['ocr-reader-comparison8016','ocr-reader-heldout8016','ocr-coverage8017-holdout',bridge]:
        folder=QA/name;sample_path=(QA/'ocr-reader-heldout8016/sample.json') if name==bridge else folder/'sample.json'
        sample=read(sample_path)
        manifest=out/(name+'-input.jsonl');target=out/(name+'-output.jsonl')
        inputs=records(folder/'input.jsonl') if name==bridge else [dict(id=c['id'],base=c['readings']['current'],first=c['readings']['english-v5'],second=c['readings']['multilingual-v6-small']) for c in sample['cases']]
        atomic(manifest,''.join(json.dumps(r)+'\n' for r in inputs))
        with manifest.open('rb') as src,target.open('wb') as dest:subprocess.run([str(binary),str(tokenizer)],stdin=src,stdout=dest,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
        old_path=folder/'output.jsonl' if name==bridge else folder/'coverage/output.jsonl' if name=='ocr-coverage8017-holdout' else QA/'ocr-coverage8017-development'/(name+'-output.jsonl')
        old={r['id']:r for r in records(old_path)};rows=records(target);assert len(rows)==len(inputs)==124
        for r,i in zip(rows,inputs):
            assert all(r[k]==v for k,v in i.items())
            if r['selected']!=old[r['id']]['selected']:changes.append(dict(cohort=name,id=r['id'],base=r['base'],before=old[r['id']]['selected'],after=r['selected'],preview=sample['cases'][r['id']-1]['preview']))
        sets[name]=dict(sample_sha256=digest(sample_path),previous_output_sha256=digest(old_path),input_sha256=digest(manifest),
            output_sha256=digest(target),policy_evaluations=124)
    # Full manual transcriptions are available only for the first two sets.
    manual_paths=[ROOT/'benchmarks/full-comics/ocr8016-manual-transcriptions.json',ROOT/'benchmarks/full-comics/ocr8016-heldout-full-manual-transcriptions.json']
    truths=[{r['id']:r['visible_english'] for r in read(manual_paths[0])['entries']},{r[0]:r[1] for r in read(manual_paths[1])}]
    evaluations={}
    for name,truth,path in zip(list(sets)[:2]+[bridge],truths+[truths[1]],manual_paths+[manual_paths[1]]):
        old_path=QA/bridge/'output.jsonl' if name==bridge else QA/'ocr-coverage8017-development'/(name+'-output.jsonl')
        rows=records(out/(name+'-output.jsonl'));old={r['id']:r for r in records(old_path)}
        entries=[dict(id=r['id'],expected=truth[r['id']],before=old[r['id']]['selected'],after=r['selected'],
            before_strict=strict_compare(truth[r['id']],old[r['id']]['selected']),after_strict=strict_compare(truth[r['id']],r['selected']),
            before_legacy=compare(truth[r['id']],old[r['id']]['selected']),after_legacy=compare(truth[r['id']],r['selected'])) for r in rows]
        evaluations[name]=dict(crops=124,manual_sha256=digest(path),strict_before_word_errors=sum(r['before_strict']['word_errors'] for r in entries),
            strict_after_word_errors=sum(r['after_strict']['word_errors'] for r in entries),
            legacy_before_word_errors=sum(r['before_legacy']['word_errors'] for r in entries),legacy_after_word_errors=sum(r['after_legacy']['word_errors'] for r in entries),entries=entries)
    for name in ['ocr_consensus_candidate.h','ocr_coverage_candidate.h']:shutil.copy2(ROOT/'native'/name,out/name)
    shutil.copy2(binary,out/'native.exe')
    value=dict(policy_evaluations=496,unique_pixel_locations=372,windows_bridge_overlaps_second_pixel_cohort=True,
        native_guards=guards,cohorts=sets,evaluations=evaluations,changes=changes,
        binary_sha256=digest(binary),policies={name:digest(out/name) for name in ['ocr_consensus_candidate.h','ocr_coverage_candidate.h']},
        vocabulary_sha256=digest(tokenizer),application_modified=False,new_ocr_model_executions=0,
        third_cohort_unchanged_meanings_reviewed=False,third_cohort_unreviewed_locations=108,
        all_chapter_words_visually_reviewed=False,screen_attempt_failure_probability=None,
        normalization='Strict words retain internal apostrophes; legacy punctuation-ignoring results reported separately')
    atomic(out/'summary.json',json.dumps(value,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in value.items() if k not in ['evaluations']},ensure_ascii=True),flush=True)


if __name__=='__main__':main()
