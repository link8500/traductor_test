"""Bind all specialist judgments to exact inputs and model output artifacts."""
import json
from audit_corpus_quality import ROOT, QA, atomic, digest, read, records
from publish_normalized_llm8023 import count


def main():
    previous_path=ROOT/'benchmarks/full-comics/windows8021-full-viewports-semantic-review.json'
    previous=read(previous_path);folder=QA/'hy8024-full-viewports';summary=read(folder/'summary.json')
    assert summary['sources_completed']==215 and summary['regions']==228 and not summary['errors']
    manual_path=ROOT/'benchmarks/full-comics/hy8024-meaning-decisions.json';manual=read(manual_path)
    assert [r[0] for r in manual]==list(range(1,125))
    rows=records(folder/'output.jsonl');old=records(QA/'windows8021-full-viewports-full-agreement/output.jsonl')
    assert [(r['image'],r['bounds'],r['source']) for r in old]==[(r['image'],r['bounds'],r['source']) for r in rows]
    prepared={r['source']:r for r in records(QA/'local-llm8023-normalized/native-prepared.jsonl')}
    assert all(r['prepared_model_input']==prepared[r['source']]['prepared'] for r in rows)
    proof=read(folder/'provenance.json');assert proof['outputs_not_used_to_train_other_models']
    assert not proof['human_or_reference_text_supplied'] and proof['local_only']
    entries=[]
    for original,(ident,judgment,note) in zip(previous['entries'],manual):
        assert original['id']==ident and judgment in ['acceptable','incorrect','incomplete','clipped','needs_review']
        viewrows=[r for r in rows if r['image']==ident]
        files=[folder/f"source-{prepared[r['source']]['id']:03d}.json" for r in viewrows]
        assert [read(p)['translation'] for p in files]==[r['translation'] for r in viewrows]
        entries.append(dict(id=ident,before=original['after'],after=judgment,note=note,
            visible_dialogue_clipped=original['visible_dialogue_clipped'],
            isolated_source_output_sha256=[digest(p) for p in files],
            meaning_reviewed_against_complete_original_inventory=True))
    cohorts={name:count(subset,'before') for name,subset in [
        ('all124_fixed_reading_viewports',entries),
        ('no_visible_dialogue_clipped',[r for r in entries if not r['visible_dialogue_clipped']])]}
    value=dict(schema=1,viewports=124,source_regions=228,all124_new_meanings_reviewed=True,
        all_original_visible_dialogue_inventoried=True,native_ocr_sources_and_bounds_all_identical=True,
        cohorts=cohorts,entries=entries,manual_sha256=digest(manual_path),
        previous_native_review_sha256=digest(previous_path),output_sha256=digest(folder/'output.jsonl'),
        provenance_sha256=digest(folder/'provenance.json'),local_model='HY-MT1.5-1.8B-Q8_0',
        independent_source_calls=True,official_translation_prompt=True,weights_trained=False,application_modified=False,
        outputs_not_used_to_train_other_models=True,license='Tencent HY Community License Agreement',
        distribution_approved=False,provider_accepted_for_deployment=False,
        candidate_improved_on_this_cohort=cohorts['all124_fixed_reading_viewports']['after_not_approved']<58,
        all_paintings_visually_reviewed=False,all_chapter_words_visually_reviewed=False,
        complete_live_app_use_including_capture_and_movement=False,screen_attempt_failure_probability=None,
        target_achieved=False,ready_for_release=False)
    target=ROOT/'benchmarks/full-comics/hy8024-full-viewports-semantic-review.json'
    atomic(target,json.dumps(value,ensure_ascii=False,indent=2))
    atomic(folder/'semantic-summary.json',json.dumps({k:v for k,v in value.items() if k!='entries'},indent=2))
    print(json.dumps(dict(cohorts=cohorts,candidate_improved=value['candidate_improved_on_this_cohort'],ready_for_release=False)),flush=True)


if __name__=='__main__':main()
