"""Review all checkpoint validation outputs and lock one before known controls."""
import argparse
import hashlib
import json

from tools.experiments.stability8035.core import ROOT, PRIOR, read, sha, write_new
from tools.experiments.stability8035.review import validation_counts, validation_gates

META = ROOT / 'benchmarks/onpolicy8036'
OUT = ROOT / 'build/onpolicy8036'


def key(source, translation):
    return hashlib.sha256((source + '\0' + translation).encode()).hexdigest()


def verified_run():
    protocol = read(META / 'protocol.json')
    proof = read(OUT / 'run-input-proof.json')
    summary = read(OUT / 'summary.json')
    assert proof['protocol_sha256'] == sha(META / 'protocol.json')
    for path, expected in proof['code_sha256'].items():
        assert sha(ROOT / path) == expected
    assert summary['base_weights_unchanged'] and summary['actual_weight_training_completed']
    assert summary['base_hash_before'] == summary['base_hash_after']
    assert summary['all_gradient_and_rollout_ids_are_training_only']
    for checkpoint in summary['checkpoints']:
        folder = OUT / checkpoint['name']
        assert sha(folder / 'adapter/adapter_model.safetensors') == checkpoint['adapter_sha256']
        assert sha(folder / 'validation-candidate.json') == checkpoint['output_sha256']
    return protocol, summary


def catalogue():
    sources = {}
    data = read(ROOT / 'benchmarks/finetune8034/dataset.json')['validation']
    for row in data:
        sources[row['id']] = row
    result = {}
    baseline = read(PRIOR / 'baseline-validation.json')
    base_verdicts = {row['id']: row for row in read(ROOT / 'benchmarks/finetune8034/baseline-validation-meaning-decisions.json')['entries']}
    for row in baseline:
        decision = base_verdicts[row['id']]
        result[key(row['source'], row['translation'])] = dict(after=decision['status'], note=decision.get('note'), reused_from='8034-baseline')
    decisions = {row['id']: row for row in read(ROOT / 'benchmarks/finetune8034/validation-meaning-decisions.json')['entries']}
    for row in read(PRIOR / 'candidate-validation.json'):
        result[key(row['source'], row['translation'])] = dict(after=decisions[row['id']]['after'], note=decisions[row['id']].get('note'), reused_from='8034-candidate')
    strengths = read(ROOT / 'benchmarks/stability8035/validation-review.json')['variants']
    for name, review in strengths.items():
        decisions = {row['id']: row for row in review['entries']}
        for row in read(ROOT / f'build/stability8035/validation-{name}.json'):
            result[key(row['source'], row['translation'])] = dict(after=decisions[row['id']]['after'], note=decisions[row['id']].get('note'), reused_from=f'8035-{name}')
    return sources, result, base_verdicts


def prepare(summary):
    sources, historical, baseline = catalogue()
    cases = {}
    for checkpoint in summary['checkpoints']:
        for row in read(OUT / checkpoint['name'] / 'validation-candidate.json'):
            ident = row['id']
            assert row['source'] == sources[ident]['source']
            ident_key = key(row['source'], row['translation'])
            if ident_key in historical:
                continue
            if ident_key not in cases:
                cases[ident_key] = dict(key=ident_key, id=ident, source=row['source'],
                                       reference=sources[ident]['target'], translation=row['translation'],
                                       base_status=baseline[ident]['status'], checkpoints=[])
            cases[ident_key]['checkpoints'].append(checkpoint['name'])
    write_new(OUT / 'validation-review-queue.json', list(cases.values()))
    for row in cases.values():
        print(json.dumps(row, ensure_ascii=False))
    print(json.dumps(dict(novel_distinct_outputs=len(cases))))


def lock(protocol, summary):
    assert not (OUT / 'controls-input-proof.json').exists()
    sources, historical, baseline = catalogue()
    queue = read(OUT / 'validation-review-queue.json')
    manual = read(META / 'validation-novel-decisions.json')
    assert manual['queue_sha256'] == sha(OUT / 'validation-review-queue.json')
    reviewed = {row['key']: row for row in manual['entries']}
    assert set(reviewed) == {row['key'] for row in queue}
    checkpoint_reviews = {}
    for checkpoint in summary['checkpoints']:
        rows = read(OUT / checkpoint['name'] / 'validation-candidate.json')
        entries = []
        for row in rows:
            source = sources[row['id']]
            ident_key = key(row['source'], row['translation'])
            if ident_key in historical:
                decision = historical[ident_key]
                method = 'exact_source_and_output_identity'
            else:
                decision = reviewed[ident_key]
                method = 'assistant_source_reference_and_output_review'
            entries.append(dict(id=row['id'], validation_group=source['validation_group'],
                                before=baseline[row['id']]['status'], after=decision['after'],
                                note=decision.get('note'), reviewed=True, review_method=method,
                                source_output_key=ident_key))
        counts = validation_counts(entries)
        gates = validation_gates(protocol, counts, checkpoint['format_alerts'])
        checkpoint_reviews[checkpoint['name']] = dict(entries=entries, counts=counts,
                                                     gates=gates, eligible=all(gates.values()))
        print(json.dumps(dict(checkpoint=checkpoint['name'], counts=counts, gates=gates)), flush=True)
    write_new(META / 'validation-review.json', dict(checkpoints=checkpoint_reviews,
              validation_used_for_selection_not_independent_test=True,
              novel_decisions_sha256=sha(META / 'validation-novel-decisions.json')))
    eligible = [row for row in summary['checkpoints'] if checkpoint_reviews[row['name']]['eligible']]
    eligible.sort(key=lambda row: (
        checkpoint_reviews[row['name']]['counts']['known']['confirmed_errors_after'],
        -checkpoint_reviews[row['name']]['counts']['new']['complete_corrections'],
        -row['validation_chrfpp'], row['optimizer_step']))
    selected = eligible[0] if eligible else None
    write_new(META / 'selection.json', dict(
        selected_checkpoint=selected['name'] if selected else None,
        all_selection_gates_passed=bool(selected),
        checkpoint=selected, protocol_sha256=sha(META / 'protocol.json'),
        review_sha256=sha(META / 'validation-review.json'),
        frozen_before_control_inference=True, controls_used_for_selection=False,
        new_blind_test_chapters_opened=0))
    print(json.dumps(dict(state='selection_locked', selected=selected)), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['prepare', 'lock'])
    args = parser.parse_args()
    protocol, summary = verified_run()
    if args.stage == 'prepare':
        prepare(summary)
    else:
        lock(protocol, summary)


if __name__ == '__main__':
    main()
