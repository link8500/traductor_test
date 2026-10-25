"""Publish manual geometry trial review without counting identical results twice."""
import argparse
import collections
import json
from audit_corpus_quality import ROOT, QA, CLEAR_ERRORS, atomic, digest, read


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--final',action='store_true');parser.add_argument('--render',action='store_true');args=parser.parse_args()
    folder='windows8017-render-heldout-pixels' if args.render else 'windows8017-final-heldout-pixels' if args.final else 'windows8017-preserve-heldout-pixels'
    review = QA/folder/'visual-review'
    sample = read(review/'sample.json')
    previous_path = ROOT/'benchmarks/full-comics/windows8016-heldout-semantic-review.json'
    assert digest(previous_path) == sample['previous_semantic_review_sha256']
    old = read(previous_path)
    before = QA/'windows8016-heldout-pixels/summary.json'
    current = QA/folder/'summary.json'
    assert digest(before) == sample['baseline_summary_sha256']
    assert digest(current) == sample['current_summary_sha256']
    manual_path = review/'manual-decisions.json'
    decisions = {row[0]: row for row in read(manual_path)}
    reuse_path=review/'judgment-reuse-provenance.json'
    reuse=read(reuse_path) if reuse_path.exists() else None
    if reuse:
        assert reuse['identical_candidate_outputs_and_original_reference_pixels_verified']
        assert digest(current.parent/'output.jsonl')==reuse['final_native_output_sha256']
    cases = {case['location_id']: case for case in sample['cases']}
    assert set(decisions) == {case['id'] for case in cases.values()}
    identical = {case['id']: case for case in sample['reused_identical_location_outputs']}
    assert len(cases)+len(identical) == 124
    entries = []
    for entry in old['entries']:
        ident = entry['id']
        new = dict(entry, before=entry['after'], before_translation=entry['translation'])
        if ident in cases:
            case = cases[ident]
            _, judgment, note = decisions[case['id']]
            assert judgment in {'acceptable','incorrect','incomplete','fragmented','needs_improvement'}
            new.update(after=judgment, translation=case['translation'], note_es=note,
                changed_output_reinspected_against_both_pixel_references=not bool(reuse),
                meaning_judgment_reused_from_identical_trial_output=bool(reuse),
                before_judgment_reused_only_when_actual_output_identical=False)
        else:
            assert entry['current_source'] == identical[ident]['source']
            assert entry['translation'] == ' '.join(identical[ident]['translations'])
            new.update(before_judgment_reused_only_when_actual_output_identical=True)
        entries.append(new)
    cohorts = {}
    for name, selected in [('all_124_including_clipped_edges', entries),
                           ('uncut_120', [e for e in entries if not e['edge_clipped']])]:
        b = collections.Counter(e['before'] for e in selected)
        a = collections.Counter(e['after'] for e in selected)
        count = len(selected)
        old_errors, new_errors = count-b['acceptable'], count-a['acceptable']
        cohorts[name] = dict(locations=count, before_categories=dict(b), after_categories=dict(a),
            before_clear_errors=sum(b[k] for k in CLEAR_ERRORS), after_clear_errors=sum(a[k] for k in CLEAR_ERRORS),
            before_not_approved=old_errors, after_not_approved=new_errors,
            corrected=sum(e['before']!='acceptable' and e['after']=='acceptable' for e in selected),
            regressed=sum(e['before']=='acceptable' and e['after']!='acceptable' for e in selected),
            relative_unapproved_reduction_percent=100*(old_errors-new_errors)/old_errors)
    value = dict(schema=1, platform='Windows', before_build='801601', after_build='801704' if args.render else '801703' if args.final else '801702',
        reviewed_locations=124, chapters_sampled=124, changed_locations_reinspected=len(cases),
        identical_location_judgments_reused=len(identical), all_124_original_source_strings_preserved=True,
        cohorts=cohorts, entries=entries, original_semantic_review_sha256=digest(previous_path),
        manual_sha256=digest(manual_path), sample_sha256=digest(review/'sample.json'),
        baseline_summary_sha256=digest(before), current_summary_sha256=digest(current),
        native_output_sha256=digest(current.parent/'output.jsonl'),
        naive_trial_rejected_due_to_recognition_regression=True, model_weights_changed=False,
        experimental_ocr_consensus_included=False, experimental_short_clause_policy_included=False,
        strict_approval_requires_acceptable=True, onomatopoeia_may_remain_unchanged=True,
        all_chapter_words_visually_reviewed=False, population_accuracy_estimate=False,
        screen_attempt_failure_probability=None, target_achieved=False)
    if reuse:
        value['identical_trial_judgment_reuse_sha256']=digest(reuse_path)
        value['meaning_judgments_reused_from_identical_candidate']=len(cases)
        value['current_native_render_pairs_inspected']=reuse['current_render_pairs_inspected']
    report_name='windows8017-render-geometry-semantic-review.json' if args.render else 'windows8017-final-geometry-semantic-review.json' if args.final else 'windows8017-geometry-semantic-review.json'
    atomic(ROOT/'benchmarks/full-comics'/report_name, json.dumps(value, ensure_ascii=False, indent=2))
    metrics = cohorts['all_124_including_clipped_edges']
    images = ''.join(f'<img loading="lazy" src="sheet-{i:02d}.jpg" alt="Comparación {i}">' for i in range(1,(len(cases)+1)//2+1))
    atomic(review/'index.html', f'''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luma · Windows 8017</title><style>body{{font:17px system-ui;background:#f1f4ed;color:#243b2b;margin:24px}}img{{display:block;width:100%;max-width:1600px;margin:24px auto}}p{{line-height:1.6;max-width:1100px}}</style><h1>Windows · unión de renglones con lectura conservada</h1><p>Los dos binarios procesaron los mismos 124 recortes originales. El texto reconocido, incluida su puntuación, permanece idéntico en las 124 ubicaciones. Cambió la traducción de diez; se cotejaron de nuevo esas diez con el original y Olympus. Las otras 114 conservan exactamente su salida anterior y su dictamen manual.</p><p><b>{metrics['before_not_approved']} → {metrics['after_not_approved']} traducciones sin aprobar</b>, {metrics['corrected']} correcciones completas y {metrics['regressed']} regresiones observadas. Reducción relativa de {metrics['relative_unapproved_reduction_percent']:.1f} % en este mismo lote de 124 recortes. Quedan {metrics['after_clear_errors']} errores claros y {metrics['after_categories'].get('needs_improvement',0)} casos que requieren mejora.</p><p>La primera implementación alteró una lectura y se descartó. La revisión conservadora mantiene todas las lecturas originales antes de unir globos. No cambiaron los pesos ni se incorporaron los candidatos de OCR o recuperación de frases cortas. Estas cifras no miden pantallas completas ni todas las palabras de los capítulos; el objetivo de menos del 5 % de usos fallidos sigue sin acreditarse.</p><p><a href="../../metrics/index.html">Resultados agregados</a> · <a href="../paint/index.html">Superposición real del motor</a></p>{images}</html>''')
    print(json.dumps({k:v for k,v in value.items() if k!='entries'}), flush=True)


if __name__ == '__main__':
    main()
