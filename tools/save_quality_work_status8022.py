"""Current aggregate checkpoint: pending full-word coverage is never a pass."""
import datetime
import json
import shutil
from audit_corpus_quality import ROOT, QA, atomic, digest, read


def main():
    value=read(QA/'continuation8021.json')
    value['updated_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    for name in value['progress']:
        rows=[read(p) for p in (QA/name).glob('*.done.json')]
        value['progress'][name]=dict(chapters_complete=len(rows),regions=sum(r['regions'] for r in rows),
            runtime_errors=sum(r['runtime_errors'] for r in rows),all_words_manually_reviewed=False)
    before=read(ROOT/'benchmarks/full-comics/windows8021-full-viewports-semantic-review.json')
    current=before['cohorts']['all124_fixed_reading_viewports']
    original=before['historical_baseline_comparison']['cohorts']['all124_fixed_reading_viewports']
    value['best_comparable_viewport_progress']=dict(scope='124 fixed reading viewports, one per chapter; not all chapter words or full live uses',
        evaluated_experimental_build='802101',viewports=124,before_not_approved=original['before_not_approved'],
        current_not_approved=current['after_not_approved'],before_percent=100*original['before_not_approved']/124,
        current_percent=100*current['after_not_approved']/124,
        percentage_points_reduction=100*(original['before_not_approved']-current['after_not_approved'])/124,
        relative_reduction_percent=original['relative_unapproved_reduction_percent'],
        clear_content_error_viewports=current['after_categories']['incorrect']+current['after_categories']['incomplete'],
        clipped_only_unapproved=current['after_categories']['clipped'],meaning_needs_review=current['after_categories']['needs_review'],
        individual_word_error_count_not_measured=True,phone_apk_failure_probability_not_measured=True,
        model_weights_trained=False,screen_attempt_failure_probability=None,target_achieved=False)
    search_path=ROOT/'benchmarks/full-comics/search8022-full-viewports-semantic-review.json'
    search=read(search_path)
    value['new_search_trial8022']={k:v for k,v in search.items() if k!='entries'}
    for name in ['benchmarks/full-comics/search8022-full-viewports-semantic-review.json',
                 'build/full-comics/translation-search8022/build-provenance.json',
                 'build/full-comics/translation-search8022/summary.json']:
        value['evidence'].append(dict(path=name,sha256=digest(ROOT/name)))
    value['requested_git_removal']=dict(target=str(ROOT/'.git'),authorized_by_user=True,
        automatic_review_rejected=True,reason='blocked by policy; no more specific reason returned',
        safer_literal_path_attempt_also_rejected=True,confirmed_no_reparse_points=True,
        deleted=False,still_present=(ROOT/'.git').exists(),metadata_bytes_before=224034451,
        do_not_bypass_rejection_using_other_tools=True)
    value['storage']['free_bytes_now']=shutil.disk_usage(ROOT).free
    value['cloud_storage']=dict(requested_only_if_needed=True,drive_upload_performed=False,
        credentials_not_used_or_saved=True,local_space_sufficient_now=True)
    value['active_sessions']=[dict(session=21650,job='full frozen801704 traversal across124 chapters',log='build/full-comics/full-en8017-geometry.log'),
        dict(session=51606,job='audit_corpus_quality.py --watch --track-experiments',log='build/full-comics/metrics/experimental-progress8022.log'),
        dict(session=53356,job='HTTP server127.0.0.1:8765 rootbuild')]
    value['completed_sessions']+= [11716,13827]
    value['remaining_work']+= [
        'Wider native search trial8022 completed and reviewed:58to58 unapproved,0fullfixes0fullregressions,2partialworsenings. Rejected; no app sources/assets changed. Do not repeat this completed variant.',
        'Both old Qwen experiments used raw mostly-uppercase OCR, whereas Marian normalizes source casing. A future fair Qwen comparison should use the exact native PrepareInput results before concluding about model capability. No claim that this will improve quality; it has not been run. Weights are no longer cached; avoid unnecessary downloads and preserve the4GiB floor.',
        'The user postponed adding250 chapters. Continue existing124 only. User examples can become additional regression cases without replacing broad review.',
        'Git removal was blocked by automatic review even with explicit verified literal target. Do not hide or bypass the block. The user provided Drive credentials, but they were not used, copied, or persisted; local space is sufficient and an authorized connection should be used if external storage becomes necessary.']
    atomic(QA/'continuation8022.json',json.dumps(value,ensure_ascii=False,indent=2))
    atomic(QA/'continuation-latest.json',json.dumps(dict(path='continuation8022.json',sha256=digest(QA/'continuation8022.json')),indent=2))
    print(json.dumps(dict(saved='continuation8022.json',best_comparable_progress=value['best_comparable_viewport_progress'],
        full_traversal=value['progress']['translated-en8017-geometry'],free_GiB=round(value['storage']['free_bytes_now']/1024**3,2),
        git_removed=False,objective_complete=False)),flush=True)


if __name__=='__main__':main()
