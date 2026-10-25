"""Read normalized trial results against complete visible original inventories."""
import argparse
import json
from audit_corpus_quality import ROOT, QA, read


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--start',type=int,default=1);parser.add_argument('--end',type=int,default=124);args=parser.parse_args()
    previous=read(ROOT/'benchmarks/full-comics/windows8021-full-viewports-semantic-review.json')
    folder=QA/'local-llm8023-normalized'
    for row in previous['entries']:
        ident=row['id']
        if not args.start<=ident<=args.end:continue
        path=folder/f'{ident:03d}.json'
        if not path.exists():continue
        candidate=read(path)
        print(json.dumps(dict(id=ident,original=row['dialogue'],clipped=row['visible_dialogue_clipped'],
            before_judgment=row['after'],previous_note=row['note'],translations=candidate['translations']),ensure_ascii=True),flush=True)


if __name__=='__main__':main()
