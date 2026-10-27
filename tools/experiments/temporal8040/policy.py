"""Inverse likelihood with a fixed, conservative temporal-retention veto."""
import math

from tools.experiments.stability8035.core import format_issues


def choose(pool, scores, profiles):
    native = pool['candidates'][0]
    assert native['name'] == 'native'
    required = set(profiles['native']['categories'])
    options, blocked = [], []
    for candidate in pool['candidates'][1:]:
        name = candidate['name']
        if candidate['translation'] == native['translation'] or format_issues(pool['source'], candidate['translation']):
            continue
        score, baseline = scores.get(name), scores.get('native')
        if score is None or baseline is None or not math.isfinite(score) or not math.isfinite(baseline) or score <= baseline:
            continue
        missing = required - set(profiles[name]['categories'])
        if missing:
            blocked.append(dict(name=name, missing_categories=sorted(missing)))
        else:
            options.append(candidate)
    winner = max(options, key=lambda row: scores[row['name']]) if options else native
    return dict(selected=winner['name'], translation=winner['translation'], temporal_vetoes=blocked)
