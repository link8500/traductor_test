"""Test one-letter insertion/deletion recovery on saved independent OCR reads.

The native policy receives no transcripts or expected words. Existing reviewed
cohorts are scored only after every native policy output is frozen.
"""
import json
import subprocess

from audit_corpus_quality import ROOT, QA, atomic, digest, read, records
from evaluate_ocr_apostrophes8019 import strict_compare as compare
from score_full_viewport_ocr8023 import measure


def main():
    folder=QA/'ocr-morph-edit8029';folder.mkdir(exist_ok=True)
    binary=ROOT/'build/local-model8029/Release/luma_ocr_morph_edit_candidate.exe'
    guards=json.loads(subprocess.check_output([str(binary),'--self-test'],text=True,creationflags=subprocess.CREATE_NO_WINDOW))
    previous=QA/'ocr-morph-consensus8026';summary=read(previous/'summary.json');datasets={}
    for name in summary['cohorts']:
        path=previous/(name+'-output.jsonl');rows=records(path)
        datasets[name]=dict(inputs=[dict(id=r['id'],base=r['selected'],first=r['first'],second=r['second']) for r in rows],
                            source_reports={str(path.relative_to(ROOT)):digest(path)},has_review=True)
    path=previous/'full-viewports-output.jsonl'
    datasets['fixed124_views']=dict(inputs=[dict(id=r['id'],image=r['image'],bounds=r['bounds'],base=r['selected'],first=r['first'],second=r['second']) for r in records(path)],
                                   source_reports={str(path.relative_to(ROOT)):digest(path)},has_review=False)
    inputs=[];sources={}
    for done in sorted((QA/'translated-en8026-inflection').glob('*.done.json')):
        state=read(done)
        if not state['all_files_traversed'] or state['runtime_errors']:continue
        path=done.with_name(done.name.replace('.done.json','.jsonl'));sources[str(path.relative_to(ROOT))]=digest(path)
        for index,r in enumerate(records(path)):
            if not r.get('reader_consensus_enabled'):continue
            inputs.append(dict(id=len(inputs)+1,report=path.name,report_row=index,image=r['image'],bounds=r['bounds'],
                               base=r['source'],first=r.get('first_reader',''),second=r.get('second_reader','')))
    datasets['completed_current_chapters']=dict(inputs=inputs,source_reports=sources,has_review=False)
    outputs={};counts={};changes=[]
    for name,data in datasets.items():
        manifest=folder/(name+'-input.jsonl');target=folder/(name+'-output.jsonl')
        atomic(manifest,''.join(json.dumps(r)+'\n' for r in data['inputs']))
        with manifest.open('rb') as src,target.open('wb') as dst:
            subprocess.run([str(binary),str(ROOT/'assets/models/opus-en-es/tokenizer.json')],stdin=src,stdout=dst,
                           check=True,creationflags=subprocess.CREATE_NO_WINDOW)
        actual=records(target);assert len(actual)==len(data['inputs'])
        outputs[name]=actual
        for before,after in zip(data['inputs'],actual):
            assert all(after[k]==v for k,v in before.items())
            if before['base']!=after['selected']:changes.append(dict(cohort=name,**after,meaning_reviewed=False))
        counts[name]=dict(rows=len(actual),chapters=len(data['source_reports']) if name=='completed_current_chapters' else None,
                          changed=sum(r['base']!=r['selected'] for r in actual),source_reports=data['source_reports'],
                          input_sha256=digest(manifest),output_sha256=digest(target))
    # Pixel transcriptions are evaluation answers; they were not native inputs.
    for name in summary['cohorts']:
        truth={r['id']:r['expected'] for r in summary['cohorts'][name]['entries']}
        before=[compare(truth[r['id']],r['base']) for r in outputs[name]]
        after=[compare(truth[r['id']],r['selected']) for r in outputs[name]]
        counts[name]['scores']=dict(before_word_errors=sum(r['word_errors'] for r in before),after_word_errors=sum(r['word_errors'] for r in after),
                                    expected_words=sum(r['expected_words'] for r in before),
                                    crops_improved=sum(b['word_errors']<a['word_errors'] for a,b in zip(before,after)),
                                    crops_worsened=sum(b['word_errors']>a['word_errors'] for a,b in zip(before,after)))
    current_fixed=records(QA/'windows8028-opening-translation-replay/fixed-output.jsonl')
    assert [r['source'] for r in current_fixed]==[r['base'] for r in outputs['fixed124_views']]
    role_rows=records(QA/'windows8021-full-viewports-full-agreement/output.jsonl')
    excluded={(role_rows[i]['image'],tuple(role_rows[i]['bounds'])) for i,_,source in read(ROOT/'benchmarks/full-comics/viewport8023-ocr-row-roles.json')['excluded_from_dialogue_score'] if role_rows[i]['source']==source}
    assert len(excluded)==21
    word_scores=[]
    for entry in read(ROOT/'benchmarks/full-comics/viewport8020-original-inventory.json')['entries']:
        ident=entry['id'];expected=' '.join(entry['dialogue']);variants={}
        for side in ['before','after']:
            actual=' '.join(row['base' if side=='before' else 'selected'] for row in outputs['fixed124_views']
                            if row['image']==ident and (ident,tuple(row['bounds'])) not in excluded)
            score=compare(expected,actual)
            for edit in score['edits']:edit['kind']='inserted_word' if edit['expected'] is None else 'alignment_deleted_word' if edit['actual'] is None else 'substituted_word'
            variants[side]=dict(score,actual=actual)
        word_scores.append(dict(id=ident,visible_dialogue_clipped=entry['visible_dialogue_clipped'],variants=variants))
    atomic(folder/'dialogue-word-scores.json',json.dumps(word_scores,ensure_ascii=False,indent=2))
    dialogue={label:{side:measure(rows,side) for side in ['before','after']} for label,rows in [
        ('all124_fixed_reading_viewports',word_scores),('no_visible_dialogue_clipped',[r for r in word_scores if not r['visible_dialogue_clipped']])]}
    assert dialogue['all124_fixed_reading_viewports']['before']['word_errors']==45
    assert dialogue['all124_fixed_reading_viewports']['after']['expected_dialogue_words']==2265
    atomic(folder/'changes.json',json.dumps(changes,ensure_ascii=False,indent=2))
    value=dict(guards=guards,cohorts=counts,dialogue_ocr=dialogue,unique_reviewed_crop_pixels=372,bridge_overlaps_second_cohort=True,
               binary_sha256=digest(binary),policy_sha256=digest(ROOT/'native/ocr_morph_edit_candidate.h'),
               new_ocr_model_inferences=0,new_translation_model_inferences=0,application_modified=False,
               references_supplied_to_native_policy=False,all_chapter_words_visually_reviewed=False,
               screen_attempt_failure_probability=None,target_achieved=False)
    atomic(folder/'summary.json',json.dumps(value,indent=2))
    print(json.dumps(dict(guards=guards,cohorts={k:{a:b for a,b in v.items() if a!='source_reports'} for k,v in counts.items()},changes=changes)),flush=True)


if __name__=='__main__':main()
