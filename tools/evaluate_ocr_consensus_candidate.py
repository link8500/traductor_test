"""Run native consensus on actual reader outputs before reading transcription."""
import json
import subprocess
from audit_corpus_quality import ROOT,QA,read,records,digest,atomic
from evaluate_ocr_reader_comparison import compare


def main():
    folder=QA/'ocr-reader-comparison8016';out=folder/'consensus-conservative';out.mkdir(exist_ok=True)
    binary=ROOT/'build/ocr8016/Release/luma_ocr_consensus_candidate.exe'
    tests=subprocess.run([str(binary),'--self-test'],capture_output=True,text=True,check=True);guards=json.loads(tests.stdout)
    sample=read(folder/'sample.json');inputs=[]
    for case in sample['cases']:
        r=case['readings'];inputs.append(dict(id=case['id'],base=r['current'],first=r['english-v5'],second=r['multilingual-v6-small']))
    manifest=out/'input.jsonl';target=out/'output.jsonl';atomic(manifest,''.join(json.dumps(r)+'\n' for r in inputs))
    tokenizer=ROOT/'assets/models/opus-en-es/tokenizer.json'
    with manifest.open('rb') as src,target.open('wb') as dest:subprocess.run([str(binary),str(tokenizer)],stdin=src,stdout=dest,creationflags=subprocess.CREATE_NO_WINDOW,check=True)
    actual=records(target);assert len(actual)==124
    # The manual English labels are read only after native policy execution.
    manual_path=ROOT/'benchmarks/full-comics/ocr8016-manual-transcriptions.json';manual=read(manual_path)
    truth={r['id']:r['visible_english'] for r in manual['entries']};entries=[]
    for old,row in zip(inputs,actual):
        assert all(row[k]==old[k] for k in old)
        before=compare(truth[row['id']],row['base']);after=compare(truth[row['id']],row['selected'])
        entries.append(dict(id=row['id'],before=before,after=after,replacements=row['replacements'],source=row['base'],selected=row['selected']))
    words=sum(r['after']['expected_words'] for r in entries);bad_before=sum(r['before']['word_errors']>0 for r in entries);bad_after=sum(r['after']['word_errors']>0 for r in entries)
    result=dict(schema=1,crops=124,words=words,native_guards=guards['guards'],before_word_errors=sum(r['before']['word_errors'] for r in entries),
        after_word_errors=sum(r['after']['word_errors'] for r in entries),before_crops_with_error=bad_before,after_crops_with_error=bad_after,
        crops_fixed=sum(r['before']['word_errors']>0 and r['after']['word_errors']==0 for r in entries),
        crops_regressed=sum(r['before']['word_errors']==0 and r['after']['word_errors']>0 for r in entries),
        changed_crops=sum(r['replacements']>0 for r in entries),replaced_words=sum(r['replacements'] for r in entries),
        word_omissions_after=sum(r['after']['edit_categories'].get('omitted_word',0) for r in entries),
        transcriptions_supplied_to_native_policy=False,screen_attempt_failure_probability=None,all_chapter_words_visually_reviewed=False,
        application_modified=False,candidate_only=True,not_independent_holdout=True,manual_sha256=digest(manual_path),input_sha256=digest(manifest),output_sha256=digest(target),
        binary_sha256=digest(binary),policy_sha256=digest(ROOT/'native/ocr_consensus_candidate.h'),vocabulary_sha256=digest(tokenizer),entries=entries)
    atomic(ROOT/'benchmarks/full-comics/ocr8016-consensus-conservative-candidate.json',json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='entries'}),flush=True)


if __name__=='__main__':main()
