"""Apply integrated native tail MT only to eligible completed parent reports.

Reuses immutable pixel OCR. No reference, expected Spanish or comic inventory
is passed to native inference. Unchanged reports share their NTFS contents.
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
    source=QA/'postprocessed-en8029-refinement';destination=QA/'postprocessed-en8030-tails';destination.mkdir(exist_ok=True)
    jobs=QA/'tail8030/full-corpus-native-replays';jobs.mkdir(exist_ok=True)
    policy=ROOT/'build/local-model8030/Release/luma_translation_tail.exe'
    binary=QA/'frozen-windows803001/traductor.exe';snapshot=QA/'windows-engine803001.json'
    assert digest(binary)==read(snapshot)['binary_sha256']
    validation=QA/'windows8030-tail-translation-replay/summary.json';previous=None
    while True:
        if not validation.exists():
            if not args.watch:raise SystemExit('Complete actual integrated native validation first')
            if previous!='waiting':print('Waiting for integrated native validation; no model loaded.',flush=True);previous='waiting'
            time.sleep(15);continue
        checked=read(validation);assert checked['runtime_errors']==0 and checked['all_candidate_outputs_match_pure_policy']
        assert not checked['fixed_changed_regions'] and not checked['previous_diagnostic_changed_regions']
        completed=[]
        for done in sorted(source.glob('*.done.json')):
            base=read(done)
            if not base['all_files_traversed'] or base['runtime_errors']:continue
            name=done.name.removesuffix('.done.json');native=source/(name+'.jsonl');target=destination/native.name;marker=destination/done.name
            proof=dict(parent_report_sha256=digest(native),parent_done_sha256=digest(done),policy_sha256=digest(policy),
                       execution_script_sha256=digest(pathlib.Path(__file__)),snapshot_sha256=digest(snapshot),validation_sha256=digest(validation))
            if marker.exists():
                cached=read(marker);assert cached['tail_derivation_proof']==proof and digest(target)==cached['derived_report_sha256']
                completed.append(cached);continue
            if shutil.disk_usage(destination).free<4*1024**3+native.stat().st_size:break
            rows=records(native)
            selection=''.join(json.dumps(dict(id=i+1,source=r['source'],translation=r['translation'],retained_original=r.get('retained_original',False)))+'\n' for i,r in enumerate(rows))
            selected=subprocess.run([str(policy),'--plan'],input=selection,text=True,encoding='utf-8',capture_output=True,
                                    check=True,creationflags=subprocess.CREATE_NO_WINDOW)
            plans=[json.loads(s) for s in selected.stdout.splitlines() if s.strip()];assert len(plans)==len(rows)
            inputs=[dict(id=i+1,image=r['image'],bounds=r['bounds'],source=r['source']) for i,(r,p) in enumerate(zip(rows,plans)) if p['eligible']]
            actual={};native_output=None
            if inputs:
                manifest=jobs/(name+'.input.jsonl');native_output=jobs/(name+'.output.jsonl');contents=''.join(json.dumps(r)+'\n' for r in inputs)
                if manifest.exists():assert manifest.read_text(encoding='utf-8')==contents
                else:atomic(manifest,contents)
                if not pathlib.Path(str(native_output)+'.summary.json').exists():
                    wait_for_inference_memory(minimum_free_bytes=5*1024**3//2)
                    with (jobs/(name+'.log')).open('ab') as log:
                        subprocess.run([str(binary),'--translation-replay',str(manifest),str(native_output)],check=True,
                                       creationflags=subprocess.CREATE_NO_WINDOW,stdout=log,stderr=log,timeout=1800)
                fresh=records(native_output);assert len(fresh)==len(inputs) and all('error' not in r for r in fresh)
                assert read(pathlib.Path(str(native_output)+'.summary.json'))['runtime_errors']==0
                assert [(r['id'],r['source'],r['image'],r['bounds']) for r in fresh]==[(r['id'],r['source'],r['image'],r['bounds']) for r in inputs]
                actual={r['id']:r for r in fresh}
            merged=[];changes=[]
            for i,old in enumerate(rows):
                fresh=actual.get(i+1);row=old
                if fresh and fresh['translation']!=old['translation']:
                    assert fresh['tail_recovered'] and fresh['translation'].startswith(old['translation'])
                    row=dict(old,translation=fresh['translation'],tail_recovered=True,tail_source=fresh['tail_source'],
                             tail_translation=fresh['tail_translation'],translation_before_tail=old['translation'])
                    changes.append(dict(row=i,image=old['image'],bounds=old['bounds'],source=old['source'],
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
            value=dict(base,execution_kind='cached_pixel_reads_with_native_mt_on_tail_candidates',display_build='803001',
                       display_engine=read(snapshot)['engine'],new_ocr_inference=False,fresh_capture_in_display_build=False,
                       fresh_translation_for_all_regions=False,new_decoder_inference=bool(inputs),
                       tail_candidate_regions_retranslated=len(inputs),tail_translation_regions_changed=len(changes),
                       tail_derivation_proof=proof,tail_native_output_sha256=digest(native_output) if native_output else None,
                       derived_report_sha256=digest(target),shared_immutable_core_report=shared,
                       word_review_complete=False,semantic_review_complete=False)
            atomic(destination/(name+'.changes.json'),json.dumps(changes,ensure_ascii=False,indent=2));atomic(marker,json.dumps(value,indent=2));completed.append(value)
        summary=dict(chapters_expected=124,chapters_completed=len(completed),regions=sum(r['regions'] for r in completed),
                     candidate_regions_retranslated=sum(r['tail_candidate_regions_retranslated'] for r in completed),
                     translation_regions_changed=sum(r['tail_translation_regions_changed'] for r in completed),
                     reports_shared_without_copy=sum(r['shared_immutable_core_report'] for r in completed),
                     native_core_build='802601',display_build='803001',new_ocr_inference=False,
                     execution_kind='cached_pixel_evidence_with_native_mt_on_tail_candidates',
                     fresh_screen_capture=False,fresh_translation_for_all_regions=False,all_words_visually_reviewed=False,
                     semantic_accuracy=None,screen_attempt_failure_probability=None,target_achieved=False)
        text=json.dumps(summary,indent=2);path=destination/'summary.json'
        if not path.exists() or path.read_text(encoding='utf-8')!=text:atomic(path,text)
        if text!=previous:print(json.dumps(summary),flush=True);previous=text
        if not args.watch or len(completed)==124:break
        time.sleep(15)


if __name__=='__main__':main()
