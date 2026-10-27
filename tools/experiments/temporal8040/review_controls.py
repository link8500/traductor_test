"""Audit every control output; verdicts never feed the routing model."""
from collections import Counter

from tools.experiments.stability8035.core import ROOT, read, sha, write_new
from tools.experiments.qe8038.evaluate import key
from .route import META, OUT

ERRORS = {'incorrect', 'incomplete', 'failed_generation', 'quality_defect'}


def main():
    baseline = {(row['group'], row['id']): row for row in read(ROOT / 'benchmarks/qe8038/native-control-meaning-decisions.json')['entries']}
    reused = {(row['group'], row['id']): row for row in read(OUT / 'control-reused-decisions.json')}
    new = {(row['group'], row['id']): row for row in read(META / 'control-new-curation.json')['entries']}
    outputs = read(OUT / 'controls-candidate.json')
    rows = []
    for output in outputs:
        ident = output['group'], output['id']
        before = baseline[ident]
        if output['selected'] == 'native':
            assert key(output['source'], output['translation']) == before['key']
            verdict = before
            method = 'unchanged_native_source_output_identity'
        elif ident in reused:
            assert key(output['source'], output['translation']) == reused[ident]['key']
            verdict = reused[ident]['verdict']
            method = 'exact_source_and_reviewed_output_identity'
        else:
            verdict = new[ident]
            method = 'new_captured_source_meaning_review'
        status = verdict['status']
        if status == 'unreadable_source':
            status = 'needs_source_review'
        # Pairwise losses require comparison with the actual native output,
        # not merely reuse of an older candidate's absolute verdict.
        partial = ident in {('regression-core', 29), ('regression-core', 210)}
        note = verdict.get('note')
        if ident == ('regression-core', 29):
            note = 'The clipped source stays unresolved. Native DIO becomes DIO A CABO: the gave-out relation acquires a new malformed phrase, a partial quality/meaning deterioration.'
        elif ident == ('regression-core', 210):
            note = 'HERE is restored, but native SAZON becomes SAZONADOR, introducing a seasoning-substance versus cooking-skill uncertainty and an additional partial loss. Not a complete correction.'
        elif ident == ('regression-core', 5):
            note = 'Relative to actual native PIEL, selected PELAJE restores the fur attribute. The earlier ellipsis-only note belonged to another baseline and is not reused as a pairwise claim.'
        elif ident == ('regression-core', 146):
            note = 'Native already includes the initial question; changing NO to VERDAD is not a content correction.'
        rows.append(dict(group=ident[0], id=ident[1], source_output_key=key(output['source'], output['translation']),
                         selected=output['selected'], before=before['status'], after=status,
                         note=note, review_method=method, new_partial_loss=partial,
                         new_source_artifact=False))
    assert len(rows) == 258 and sum(row['selected'] != 'native' for row in rows) == 64
    counts = dict(inputs=len(rows), confirmed_errors_before=sum(row['before'] in ERRORS for row in rows),
                  confirmed_errors_after=sum(row['after'] in ERRORS for row in rows),
                  complete_corrections=sum(row['before'] in ERRORS and row['after'] == 'acceptable' for row in rows),
                  new_content_regressions=sum(row['before'] not in ERRORS and row['after'] in ERRORS for row in rows),
                  new_partial_losses=sum(row['new_partial_loss'] for row in rows),
                  new_source_artifacts=sum(row['new_source_artifact'] for row in rows),
                  new_context_uncertainties=sum(not row['before'].startswith('needs_') and row['after'].startswith('needs_') for row in rows),
                  unresolved_before=sum(row['before'].startswith('needs_') for row in rows),
                  unresolved_after=sum(row['after'].startswith('needs_') for row in rows),
                  switches=64, newly_reviewed_changed_outputs=11, reused_changed_outputs=53,
                  unchanged_native_outputs=194)
    write_new(META / 'control-meaning-review.json', dict(entries=rows, summary=counts,
        reviewer='assistant; not final human certification',
        evidence=[dict(path=str(path.relative_to(ROOT)), sha256=sha(path)) for path in
                  [OUT / 'controls-candidate.json', OUT / 'control-reused-decisions.json', META / 'control-new-curation.json']]))
    write_new(META / 'result.json', dict(experiment='8040', validation=read(META / 'validation-review.json')['summary'],
        controls=counts, quality_gates_passed=False, promoted=False,
        rejection_reason='Additional partial losses and new context uncertainties exceed frozen zero-tolerance control gates.',
        total_unique_evaluation_inputs=283, new_blind_test_chapters_opened=0,
        production_weights_modified=False, app_failure_probability=None, target_achieved=False))
    print(counts)


if __name__ == '__main__':
    main()
