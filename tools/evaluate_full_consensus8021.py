"""Evaluate a new isolated consensus policy on all cached reader evidence.

No gold text is supplied to the native selector. Full-viewport OCR inventory
contains dialogue only, so raw full-frame OCR WER is deliberately not reported.
"""
import collections
import json
import shutil
import subprocess
from audit_corpus_quality import ROOT, QA, atomic, digest, read, records
from evaluate_ocr_apostrophes8019 import strict_compare


def main():
    folder = QA / 'ocr-full-consensus8021'
    folder.mkdir(exist_ok=True)
    binary = ROOT / 'build/local-model8021/Release/luma_ocr_full_consensus_candidate.exe'
    tokenizer = ROOT / 'assets/models/opus-en-es/tokenizer.json'
    guards = json.loads(subprocess.check_output([str(binary), '--self-test'], text=True, creationflags=subprocess.CREATE_NO_WINDOW))
    manual1 = ROOT / 'benchmarks/full-comics/ocr8016-manual-transcriptions.json'
    manual2 = ROOT / 'benchmarks/full-comics/ocr8016-heldout-full-manual-transcriptions.json'
    manual3 = ROOT / 'benchmarks/full-comics/ocr8019-third-full-review.json'
    truths = [
        {r['id']:r['visible_english'] for r in read(manual1)['entries']},
        {r[0]:r[1] for r in read(manual2)},
        {r['id']:r['expected_visible_english'] for r in read(manual3)['entries']}]
    names = ['ocr-reader-comparison8016','ocr-reader-heldout8016','ocr-coverage8017-holdout','ocr-coverage8017-windows-bridge']
    sets = {}
    for name, truth in zip(names, truths + [truths[1]]):
        previous = QA / 'ocr-apostrophes8019' / (name + '-output.jsonl')
        rows = records(previous)
        manifest = folder / (name + '-input.jsonl')
        target = folder / (name + '-output.jsonl')
        inputs = [dict(id=r['id'], base=r['base'], first=r['first'], second=r['second']) for r in rows]
        atomic(manifest, ''.join(json.dumps(r) + '\n' for r in inputs))
        with manifest.open('rb') as src, target.open('wb') as dest:
            subprocess.run([str(binary),str(tokenizer)],stdin=src,stdout=dest,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
        result = records(target)
        assert len(rows) == len(result) == 124
        entries = []
        for old,new in zip(rows,result):
            ident = old['id'];assert new['id'] == ident
            entries.append(dict(id=ident, expected=truth[ident], before=old['selected'], after=new['selected'],
                before_score=strict_compare(truth[ident],old['selected']), after_score=strict_compare(truth[ident],new['selected']),
                complete_agreement=new['complete_agreement'],partial_withheld=new['partial_withheld']))
        sets[name] = dict(crops=124, previous_output_sha256=digest(previous),input_sha256=digest(manifest),output_sha256=digest(target),
            before_word_errors=sum(r['before_score']['word_errors'] for r in entries),
            after_word_errors=sum(r['after_score']['word_errors'] for r in entries),
            changed_crops=sum(r['before'] != r['after'] for r in entries),
            corrected=sum(r['before_score']['word_errors']>0 and r['after_score']['word_errors']==0 for r in entries),
            regressed=sum(r['before_score']['word_errors']==0 and r['after_score']['word_errors']>0 for r in entries),entries=entries)
    previous = QA / 'windows8020-full-viewports-consensus/output.jsonl'
    rows = records(previous)
    manifest = folder / 'full-viewports-input.jsonl'
    target = folder / 'full-viewports-output.jsonl'
    inputs = [dict(id=i+1,image=r['image'],bounds=r['bounds'],base=r['before_consensus'],first=r['first_reader'],second=r['second_reader']) for i,r in enumerate(rows)]
    atomic(manifest, ''.join(json.dumps(r) + '\n' for r in inputs))
    with manifest.open('rb') as src, target.open('wb') as dest:
        subprocess.run([str(binary),str(tokenizer)],stdin=src,stdout=dest,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    selected = records(target)
    changed = [dict(new,before=old['source'],before_translation=old['translation']) for old,new in zip(rows,selected) if old['source']!=new['selected']]
    atomic(folder / 'full-viewports-changes.json',json.dumps(changed,ensure_ascii=False,indent=2))
    for name in ['ocr_full_consensus_candidate.h','ocr_full_consensus_candidate_cli.cpp','ocr_consensus_candidate.h','ocr_coverage_candidate.h','ocr_recovery.h']:
        shutil.copy2(ROOT / 'native' / name,folder / name)
    shutil.copy2(binary,folder / 'selector.exe')
    value = dict(schema=1,native_guards=guards,cohorts=sets,unique_crop_pixels=372,bridge_overlaps_second_cohort=True,
        selector_calls=724,new_ocr_model_inferences=0,new_translation_model_inferences=0,
        visible_english_inventory_used_only_after_native_selection=True,
        binary_sha256=digest(binary),vocabulary_sha256=digest(tokenizer),
        full_viewports=dict(viewports=124,regions=228,changed_regions=len(changed),changed_viewports=len({r['image'] for r in changed}),
            input_sha256=digest(manifest),output_sha256=digest(target),previous_output_sha256=digest(previous),
            changes_sha256=digest(folder / 'full-viewports-changes.json'),all_new_meanings_reviewed=False),
        application_enabled=False,model_weights_trained=False,screen_attempt_failure_probability=None,target_achieved=False)
    atomic(folder / 'summary.json',json.dumps(value,ensure_ascii=False,indent=2))
    print(json.dumps(dict(cohorts={k:{a:b for a,b in v.items() if a!='entries'} for k,v in sets.items()},full_viewports=value['full_viewports'],native_guards=guards)),flush=True)


if __name__ == '__main__':
    main()
