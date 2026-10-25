"""Approve only exact native reproduction of previously reviewed full views."""
import hashlib
import json
from audit_corpus_quality import ROOT, QA, atomic, digest, read, records
from publish_normalized_llm8023 import count


def displayed(rows):
    return [{k:r.get(k) for k in ['source','translation','bounds','retained_original','sentence_recovered']} for r in rows]


def main():
    folder=QA/'windows8025-packaged-full-viewports';summary=read(folder/'summary.json')
    assert summary['viewports']==124 and summary['runtime_errors']==0
    assert summary['actual_consensus_enabled_for_every_region']
    assert summary['identical_to_reviewed_experiment_viewports']==list(range(1,125))
    reference_path=ROOT/'benchmarks/full-comics/windows8024-short-full-viewports-semantic-review.json'
    before_path=ROOT/'benchmarks/full-comics/windows8024-default-full-viewports-semantic-review.json'
    reference=read(reference_path);before=read(before_path)
    new=records(folder/'output.jsonl');expected=records(QA/'windows8024-short-full-viewports/output.jsonl')
    old=records(QA/'windows8024-short-default-full-viewports/output.jsonl')
    assert len(new)==len(expected)==len(old)==229
    proof=read(folder/'provenance.json');assert proof['no_explicit_reader_paths_or_activation_flag']
    reader_root=QA/'frozen-windows802501/ocr-readers';manifest=read(reader_root/'manifest.json')
    assert digest(reader_root/'manifest.json')==proof['packaged_reader_manifest_sha256']
    for name,sha in manifest['files'].items():assert digest(reader_root/name)==sha
    for part in range(4):
        inputs=records(folder/f'part-{part}.input.jsonl')
        assert all(not any(k in r for k in ['reader_consensus','consensus_first_directory','consensus_second_directory']) for r in inputs)
    entries=[];changed=0
    for r,b in zip(reference['entries'],before['entries']):
        ident=r['id'];assert ident==b['id']
        actual=displayed([row for row in new if row['image']==ident])
        assert actual==displayed([row for row in expected if row['image']==ident])
        changed+=actual!=displayed([row for row in old if row['image']==ident])
        entries.append(dict(id=ident,before=b['after'],after=r['after'],visible_dialogue_clipped=r['visible_dialogue_clipped'],
            historical_baseline=r['historical_baseline'],previous_full_location_meaning_judgment_reused=True,
            same_displayed_fields_sha256=hashlib.sha256(json.dumps(actual,sort_keys=True,ensure_ascii=False).encode()).hexdigest()))
    cohorts={};historical={}
    for name,subset in [('all124_fixed_reading_viewports',entries),('no_visible_dialogue_clipped',[r for r in entries if not r['visible_dialogue_clipped']])]:
        cohorts[name]=count(subset,'before');historical[name]=count(subset,'historical_baseline')
    value=dict(schema=1,build='802501',baseline_build='802402',viewports=124,native_regions=229,cohorts=cohorts,
        historical_baseline_comparison=dict(build='801901',cohorts=historical),entries=entries,
        changed_views_against_previous_normal=changed,all124_meaning_judgments_reused_only_for_identical_full_location_outputs=True,
        normal_worker_consensus_enabled=True,default_benchmark_consensus_enabled=True,no_explicit_reader_paths_or_activation_flag=True,
        source_review_sha256=digest(reference_path),baseline_review_sha256=digest(before_path),
        native_output_sha256=digest(folder/'output.jsonl'),native_provenance_sha256=digest(folder/'provenance.json'),
        native_summary_sha256=digest(folder/'summary.json'),reader_manifest_sha256=digest(reader_root/'manifest.json'),
        snapshot_sha256=digest(QA/'windows-engine802501.json'),runtime_checks_sha256=digest(QA/'windows8025-packaged-runtime-checks.json'),
        reused_dialogue_ocr_component=reference['dialogue_ocr'],paintings_reused_only_for_identical_displayed_fields=True,
        all_paintings_visually_reviewed=False,all_chapter_words_visually_reviewed=False,model_weights_trained=False,
        complete_live_app_use_including_capture_and_movement=False,screen_attempt_failure_probability=None,target_achieved=False,ready_for_release=False)
    atomic(ROOT/'benchmarks/full-comics/windows8025-packaged-full-viewports-semantic-review.json',json.dumps(value,ensure_ascii=False,indent=2))
    atomic(folder/'semantic-summary.json',json.dumps({k:v for k,v in value.items() if k!='entries'},indent=2))
    print(json.dumps(dict(cohorts=cohorts,historical=historical,actual_normal_consensus_enabled=True,target_achieved=False)),flush=True)


if __name__=='__main__':main()
