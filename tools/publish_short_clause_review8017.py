"""Publish the guarded, unshipped short-clause development experiment."""
import collections
import json
from audit_corpus_quality import ROOT, QA, atomic, digest, read


def main():
    folder = QA/'short-clause8017-guarded'
    review = folder/'visual-review'
    sample = read(review/'sample.json')
    manual_path = review/'manual-decisions.json'
    manual = read(manual_path)
    assert len(manual) == len(sample['cases']) == 14
    entries = []
    for case, (ident, before, after, note) in zip(sample['cases'], manual):
        assert ident == case['id']
        entries.append(dict(case, before=before, after=after, note_es=note,
            original_and_reference_pixels_inspected=True, meaning_reviewed=True))
    b = collections.Counter(e['before'] for e in entries)
    a = collections.Counter(e['after'] for e in entries)
    value = dict(schema=1, status='development_candidate_not_in_application',
        reviewed_changed_locations=14, before_not_approved=14-b['acceptable'],
        after_not_approved=14-a['acceptable'], before_categories=dict(b), after_categories=dict(a),
        corrected=sum(e['before']!='acceptable' and e['after']=='acceptable' for e in entries),
        regressed=sum(e['before']=='acceptable' and e['after']!='acceptable' for e in entries),
        original_and_reference_sheets_inspected=4, candidate_locations_planned=1008,
        newly_affected_native_inferences=19, native_guards=15,
        rejected_unprotected_candidate_repetition_retained=True,
        manual_sha256=digest(manual_path), sample_sha256=digest(review/'sample.json'),
        provenance_sha256=digest(folder/'provenance.json'), native_inferences_sha256=digest(folder/'inferences.jsonl'),
        model_weights_changed=False, included_in_application=False,
        all_planned_location_meanings_reviewed=False, independent_validation=False,
        screen_attempt_failure_probability=None, population_accuracy_estimate=False, entries=entries)
    atomic(ROOT/'benchmarks/full-comics/short-clause8017-candidate-semantic-review.json', json.dumps(value, ensure_ascii=False, indent=2))
    images = ''.join(f'<img loading="lazy" src="sheet-{i:02d}.jpg" alt="Comparación {i}">' for i in range(1,5))
    atomic(review/'index.html', f'''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luma · frases cortas en prueba</title><style>body{{font:17px system-ui;background:#f1f4ed;color:#243b2b;margin:24px}}img{{display:block;width:100%;max-width:1600px;margin:24px auto}}p{{line-height:1.6;max-width:1100px}}</style><h1>Recuperación de frases cortas · candidato sin incorporar</h1><p>Se planificaron 1.008 fuentes reales; 19 activaron nuevos reintentos nativos y 14 cambiaron de salida. Se inspeccionaron las 14 con los píxeles originales y la referencia de Olympus: <b>{value['before_not_approved']} → {value['after_not_approved']} sin aprobar</b>, {value['corrected']} correcciones completas y {value['regressed']} regresiones observadas. Cinco traducciones conservan errores y permanecen pendientes.</p><p>El primer candidato produjo repeticiones excesivas y se rechazó. La revisión con 15 guardas vuelve al resultado previo si un reintento repite frases artificialmente. Este candidato todavía no está incorporado a Windows. Sus datos son de desarrollo: no representan validación independiente ni la probabilidad de fallo por uso. No se aprueban por extensión las otras salidas.</p><p><a href="../../metrics/index.html">Resultados agregados</a></p>{images}</html>''')
    print(json.dumps({k:v for k,v in value.items() if k!='entries'}), flush=True)


if __name__ == '__main__':
    main()
