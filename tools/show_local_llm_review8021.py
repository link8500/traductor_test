"""Show full original inventories alongside unedited local-model outputs."""
import argparse
import json
from audit_corpus_quality import ROOT, QA, read, records


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--start',type=int,default=1);parser.add_argument('--end',type=int,default=124);parser.add_argument('--recommended',action='store_true');args=parser.parse_args()
    previous=read(ROOT/'benchmarks/full-comics/windows8021-full-viewports-semantic-review.json')
    folder=QA/('local-llm8021-full-viewports'+('-recommended' if args.recommended else ''))
    for row in previous['entries']:
        ident=row['id']
        if not args.start<=ident<=args.end:continue
        output=read(folder/f'{ident:03d}.json')
        value=dict(id=ident,original_visible_dialogue=row['dialogue'],clipped=row['visible_dialogue_clipped'],
            previous_judgment=row['after'],previous_note=row['note'],
            recognized_ocr=output['source_passages'],new_translations=output['translations'])
        print(json.dumps(value,ensure_ascii=True),flush=True)


if __name__=='__main__':main()
