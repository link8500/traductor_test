"""Cotejo integrado completo: retain exact outputs, inspect all ten new readings."""
import collections
import json
import subprocess
from audit_corpus_quality import ROOT, QA, atomic, digest, read, records


def counts(rows, before_key):
    b=collections.Counter(r[before_key] for r in rows);a=collections.Counter(r['after'] for r in rows)
    be=len(rows)-b['acceptable'];ae=len(rows)-a['acceptable']
    return dict(viewports=len(rows),before_categories=dict(b),after_categories=dict(a),
        before_not_approved=be,after_not_approved=ae,
        corrected=sum(r[before_key]!='acceptable' and r['after']=='acceptable' for r in rows),
        regressed=sum(r[before_key]=='acceptable' and r['after']!='acceptable' for r in rows),
        relative_unapproved_reduction_percent=100*(be-ae)/be if be else None)


def main():
    previous_path=ROOT/'benchmarks/full-comics/windows8020-full-viewports-semantic-review.json'
    previous=read(previous_path)
    folder=QA/'windows8021-full-viewports-full-agreement';summary=read(folder/'summary.json')
    old=records(QA/'windows8020-full-viewports-consensus/output.jsonl');new=records(folder/'output.jsonl')
    selected=records(QA/'ocr-full-consensus8021/full-viewports-output.jsonl')
    assert len(old)==len(new)==len(selected)==228 and summary['runtime_errors']==0
    changed=set()
    for a,b,c in zip(old,new,selected):
        assert (a['image'],a['bounds'],a['before_consensus'])==(b['image'],b['bounds'],b['before_consensus'])
        assert b['source']==c['selected']
        if (a['source'],a['translation'])!=(b['source'],b['translation']):changed.add(b['image'])
    manual_path=ROOT/'benchmarks/full-comics/viewport8021-meaning-decisions.json'
    manual={r[0]:r for r in read(manual_path)};assert set(manual)==changed and len(changed)==10
    entries=[]
    for row in previous['entries']:
        ident=row['id'];outputs=[r for r in new if r['image']==ident]
        result=dict(row,historical_baseline=row['before'],before=row['after'],
            baseline_outputs=row['consensus_outputs'],consensus_outputs=outputs)
        if ident in changed:
            _,judgment,note=manual[ident]
            result.update(after=judgment,note=note,new_meaning_reviewed_against_full_original=True)
        else:
            assert row['consensus_outputs']==outputs
            result.update(after=row['after'],same_full_location_output_judgment_reused=True)
        entries.append(result)
    cohorts={}
    for name,rows in [('all124_fixed_reading_viewports',entries),('no_visible_dialogue_clipped',[r for r in entries if not r['visible_dialogue_clipped']])]:
        cohorts[name]=counts(rows,'before')
    historical={name:counts(entries if name=='all124_fixed_reading_viewports' else [r for r in entries if not r['visible_dialogue_clipped']],'historical_baseline') for name in cohorts}
    value=dict(schema=1,before_build='802001',after_build='802101',viewports=124,native_regions=228,
        all_original_visible_dialogue_inventoried=True,all124_paired_meanings_reviewed=True,
        changed_viewports_reinspected=10,same_full_location_outputs_reused=114,
        previous_full_viewport_review_sha256=digest(previous_path),manual_sha256=digest(manual_path),
        inventory_sha256=previous['inventory_sha256'],cohorts=cohorts,
        historical_baseline_comparison=dict(build='801901',cohorts=historical),entries=entries,
        native_output_sha256=digest(folder/'output.jsonl'),native_provenance_sha256=digest(folder/'provenance.json'),
        native_summary_sha256=digest(folder/'summary.json'),snapshot_sha256=digest(QA/'windows-engine802101.json'),
        selector_evaluation_sha256=digest(QA/'ocr-full-consensus8021/summary.json'),
        exact_selector_prediction_matches_all228_actual_windows_sources=True,
        default_live_worker_enabled=False,installed_model_assets_modified=False,model_weights_trained=False,
        painting_all124_visually_reviewed=False,all_chapter_words_visually_reviewed=False,
        complete_app_use_including_capture_toolbar_and_movement=False,
        screen_attempt_failure_probability=None,target_achieved=False,ready_for_release=False)
    path=ROOT/'benchmarks/full-comics/windows8021-full-viewports-semantic-review.json'
    atomic(path,json.dumps(value,ensure_ascii=False,indent=2))
    paint=folder/'paint';paint.mkdir(exist_ok=True)
    manifest=[dict(path=str(QA/'recovery-viewports801201'/f'{ident:03d}.png'),rows=[r for r in new if r['image']==ident],output=str(paint/f'{ident:03d}.jpg')) for ident in sorted(changed)]
    manifest_path=paint/'input.jsonl';atomic(manifest_path,''.join(json.dumps(r)+'\n' for r in manifest))
    target=paint/'result.json';binary=QA/'frozen-windows802101/traductor.exe'
    assert digest(binary)==read(QA/'windows-engine802101.json')['binary_sha256']
    subprocess.run([str(binary),'--review-export',str(manifest_path),str(target)],check=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=300)
    assert read(target)['success'] and read(target)['images']==10
    atomic(paint/'provenance.json',json.dumps(dict(manifest_sha256=digest(manifest_path),native_result_sha256=digest(target),
        native_output_sha256=digest(folder/'output.jsonl'),binary_sha256=digest(binary),visually_reviewed=False),indent=2))
    print(json.dumps(dict(cohorts=cohorts,historical_baseline=historical,report_sha256=digest(path))),flush=True)


if __name__=='__main__':main()
