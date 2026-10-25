"""Preserve all fixed-view meanings, word inventory and new native paintings."""
import json
import subprocess
from audit_corpus_quality import ROOT, QA, atomic, digest, read, records
from publish_normalized_llm8023 import count
from score_full_viewport_ocr8023 import measure
from evaluate_ocr_apostrophes8019 import strict_compare


def displayed(rows):
    return [{k:r.get(k) for k in ['source','translation','bounds','retained_original','sentence_recovered']} for r in rows]


def main():
    previous_path=ROOT/'benchmarks/full-comics/windows8021-full-viewports-semantic-review.json'
    previous=read(previous_path);folder=QA/'windows8024-short-full-viewports';summary=read(folder/'summary.json')
    old=records(QA/'windows8021-full-viewports-full-agreement/output.jsonl');new=records(folder/'output.jsonl')
    assert summary['viewports']==124 and summary['runtime_errors']==0
    manual_path=ROOT/'benchmarks/full-comics/short8024-meaning-decisions.json'
    manual={r[0]:r for r in read(manual_path)}
    changes=read(folder/'changes.json');changed={r['id'] for r in changes};assert set(manual)==changed
    entries=[]
    for original in previous['entries']:
        ident=original['id'];before=[r for r in old if r['image']==ident];after=[r for r in new if r['image']==ident]
        item=dict(id=ident,before=original['after'],after=original['after'],
            historical_baseline=original['historical_baseline'],dialogue=original['dialogue'],
            visible_dialogue_clipped=original['visible_dialogue_clipped'],before_outputs=before,candidate_outputs=after)
        if ident in changed:
            _,judgment,note=manual[ident];assert judgment in ['acceptable','incorrect','incomplete','clipped','needs_review']
            item.update(after=judgment,note=note,new_meaning_reviewed_against_complete_original_inventory=True)
        else:
            assert displayed(before)==displayed(after)
            item.update(same_full_location_output_judgment_reused=True,note=original['note'])
        entries.append(item)
    cohorts={};historical={}
    for name,subset in [('all124_fixed_reading_viewports',entries),('no_visible_dialogue_clipped',[r for r in entries if not r['visible_dialogue_clipped']])]:
        cohorts[name]=count(subset,'before');historical[name]=count(subset,'historical_baseline')
    # Exclude only the exact previously inspected non-dialogue locations.
    # Every new region is included; expected words missed by all readers remain.
    roles_path=ROOT/'benchmarks/full-comics/viewport8023-ocr-row-roles.json';roles=read(roles_path)
    excluded={(old[index]['image'],tuple(old[index]['bounds'])) for index,_,source in roles['excluded_from_dialogue_score'] if old[index]['source']==source}
    assert len(excluded)==21
    inventory_path=ROOT/'benchmarks/full-comics/viewport8020-original-inventory.json'
    ocr=[]
    for original in read(inventory_path)['entries']:
        ident=original['id'];expected=' '.join(original['dialogue']);variants={}
        for label,rows in [('before',old),('after',new)]:
            actual=' '.join(r['source'] for r in rows if r['image']==ident and (ident,tuple(r['bounds'])) not in excluded)
            score=strict_compare(expected,actual)
            for edit in score['edits']:edit['kind']='inserted_word' if edit['expected'] is None else 'alignment_deleted_word' if edit['actual'] is None else 'substituted_word'
            variants[label]=dict(score,actual=actual)
        ocr.append(dict(id=ident,expected_visible_dialogue=expected,visible_dialogue_clipped=original['visible_dialogue_clipped'],variants=variants))
    ocr_cohorts={name:{label:measure(subset,label) for label in ['before','after']} for name,subset in [
        ('all124_fixed_reading_viewports',ocr),('no_visible_dialogue_clipped',[r for r in ocr if not r['visible_dialogue_clipped']])]}
    value=dict(schema=1,build='802401',viewports=124,native_regions=len(new),cohorts=cohorts,
        historical_baseline_comparison=dict(build='801901',cohorts=historical),dialogue_ocr=ocr_cohorts,
        entries=entries,ocr_entries=ocr,changed_viewports_reviewed=len(changed),identical_full_location_judgments_reused=124-len(changed),
        recovered_short_regions=summary['recovered_short_regions'],manual_sha256=digest(manual_path),
        previous_native_review_sha256=digest(previous_path),native_output_sha256=digest(folder/'output.jsonl'),
        provenance_sha256=digest(folder/'provenance.json'),native_summary_sha256=digest(folder/'summary.json'),
        inventory_sha256=digest(inventory_path),manual_row_roles_sha256=digest(roles_path),
        snapshot_sha256=digest(QA/'windows-engine802401.json'),all_original_visible_dialogue_inventoried=True,
        no_reference_or_inventory_inputs=True,model_weights_trained=False,default_live_worker_enabled=False,
        all_paintings_visually_reviewed=False,all_chapter_words_visually_reviewed=False,
        complete_live_app_use_including_capture_and_movement=False,screen_attempt_failure_probability=None,
        target_achieved=False,ready_for_release=False)
    target=ROOT/'benchmarks/full-comics/windows8024-short-full-viewports-semantic-review.json'
    atomic(target,json.dumps(value,ensure_ascii=False,indent=2))
    paint=folder/'paint';paint.mkdir(exist_ok=True)
    manifest=[dict(path=str(QA/f'recovery-viewports801201/{ident:03d}.png'),rows=[r for r in new if r['image']==ident],
        output=str(paint/f'{ident:03d}.jpg')) for ident in sorted(changed)]
    manifest_path=paint/'input.jsonl';atomic(manifest_path,''.join(json.dumps(r)+'\n' for r in manifest))
    result_path=paint/'result.json';binary=QA/'frozen-windows802401/traductor.exe'
    subprocess.run([str(binary),'--review-export',str(manifest_path),str(result_path)],check=True,
        creationflags=subprocess.CREATE_NO_WINDOW,timeout=180)
    assert read(result_path)['success'] and read(result_path)['images']==len(changed)
    atomic(paint/'provenance.json',json.dumps(dict(manifest_sha256=digest(manifest_path),
        result_sha256=digest(result_path),native_output_sha256=digest(folder/'output.jsonl'),
        binary_sha256=digest(binary),all_paintings_visually_reviewed=False),indent=2))
    print(json.dumps(dict(cohorts=cohorts,historical=historical,dialogue_ocr=ocr_cohorts)),flush=True)


if __name__=='__main__':main()
