"""Reuse only exact prior pixel judgments; expose every newly changed location."""
import json
import prepare_corpus_review_sample as sheets
from audit_corpus_quality import ROOT,QA,atomic,digest,read


def main():
    folder=QA/'full8012-review-checkpoint02';sample=read(folder/'sample.json')
    old_folder=QA/'full8012-review-checkpoint01';old=read(old_folder/'sample.json')
    manual={r[0]:r for r in read(old_folder/'manual-decisions.json')}
    known={case['original_id']:case for case in old['cases']}
    reused=[];pending=[]
    for case in sample['cases']:
        before=known.get(case['original_id'])
        exact=before and all(before[k]==case[k] for k in ['chapter','source_image','bounds','source','before_translation','translation'])
        if exact:
            for key in ['source_page','reference_page']:assert before[key]['sha256']==case[key]['sha256']
            reused.append(dict(checkpoint02_case_id=case['id'],original_id=case['original_id'],
                previous_case_id=before['id'],decision=manual[before['id']],exact_source_output_pixels=True))
        else:
            pending.append(dict(case,checkpoint02_case_id=case['id'],id=len(pending)+1))
    out=folder/'followup';out.mkdir(exist_ok=True)
    value=dict(cases=pending,reused_changed_pixel_judgments=reused,chapters=124,
        fixed_locations=744,changed_locations=99,new_changed_locations_pending=len(pending),
        checkpoint02_sample_sha256=digest(folder/'sample.json'),
        old_sample_sha256=digest(old_folder/'sample.json'),old_manual_sha256=digest(old_folder/'manual-decisions.json'),
        all_chapter_words_visually_reviewed=False)
    path=out/'sample.json'
    if path.exists():assert read(path)==value
    else:atomic(path,json.dumps(value,ensure_ascii=False,indent=2))
    sheets.OUT=out;sheets.render(value,100,90)
    print(json.dumps(dict(new_changed_locations=len(pending),reused_changed_judgments=len(reused),sheets=(len(pending)+3)//4)),flush=True)


if __name__=='__main__':main()
