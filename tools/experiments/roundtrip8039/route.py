"""Apply only preregistered policies to immutable candidate strings."""
import argparse
import json

from tools.experiments.stability8035.core import ROOT, read, sha, write_new
from tools.experiments.qe8038.evaluate import key
from .policy import choose

OUT = ROOT / 'build/roundtrip8039'
META = ROOT / 'benchmarks/roundtrip8039'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['validation', 'controls'])
    args = parser.parse_args()
    protocol = read(META / 'protocol.json')
    if args.stage == 'validation':
        policies = protocol['policies']
        qe_path = ROOT / 'build/qe8038/validation-scores.json'
    else:
        selection = read(META / 'selection.json')
        assert selection['eligible'] and selection['frozen_before_controls']
        policies = [selection['policy']]
        qe_path = OUT / 'controls-qe-scores.json'
    inverse = read(OUT / f'{args.stage}-inverse-scores.json')['scores']
    qe = read(qe_path)['scores'] if qe_path.exists() else {}
    if 'inverse_and_qe' in policies:
        assert qe, 'Consensus requires independently computed QE scores'
    pools = read(ROOT / 'build/qe8038/candidate-pools.json')
    pools = [row for row in pools if (row['group'] == 'validation') == (args.stage == 'validation')]
    for policy in policies:
        outputs = []
        for pool in pools:
            backward = {row['name']: inverse.get(key(pool['source'], row['translation']), {}).get('mean_log_probability') for row in pool['candidates']}
            forward = {row['name']: qe.get(key(pool['source'], row['translation'])) for row in pool['candidates']}
            result = choose(pool, backward, forward, consensus=policy == 'inverse_and_qe')
            outputs.append(dict(group=pool['group'], id=pool['id'], source=pool['source'],
                                **result, inverse_scores=backward, qe_scores=forward))
        path = OUT / f'{args.stage}-{policy}.json'
        write_new(path, outputs)
        print(json.dumps(dict(state='inverse_routing_complete', stage=args.stage, policy=policy,
                              rows=len(outputs), switches=sum(row['selected'] != 'native' for row in outputs),
                              output_sha256=sha(path))), flush=True)


if __name__ == '__main__':
    main()
