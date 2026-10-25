"""Approve only the reviewed MT change; preserve the frozen OCR provenance."""
import json
import subprocess
from audit_corpus_quality import ROOT, QA, atomic, digest, read, records
from publish_normalized_llm8023 import count


def displayed(rows):return [{k:r.get(k) for k in ['source','translation','bounds','retained_original','sentence_recovered']} for r in rows]


def main():
    folder=QA/'windows8027-question-translation-replay';summary=read(folder/'summary.json')
    assert summary['viewports']==124 and summary['regions']==229 and summary['runtime_errors']==0
    assert summary['all229_actual_model_outputs_match_pure_rule_prediction'] and summary['all_sources_and_bounds_unchanged']
    assert not summary['new_ocr_inference'] and summary['fresh_translation_model_inference']
    before_path=ROOT/'benchmarks/full-comics/windows8026-inflection-full-viewports-semantic-review.json';before=read(before_path)
    old=records(QA/'windows8026-inflection-full-viewports/output.jsonl');new=records(folder/'output.jsonl')
    decisions_path=ROOT/'benchmarks/full-comics/question8027-meaning-decisions.json';decisions=read(decisions_path)
    manual={r['id']:r for r in decisions['entries']};changed={r['image'] for r in read(folder/'changes.json')}
    assert set(manual)==changed
    entries=[]
    for original in before['entries']:
        ident=original['id'];a=[r for r in old if r['image']==ident];b=[r for r in new if r['image']==ident]
        row=dict(id=ident,before=original['after'],after=original['after'],historical_baseline=original['historical_baseline'],
                 visible_dialogue_clipped=original['visible_dialogue_clipped'])
        if ident in changed:row.update(after=manual[ident]['after'],note=manual[ident]['note'],new_complete_location_meaning_reviewed=True)
        else:
            assert displayed(a)==displayed(b)
            row['same_complete_location_output_judgment_reused']=True
        entries.append(row)
    cohorts={};historical={}
    for label,subset in [('all124_fixed_reading_viewports',entries),('no_visible_dialogue_clipped',[r for r in entries if not r['visible_dialogue_clipped']])]:
        cohorts[label]=count(subset,'before');historical[label]=count(subset,'historical_baseline')
    evaluation_path=QA/'translation-punctuation8027/summary.json';evaluation=read(evaluation_path)
    value=dict(schema=1,build='802701',baseline_build='802601',viewports=124,native_regions=229,entries=entries,cohorts=cohorts,
        historical_baseline_comparison=dict(build='801901',cohorts=historical),
        dialogue_ocr={k:dict(before=v['after'],after=v['after']) for k,v in before['dialogue_ocr'].items()},
        ocr_score_reused_only_because_all_sources_and_bounds_are_identical=True,
        changed_complete_location_meanings_reviewed=len(changed),identical_complete_location_judgments_reused=124-len(changed),
        validation_mode='actual_packaged_native_mt_on_frozen_native_ocr_sources',native_ocr_build='802601',
        fresh_translation_inference=True,new_ocr_inference=False,fresh_screen_capture=False,
        native_punctuation_guards=evaluation['guards'],historical_full_corpus_rows_checked=evaluation['cohorts']['complete124_historical']['rows'],
        historical_full_corpus_chapters_checked=124,additional_question_intents=decisions['additional_intent_review'],
        native_output_sha256=digest(folder/'native-output.jsonl'),combined_output_sha256=digest(folder/'output.jsonl'),
        native_provenance_sha256=digest(folder/'provenance.json'),native_summary_sha256=digest(folder/'summary.json'),
        previous_native_output_sha256=digest(QA/'windows8026-inflection-full-viewports/output.jsonl'),previous_review_sha256=digest(before_path),
        snapshot_sha256=digest(QA/'windows-engine802701.json'),runtime_checks_sha256=digest(QA/'windows8027-question-runtime-checks.json'),
        core_equivalence_sha256=digest(QA/'translation-punctuation8027/core-equivalence.json'),
        rule_evaluation_sha256=digest(evaluation_path),manual_decisions_sha256=digest(decisions_path),
        normal_live_worker_uses_same_final_rule=True,decoder_core_and_model_weights_unchanged=True,
        model_weights_trained=False,manual_or_reference_answers_supplied_to_app=False,
        all_chapter_words_visually_reviewed=False,all_paintings_visually_reviewed=False,
        complete_live_app_use_including_capture_and_movement=False,screen_attempt_failure_probability=None,target_achieved=False,ready_for_release=False)
    atomic(ROOT/'benchmarks/full-comics/windows8027-question-semantic-review.json',json.dumps(value,ensure_ascii=False,indent=2))
    atomic(folder/'semantic-summary.json',json.dumps({k:v for k,v in value.items() if k!='entries'},indent=2))
    paint=folder/'paint';paint.mkdir(exist_ok=True)
    manifest=[dict(path=str(QA/f'recovery-viewports801201/{ident:03d}.png'),rows=[r for r in new if r['image']==ident],output=str(paint/f'{ident:03d}.jpg')) for ident in sorted(changed)]
    manifest_path=paint/'input.jsonl';atomic(manifest_path,''.join(json.dumps(r)+'\n' for r in manifest))
    result_path=paint/'result.json';binary=QA/'frozen-windows802701/traductor.exe'
    subprocess.run([str(binary),'--review-export',str(manifest_path),str(result_path)],check=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=180)
    assert read(result_path)['success'] and read(result_path)['images']==len(changed)
    atomic(paint/'provenance.json',json.dumps(dict(output_sha256=digest(folder/'output.jsonl'),binary_sha256=digest(binary),
        manifest_sha256=digest(manifest_path),result_sha256=digest(result_path),all_new_paintings_visually_reviewed=False),indent=2))
    print(json.dumps(dict(cohorts=cohorts,historical=historical,validation_mode=value['validation_mode'],target_achieved=False)),flush=True)


if __name__=='__main__':main()
