"""Freeze every proposed OCR change and short-question recovery for pixel review."""
import json
import pathlib
import shutil
import subprocess

from audit_corpus_quality import ROOT, QA, atomic, digest, read, records
from quality_resources import wait_for_inference_memory


def main():
    folder=QA/'refinement8029';folder.mkdir(exist_ok=True)
    edits=read(QA/'ocr-morph-edit8029/changes.json')
    selected=[r for r in edits if r['cohort']=='completed_current_chapters']
    original=[];inputs=[];parents={}
    for i,r in enumerate(selected):
        path=QA/'postprocessed-en8028-openings'/r['report'];old=records(path)[r['report_row']]
        assert (old['source'],old['bounds'],old['image'])==(r['base'],r['bounds'],r['image'])
        parents[str(path.relative_to(ROOT))]=digest(path);original.append(old)
        inputs.append(dict(id=i+1,image=r['image'],bounds=r['bounds'],source=r['selected']))
    manifest=folder/'translation-input.jsonl';text=''.join(json.dumps(r)+'\n' for r in inputs)
    if manifest.exists():assert manifest.read_text(encoding='utf-8')==text
    else:atomic(manifest,text)
    target=folder/'translation-output.jsonl';binary=QA/'frozen-windows802801/traductor.exe'
    proof=dict(binary_sha256=digest(binary),input_sha256=digest(manifest),parent_reports=parents,
               ocr_selector_summary_sha256=digest(QA/'ocr-morph-edit8029/summary.json'),
               source_only_input=True,reference_or_manual_answers_supplied=False,new_ocr_model_inference=False,
               production_modified=False)
    pin=folder/'translation-provenance.json'
    if pin.exists():assert read(pin)==proof
    else:atomic(pin,json.dumps(proof,indent=2))
    if not pathlib.Path(str(target)+'.summary.json').exists():
        assert shutil.disk_usage(folder).free>=4*1024**3
        wait_for_inference_memory(minimum_free_bytes=5*1024**3//2)
        with (folder/'translation-runtime.log').open('ab') as log:
            subprocess.run([str(binary),'--translation-replay',str(manifest),str(target)],check=True,
                           creationflags=subprocess.CREATE_NO_WINDOW,stdout=log,stderr=log,timeout=900)
    actual=records(target);assert len(actual)==len(inputs) and all('error' not in r for r in actual)
    cases=[]
    for r,old,new in zip(selected,original,actual):
        assert new['source']==r['selected']
        cases.append(dict(id=len(cases)+1,kind='one_letter_ocr',report=r['report'],report_row=r['report_row'],image=r['image'],bounds=r['bounds'],
                          source=r['base'],selected_source=r['selected'],
                          policy=dict(translation=old['translation'],candidate_translation=new['translation']),
                          meaning_reviewed=False))
    question={r['id']:r for r in read(QA/'question-clause8029/evaluated.json')}
    for r in records(QA/'question-clause8029/policy-output.jsonl'):
        if not r['opening_recovered']:continue
        c=question[r['id']]
        cases.append(dict(id=len(cases)+1,kind='short_question',report=c['report'],report_row=c['report_row'],image=c['image'],bounds=c['bounds'],source=c['source'],
                          policy=dict(translation=r['translation'],candidate_translation=r['candidate_translation']),meaning_reviewed=False))
    atomic(folder/'changes.json',json.dumps(cases,ensure_ascii=False,indent=2))
    summary=dict(ocr_change_positions=len(selected),short_question_positions=len(cases)-len(selected),
                 native_translation_records=len(actual),new_ocr_model_inferences=0,model_weights_changed=False,
                 fixed_viewport_ocr_change_also_occurs_in_full_corpus=True,cohorts_overlap_do_not_add=True,
                 all_new_meanings_reviewed=False,screen_attempt_failure_probability=None,target_achieved=False)
    atomic(folder/'summary.json',json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
