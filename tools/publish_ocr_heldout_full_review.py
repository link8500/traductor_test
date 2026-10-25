"""Score all held-out pixel crops; retain the earlier changed-only checkpoint."""
import collections
import html
import json
import pathlib

from audit_corpus_quality import ROOT, QA, atomic, digest, read, records
from evaluate_ocr_reader_comparison import compare


def main():
    folder = QA / 'ocr-reader-heldout8016'
    sample_path = folder / 'sample.json'
    sample = read(sample_path)
    manual_path = ROOT / 'benchmarks/full-comics/ocr8016-heldout-full-manual-transcriptions.json'
    manual = {row[0]: row for row in read(manual_path)}
    assert set(manual) == set(range(1,125))
    assert len(list(folder.glob('sheet-*.jpg'))) == 31
    assert digest(folder / 'provenance.json') == sample['provenance_sha256']
    consensus_path = folder / 'consensus/output.jsonl'
    consensus = {row['id']: row for row in records(consensus_path)}
    assert len(consensus) == 124
    proof = read(folder / 'consensus/sample.json')
    assert digest(consensus_path) == proof['output_sha256']
    native = {}
    for name, sha in sample['native_outputs_sha256'].items():
        path = folder / (name + '.jsonl')
        assert digest(path) == sha
        native[name] = {row['id']: row['grouped_reading'] for row in records(path)}
    entries = []
    # These crops have visible glyphs cut by a viewport edge. They remain
    # diagnostic evidence, and an additional uncut cohort is reported.
    clipped = [7,51,79,87]
    for case in sample['cases']:
        ident, truth, note = manual[case['id']]
        assert digest(pathlib.Path(case['preview'])) == case['preview_sha256']
        assert digest(pathlib.Path(case['source_page']['path'])) == case['source_page']['sha256']
        assert digest(folder / f'{ident:03d}.bgra') == case['pixels_sha256']
        assert all(case['readings'][name] == native[name][ident] for name in native)
        row = consensus[ident]
        assert row['base'] == case['readings']['current']
        readings = dict(case['readings'], conservative_consensus=row['selected'])
        entries.append(dict(id=ident, expected_visible_english=truth,
            edge_clipped=ident in clipped, note_es=note,
            readings=readings, models={name:compare(truth,text) for name,text in readings.items()}))
    cohorts = {}
    for name, selected in [('all_124_including_clipped_edges', entries),
                           ('uncut_120', [row for row in entries if not row['edge_clipped']])]:
        models = {}
        for model in entries[0]['models']:
            counts = collections.Counter()
            for row in selected:
                counts.update(row['models'][model]['edit_categories'])
            errors = sum(row['models'][model]['word_errors'] for row in selected)
            words = sum(row['models'][model]['expected_words'] for row in selected)
            failed = sum(row['models'][model]['word_errors'] > 0 for row in selected)
            models[model] = dict(expected_words=words,word_errors=errors,
                word_error_rate_percent=100*errors/words, crops_with_word_error=failed,
                crop_error_rate_percent=100*failed/len(selected),edit_categories=dict(counts),
                crops_fixed_vs_current=sum(row['models']['current']['word_errors']>0 and row['models'][model]['word_errors']==0 for row in selected),
                crops_regressed_vs_current=sum(row['models']['current']['word_errors']==0 and row['models'][model]['word_errors']>0 for row in selected))
        cohorts[name] = dict(crops=len(selected),models=models)
    value = dict(schema=1,crops_visually_reviewed=124,sheets_visually_inspected=31,
        prior_changed_crops_reviewed=12,additional_unchanged_crops_reviewed=112,
        words=sum(row['models']['current']['expected_words'] for row in entries),
        edge_clipped_crops=clipped,cohorts=cohorts,
        manual_sha256=digest(manual_path),sample_sha256=digest(sample_path),
        consensus_output_sha256=digest(consensus_path),policy_sha256=proof['policy_sha256'],
        native_provenance_sha256=sample['provenance_sha256'],native_outputs_sha256=sample['native_outputs_sha256'],
        earlier_changed_only_report_preserved=True,rule_frozen_before_location_selection=True,
        source_locations_disjoint_from_previous_744=True,manual_transcription_used_for_inference=False,
        screen_attempt_failure_probability=None,all_chapter_words_visually_reviewed=False,
        population_accuracy_estimate=False,application_modified=False,entries=entries)
    target = ROOT / 'benchmarks/full-comics/ocr8016-consensus-heldout-full-review.json'
    atomic(target,json.dumps(value,ensure_ascii=False,indent=2))
    metrics = cohorts['all_124_including_clipped_edges']['models']
    table = ''.join(f'<tr><td>{html.escape(name)}</td><td>{m["word_errors"]} / {m["expected_words"]}</td><td>{m["crops_with_word_error"]} / 124</td><td>{m["edit_categories"].get("omitted_word",0)}</td><td>{m["crops_fixed_vs_current"]} / {m["crops_regressed_vs_current"]}</td></tr>' for name,m in metrics.items())
    sheets = ''.join(f'<img loading="lazy" src="../sheet-{i:02d}.jpg" alt="Cotejo {i}">' for i in range(1,32))
    dest = folder / 'full-review';dest.mkdir(exist_ok=True)
    atomic(dest/'index.html',f'''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luma · Todas las lecturas del lote nuevo</title><style>body{{font:17px system-ui;background:#f1f4ed;color:#243b2b;margin:24px}}img{{display:block;width:100%;max-width:1600px;margin:24px auto}}p{{line-height:1.6;max-width:1100px}}table{{border-collapse:collapse;background:white}}td,th{{border:1px solid #bbb;padding:12px}}</style><h1>Reconocimiento · 124 ubicaciones nuevas cotejadas completas</h1><p>Se transcribieron y cotejaron las palabras visibles de los 124 recortes: los doce cambios anteriores y las otras 112 lecturas sin cambios. La regla estaba congelada antes de elegir ubicaciones y ejecutar los lectores; las respuestas manuales no entraron a la inferencia. El informe anterior de solo doce cambios se conserva.</p><table><tr><th>Lector</th><th>Errores / palabras</th><th>Recortes con algún error</th><th>Palabras omitidas</th><th>Corregidos / empeorados frente a la base</th></tr>{table}</table><p>Hay cuatro recortes con algún renglón cortado por el borde; el JSON separa los otros 120. Esta prueba diagnostica reconocimiento de regiones, sin aprobar traducciones ni pantallas completas. Una onomatopeya puede conservarse. El consenso sigue separado de la app y no se atribuye a la versión Windows distribuida.</p><p><a href="../../metrics/index.html">Resultados agregados</a> · <a href="../consensus/index.html">Punto de control anterior: doce cambios</a></p>{sheets}</html>''')
    print(json.dumps({k:v for k,v in value.items() if k!='entries'}),flush=True)


if __name__ == '__main__':
    main()
