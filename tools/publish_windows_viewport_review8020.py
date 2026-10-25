"""Publish the full visible-dialogue inventory and all124 paired judgments.

This cohort is 124 fixed reading viewports, not complete chapters or live uses.
Every unchanged output was reviewed against its own full original inventory.
"""
import collections
import html
import json
from audit_corpus_quality import ROOT, QA, atomic, digest, read, records


def main():
    inventory_path = ROOT / 'benchmarks/full-comics/viewport8020-original-inventory.json'
    decisions_path = ROOT / 'benchmarks/full-comics/viewport8020-meaning-decisions.json'
    inventory = read(inventory_path)
    decisions = read(decisions_path)
    assert inventory['all124_original_inventories_complete'] and decisions['all124_complete']
    assert [r['id'] for r in inventory['entries']] == list(range(1, 125))
    assert [r[0] for r in decisions['entries']] == list(range(1, 125))
    variants = {name: records(QA / ('windows8020-full-viewports-' + name) / 'output.jsonl')
                for name in ['baseline', 'consensus']}
    assert len(variants['baseline']) == len(variants['consensus']) == 228
    for a, b in zip(variants['baseline'], variants['consensus']):
        assert (a['image'], a['bounds'], a['source']) == (b['image'], b['bounds'], b['before_consensus'])
    entries = []
    for original, judgment in zip(inventory['entries'], decisions['entries']):
        ident, before, after, note = judgment
        assert before in ['acceptable', 'incorrect', 'incomplete', 'needs_review', 'clipped']
        assert after in ['acceptable', 'incorrect', 'incomplete', 'needs_review', 'clipped']
        outputs = {name: [r for r in rows if r['image'] == ident] for name, rows in variants.items()}
        entries.append(dict(original, before=before, after=after, note=note,
            baseline_outputs=outputs['baseline'], consensus_outputs=outputs['consensus'],
            all_visible_dialogue_inventoried=True, both_output_meanings_reviewed=True,
            painting_visually_reviewed=False))
    cohorts = {}
    for name, rows in [('all124_fixed_reading_viewports', entries),
                       ('no_visible_dialogue_clipped', [r for r in entries if not r['visible_dialogue_clipped']])]:
        b = collections.Counter(r['before'] for r in rows)
        a = collections.Counter(r['after'] for r in rows)
        be, ae = len(rows) - b['acceptable'], len(rows) - a['acceptable']
        cohorts[name] = dict(viewports=len(rows), before_categories=dict(b), after_categories=dict(a),
            before_not_approved=be, after_not_approved=ae,
            corrected=sum(r['before'] != 'acceptable' and r['after'] == 'acceptable' for r in rows),
            regressed=sum(r['before'] == 'acceptable' and r['after'] != 'acceptable' for r in rows),
            relative_unapproved_reduction_percent=100 * (be - ae) / be if be else None)
    value = dict(schema=1, before_build='801901', after_build='802001',
        viewports=124, native_regions=228, all_original_visible_dialogue_inventoried=True,
        all124_paired_meanings_reviewed=True, unchanged_full_viewports_independently_reviewed=True,
        judgment_reused_from_crop_cohorts=False, cohorts=cohorts, entries=entries,
        inventory_sha256=digest(inventory_path), manual_sha256=digest(decisions_path),
        native_outputs={name: digest(QA / ('windows8020-full-viewports-' + name) / 'output.jsonl') for name in variants},
        native_provenance={name: digest(QA / ('windows8020-full-viewports-' + name) / 'provenance.json') for name in variants},
        sfx_omissions_exempt=True, sfx_corruptions_separately_noted=True,
        layout_all124_visually_reviewed=False, live_worker_enabled=False,
        complete_chapter_traversal=False, all_chapter_words_visually_reviewed=False,
        saved_viewport_selection_anchored_to_previous_detection=True, population_accuracy_estimate=False,
        complete_app_use_including_capture_toolbar_and_movement=False,
        screen_attempt_failure_probability=None, target_achieved=False, ready_for_release=False)
    target = ROOT / 'benchmarks/full-comics/windows8020-full-viewports-semantic-review.json'
    atomic(target, json.dumps(value, ensure_ascii=False, indent=2))
    folder = QA / 'windows8020-full-viewports-review'
    m = cohorts['all124_fixed_reading_viewports']
    details = []
    for row in entries:
        text = ' '.join(row['dialogue'])
        old = ' / '.join(r['translation'] for r in row['baseline_outputs'])
        new = ' / '.join(r['translation'] for r in row['consensus_outputs'])
        details.append(f'<details><summary>Vista {row["id"]} · {row["before"]} → {row["after"]}</summary>'
            f'<p><b>Original inventariado:</b> {html.escape(text)}</p><p><b>Anterior:</b> {html.escape(old)}</p>'
            f'<p><b>Ensayo:</b> {html.escape(new)}</p><p>{html.escape(row["note"])}</p>'
            f'<div><img loading="lazy" src="../recovery-viewports801201/{row["id"]:03d}.png" alt="Original">'
            f'<img loading="lazy" src="consensus/{row["id"]:03d}.jpg" alt="Superposición nativa pendiente de revisión visual"></div></details>')
    atomic(folder / 'index.html', '<!doctype html><html lang="es"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>Luma · vistas completas</title>'
        '<style>body{font:17px system-ui;background:#f1f4ed;color:#243b2b;margin:24px}p{max-width:1100px;line-height:1.6}'
        'details{margin:18px 0;border:1px solid #abc;padding:15px}div{display:flex}img{width:48%;object-fit:contain;align-self:start}</style>'
        f'<h1>124 vistas de lectura · inventario completo del diálogo visible</h1><p><b>{m["before_not_approved"]} → {m["after_not_approved"]} sin aprobar</b>; '
        f'{m["corrected"]} correcciones completas, {m["regressed"]} regresiones; reducción relativa del {m["relative_unapproved_reduction_percent"]:.2f} % '
        'en este mismo lote. Se inspeccionaron los 124 originales y todos los significados, incluidos los resultados sin cambios. '
        'Las capturas con diálogo cortado conservan su limitación. Las onomatopeyas no requieren traducción.</p>'
        '<p>La superposición fue exportada por ambos ejecutables reales, pero su revisión visual completa sigue pendiente. '
        'Son vistas guardadas, una por capítulo: no son todos los textos de los capítulos ni usos completos en vivo. '
        'La variante permanece desactivada en el uso normal y no está lista para publicar. El objetivo de menos del 5 % no está acreditado.</p>'
        '<p><a href="../metrics/index.html">Resultados agregados</a></p>' + ''.join(details) + '</html>')
    print(json.dumps(dict(cohorts=cohorts, report_sha256=digest(target), ready_for_release=False)), flush=True)


if __name__ == '__main__':
    main()
