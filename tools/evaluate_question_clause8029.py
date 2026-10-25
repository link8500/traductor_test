"""Check every short initial question in the completed124-chapter control.

Input is source text only. Reference Spanish and judgments are never supplied
to the native model. Completed .done files exclude transient work duplicates.
"""
import json
import pathlib
import re
import shutil
import subprocess

from audit_corpus_quality import ROOT, QA, atomic, digest, read, records
from quality_resources import wait_for_inference_memory


def main():
    folder=QA/'question-clause8029';folder.mkdir(exist_ok=True)
    sample=folder/'sample.json'
    if not sample.exists():
        first_words={'what','why','who','whom','where','when','how','which','whose',
                     'are','is','was','were','do','does','did','can','could','will','would',
                     'shall','should','may','might','have','has','had'}
        paths=sorted((QA/'translated-en8017-geometry').glob('*.done.json'));assert len(paths)==124
        cases=[];reports={}
        for done in paths:
            state=read(done);assert state['all_files_traversed'] and not state['runtime_errors']
            path=done.with_name(done.name.replace('.done.json','.jsonl'));reports[path.name]=digest(path)
            for index,row in enumerate(records(path)):
                source=row.get('source','').strip();match=re.fullmatch(r"([^.!?]{2,65}\?)\s+(.{15,})",source)
                if not match:continue
                words=re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?",match[1])
                if not 2<=len(words)<=4 or words[0].casefold() not in first_words:continue
                opening=re.sub(r'\bi\b','I',match[1][:1].upper()+match[1][1:].lower())
                cases.append(dict(id=len(cases)+1,report=path.name,report_row=index,source=source,
                                  opening=match[1],model_opening=opening,rest=match[2],
                                  image=row['image'],bounds=row['bounds']))
        atomic(sample,json.dumps(dict(chapters_scanned=124,cases=cases,reports=reports,
               selection='Every initial question of2 to4 words headed by an English interrogative or auxiliary; no transient report files',
               all_chapter_words_visually_reviewed=False),ensure_ascii=False,indent=2))
    frozen=read(sample)
    for name,expected in frozen['reports'].items():assert digest(QA/'translated-en8017-geometry'/name)==expected
    inputs=[];ids={}
    for c in frozen['cases']:
        for key in ['source','model_opening','rest']:
            text=c[key]
            if text not in ids:
                ids[text]=len(inputs)+1;inputs.append(dict(id=ids[text],image=0,bounds=[0,0,1,1],source=text))
    manifest=folder/'input.jsonl';contents=''.join(json.dumps(r)+'\n' for r in inputs)
    if manifest.exists():assert manifest.read_text(encoding='utf-8')==contents
    else:atomic(manifest,contents)
    binary=QA/'frozen-windows802801/traductor.exe';snapshot=QA/'windows-engine802801.json'
    assert digest(binary)==read(snapshot)['binary_sha256']
    proof=dict(binary_sha256=digest(binary),snapshot_sha256=digest(snapshot),input_sha256=digest(manifest),
               sample_sha256=digest(sample),source_only_input=True,manual_or_reference_answers_supplied=False,
               new_ocr_inference=False,fresh_capture=False,production_modified=False,model_weights_changed=False)
    pin=folder/'provenance.json'
    if pin.exists():assert read(pin)==proof
    else:atomic(pin,json.dumps(proof,indent=2))
    output=folder/'native-output.jsonl'
    if not pathlib.Path(str(output)+'.summary.json').exists():
        assert shutil.disk_usage(folder).free>=4*1024**3
        wait_for_inference_memory(minimum_free_bytes=5*1024**3//2)
        with (folder/'runtime.log').open('ab') as log:
            subprocess.run([str(binary),'--translation-replay',str(manifest),str(output)],check=True,
                           creationflags=subprocess.CREATE_NO_WINDOW,stdout=log,stderr=log,timeout=1800)
    actual=records(output);assert len(actual)==len(inputs) and all('error' not in r for r in actual)
    assert read(pathlib.Path(str(output)+'.summary.json'))['runtime_errors']==0
    by_source={r['source']:r for r in actual}
    evaluated=[dict(c,native={key:by_source[c[key]] for key in ['source','model_opening','rest']},meaning_reviewed=False) for c in frozen['cases']]
    atomic(folder/'evaluated.json',json.dumps(evaluated,ensure_ascii=False,indent=2))
    value=dict(chapters_scanned=124,candidates=len(evaluated),actual_native_output_records=len(actual),
               runtime_errors=0,transient_reports_excluded=True,production_modified=False,
               provenance_sha256=digest(pin),output_sha256=digest(output),
               all_chapter_words_visually_reviewed=False,screen_attempt_failure_probability=None,target_achieved=False)
    atomic(folder/'summary.json',json.dumps(value,indent=2));print(json.dumps(value),flush=True)


if __name__=='__main__':main()
