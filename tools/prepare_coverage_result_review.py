"""Render changed real native translations for assessment; preserve old judgments.

Byte-identical output in the same previously inspected location may retain
its judgment. Changed output remains pending even if a heuristic likes it.
"""
import json
import prepare_corpus_review_sample as sheets
from audit_corpus_quality import ROOT, QA, read, records, digest, atomic


def main():
    folder=QA/'sentence-coverage8014';out=folder/'visual-review';out.mkdir(exist_ok=True)
    inputs=read(folder/'cases.json');outputs={r['source']:r for r in records(folder/'output.jsonl')}
    previous_path=ROOT/'benchmarks/full-comics/current8011-extended-semantic-review.json'
    assert digest(previous_path)==inputs['review_sha256']
    base={}
    for group,name in [('a','current8011-full-a'),('b','current8011-full-b'),('short','corpus-review-short8011'),('next','corpus-review-next8011')]:
        for case in read(QA/name/'sample.json')['cases']:base[(group,case['id'])]=case
    original={e['id']:e for e in read(previous_path)['entries']}
    cases=[];unchanged=0
    for case in inputs['cases']:
        if case['group']!='reviewed':continue
        inference=outputs.get(case['source'])
        if inference is None:continue
        if inference['translation']==case['control_translation']:unchanged+=1;continue
        entry=original[case['id']];previous=base[(entry['group'],entry['original_id'])]
        cases.append(dict(previous,id=len(cases)+1,original_id=entry['id'],source=case['source'],
            translation=inference['translation'],before_translation=case['control_translation'],before_judgment=case['before_judgment'],
            bounds=entry['bounds'],current_inference=inference,meaning_reviewed=False))
    value=dict(cases=cases,chapters=len({c['chapter'] for c in cases}),changed_outputs=len(cases),unchanged_outputs=unchanged,
        inference_complete=len(outputs)==len(records(folder/'input.jsonl')),all_chapter_words_visually_reviewed=False,
        source_review_sha256=digest(previous_path),inference_output_sha256=digest(folder/'output.jsonl'))
    atomic(out/'sample.json',json.dumps(value,ensure_ascii=False,indent=2))
    sheets.OUT=out;sheets.render(value,100,80)
    print(json.dumps({k:v for k,v in value.items() if k!='cases'}))


if __name__=='__main__':main()
