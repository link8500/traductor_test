"""Route frozen translations using cached inverse scores and local morphology."""
import argparse
import json
from pathlib import Path

from tools.experiments.stability8035.core import ROOT, read, sha, write_new
from tools.experiments.qe8038.evaluate import key
from .grammar import profile
from .policy import choose

OUT = ROOT / 'build/temporal8040'
META = ROOT / 'benchmarks/temporal8040'


def verify():
    protocol = read(META / 'protocol.json')
    for row in protocol['immutable_inputs']:
        assert sha(ROOT / row['path']) == row['sha256'], row['path']
    return protocol


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['validation', 'controls'])
    args = parser.parse_args()
    verify()
    if args.stage == 'controls':
        selection = read(META / 'selection.json')
        assert selection['eligible'] and selection['frozen_before_controls']
    import spacy
    nlp = spacy.load('es_core_news_sm', disable=['ner'])
    score_path = ROOT / 'build/roundtrip8039/validation-inverse-scores.json' if args.stage == 'validation' else OUT / 'controls-inverse-scores.json'
    scores = read(score_path)['scores']
    pools = [row for row in read(ROOT / 'build/qe8038/candidate-pools.json')
             if (row['group'] == 'validation') == (args.stage == 'validation')]
    texts = dict.fromkeys(candidate['translation'] for pool in pools for candidate in pool['candidates'])
    parsed = {text: profile(doc) for text, doc in zip(texts, nlp.pipe(texts, batch_size=32))}
    outputs = []
    for pool in pools:
        values = {candidate['name']: scores.get(key(pool['source'], candidate['translation']), {}).get('mean_log_probability') for candidate in pool['candidates']}
        profiles = {candidate['name']: parsed[candidate['translation']] for candidate in pool['candidates']}
        outputs.append(dict(group=pool['group'], id=pool['id'], source=pool['source'],
                            **choose(pool, values, profiles), inverse_scores=values, profiles=profiles))
    write_new(OUT / f'{args.stage}-candidate.json', outputs)
    write_new(OUT / f'{args.stage}-routing-proof.json', dict(
        protocol_sha256=sha(META / 'protocol.json'), scores_sha256=sha(score_path),
        code_sha256={str(path.relative_to(ROOT)): sha(path) for path in Path(__file__).parent.glob('*.py')},
        references_or_meaning_verdicts_used=False, source_word_rules=False,
        sentence_rewriting=False, model=nlp.meta['name'], version=nlp.meta['version']))
    print(json.dumps(dict(stage=args.stage, rows=len(outputs), switches=sum(row['selected'] != 'native' for row in outputs),
                          vetoed_alternatives=sum(len(row['temporal_vetoes']) for row in outputs))), flush=True)


if __name__ == '__main__':
    main()
