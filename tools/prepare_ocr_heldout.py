"""Select new pixel locations before inference, excluding all 744 reviewed ones."""
import json
import prepare_corpus_review_sample as sample_tool
from audit_corpus_quality import ROOT,QA,read,digest,atomic


def main():
    folder=QA/'ocr-reader-heldout8016-source';folder.mkdir(exist_ok=True)
    excluded=folder/'excluded.json';base=ROOT/'benchmarks/full-comics/current8011-six-regions-semantic-review.json'
    atomic(excluded,json.dumps(dict(cases=read(base)['entries']),ensure_ascii=False))
    sample_tool.OUT=folder;sample=sample_tool.build(per_chapter=1,exclude_sample=excluded)
    assert len(sample['cases'])==124
    proof=dict(selection_sha256=digest(folder/'sample.json'),excluded_review_sha256=digest(base),
        frozen_policy_sha256=digest(ROOT/'native/ocr_consensus_candidate.h'),frozen_binary_sha256=digest(ROOT/'build/ocr8016/Release/luma_ocr_consensus_candidate.exe'),
        excluded_reviewed_locations=744,new_locations=124,selection_before_inference=True,selected_by_model_output=False)
    path=folder/'selection-provenance.json'
    if path.exists():assert read(path)==proof
    else:atomic(path,json.dumps(proof,indent=2))
    print(json.dumps(proof),flush=True)


if __name__=='__main__':main()
