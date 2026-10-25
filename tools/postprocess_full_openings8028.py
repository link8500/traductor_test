"""Reuse immutable full OCR reports, retranslating only eligible speech openings.

Every native candidate receives source text only. Derived reports retain all
rows and core provenance; they are not a fresh full-corpus OCR/capture run.
"""
import argparse
import datetime
import json
import os
import pathlib
import shutil
import stat
import subprocess
import time

from audit_corpus_quality import ROOT, QA, atomic, digest, read, records
from quality_resources import wait_for_inference_memory


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--watch',action='store_true');args=parser.parse_args()
    source=QA/'postprocessed-en8027-questions';destination=QA/'postprocessed-en8028-openings';destination.mkdir(exist_ok=True)
    jobs=QA/'opening8028/full-corpus-native-replays';jobs.mkdir(exist_ok=True)
    policy=QA/'opening8028/policy.exe';compiled=ROOT/'build/local-model8028/Release/luma_translation_opening.exe'
    if policy.exists():assert digest(policy)==digest(compiled)
    else:shutil.copy2(compiled,policy);os.chmod(policy,stat.S_IREAD)
    application=QA/'frozen-windows802801/traductor.exe';snapshot=QA/'windows-engine802801.json'
    assert digest(application)==read(snapshot)['binary_sha256']
    validation=QA/'windows8028-opening-translation-replay/summary.json';validated=read(validation)
    assert validated['all_outputs_match_conservative_prediction'] and validated['runtime_errors']==0
    assert read(snapshot)['source_sha256']['native/translation_opening.h']==digest(ROOT/'native/translation_opening.h')
    previous=None
    while True:
        completed=[]
        for done in sorted(source.glob('*.done.json')):
            base=read(done)
            if not base['all_files_traversed'] or base['runtime_errors']:continue
            name=done.name.removesuffix('.done.json');native=source/(name+'.jsonl')
            marker=destination/done.name;target=destination/native.name
            proof=dict(parent_report_sha256=digest(native),parent_done_sha256=digest(done),
                       opening_policy_sha256=digest(policy),application_snapshot_sha256=digest(snapshot),
                       actual_replay_validation_sha256=digest(validation))
            if marker.exists():
                cached=read(marker);assert cached['opening_derivation_proof']==proof and digest(target)==cached['derived_report_sha256']
                completed.append(cached);continue
            if shutil.disk_usage(destination).free<4*1024**3+native.stat().st_size:break
            rows=records(native)
            plan_input=''.join(json.dumps(dict(id=i+1,source=r['source']))+'\n' for i,r in enumerate(rows))
            plan=subprocess.run([str(policy),'--plan'],input=plan_input,text=True,encoding='utf-8',capture_output=True,
                                check=True,creationflags=subprocess.CREATE_NO_WINDOW)
            planned=[json.loads(line) for line in plan.stdout.splitlines() if line.strip()]
            assert len(planned)==len(rows)
            selected=[dict(id=i+1,image=r['image'],bounds=r['bounds'],source=r['source']) for i,(r,p) in enumerate(zip(rows,planned)) if p['eligible']]
            actual={};native_output=None
            if selected:
                manifest=jobs/(name+'.input.jsonl');native_output=jobs/(name+'.output.jsonl')
                contents=''.join(json.dumps(r)+'\n' for r in selected)
                if manifest.exists():assert manifest.read_text(encoding='utf-8')==contents
                else:atomic(manifest,contents)
                if not pathlib.Path(str(native_output)+'.summary.json').exists():
                    wait_for_inference_memory(minimum_free_bytes=5*1024**3//2)
                    with (jobs/(name+'.log')).open('ab') as log:
                        subprocess.run([str(application),'--translation-replay',str(manifest),str(native_output)],check=True,
                                       creationflags=subprocess.CREATE_NO_WINDOW,stdout=log,stderr=log,timeout=900)
                result=records(native_output)
                assert len(result)==len(selected) and all('error' not in r for r in result)
                assert read(pathlib.Path(str(native_output)+'.summary.json'))['runtime_errors']==0
                assert [(r['id'],r['source'],r['image'],r['bounds']) for r in result]==[(r['id'],r['source'],r['image'],r['bounds']) for r in selected]
                actual={r['id']:r for r in result}
            changes=[];merged=[]
            for i,old in enumerate(rows):
                new=actual.get(i+1);row=old
                if new:
                    if new['opening_recovered']:
                        assert new['translation'].endswith(' '+old['translation']), 'Existing full-core output changed; needs separate review'
                        row=dict(old,translation=new['translation'],opening_recovered=True,
                                 opening_source=new['opening_source'],opening_translation=new['opening_translation'],
                                 native_translation_before_opening=old['translation'])
                        changes.append(dict(row=i,image=old['image'],bounds=old['bounds'],source=old['source'],
                                            before_translation=old['translation'],after_translation=new['translation'],meaning_reviewed=False))
                    else:assert new['translation']==old['translation'], 'Unexpected base translation change'
                merged.append(row)
            if changes:
                assert not target.exists(), 'Never overwrite an unverified derived output'
                atomic(target,''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in merged));shared=False
            else:
                if target.exists():assert digest(target)==proof['parent_report_sha256']
                else:os.link(native,target)
                os.chmod(target,stat.S_IREAD);shared=True
            assert digest(native)==proof['parent_report_sha256']
            marker_value=dict(base,execution_kind='frozen_native_core_plus_question_rule_and_native_opening_replay',
                              display_build='802801',display_engine=read(snapshot)['engine'],
                              fresh_capture_in_display_build=False,new_ocr_inference=False,
                              new_decoder_inference=bool(selected),fresh_translation_for_all_regions=False,
                              opening_candidate_regions_retranslated=len(selected),openings_recovered=len(changes),
                              opening_derivation_proof=proof,
                              opening_native_output_sha256=digest(native_output) if native_output else None,
                              derived_report_sha256=digest(target),shared_immutable_core_report=shared,
                              word_review_complete=False,semantic_review_complete=False)
            atomic(destination/(name+'.changes.json'),json.dumps(changes,ensure_ascii=False,indent=2))
            atomic(marker,json.dumps(marker_value,indent=2));completed.append(marker_value)
        summary=dict(chapters_expected=124,chapters_completed=len(completed),regions=sum(r['regions'] for r in completed),
                     candidate_regions_retranslated=sum(r['opening_candidate_regions_retranslated'] for r in completed),
                     openings_recovered=sum(r['openings_recovered'] for r in completed),
                     reports_shared_without_copy=sum(r['shared_immutable_core_report'] for r in completed),
                     native_core_build='802601',display_build='802801',
                     execution_kind='immutable_core_reports_with_native_translation_of_opening_candidates',
                     new_ocr_inference=False,fresh_screen_capture=False,fresh_translation_for_all_regions=False,
                     all_words_visually_reviewed=False,semantic_accuracy=None,screen_attempt_failure_probability=None,target_achieved=False)
        text=json.dumps(summary,indent=2);path=destination/'summary.json'
        if not path.exists() or path.read_text(encoding='utf-8')!=text:atomic(path,text)
        if text!=previous:print(json.dumps(summary),flush=True);previous=text
        if not args.watch or len(completed)==124:break
        time.sleep(15)


if __name__=='__main__':main()
