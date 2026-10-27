"""Fixed inverse-only and agreement rules, with native output as default."""
import math

from tools.experiments.stability8035.core import format_issues


def choose(pool, inverse, qe, *, consensus):
    baseline = pool['candidates'][0]
    assert baseline['name'] == 'native'
    options = []
    for candidate in pool['candidates'][1:]:
        name = candidate['name']
        if candidate['translation'] == baseline['translation'] or format_issues(pool['source'], candidate['translation']):
            continue
        if inverse.get(name) is None or inverse.get('native') is None:
            continue
        if not (math.isfinite(inverse[name]) and inverse[name] > inverse['native']):
            continue
        if consensus and (qe.get(name) is None or qe.get('native') is None or
                          not math.isfinite(qe[name]) or not qe[name] > qe['native']):
            continue
        options.append(candidate)
    winner = max(options, key=lambda row: inverse[row['name']]) if options else baseline
    return dict(selected=winner['name'], translation=winner['translation'],
                invalid_selected_format=bool(format_issues(pool['source'], winner['translation'])))
