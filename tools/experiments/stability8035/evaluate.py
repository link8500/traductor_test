"""Evaluate validation first; evaluate only a locked candidate on known controls."""
import argparse
import json
import shutil

from sacrebleu.metrics import CHRF

from .core import (META, OUT, PRIOR, ROOT, read, sha, source_only,
                   text_outputs, validate_provenance, write_new)


def proof(stage, protocol):
    assert shutil.disk_usage(ROOT).free >= 4 * 1024**3
    code = sorted((ROOT / 'tools/experiments/stability8035').glob('*.py'))
    value = dict(stage=stage, protocol_sha256=sha(META / 'protocol.json'),
                 executed_code={str(path.relative_to(ROOT)): sha(path) for path in code},
                 immutable_inputs=protocol['immutable_inputs'],
                 new_gradient_updates=0, references_sent_to_generation=False,
                 new_blind_test_chapters_opened=0, application_modified=False)
    write_new(OUT / f'{stage}-input-proof.json', value)


def validation(protocol, data):
    from .runtime import Runtime
    proof('validation', protocol)
    inputs = source_only(data['validation'])
    write_new(OUT / 'validation-source-only-input.json', inputs)
    runtime = Runtime(protocol['generation'])
    previous = runtime.generate(inputs, 1)
    assert text_outputs(previous) == read(PRIOR / 'candidate-validation.json'), '8034 parity failed'
    baseline = runtime.generate(inputs, 0)
    assert text_outputs(baseline) == read(PRIOR / 'baseline-validation.json'), 'Base parity failed'
    write_new(OUT / 'parity.json', dict(full_adapter_exact=True, zero_adapter_exact=True,
                                     lora_layers=len(runtime.layers), rows=len(inputs)))
    metric = CHRF(word_order=2)
    refs = [[row['target'] for row in data['validation']]]
    summaries = []
    for variant in protocol['variants']:
        candidate = runtime.generate(inputs, variant['strength'])
        path = OUT / f"validation-{variant['id']}.json"
        write_new(path, candidate)
        value = dict(variant=variant, rows=len(candidate), output_sha256=sha(path),
                     changed_from_base=sum(a['translation'] != b['translation'] for a, b in zip(candidate, baseline)),
                     chrfpp=metric.corpus_score([row['translation'] for row in candidate], refs).score,
                     format_alerts=sum(bool(row['format_issues']) for row in candidate),
                     semantic_review_completed=False, probability_of_app_failure=None)
        summaries.append(value)
        print(json.dumps(dict(state='validation_variant_complete', **value)), flush=True)
    write_new(OUT / 'validation-summary.json', summaries)


def controls(protocol):
    from .runtime import Runtime
    selection = read(META / 'selection.json')
    assert selection['frozen_before_control_generation'] is True
    eligible = {variant['id']: variant for variant in protocol['variants']}
    variant = eligible[selection['variant_id']]
    assert selection['validation_outputs_sha256'] == sha(OUT / f"validation-{variant['id']}.json")
    assert selection['validation_review_sha256'] == sha(META / 'validation-review.json')
    assert selection['protocol_sha256'] == sha(META / 'protocol.json')
    proof('controls', protocol)
    write_new(OUT / 'controls-selection-proof.json', dict(selection=selection, selection_sha256=sha(META / 'selection.json')))
    runtime = Runtime(protocol['generation'])
    for name in ['regression-core', 'known-test', 'early-known-test']:
        baseline = read(PRIOR / f'{name}-baseline.json')
        inputs = source_only(baseline)
        write_new(OUT / f'{name}-source-only-input.json', inputs)
        candidate = runtime.generate(inputs, variant['strength'])
        output = OUT / f'{name}-candidate.json'
        write_new(output, candidate)
        summary = dict(rows=len(candidate), changed_from_base=sum(
            a['translation'] != b['translation'] for a, b in zip(baseline, candidate)),
            baseline_sha256=sha(PRIOR / f'{name}-baseline.json'), output_sha256=sha(output),
            selection_sha256=sha(META / 'selection.json'),
            format_alerts=sum(bool(row['format_issues']) for row in candidate),
            generation_limits_reached=sum(row['generation_limit_reached'] for row in candidate),
            fresh_blind_test=False, production_ocr_repeated=False, semantic_review_complete=False)
        write_new(OUT / f'{name}-summary.json', summary)
        print(json.dumps(dict(state='known_control_complete', name=name, **summary)), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['validation', 'controls'])
    args = parser.parse_args()
    protocol, data = validate_provenance()
    if args.stage == 'validation':
        validation(protocol, data)
    else:
        controls(protocol)


if __name__ == '__main__':
    main()
