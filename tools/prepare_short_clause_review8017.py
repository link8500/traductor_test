"""Resolve the fourteen changed candidate outputs to their exact source pixels."""
import json
import prepare_corpus_review_sample as sheets
from audit_corpus_quality import ROOT,QA,atomic,digest,read


def main():
    folder=QA/'short-clause8017-guarded';out=folder/'visual-review';out.mkdir(exist_ok=True)
    changes=read(folder/'summary.json')['changes']
    old=read(ROOT/'benchmarks/full-comics/current8011-six-regions-semantic-review.json')['entries']
    templates={}
    for group,name in [('a','current8011-full-a'),('b','current8011-full-b'),('short','corpus-review-short8011'),('next','corpus-review-next8011'),('sixth','corpus-review-sixth8011')]:
        for case in read(QA/name/'sample.json')['cases']:templates[(group,case['id'])]=case
    heldout={c['id']:c for c in read(QA/'windows8016-heldout-pixels/visual-review/sample.json')['cases']}
    heldout_manual={r[0]:r for r in read(QA/'windows8016-heldout-pixels/visual-review/manual-decisions.json')}
    cases=[]
    for row in changes:
        if row['cohort']=='actual_windows_heldout':
            seed=heldout[row['image']];judgment=heldout_manual[row['image']][1]
        else:
            matches=[e for e in old if e['source']==row['source']];assert len(matches)==1
            match=matches[0];seed=templates[(match['group'],match['original_id'])];judgment=match['after']
        cases.append({**seed,**row,'id':len(cases)+1,'inference_id':row['id'],
            'original_before_judgment':judgment,'meaning_reviewed':False})
    value=dict(cases=cases,chapters=len({c['chapter'] for c in cases}),changed_outputs=len(cases),candidate_summary_sha256=digest(folder/'summary.json'),
        all_chapter_words_visually_reviewed=False,strict_full_content_review_required=True)
    atomic(out/'sample.json',json.dumps(value,ensure_ascii=False,indent=2))
    sheets.OUT=out;sheets.render(value,100,90)
    print(json.dumps(dict(changed_outputs=len(cases),sheets=(len(cases)+3)//4)),flush=True)


if __name__=='__main__':main()
