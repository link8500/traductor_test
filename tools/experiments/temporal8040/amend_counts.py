"""Correct legacy unreadable-source status normalization, preserving v1 evidence."""
from tools.experiments.stability8035.core import ROOT, read, sha, write_new
from .route import META


def uncertainty(status):
    return status == 'unreadable_source' or status.startswith('needs_')


def main():
    prior = read(META / 'control-meaning-review.json')
    rows = prior['entries']
    summary = dict(prior['summary'])
    summary.update(new_context_uncertainties=sum(not uncertainty(row['before']) and uncertainty(row['after']) for row in rows),
                   unresolved_before=sum(uncertainty(row['before']) for row in rows),
                   unresolved_after=sum(uncertainty(row['after']) for row in rows))
    amendment = dict(reason='Legacy unreadable_source and needs_source_review denote the same unresolved source category. V1 normalized only the after status and incorrectly counted one unchanged output as a new uncertainty.',
                     previous_review_sha256=sha(META / 'control-meaning-review.json'),
                     semantic_decisions_changed=False, selected_outputs_changed=False)
    write_new(META / 'control-meaning-review-v2.json', dict(**{key: value for key, value in prior.items() if key != 'summary'},
                                                           summary=summary, amendment=amendment))
    result = read(META / 'result.json')
    result.update(controls=summary, count_amendment=amendment)
    write_new(META / 'result-v2.json', result)
    print(summary)


if __name__ == '__main__':
    main()
