"""Inspect completed whole-view changes; never approve a partial output prefix."""
import argparse
import json
from audit_corpus_quality import ROOT, QA, read, records


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--start',type=int,default=1);parser.add_argument('--end',type=int,default=124);args=parser.parse_args()
    previous=read(ROOT/'benchmarks/full-comics/windows8021-full-viewports-semantic-review.json')
    known={r['source']:r for r in records(QA/'translation-search8022/unique-output.jsonl')}
    completed=changed=0
    for view in previous['entries']:
        old=view['consensus_outputs'];ident=view['id']
        if not all(r['source'] in known for r in old):continue
        completed+=1
        differences=[dict(source=r['source'],before=r['translation'],after=known[r['source']]['translation'])
            for r in old if r['translation']!=known[r['source']]['translation']]
        if not differences:continue
        changed+=1
        if not args.start<=ident<=args.end:continue
        print(json.dumps(dict(id=ident,original_visible_dialogue=view['dialogue'],clipped=view['visible_dialogue_clipped'],
            before_judgment=view['after'],previous_note=view['note'],changes=differences,
            all_new_passages=[known[r['source']]['translation'] for r in old]),ensure_ascii=True),flush=True)
    print(json.dumps(dict(complete_viewports=completed,changed_complete_viewports=changed)),flush=True)


if __name__=='__main__':main()
