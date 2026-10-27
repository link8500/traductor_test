"""Select unchanged candidate text, with the production engine as default."""
import math

from .policy import choose
from tools.experiments.stability8035.core import format_issues


def select(source, candidates, scores, margin):
    assert candidates and candidates[0]['name'] == 'native'
    baseline = candidates[0]
    alternatives = [row for row in candidates[1:]
                    if row['translation'] != baseline['translation']
                    and not format_issues(source, row['translation'])
                    and scores.get(row['name']) is not None
                    and math.isfinite(scores[row['name']])]
    if not alternatives:
        unscored_valid = any(row['translation'] != baseline['translation']
                             and not format_issues(source, row['translation'])
                             for row in candidates[1:])
        return dict(selected='native', translation=baseline['translation'], reason='no_scored_valid_alternative',
                    unresolved=bool(format_issues(source, baseline['translation'])) or unscored_valid)
    # Stable max retains the fixed lower-complexity pool order for equal scores.
    alternative = max(alternatives, key=lambda row: scores[row['name']])
    decision = choose(source, baseline['translation'], alternative['translation'],
                      scores.get('native'), scores[alternative['name']], margin)
    selected = alternative if decision['selected'] == 'candidate' else baseline
    return dict(selected=selected['name'], translation=selected['translation'],
                reason=decision['reason'], unresolved=decision['unresolved'])
