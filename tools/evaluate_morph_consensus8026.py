"""Evaluate only pixel-derived spelling evidence; references enter after selection."""
import json
import shutil
import subprocess
from audit_corpus_quality import ROOT, QA, atomic, digest, read, records
from evaluate_ocr_apostrophes8019 import strict_compare
from score_full_viewport_ocr8023 import measure


def main():
    folder=QA/'ocr-morph-consensus8026';folder.mkdir(exist_ok=True)
    binary=ROOT/'build/local-model8026/Release/luma_ocr_morph_consensus_candidate.exe'
    tokenizer=ROOT/'assets/models/opus-en-es/tokenizer.json'
    guards=json.loads(subprocess.check_output([str(binary),'--self-test'],text=True,creationflags=subprocess.CREATE_NO_WINDOW))
    def infer(name,inputs):
        manifest=folder/f'{name}-input.jsonl';target=folder/f'{name}-output.jsonl'
        atomic(manifest,''.join(json.dumps(r)+'\n' for r in inputs))
        with manifest.open('rb') as src,target.open('wb') as dst:
            subprocess.run([str(binary),str(tokenizer)],stdin=src,stdout=dst,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
        rows=records(target);assert len(rows)==len(inputs)
        return rows,dict(input_sha256=digest(manifest),output_sha256=digest(target))
    manual1=ROOT/'benchmarks/full-comics/ocr8016-manual-transcriptions.json'
    manual2=ROOT/'benchmarks/full-comics/ocr8016-heldout-full-manual-transcriptions.json'
    manual3=ROOT/'benchmarks/full-comics/ocr8019-third-full-review.json'
    truths=[{r['id']:r['visible_english'] for r in read(manual1)['entries']},
            {r[0]:r[1] for r in read(manual2)},
            {r['id']:r['expected_visible_english'] for r in read(manual3)['entries']}]
    names=['ocr-reader-comparison8016','ocr-reader-heldout8016','ocr-coverage8017-holdout','ocr-coverage8017-windows-bridge']
    cohorts={}
    for name,truth in zip(names,truths+[truths[1]]):
        previous=QA/'ocr-full-consensus8021'/f'{name}-output.jsonl';old=records(previous)
        output,proof=infer(name,[{k:r[k] for k in ['id','base','first','second']} for r in old])
        entries=[]
        for a,b in zip(old,output):
            assert a['id']==b['id'];ident=a['id']
            entries.append(dict(id=ident,expected=truth[ident],before=a['selected'],after=b['selected'],
                                before_score=strict_compare(truth[ident],a['selected']),after_score=strict_compare(truth[ident],b['selected'])))
        cohorts[name]=dict(crops=124,previous_output_sha256=digest(previous),**proof,entries=entries,
            changed_crops=sum(r['before']!=r['after'] for r in entries),
            before_word_errors=sum(r['before_score']['word_errors'] for r in entries),
            after_word_errors=sum(r['after_score']['word_errors'] for r in entries),
            corrected=sum(r['before_score']['word_errors']>0 and r['after_score']['word_errors']==0 for r in entries),
            worsened=sum(r['after_score']['word_errors']>r['before_score']['word_errors'] for r in entries),
            regressed=sum(r['before_score']['word_errors']==0 and r['after_score']['word_errors']>0 for r in entries))
    previous=QA/'windows8025-packaged-full-viewports/output.jsonl';old=records(previous)
    assert len(old)==229 and len({r['image'] for r in old})==124
    inputs=[dict(id=i+1,image=r['image'],bounds=r['bounds'],base=r.get('before_consensus',r['source']),
                 first=r.get('first_reader',''),second=r.get('second_reader','')) for i,r in enumerate(old)]
    output,proof=infer('full-viewports',inputs)
    changes=[dict(id=b['id'],image=a['image'],bounds=a['bounds'],before_source=a['source'],after_source=b['selected'],
                  before_translation=a['translation']) for a,b in zip(old,output) if a['source']!=b['selected']]
    atomic(folder/'full-viewports-changes.json',json.dumps(changes,ensure_ascii=False,indent=2))
    roles_path=ROOT/'benchmarks/full-comics/viewport8023-ocr-row-roles.json'
    old_role_rows=records(QA/'windows8021-full-viewports-full-agreement/output.jsonl')
    excluded={(old_role_rows[i]['image'],tuple(old_role_rows[i]['bounds'])) for i,_,source in read(roles_path)['excluded_from_dialogue_score'] if old_role_rows[i]['source']==source}
    assert len(excluded)==21
    inventory_path=ROOT/'benchmarks/full-comics/viewport8020-original-inventory.json';scores=[]
    for entry in read(inventory_path)['entries']:
        ident=entry['id'];expected=' '.join(entry['dialogue']);variants={}
        for name in ['before','after']:
            actual=' '.join((a['source'] if name=='before' else b['selected']) for a,b in zip(old,output)
                            if a['image']==ident and (ident,tuple(a['bounds'])) not in excluded)
            score=strict_compare(expected,actual)
            for edit in score['edits']:edit['kind']='inserted_word' if edit['expected'] is None else 'alignment_deleted_word' if edit['actual'] is None else 'substituted_word'
            variants[name]=dict(score,actual=actual)
        scores.append(dict(id=ident,visible_dialogue_clipped=entry['visible_dialogue_clipped'],variants=variants))
    metrics={label:{side:measure(rows,side) for side in ['before','after']} for label,rows in [
        ('all124_fixed_reading_viewports',scores),('no_visible_dialogue_clipped',[r for r in scores if not r['visible_dialogue_clipped']])]}
    assert metrics['all124_fixed_reading_viewports']['before']['word_errors']==47
    assert metrics['all124_fixed_reading_viewports']['after']['expected_dialogue_words']==2265
    atomic(folder/'dialogue-word-scores.json',json.dumps(scores,ensure_ascii=False,indent=2))
    for name in ['ocr_morph_consensus_candidate.h','ocr_morph_consensus_candidate_cli.cpp','ocr_full_consensus_candidate.h','ocr_consensus_candidate.h','ocr_coverage_candidate.h','ocr_recovery.h']:
        shutil.copy2(ROOT/'native'/name,folder/name)
    shutil.copy2(binary,folder/'selector.exe')
    value=dict(schema=1,native_guards=guards,cohorts=cohorts,unique_crop_pixels=372,bridge_overlaps_second_cohort=True,
        selector_calls=725,new_ocr_model_inferences=0,new_translation_model_inferences=0,
        references_used_only_after_native_selection=True,binary_sha256=digest(binary),vocabulary_sha256=digest(tokenizer),
        full_viewports=dict(viewports=124,regions=229,changed_regions=len(changes),changed_views=len({r['image'] for r in changes}),
                            **proof,previous_output_sha256=digest(previous),changes_sha256=digest(folder/'full-viewports-changes.json'),
                            dialogue_ocr=metrics,inventory_sha256=digest(inventory_path),row_roles_sha256=digest(roles_path),
                            all_new_meanings_reviewed=False),
        application_enabled=False,model_weights_trained=False,screen_attempt_failure_probability=None,target_achieved=False)
    atomic(folder/'summary.json',json.dumps(value,ensure_ascii=False,indent=2))
    print(json.dumps(dict(cohorts={k:{a:b for a,b in v.items() if a!='entries'} for k,v in cohorts.items()},
                         full_viewports=value['full_viewports'],guards=guards)),flush=True)


if __name__=='__main__':main()
