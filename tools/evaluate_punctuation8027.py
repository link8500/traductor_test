"""Check conservative question preservation over complete saved corpora."""
import json
import subprocess
from audit_corpus_quality import ROOT, QA, atomic, digest, read, records


def main():
    folder=QA/'translation-punctuation8027';folder.mkdir(exist_ok=True)
    binary=ROOT/'build/local-model8027/Release/luma_translation_punctuation.exe'
    guards=json.loads(subprocess.check_output([str(binary),'--self-test'],text=True,creationflags=subprocess.CREATE_NO_WINDOW))
    fixed=QA/'windows8026-inflection-full-viewports/output.jsonl'
    datasets={'fixed124_views':([fixed],124)}
    for name,dirname in [('complete124_historical','translated-en8014-fixed-ocr'),('current_completed_control','translated-en8017-geometry')]:
        paths=[]
        for n in range(1,125):
            path=QA/dirname/f'absolute-regression-{n:02d}-en.jsonl';done=path.with_name(path.stem+'.done.json')
            if done.exists() and read(done).get('all_files_traversed') and not read(done).get('runtime_errors'):paths.append(path)
        datasets[name]=(paths,len(paths))
    assert datasets['complete124_historical'][1]==124
    cohorts={};all_changes=[]
    for name,(paths,chapters) in datasets.items():
        old=[dict(row,report=str(path.relative_to(ROOT)),report_row=i) for path in paths for i,row in enumerate(records(path))]
        manifest=folder/f'{name}-input.jsonl';target=folder/f'{name}-output.jsonl'
        inputs=[dict(id=i,source=r.get('source',''),translation=r.get('translation',''),retained_original=r.get('retained_original',False)) for i,r in enumerate(old)]
        atomic(manifest,''.join(json.dumps(r)+'\n' for r in inputs))
        with manifest.open('rb') as src,target.open('wb') as dst:
            subprocess.run([str(binary)],stdin=src,stdout=dst,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
        output=records(target);assert len(output)==len(old)
        changes=[]
        for before,after in zip(old,output):
            if before.get('translation','')==after['translation']:continue
            changes.append(dict(report=before['report'],report_row=before['report_row'],image=before['image'],bounds=before['bounds'],
                source=before['source'],before_translation=before['translation'],after_translation=after['translation'],
                all_words_unchanged=True,meaning_reviewed=False))
        atomic(folder/f'{name}-changes.json',json.dumps(changes,ensure_ascii=False,indent=2))
        cohorts[name]=dict(chapters=chapters,rows=len(old),changed_rows=len(changes),
            input_sha256=digest(manifest),output_sha256=digest(target),changes_sha256=digest(folder/f'{name}-changes.json'),
            original_reports={str(path.relative_to(ROOT)):digest(path) for path in paths},all_words_unchanged=True,meanings_reviewed=False)
        all_changes.extend(changes)
    unique={}
    for row in all_changes:unique.setdefault((row['source'],row['before_translation'],row['after_translation']),row)
    atomic(folder/'unique-changes.json',json.dumps(list(unique.values()),ensure_ascii=False,indent=2))
    value=dict(schema=1,guards=guards,cohorts=cohorts,unique_changed_passages=len(unique),
        cohorts_overlap_and_are_not_added=True,new_ocr_model_inferences=0,new_translation_model_inferences=0,
        application_modified=False,manual_or_reference_answers_supplied_to_rule=False,
        binary_sha256=digest(binary),source_sha256=digest(ROOT/'native/translation_punctuation.h'),
        screen_attempt_failure_probability=None,target_achieved=False)
    atomic(folder/'summary.json',json.dumps(value,indent=2))
    print(json.dumps(dict(guards=guards,cohorts={k:{a:b for a,b in v.items() if a!='original_reports'} for k,v in cohorts.items()},
                         unique_changed_passages=len(unique),application_modified=False)),flush=True)


if __name__=='__main__':main()
