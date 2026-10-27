"""Aggregate explicit meaning decisions; unreviewed rows cannot pass a gate."""
ERRORS = {'incorrect', 'incomplete', 'failed_generation'}
CONTEXT = {'needs_context', 'needs_source_review'}


def validation_counts(entries):
    result = {}
    for group in ['known', 'new']:
        rows = [row for row in entries if row['validation_group'] == group]
        assert len(rows) == (14 if group == 'known' else 11)
        assert len({row['id'] for row in rows}) == len(rows)
        assert all(row['reviewed'] and row['after'] in ERRORS | CONTEXT | {'acceptable'} for row in rows)
        result[group] = dict(
            pairs=len(rows),
            confirmed_errors_before=sum(row['before'] in ERRORS for row in rows),
            confirmed_errors_after=sum(row['after'] in ERRORS for row in rows),
            complete_corrections=sum(row['before'] in ERRORS and row['after'] == 'acceptable' for row in rows),
            new_content_regressions=sum(row['before'] not in ERRORS and row['after'] in ERRORS for row in rows),
            new_context_uncertainties=sum(row['before'] not in CONTEXT and row['after'] in CONTEXT for row in rows),
            context_uncertain=sum(row['after'] in CONTEXT for row in rows),
        )
    return result


def validation_gates(protocol, counts, format_alerts):
    rule = protocol['selection']
    known, new = counts['known'], counts['new']
    return dict(
        known_errors=known['confirmed_errors_after'] <= rule['known_validation_maximum_confirmed_errors'],
        new_net_fixes=new['complete_corrections'] - new['new_content_regressions'] >= rule['new_validation_minimum_net_complete_corrections'],
        no_new_validation_regressions=new['new_content_regressions'] <= rule['new_validation_maximum_new_content_regressions'],
        no_new_validation_context=new['new_context_uncertainties'] <= rule['new_validation_maximum_new_context_uncertainties'],
        no_known_validation_regressions=known['new_content_regressions'] <= rule['maximum_new_content_regressions_on_known_validation'],
        no_format_alerts=format_alerts <= rule['maximum_format_alerts'],
    )
