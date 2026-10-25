"""Show actual paired outputs beside the independently inventoried source."""
import argparse
import json
from audit_corpus_quality import ROOT, QA, read, records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', type=int, required=True)
    parser.add_argument('--end', type=int, required=True)
    args = parser.parse_args()
    inventory = read(ROOT / 'benchmarks/full-comics/viewport8020-original-inventory.json')
    a = records(QA / 'windows8020-full-viewports-baseline/output.jsonl')
    b = records(QA / 'windows8020-full-viewports-consensus/output.jsonl')
    for row in inventory['entries']:
        ident = row['id']
        if not args.start <= ident <= args.end:
            continue
        before = [r['translation'] for r in a if r['image'] == ident]
        after = [r['translation'] for r in b if r['image'] == ident]
        print(json.dumps(dict(id=ident, gold=row['dialogue'], clipped=row['visible_dialogue_clipped'],
            before=before, after=after), ensure_ascii=True))


if __name__ == '__main__':
    main()
