"""Reuse pixel-reader evidence and infer MT only for changed/eligible regions.

New OCR word selection is pure over the original independent pixel readings.
These derived reports never pretend to be fresh full-chapter OCR/captures.
"""
import argparse
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
    source=QA/'postprocessed-en8028-openings';destination=QA/'postprocessed-en8029-refinement';destination.mkdir(exist_ok=True)
    jobs=QA/'refinement8029/full-corpus-native-replays';jobs.mkdir(exist_ok=True)
    policies=[]
    for compiled_name,name in [('luma_ocr_morph_edit_candidate.exe','ocr-policy.exe'),('luma_translation_question_clause.exe','question-policy.exe')]:
        compiled=ROOT/'build/local-model8029/Release'/compiled_name;target=QA/'refinement8029'/name
        if target.exists():assert digest(target)==digest(compiled)
        else:shutil.copy2(compiled,target);os.chmod(target,stat.S_IREAD)
        policies.append(target)
    binary=QA/'frozen-windows802901/traductor.exe';snapshot=QA/'windows-engine802901.json'
    assert digest(binary)==read(snapshot)['binary_sha256']
    tokenizer=binary.parent/'data/flutter_assets/assets/models/opus-en-es/tokenizer.json'
    validation=QA/'windows8029-refinement-full-viewports/summary.json';previous=None
    while True:
        if not validation.exists():
            if not args.watch:raise SystemExit('Complete actual native validation first')
            if previous!='waiting':print('Waiting for fresh131-image native validation; no extra model loaded.',flush=True);previous='waiting'
            time.sleep(15);continue
        checked=read(validation);assert checked['runtime_errors']==0 and checked['all_fixed_sources_match_pure_policy_prediction']
        completed=[]
        for done in sorted(source.glob('*.done.json')):
            base=read(done)
            if not base['all_files_traversed'] or base['runtime_errors']:continue
            name=done.name.removesuffix('.done.json');native=source/(name+'.jsonl');target=destination/native.name;marker=destination/done.name
            proof=dict(parent_report_sha256=digest(native),parent_done_sha256=digest(done),
                       ocr_policy_sha256=digest(policies[0]),question_policy_sha256=digest(policies[1]),
                       vocabulary_sha256=digest(tokenizer),
                       selection_base='original_recorded_before_consensus',execution_script_sha256=digest(pathlib.Path(__file__)),
                       snapshot_sha256=digest(snapshot),actual_validation_sha256=digest(validation))
            if marker.exists():
                cached=read(marker);assert cached['refinement_derivation_proof']==proof and digest(target)==cached['derived_report_sha256']
                completed.append(cached);continue
            if shutil.disk_usage(destination).free<4*1024**3+native.stat().st_size:break
            rows=records(native)
            ocr_input=''.join(json.dumps(dict(id=i+1,base=r.get('before_consensus',r['source']),first=r.get('first_reader',''),second=r.get('second_reader','')))+'\n' for i,r in enumerate(rows))
            selected=subprocess.run([str(policies[0]),str(tokenizer)],input=ocr_input,text=True,
                                    encoding='utf-8',capture_output=True,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
            ocr=[json.loads(line) for line in selected.stdout.splitlines() if line.strip()]
            assert len(ocr)==len(rows)
            question_input=''.join(json.dumps(dict(id=i+1,source=r['selected']))+'\n' for i,r in enumerate(ocr))
            plan=subprocess.run([str(policies[1]),'--plan'],input=question_input,text=True,encoding='utf-8',capture_output=True,
                                check=True,creationflags=subprocess.CREATE_NO_WINDOW)
            plans=[json.loads(line) for line in plan.stdout.splitlines() if line.strip()];assert len(plans)==len(rows)
            inputs=[dict(id=i+1,image=r['image'],bounds=r['bounds'],source=o['selected']) for i,(r,o,p) in enumerate(zip(rows,ocr,plans)) if r['source']!=o['selected'] or p['eligible']]
            actual={};native_output=None
            if inputs:
                manifest=jobs/(name+'.input.jsonl');native_output=jobs/(name+'.output.jsonl');contents=''.join(json.dumps(r)+'\n' for r in inputs)
                if manifest.exists():assert manifest.read_text(encoding='utf-8')==contents
                else:atomic(manifest,contents)
                if not pathlib.Path(str(native_output)+'.summary.json').exists():
                    wait_for_inference_memory(minimum_free_bytes=5*1024**3//2)
                    with (jobs/(name+'.log')).open('ab') as log:
                        subprocess.run([str(binary),'--translation-replay',str(manifest),str(native_output)],check=True,
                                       creationflags=subprocess.CREATE_NO_WINDOW,stdout=log,stderr=log,timeout=900)
                result=records(native_output);assert len(result)==len(inputs) and all('error' not in r for r in result)
                assert read(pathlib.Path(str(native_output)+'.summary.json'))['runtime_errors']==0
                assert [(r['id'],r['source'],r['image'],r['bounds']) for r in result]==[(r['id'],r['source'],r['image'],r['bounds']) for r in inputs]
                actual={r['id']:r for r in result}
            changes=[];merged=[]
            for i,(old,selection) in enumerate(zip(rows,ocr)):
                fresh=actual.get(i+1);row=old
                assert selection['base']==old.get('before_consensus',old['source'])
                if fresh and (fresh['translation']!=old['translation'] or fresh['source']!=old['source']):
                    if fresh['source']==old['source']:
                        assert fresh['opening_recovered'] and fresh['translation'].endswith(' '+old['translation'])
                    row=dict(old,source=fresh['source'],translation=fresh['translation'],
                             retained_original=fresh['retained_original'],sentence_recovered=fresh['sentence_recovered'],
                             question_recovered=fresh['question_recovered'],opening_recovered=fresh['opening_recovered'],
                             source_before_refinement=old['source'],translation_before_refinement=old['translation'])
                    changes.append(dict(row=i,image=old['image'],bounds=old['bounds'],before_source=old['source'],after_source=row['source'],
                                        before_translation=old['translation'],after_translation=row['translation'],meaning_reviewed=False))
                merged.append(row)
            if changes:
                assert not target.exists(),'Never overwrite an unverified derived report'
                atomic(target,''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in merged));shared=False
            else:
                if target.exists():assert digest(target)==proof['parent_report_sha256']
                else:os.link(native,target)
                os.chmod(target,stat.S_IREAD);shared=True
            assert digest(native)==proof['parent_report_sha256']
            value=dict(base,execution_kind='cached_independent_pixel_reads_with_new_word_selection_and_native_candidate_mt',
                       display_build='802901',display_engine=read(snapshot)['engine'],new_ocr_inference=False,
                       fresh_capture_in_display_build=False,fresh_translation_for_all_regions=False,
                       new_decoder_inference=bool(inputs),refinement_candidate_regions_retranslated=len(inputs),
                       refinement_source_regions_changed=sum(r['before_source']!=r['after_source'] for r in changes),
                       refinement_translation_regions_changed=sum(r['before_translation']!=r['after_translation'] for r in changes),
                       refinement_derivation_proof=proof,refinement_native_output_sha256=digest(native_output) if native_output else None,
                       derived_report_sha256=digest(target),shared_immutable_core_report=shared,
                       word_review_complete=False,semantic_review_complete=False)
            atomic(destination/(name+'.changes.json'),json.dumps(changes,ensure_ascii=False,indent=2));atomic(marker,json.dumps(value,indent=2));completed.append(value)
        summary=dict(chapters_expected=124,chapters_completed=len(completed),regions=sum(r['regions'] for r in completed),
                     candidate_regions_retranslated=sum(r['refinement_candidate_regions_retranslated'] for r in completed),
                     source_regions_changed=sum(r['refinement_source_regions_changed'] for r in completed),
                     translation_regions_changed=sum(r['refinement_translation_regions_changed'] for r in completed),
                     reports_shared_without_copy=sum(r['shared_immutable_core_report'] for r in completed),
                     native_core_build='802601',display_build='802901',new_ocr_inference=False,
                     execution_kind='cached_pixel_evidence_with_native_mt_on_refinement_candidates',
                     fresh_screen_capture=False,fresh_translation_for_all_regions=False,all_words_visually_reviewed=False,
                     semantic_accuracy=None,screen_attempt_failure_probability=None,target_achieved=False)
        text=json.dumps(summary,indent=2);path=destination/'summary.json'
        if not path.exists() or path.read_text(encoding='utf-8')!=text:atomic(path,text)
        if text!=previous:print(json.dumps(summary),flush=True);previous=text
        if not args.watch or len(completed)==124:break
        time.sleep(15)


if __name__=='__main__':main()
