"""Score fixed candidate pools with no references, then apply frozen routing rules."""
import argparse
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path

from tools.experiments.stability8035.core import ROOT, read, sha, write_new, format_issues
from .pool_policy import select

META = ROOT / 'benchmarks/qe8038'
OUT = ROOT / 'build/qe8038'


def key(source, translation):
    return hashlib.sha256((source + '\0' + translation).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['validation', 'controls'])
    args = parser.parse_args()
    protocol = read(META / 'protocol.json')
    for entry in protocol['immutable_inputs']:
        assert sha(ROOT / entry['path']) == entry['sha256'], entry['path']
    pools = read(OUT / 'candidate-pools.json')
    pools = [row for row in pools if (row['group'] == 'validation') == (args.stage == 'validation')]
    assert len(pools) == (25 if args.stage == 'validation' else 258)
    if args.stage == 'controls':
        selection = read(META / 'selection.json')
        assert selection['eligible'] and selection['frozen_before_controls']
        assert selection['validation_review_sha256'] == sha(META / 'validation-review.json')
        assert selection['protocol_sha256'] == sha(META / 'protocol.json')
        margins = [selection['margin']]
    else:
        margins = protocol['margins']
    assert read(META / 'native-validation-meaning-decisions.json')['reviewed_before_qe_scores']
    assert read(META / 'native-control-meaning-decisions.json')['reviewed_before_control_qe_scores']
    proof = dict(protocol_sha256=sha(META / 'protocol.json'),
                 code_sha256={str(path.relative_to(ROOT)): sha(path) for path in Path(__file__).parent.glob('*.py')},
                 packages={name: importlib.metadata.version(name) for name in ['torch', 'transformers', 'unbabel-comet', 'pytorch-lightning', 'numpy']},
                 references_used_for_prediction=False, source_or_translation_uploaded=False,
                 new_blind_test_chapters_opened=0, new_training=False)
    if args.stage == 'controls':
        proof['selection_sha256'] = sha(META / 'selection.json')
    write_new(OUT / f'{args.stage}-input-proof.json', proof)
    requests = {}
    for pool in pools:
        if len({row['translation'] for row in pool['candidates']}) == 1:
            continue
        for row in pool['candidates']:
            if not format_issues(pool['source'], row['translation']):
                requests[key(pool['source'], row['translation'])] = dict(src=pool['source'], mt=row['translation'])
    write_new(OUT / f'{args.stage}-qe-input.json', requests)
    from .model import QualityEstimator
    estimator = QualityEstimator()
    token = estimator.model.encoder.tokenizer
    eligible = {ident: row for ident, row in requests.items() if all(
        len(token(text, truncation=False)['input_ids']) <= estimator.limit for text in row.values())}
    unsupported = sorted(set(requests) - set(eligible))
    predictions = estimator.score(list(eligible.values()))
    assert all(math.isfinite(value) for value in predictions)
    scores = dict(zip(eligible, predictions))
    scores.update({ident: None for ident in unsupported})
    write_new(OUT / f'{args.stage}-scores.json', dict(
        scores=scores, unsupported_without_truncation=unsupported,
        request_sha256=sha(OUT / f'{args.stage}-qe-input.json'),
        score_is_not_failure_probability=True))
    for margin in margins:
        rows = []
        for pool in pools:
            values = {row['name']: scores.get(key(pool['source'], row['translation'])) for row in pool['candidates']}
            decision = select(pool['source'], pool['candidates'], values, margin)
            rows.append(dict(group=pool['group'], id=pool['id'], source=pool['source'],
                             **decision, margin=margin, qe_scores=values))
        label = f'{margin:.2f}'.replace('.', '')
        path = OUT / f'{args.stage}-margin{label}.json'
        write_new(path, rows)
        print(json.dumps(dict(state='qe_routing_complete', stage=args.stage, margin=margin,
                              rows=len(rows), switches=sum(row['selected'] != 'native' for row in rows),
                              unresolved=sum(row['unresolved'] for row in rows), output_sha256=sha(path))), flush=True)


if __name__ == '__main__':
    main()
