"""Freeze omission-recovery policy, then select124 unseen source locations."""
import json
import shutil

import prepare_corpus_review_sample as sample_tool
from audit_corpus_quality import ROOT,QA,atomic,digest,read


def main():
    folder=QA/'ocr-coverage8017-holdout-source';folder.mkdir(exist_ok=True)
    prior=ROOT/'benchmarks/full-comics/current8011-six-regions-semantic-review.json'
    heldout=QA/'ocr-reader-heldout8016-source/sample.json'
    excluded=folder/'excluded.json'
    cases=read(prior)['entries']+read(heldout)['cases']
    assert len(cases)==868
    atomic(excluded,json.dumps(dict(cases=cases),ensure_ascii=False))
    frozen=QA/'ocr-coverage8017-development'
    # The compiled candidate and headers were saved before any third-cohort
    # source location or result is selected. Do not rebuild this snapshot.
    assert digest(frozen/'native.exe')==digest(ROOT/'build/ocr8016/Release/luma_ocr_coverage_candidate.exe')
    before=dict(policy_sha256=digest(frozen/'ocr_coverage_candidate.h'),
        base_policy_sha256=digest(frozen/'ocr_consensus_candidate.h'),
        binary_sha256=digest(frozen/'native.exe'),excluded_sha256=digest(excluded))
    atomic(folder/'policy-before-selection.json',json.dumps(before,indent=2))
    sample_tool.OUT=folder
    sample=sample_tool.build(per_chapter=1,exclude_sample=excluded)
    assert len(sample['cases'])==124
    result=dict(before,selection_sha256=digest(folder/'sample.json'),
        excluded_previously_reviewed_locations=868,new_locations=124,
        selection_before_inference=True,rule_frozen_before_selection=True,
        selected_by_candidate_output=False)
    target=folder/'selection-provenance.json'
    if target.exists():assert read(target)==result
    else:atomic(target,json.dumps(result,indent=2))
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
