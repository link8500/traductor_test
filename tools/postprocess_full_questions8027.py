"""Apply the validated native final rule to each completed immutable core report.

This is an explicitly derived result, not a new capture/OCR/decoder traversal.
"""
import argparse
import json
import os
import shutil
import stat
import subprocess
import time
from audit_corpus_quality import ROOT, QA, atomic, digest, read, records


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--watch',action='store_true');args=parser.parse_args()
    source=QA/'translated-en8026-inflection';destination=QA/'postprocessed-en8027-questions';destination.mkdir(exist_ok=True)
    application=read(QA/'windows-engine802701.json')
    evaluation=read(QA/'translation-punctuation8027/summary.json')
    binary=QA/'translation-punctuation8027/postprocessor.exe'
    if not binary.exists():
        shutil.copy2(ROOT/'build/local-model8027/Release/luma_translation_punctuation.exe',binary)
        os.chmod(binary,stat.S_IREAD)
    assert digest(binary)==evaluation['binary_sha256']
    assert application['source_sha256']['native/translation_punctuation.h']==evaluation['source_sha256']
    previous=None
    while True:
        validation=QA/'windows8027-question-translation-replay/summary.json'
        if not validation.exists():
            if not args.watch:raise SystemExit('Actual native MT validation must finish first.')
            if previous!='waiting':print('Waiting for actual packaged native MT validation.',flush=True);previous='waiting'
            time.sleep(15);continue
        assert read(validation)['all229_actual_model_outputs_match_pure_rule_prediction']
        core_engine=read(QA/'windows-engine802601.json')['engine'];completed=[]
        for number in range(1,125):
            chapter=f'absolute-regression-{number:02d}-en';native=source/(chapter+'.jsonl');done=source/(chapter+'.done.json')
            if not done.exists():continue
            base=read(done)
            if not base.get('all_files_traversed') or base.get('runtime_errors'):continue
            assert base['engine']==core_engine
            proof=dict(native_report_sha256=digest(native),native_done_sha256=digest(done),postprocessor_sha256=digest(binary),
                       display_snapshot_sha256=digest(QA/'windows-engine802701.json'),mt_validation_sha256=digest(validation))
            marker=destination/(chapter+'.done.json');target=destination/(chapter+'.jsonl')
            if marker.exists():
                cached=read(marker);assert cached['derivation_proof']==proof and digest(target)==cached['derived_report_sha256']
                completed.append(cached);continue
            assert native.resolve().is_relative_to(source.resolve()) and target.parent.resolve()==destination.resolve()
            if shutil.disk_usage(destination).free<4*1024**3+native.stat().st_size:break
            rows=records(native)
            inputs=[dict(id=i,source=r['source'],translation=r['translation'],retained_original=r.get('retained_original',False)) for i,r in enumerate(rows)]
            result=subprocess.run([str(binary)],input=''.join(json.dumps(r)+'\n' for r in inputs),
                text=True,encoding='utf-8',stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
            actual=[json.loads(line) for line in result.stdout.splitlines() if line.strip()];assert len(actual)==len(rows)
            changes=[];merged=[]
            for i,(original,after) in enumerate(zip(rows,actual)):
                assert after['id']==i and after['source']==original['source']
                if after['translation']!=original['translation']:
                    changes.append(dict(row=i,image=original['image'],bounds=original['bounds'],source=original['source'],
                        before_translation=original['translation'],after_translation=after['translation'],meaning_reviewed=False))
                    original=dict(original,translation=after['translation'],question_recovered=True,native_translation_before_question=original['translation'])
                merged.append(original)
            if changes:
                assert not target.exists(),'Never overwrite an unverified derived report'
                atomic(target,''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in merged));shared=False
            else:
                # A completed frozen-core report will not be rewritten by the
                # traversal. Share it read-only instead of copying its bytes.
                if target.exists():assert digest(target)==proof['native_report_sha256']
                else:os.link(native,target)
                os.chmod(target,stat.S_IREAD);shared=True
            assert digest(native)==proof['native_report_sha256']
            value=dict(base,execution_kind='frozen_native_core_plus_validated_final_question_rule',
                native_core_build='802601',display_build='802701',display_engine=application['engine'],
                fresh_capture_in_display_build=False,new_ocr_inference=False,new_decoder_inference=False,
                derivation_proof=proof,derived_report_sha256=digest(target),shared_immutable_core_report=shared,
                questions_recovered=len(changes),word_review_complete=False,semantic_review_complete=False)
            atomic(destination/(chapter+'.changes.json'),json.dumps(changes,ensure_ascii=False,indent=2))
            atomic(marker,json.dumps(value,indent=2));completed.append(value)
        summary=dict(chapters_expected=124,chapters_completed=len(completed),
            regions=sum(r['regions'] for r in completed),questions_recovered=sum(r['questions_recovered'] for r in completed),
            reports_shared_without_copy=sum(r['shared_immutable_core_report'] for r in completed),
            native_core_build='802601',display_build='802701',execution_kind='derived_final_rule_on_immutable_native_results',
            fresh_screen_capture=False,new_ocr_inference=False,new_decoder_inference=False,
            all_words_visually_reviewed=False,semantic_accuracy=None,screen_attempt_failure_probability=None,target_achieved=False)
        text=json.dumps(summary,indent=2);path=destination/'summary.json'
        if not path.exists() or path.read_text(encoding='utf-8')!=text:atomic(path,text)
        if text!=previous:print(json.dumps(summary),flush=True);previous=text
        if not args.watch or len(completed)==124:break
        time.sleep(15)


if __name__=='__main__':main()
