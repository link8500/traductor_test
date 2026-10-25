"""Retranslate all229 actual native OCR regions with the actual packaged app."""
import json
import pathlib
import subprocess
from audit_corpus_quality import ROOT, QA, atomic, digest, read, records
from quality_resources import wait_for_inference_memory


def verify_core():
    folder=QA/'translation-punctuation8027'
    before_path=folder/'before/local_translation.cpp';before=before_path.read_text(encoding='utf-8')
    after=(ROOT/'native/local_translation.cpp').read_text(encoding='utf-8')
    begin=after.index('TranslationResult LocalTranslationModel::TranslateDetailed(')
    end=after.index('\n}\n',begin)+3
    core=(after[:begin]+after[end:]).replace('#include "translation_punctuation.h"\n','')
    core=core.replace('LocalTranslationModel::TranslateCoreDetailed(','LocalTranslationModel::TranslateDetailed(')
    assert core==before,'The decoder/core changed beyond the isolated final wrapper'
    assert digest(before_path)==read(QA/'windows-engine802601.json')['source_sha256']['native/local_translation.cpp']
    value=dict(decoder_and_existing_coverage_body_unchanged=True,before_sha256=digest(before_path),
               new_cpp_sha256=digest(ROOT/'native/local_translation.cpp'),rule_sha256=digest(ROOT/'native/translation_punctuation.h'))
    atomic(folder/'core-equivalence.json',json.dumps(value,indent=2))
    return folder/'core-equivalence.json'


def main():
    core=verify_core();folder=QA/'windows8027-question-translation-replay';folder.mkdir(exist_ok=True)
    old_path=QA/'windows8026-inflection-full-viewports/output.jsonl';old=records(old_path)
    assert len(old)==229 and len({r['image'] for r in old})==124
    binary=QA/'frozen-windows802701/traductor.exe';snapshot=QA/'windows-engine802701.json'
    assert digest(binary)==read(snapshot)['binary_sha256']
    manifest=folder/'input.jsonl';target=folder/'native-output.jsonl'
    inputs=[dict(id=i+1,image=r['image'],bounds=r['bounds'],source=r['source']) for i,r in enumerate(old)]
    atomic(manifest,''.join(json.dumps(r)+'\n' for r in inputs))
    proof=dict(build='802701',binary_sha256=digest(binary),snapshot_sha256=digest(snapshot),input_sha256=digest(manifest),
        source_native_build='802601',source_native_output_sha256=digest(old_path),
        source_native_provenance_sha256=digest(QA/'windows8026-inflection-full-viewports/provenance.json'),
        core_equivalence_sha256=digest(core),fresh_model_translation_inference=True,new_ocr_inference=False,fresh_screen_capture=False,
        manual_or_reference_answers_supplied=False,expected_translation_supplied=False,
        assets_manifest_sha256=digest(binary.parent/'data/flutter_assets/assets/models/opus-en-es/manifest.json'))
    pin=folder/'provenance.json'
    if pin.exists():assert read(pin)==proof
    else:atomic(pin,json.dumps(proof,indent=2))
    if not (folder/'summary.json').exists():
        # Translation-only uses neither the OCR models nor full-image buffers.
        wait_for_inference_memory(minimum_free_bytes=5*1024**3//2)
        with (folder/'runtime.log').open('ab') as log:
            subprocess.run([str(binary),'--translation-replay',str(manifest),str(target)],check=True,
                creationflags=subprocess.CREATE_NO_WINDOW,stdout=log,stderr=log,timeout=900)
        native=records(target);assert len(native)==229 and all('error' not in r for r in native)
        assert read(pathlib.Path(str(target)+'.summary.json'))['runtime_errors']==0
        proposed=records(QA/'translation-punctuation8027/fixed124_views-output.jsonl')
        combined=[];changes=[]
        for before,fresh,expected in zip(old,native,proposed):
            assert fresh['source']==before['source']==expected['source']
            assert fresh['translation']==expected['translation'],'Unexpected new model inference; review before publishing'
            assert fresh['retained_original']==before['retained_original'] and fresh['sentence_recovered']==before['sentence_recovered']
            assert fresh['question_recovered']==expected['question_restored']
            row=dict(before,translation=fresh['translation'],question_recovered=fresh['question_recovered'])
            combined.append(row)
            if before['translation']!=fresh['translation']:changes.append(dict(image=before['image'],before=before,after=row))
        atomic(folder/'output.jsonl',''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in combined))
        atomic(folder/'changes.json',json.dumps(changes,ensure_ascii=False,indent=2))
        value=dict(viewports=124,regions=229,runtime_errors=0,changed_views=len({r['image'] for r in changes}),
            all229_actual_model_outputs_match_pure_rule_prediction=True,all_sources_and_bounds_unchanged=True,
            actual_packaged_native_app_used=True,fresh_translation_model_inference=True,new_ocr_inference=False,
            reused_ocr_build='802601',native_output_sha256=digest(target),output_sha256=digest(folder/'output.jsonl'),
            provenance_sha256=digest(pin),fresh_screen_capture=False,all_new_meanings_reviewed=False,
            screen_attempt_failure_probability=None,target_achieved=False)
        atomic(folder/'summary.json',json.dumps(value,indent=2))
    print(json.dumps(read(folder/'summary.json')),flush=True)


if __name__=='__main__':main()
