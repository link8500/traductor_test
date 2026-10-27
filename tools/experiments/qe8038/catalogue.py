"""Reuse meaning decisions only for exactly identical source and output text."""
import hashlib

from tools.experiments.stability8035.core import ROOT, PRIOR, read
from tools.experiments.onpolicy8036.select_checkpoint import catalogue as validation_catalogue


def key(source, translation):
    return hashlib.sha256((source + '\0' + translation).encode()).hexdigest()


def build():
    _, validation, _ = validation_catalogue()
    result = {ident: dict(status=row['after'], note=row.get('note'), origin=row.get('reused_from'))
              for ident, row in validation.items()}
    for experiment in ['8031', '8032', '8033', '8034']:
        folder = ROOT / f'build/finetune{experiment}/lora-pilot'
        meta = ROOT / f'benchmarks/finetune{experiment}'
        for group in ['regression-core', 'known-test', 'early-known-test']:
            name = 'fresh-test' if group == 'known-test' and experiment in ['8032', '8033'] else group
            decisions = meta / f'{name}-meaning-decisions.json'
            predictions = folder / f'{name}-candidate.json'
            if not (decisions.exists() and predictions.exists()):
                continue
            candidate = {row['id']: row for row in read(predictions)}
            baseline = {row['id']: row for row in read(PRIOR / f'{group}-baseline.json')}
            for decision in read(decisions)['entries']:
                ident = decision['id']
                if ident not in candidate or ident not in baseline:
                    continue
                a, b = baseline[ident], candidate[ident]
                assert a['source'] == b['source']
                result[key(a['source'], a['translation'])] = dict(status=decision['before'], note='Previously reviewed baseline output.', origin=str(decisions.relative_to(ROOT)))
                result[key(b['source'], b['translation'])] = dict(status=decision['after'], note=decision.get('note'), origin=str(decisions.relative_to(ROOT)))
    for folder, meta in [('stability8035', 'stability8035'), ('onpolicy8036', 'onpolicy8036')]:
        review = read(ROOT / f'benchmarks/{meta}/control-meaning-review.json')
        outputs = {name: {row['id']: row for row in read(ROOT / f'build/{folder}/{name}-candidate.json')}
                   for name in ['regression-core', 'known-test', 'early-known-test']}
        for decision in review['entries']:
            row = outputs[decision['name']][decision['id']]
            result[key(row['source'], row['translation'])] = dict(status=decision['after'], note=decision.get('note'), origin=meta)
    for experiment in ['onpolicy8036', 'decoder8037']:
        review = read(ROOT / f'benchmarks/{experiment}/validation-review.json')
        if experiment == 'onpolicy8036':
            variants = review['checkpoints']
        else:
            variants = review['variants']
        for name, decisions in variants.items():
            path = (ROOT / f'build/{experiment}/{name}/validation-candidate.json' if experiment == 'onpolicy8036'
                    else ROOT / f'build/{experiment}/validation-{name}.json')
            outputs = {row['id']: row for row in read(path)}
            for decision in decisions['entries']:
                row = outputs[decision['id']]
                result[key(row['source'], row['translation'])] = dict(status=decision['after'], note=decision.get('note'), origin=experiment)
    # Most recent native validation was judged before any QE predictions.
    decisions = read(ROOT / 'benchmarks/qe8038/native-validation-meaning-decisions.json')
    for decision in decisions['entries']:
        result[decision['source_output_key']] = dict(status=decision['status'], note=decision.get('note'), origin='native-validation8038')
    return result
