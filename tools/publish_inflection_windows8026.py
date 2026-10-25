"""Bind actual Windows outputs to complete-location meanings and preserved words."""
import json
import subprocess
from audit_corpus_quality import ROOT, QA, atomic, digest, read, records
from publish_normalized_llm8023 import count


def displayed(rows):
    return [{k:r.get(k) for k in ['source','translation','bounds','retained_original','sentence_recovered']} for r in rows]


def main():
    folder=QA/'windows8026-inflection-full-viewports';summary=read(folder/'summary.json')
    assert summary['viewports']==124 and summary['regions']==229 and summary['runtime_errors']==0
    assert summary['identical_to_reviewed_experiment_viewports']==list(range(1,125))
    assert summary['actual_consensus_enabled_for_every_region']
    proof=read(folder/'provenance.json')
    assert proof['no_explicit_reader_paths_or_activation_flag'] and proof['no_reference_or_inventory_inputs']
    for part in range(4):
        for item in records(folder/f'part-{part}.input.jsonl'):
            assert not any(k in item for k in ['source','translation','reference','inventory','reader_consensus','consensus_first_directory','consensus_second_directory'])
            assert item['recover_paragraphs'] and item['complete_lines'] and item['augment_detection'] and not item['ocr_only']
    previous_path=ROOT/'benchmarks/full-comics/windows8025-packaged-full-viewports-semantic-review.json'
    previous=read(previous_path);old=records(QA/'windows8025-packaged-full-viewports/output.jsonl')
    new=records(folder/'output.jsonl');changes=read(folder/'changes.json');changed={r['id'] for r in changes}
    manual_path=ROOT/'benchmarks/full-comics/morph8026-meaning-decisions.json'
    manual={r[0]:r for r in read(manual_path)};assert set(manual)==changed
    selector_path=QA/'ocr-morph-consensus8026/summary.json';selector=read(selector_path)
    assert selector['native_guards']['success'] and all(not r['worsened'] for r in selector['cohorts'].values())
    assert digest(QA/'windows8025-packaged-full-viewports/output.jsonl')==previous['native_output_sha256']
    assert selector['full_viewports']['previous_output_sha256']==previous['native_output_sha256']
    assert [r['source'] for r in new]==[r['selected'] for r in records(QA/'ocr-morph-consensus8026/full-viewports-output.jsonl')]
    entries=[]
    for original in previous['entries']:
        ident=original['id'];a=[r for r in old if r['image']==ident];b=[r for r in new if r['image']==ident]
        row=dict(id=ident,before=original['after'],after=original['after'],historical_baseline=original['historical_baseline'],
                 visible_dialogue_clipped=original['visible_dialogue_clipped'])
        if ident in changed:
            _,judgment,note=manual[ident]
            assert judgment in ['acceptable','incorrect','incomplete','clipped','needs_review']
            row.update(after=judgment,note=note,new_full_location_meaning_reviewed=True)
        else:
            assert displayed(a)==displayed(b)
            row['same_full_location_output_judgment_reused']=True
        entries.append(row)
    cohorts={};historical={}
    for name,subset in [('all124_fixed_reading_viewports',entries),('no_visible_dialogue_clipped',[r for r in entries if not r['visible_dialogue_clipped']])]:
        cohorts[name]=count(subset,'before');historical[name]=count(subset,'historical_baseline')
    value=dict(schema=1,build='802601',baseline_build='802501',viewports=124,native_regions=229,entries=entries,
        cohorts=cohorts,historical_baseline_comparison=dict(build='801901',cohorts=historical),
        dialogue_ocr=selector['full_viewports']['dialogue_ocr'],native_guards=selector['native_guards'],
        control_crops_unique=372,control_bridge_overlaps_second_cohort=True,
        control_crop_cohorts={k:{a:b for a,b in v.items() if a!='entries'} for k,v in selector['cohorts'].items()},
        changed_full_location_meanings_reviewed=len(changed),identical_full_location_judgments_reused=124-len(changed),
        partial_content_improvements_not_counted_as_complete_corrections=2,
        all124_displayed_locations_match_the_reviewed_selection_and_translation_plan=True,
        normal_worker_inflection_support_enabled=True,no_explicit_reader_paths_or_activation_flag=True,
        native_output_sha256=digest(folder/'output.jsonl'),native_summary_sha256=digest(folder/'summary.json'),
        native_provenance_sha256=digest(folder/'provenance.json'),snapshot_sha256=digest(QA/'windows-engine802601.json'),
        runtime_checks_sha256=digest(QA/'windows8026-inflection-runtime-checks.json'),previous_review_sha256=digest(previous_path),
        previous_native_output_sha256=digest(QA/'windows8025-packaged-full-viewports/output.jsonl'),
        selector_summary_sha256=digest(selector_path),manual_sha256=digest(manual_path),
        isolated_translation_output_sha256=digest(QA/'ocr-morph-consensus8026/translation-output.jsonl'),
        original_visible_dialogue_inventory_sha256=digest(ROOT/'benchmarks/full-comics/viewport8020-original-inventory.json'),
        reference_or_manual_answers_supplied_to_app=False,new_model_weights=False,model_weights_trained=False,
        all_paintings_visually_reviewed=False,all_chapter_words_visually_reviewed=False,
        complete_live_app_use_including_capture_and_movement=False,screen_attempt_failure_probability=None,
        target_achieved=False,ready_for_release=False)
    atomic(ROOT/'benchmarks/full-comics/windows8026-inflection-full-viewports-semantic-review.json',json.dumps(value,ensure_ascii=False,indent=2))
    atomic(folder/'semantic-summary.json',json.dumps({k:v for k,v in value.items() if k!='entries'},indent=2))
    paint=folder/'paint';paint.mkdir(exist_ok=True)
    manifest=[dict(path=str(QA/f'recovery-viewports801201/{ident:03d}.png'),rows=[r for r in new if r['image']==ident],output=str(paint/f'{ident:03d}.jpg')) for ident in sorted(changed)]
    manifest_path=paint/'input.jsonl';atomic(manifest_path,''.join(json.dumps(r)+'\n' for r in manifest))
    result_path=paint/'result.json';binary=QA/'frozen-windows802601/traductor.exe'
    subprocess.run([str(binary),'--review-export',str(manifest_path),str(result_path)],check=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=180)
    assert read(result_path)['success'] and read(result_path)['images']==len(changed)
    atomic(paint/'provenance.json',json.dumps(dict(native_output_sha256=digest(folder/'output.jsonl'),binary_sha256=digest(binary),
        manifest_sha256=digest(manifest_path),result_sha256=digest(result_path),all_new_paintings_visually_reviewed=False),indent=2))
    print(json.dumps(dict(cohorts=cohorts,historical=historical,dialogue_ocr=value['dialogue_ocr'],target_achieved=False)),flush=True)


if __name__=='__main__':main()
