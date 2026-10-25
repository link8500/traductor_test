"""Validate actual production recovery on every fixed view and broad candidate.

Only recognized English sources and geometry enter native model inference.
The expanded set contains every matching opening in the 124-chapter control.
"""
import json
import pathlib
import shutil
import subprocess

from audit_corpus_quality import ROOT, QA, atomic, digest, read, records
from quality_resources import wait_for_inference_memory


def main():
    folder=QA/'windows8028-opening-translation-replay';folder.mkdir(exist_ok=True)
    fixed_path=QA/'windows8027-question-translation-replay/output.jsonl';fixed=records(fixed_path)
    expanded_path=QA/'opening8028/evaluated.json';expanded=read(expanded_path)
    assert len(fixed)==229 and len(expanded)==68
    inputs=[dict(id=i+1,image=r['image'],bounds=r['bounds'],source=r['source']) for i,r in enumerate(fixed)]
    inputs.extend(dict(id=229+c['id'],image=c['image'],bounds=c['bounds'],source=c['source']) for c in expanded)
    manifest=folder/'input.jsonl';text=''.join(json.dumps(r)+'\n' for r in inputs)
    if manifest.exists():assert manifest.read_text(encoding='utf-8')==text
    else:atomic(manifest,text)
    binary=QA/'frozen-windows802801/traductor.exe';snapshot=QA/'windows-engine802801.json'
    assert digest(binary)==read(snapshot)['binary_sha256']
    proof=dict(build='802801',binary_sha256=digest(binary),snapshot_sha256=digest(snapshot),
               fixed_native_output_sha256=digest(fixed_path),expanded_actual_before_sha256=digest(expanded_path),
               input_sha256=digest(manifest),core_equivalence_sha256=digest(QA/'opening8028/core-equivalence.json'),
               source_only_input=True,manual_or_reference_answers_supplied=False,model_weights_changed=False,
               fresh_translation_model_inference=True,new_ocr_inference=False,fresh_screen_capture=False)
    pin=folder/'provenance.json'
    if pin.exists():assert read(pin)==proof
    else:atomic(pin,json.dumps(proof,indent=2))
    target=folder/'native-output.jsonl'
    if not pathlib.Path(str(target)+'.summary.json').exists():
        assert shutil.disk_usage(folder).free>=4*1024**3
        wait_for_inference_memory(minimum_free_bytes=5*1024**3//2)
        with (folder/'runtime.log').open('ab') as log:
            subprocess.run([str(binary),'--translation-replay',str(manifest),str(target)],check=True,
                           creationflags=subprocess.CREATE_NO_WINDOW,stdout=log,stderr=log,timeout=1800)
    actual=records(target);assert len(actual)==297 and all('error' not in r for r in actual)
    assert read(pathlib.Path(str(target)+'.summary.json'))['runtime_errors']==0
    assert [(r['id'],r['source'],r['image'],r['bounds']) for r in actual]==[(r['id'],r['source'],r['image'],r['bounds']) for r in inputs]
    fields=['translation','retained_original','sentence_recovered','question_recovered']
    for old,new in zip(fixed,actual[:229]):
        assert all(old.get(key,False)==new.get(key,False) for key in fields)
        assert not new['opening_recovered']
    policy=records(QA/'opening8028/speech-policy-output.jsonl');changes=[]
    for case,new,expected in zip(expanded,actual[229:],policy):
        assert new['translation']==expected['candidate_translation'], 'Unexpected model result requires review'
        assert new['opening_recovered']==expected['opening_recovered']
        if new['opening_recovered']:
            before=case['native']['source']['translation']
            assert new['translation'].endswith(' '+before)
            changes.append(dict(id=case['id'],before=before,after=new['translation']))
    atomic(folder/'expanded-changes.json',json.dumps(changes,ensure_ascii=False,indent=2))
    atomic(folder/'fixed-output.jsonl',''.join(json.dumps(dict(old,opening_recovered=False),ensure_ascii=False)+'\n' for old in fixed))
    value=dict(build='802801',fixed_viewports=124,fixed_regions=229,fixed_displayed_outputs_changed=0,
               expanded_candidates=68,expanded_changed_regions=len(changes),runtime_errors=0,
               actual_native_output_records=len(actual),all_outputs_match_conservative_prediction=True,
               every_existing_word_preserved_in_changed_outputs=True,expanded_selection_scans_all124_control_chapters=True,
               provenance_sha256=digest(pin),native_output_sha256=digest(target),
               fixed_output_sha256=digest(folder/'fixed-output.jsonl'),expanded_changes_sha256=digest(folder/'expanded-changes.json'),
               fresh_translation_model_inference=True,new_ocr_inference=False,fresh_screen_capture=False,
               all_chapter_words_visually_reviewed=False,screen_attempt_failure_probability=None,target_achieved=False)
    atomic(folder/'summary.json',json.dumps(value,indent=2));print(json.dumps(value),flush=True)


if __name__=='__main__':main()
