"""Read specialist results alongside the complete original viewport inventory."""
import argparse
import json
from audit_corpus_quality import ROOT, QA, read, records


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--start',type=int,default=1);parser.add_argument('--end',type=int,default=124);args=parser.parse_args()
    previous=read(ROOT/'benchmarks/full-comics/windows8021-full-viewports-semantic-review.json')
    rows=records(QA/'windows8021-full-viewports-full-agreement/output.jsonl')
    prepared={r['source']:r['id'] for r in records(QA/'local-llm8023-normalized/native-prepared.jsonl')}
    folder=QA/'hy8024-full-viewports'
    for row in previous['entries']:
        ident=row['id']
        if not args.start<=ident<=args.end:continue
        sources=[r for r in rows if r['image']==ident]
        files=[folder/f"source-{prepared[r['source']]:03d}.json" for r in sources]
        if not all(p.exists() for p in files):continue
        print(json.dumps(dict(id=ident,original=row['dialogue'],clipped=row['visible_dialogue_clipped'],
            before=row['after'],translations=[read(p)['translation'] for p in files]),ensure_ascii=True),flush=True)


if __name__=='__main__':main()
