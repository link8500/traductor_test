"""Measure an isolated omission-recovery policy against both inspected cohorts."""
import collections
import json
import shutil
import subprocess

from audit_corpus_quality import ROOT, QA, atomic, digest, read, records
from evaluate_ocr_reader_comparison import compare


def main():
    out = QA/'ocr-coverage8017-development';out.mkdir(exist_ok=True)
    binary = ROOT/'build/ocr8016/Release/luma_ocr_coverage_candidate.exe'
    guards = json.loads(subprocess.check_output([str(binary),'--self-test'],text=True))
    cohorts = ['ocr-reader-comparison8016','ocr-reader-heldout8016']
    inference = {}
    for name in cohorts:
        folder=QA/name;sample=read(folder/'sample.json')
        inputs=[dict(id=c['id'],base=c['readings']['current'],first=c['readings']['english-v5'],second=c['readings']['multilingual-v6-small']) for c in sample['cases']]
        manifest=out/(name+'-input.jsonl');target=out/(name+'-output.jsonl')
        atomic(manifest,''.join(json.dumps(row)+'\n' for row in inputs))
        with manifest.open('rb') as src,target.open('wb') as dest:
            subprocess.run([str(binary),str(ROOT/'assets/models/opus-en-es/tokenizer.json')],stdin=src,stdout=dest,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
        actual=records(target);assert len(actual)==len(inputs)==124
        for expected,row in zip(inputs,actual):
            assert all(row[k]==v for k,v in expected.items())
        inference[name]=actual
    # Scoring answers are accessed only after every native policy inference.
    manuals={cohorts[0]:{r['id']:r['visible_english'] for r in read(ROOT/'benchmarks/full-comics/ocr8016-manual-transcriptions.json')['entries']},
             cohorts[1]:{r[0]:r[1] for r in read(ROOT/'benchmarks/full-comics/ocr8016-heldout-full-manual-transcriptions.json')}}
    evaluations={};changes=[]
    for name in cohorts:
        folder=QA/name;entries=[]
        previous_folder='consensus-conservative' if name==cohorts[0] else 'consensus'
        previous={r['id']:r for r in records(folder/previous_folder/'output.jsonl')}
        source={r['id']:r for r in read(folder/'sample.json')['cases']}
        for row in inference[name]:
            ident=row['id'];truth=manuals[name][ident]
            before=compare(truth,row['base']);after=compare(truth,row['selected']);prior=compare(truth,previous[ident]['selected'])
            entry=dict(id=ident,before=before,after=after,previous_consensus=prior,
                source=row['base'],selected=row['selected'],previous_selected=previous[ident]['selected'],
                insertions=row['insertions'],replacements=row['replacements'])
            entries.append(entry)
            if row['selected']!=previous[ident]['selected']:
                changes.append(dict(entry,cohort=name,expected=truth,preview=source[ident]['preview']))
        counts={}
        for label in ['before','previous_consensus','after']:
            types=collections.Counter()
            for row in entries:types.update(row[label]['edit_categories'])
            counts[label]=dict(word_errors=sum(r[label]['word_errors'] for r in entries),
                crops_with_word_errors=sum(r[label]['word_errors']>0 for r in entries),edit_categories=dict(types))
        evaluations[name]=dict(crops=124,counts=counts,
            crops_fixed_vs_previous_consensus=sum(r['previous_consensus']['word_errors']>0 and r['after']['word_errors']==0 for r in entries),
            crops_regressed_vs_previous_consensus=sum(r['previous_consensus']['word_errors']==0 and r['after']['word_errors']>0 for r in entries),
            total_insertions=sum(r['insertions'] for r in entries),entries=entries)
    for filename in ['ocr_coverage_candidate.h','ocr_consensus_candidate.h']:
        shutil.copy2(ROOT/'native'/filename,out/filename)
    shutil.copy2(binary,out/'native.exe')
    value=dict(schema=1,development_cohorts=evaluations,native_guards=guards['guards'],
        candidate_rule_created_after_inspecting_these_cohorts=True,independent_validation=False,
        application_modified=False,reference_or_transcription_supplied_to_native_policy=False,
        screen_attempt_failure_probability=None,all_chapter_words_visually_reviewed=False,
        binary_sha256=digest(binary),policy_sha256=digest(ROOT/'native/ocr_coverage_candidate.h'),
        base_policy_sha256=digest(ROOT/'native/ocr_consensus_candidate.h'),
        input_output_hashes={p.name:digest(p) for p in out.glob('*.jsonl')},changes=changes)
    atomic(out/'summary.json',json.dumps(value,ensure_ascii=False,indent=2))
    print(json.dumps(dict(guards=guards,cohorts={k:{kk:vv for kk,vv in v.items() if kk!='entries'} for k,v in evaluations.items()},changes=changes)),flush=True)


if __name__=='__main__':main()
