"""Routing uses only source, alternatives and QE estimates; never reviewed answers."""
import math

from tools.experiments.stability8035.core import format_issues


def choose(source, baseline, candidate, baseline_score, candidate_score, margin):
    assert margin >= 0
    base_invalid = bool(format_issues(source, baseline))
    candidate_invalid = bool(format_issues(source, candidate))
    if baseline == candidate:
        return dict(selected='base', reason='identical_outputs', unresolved=base_invalid)
    if candidate_invalid:
        return dict(selected='base', reason='candidate_invalid_format', unresolved=base_invalid)
    if base_invalid:
        return dict(selected='candidate', reason='baseline_invalid_format', unresolved=False)
    if baseline_score is None or candidate_score is None:
        return dict(selected='base', reason='quality_estimate_unavailable', unresolved=True)
    if not (math.isfinite(baseline_score) and math.isfinite(candidate_score)):
        return dict(selected='base', reason='nonfinite_quality_estimate', unresolved=True)
    if candidate_score > baseline_score + margin:
        return dict(selected='candidate', reason='quality_margin_exceeded', unresolved=False)
    return dict(selected='base', reason='retain_baseline', unresolved=False)
