"""Freeze a selection from explicit validation reviews, before control inference."""
import hashlib
import json

from .core import META, OUT, PRIOR, ROOT, read, sha, validate_provenance, write_new
from .review import validation_counts, validation_gates


def main():
    protocol, data = validate_provenance()
    assert not (OUT / 'controls-input-proof.json').exists()
    previous = read(PRIOR / 'candidate-validation.json')
    baseline = read(PRIOR / 'baseline-validation.json')
    old = {row['id']: row for row in read(ROOT / 'benchmarks/finetune8034/validation-meaning-decisions.json')['entries']}
    base_verdict = {row['id']: row['status'] for row in read(ROOT / 'benchmarks/finetune8034/baseline-validation-meaning-decisions.json')['entries']}
    novel = read(META / 'validation-novel-decisions.json')
    summaries = {row['variant']['id']: row for row in read(OUT / 'validation-summary.json')}
    variants = {}
    for variant in protocol['variants']:
        name = variant['id']
        outputs = read(OUT / f'validation-{name}.json')
        assert novel[name]['outputs_sha256'] == sha(OUT / f'validation-{name}.json')
        manual = {row['id']: row for row in novel[name]['entries']}
        decisions = []
        for source, row, before, prior in zip(data['validation'], outputs, baseline, previous):
            ident = source['id']
            assert row['source'] == source['source'] == before['source'] == prior['source']
            if row['translation'] == before['translation']:
                status = base_verdict[ident]
                method = 'exact_source_and_base_output_identity'
                note = 'Baseline verdict reused for identical source and output.'
            elif row['translation'] == prior['translation']:
                status = old[ident]['after']
                method = 'exact_source_and_prior_candidate_output_identity'
                note = old[ident].get('note', 'Prior verdict reused for identical source and output.')
            else:
                status, note = manual[ident]['after'], manual[ident]['note']
                method = 'assistant_source_reference_and_output_review'
            decisions.append(dict(
                id=ident, validation_group=source['validation_group'],
                before=base_verdict[ident], after=status, reviewed=True,
                review_method=method, note=note,
                source_sha256=hashlib.sha256(source['source'].encode()).hexdigest(),
                translation_sha256=hashlib.sha256(row['translation'].encode()).hexdigest()))
        counts = validation_counts(decisions)
        gates = validation_gates(protocol, counts, summaries[name]['format_alerts'])
        variants[name] = dict(entries=decisions, counts=counts, gates=gates,
                              eligible=all(gates.values()), output_sha256=sha(OUT / f'validation-{name}.json'))
        print(json.dumps(dict(variant=name, counts=counts, gates=gates)), flush=True)
    review = dict(schema=1, reviewer='assistant_meaning_review_with_exact_identity_reuse',
                  validation_is_development_data=True, variants=variants,
                  novel_decisions_sha256=sha(META / 'validation-novel-decisions.json'))
    write_new(META / 'validation-review.json', review)
    eligible = [variant for variant in protocol['variants'] if variants[variant['id']]['eligible']]
    assert eligible, 'No eligible variant; reject without opening controls or extending the grid.'
    eligible.sort(key=lambda variant: (
        variants[variant['id']]['counts']['known']['confirmed_errors_after'],
        -variants[variant['id']]['counts']['new']['complete_corrections'],
        -summaries[variant['id']]['chrfpp'], variant['strength']))
    selected = eligible[0]
    write_new(META / 'selection.json', dict(
        variant_id=selected['id'], strength=selected['strength'], protocol_sha256=sha(META / 'protocol.json'),
        validation_outputs_sha256=sha(OUT / f"validation-{selected['id']}.json"),
        validation_review_sha256=sha(META / 'validation-review.json'),
        frozen_before_control_generation=True, all_selection_gates_passed=True,
        selection_uses_controls_or_test_outputs=False, new_blind_test_chapters_opened=0))
    print(json.dumps(dict(state='selection_locked', selected=selected)), flush=True)


if __name__ == '__main__':
    main()
