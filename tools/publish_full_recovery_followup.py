"""Finish the old full124 OCR control with strict, non-overlapping counts."""
import collections
import json
import pathlib
from audit_corpus_quality import ROOT,QA,CLEAR_ERRORS,atomic,digest,read,records


def main():
    folder=QA/'full8012-review-checkpoint02';follow=folder/'followup'
    sample=read(folder/'sample.json');new=read(follow/'sample.json')
    assert digest(folder/'sample.json')==new['checkpoint02_sample_sha256']
    old_folder=QA/'full8012-review-checkpoint01'
    assert digest(old_folder/'sample.json')==new['old_sample_sha256']
    assert digest(old_folder/'manual-decisions.json')==new['old_manual_sha256']
    manual_path=follow/'manual-decisions.json';manual={r[0]:r for r in read(manual_path)}
    assert set(manual)=={c['id'] for c in new['cases']} and len(manual)==51
    decided={}
    for row in new['reused_changed_pixel_judgments']:
        assert row['exact_source_output_pixels'];decided[row['checkpoint02_case_id']]=row['decision'][1:]
    revisions=[]
    for case in new['cases']:
        decided[case['checkpoint02_case_id']]=manual[case['id']][1:]
        for key in ['source_page','reference_page']:
            page=case[key];assert digest(pathlib.Path(page['path']))==page['sha256']
        # An identical wrong idiom was previously labelled a mild defect.
        # Correct the judgment explicitly; do not call it a code regression.
        if case['id']==42:
            assert case['before_translation']==case['translation'] and case['before_judgment']=='needs_improvement'
            revisions.append(dict(original_id=case['original_id'],previous='needs_improvement',revised='incorrect',
                reason_es='La misma salida confunde lograr algo con hacerlo pasar; cambia el significado antes y después.'))
    changed={c['original_id']:c for c in sample['cases']}
    previous_path=ROOT/'benchmarks/full-comics/current8011-six-regions-semantic-review.json'
    assert digest(previous_path)==sample['previous_review_sha256']
    old={e['id']:e for e in read(previous_path)['entries']};reports={}
    for chapter,proof in sample['frozen_reports'].items():
        path=QA/'translated-en8012-recovery'/(chapter+'-en.jsonl')
        assert digest(path)==proof['report_sha256'] and digest(path.with_name(path.stem+'.done.json'))==proof['done_sha256']
        reports[chapter]=records(path)
    entries=[]
    for pair in sample['all_pairs']:
        prior=old[pair['id']];assert prior['translation']==pair['before_translation']
        rows=[reports[pair['chapter']][i] for i in pair['selected_regions']]
        assert pair['source']==' '.join(r['source'] for r in rows) and pair['translation']==' '.join(r['translation'] for r in rows)
        before=pair['before_judgment'];after=before;note='Fuente y salida idénticas; se conserva el dictamen anterior.'
        if pair['id'] in changed:after,note=decided[changed[pair['id']]['id']]
        if any(r['original_id']==pair['id'] for r in revisions):before='incorrect'
        entries.append(dict(**pair,before=before,after=after,note_es=note))
    selected=[e for e in entries if not e['comparison_excluded'] and 'unresolved' not in (e['before'],e['after'])]
    b=collections.Counter(e['before'] for e in selected);a=collections.Counter(e['after'] for e in selected)
    metrics=dict(comparable_regions=len(selected),excluded_unresolved_regions=len(entries)-len(selected),
        before_categories=dict(b),after_categories=dict(a),
        before_not_approved=len(selected)-b['acceptable'],after_not_approved=len(selected)-a['acceptable'],
        corrected=sum(e['before']!='acceptable' and e['after']=='acceptable' for e in selected),
        regressed=sum(e['before']=='acceptable' and e['after']!='acceptable' for e in selected),
        before_clear_errors=sum(b[k] for k in CLEAR_ERRORS),after_clear_errors=sum(a[k] for k in CLEAR_ERRORS))
    assert metrics['before_not_approved']-metrics['after_not_approved']==metrics['corrected']-metrics['regressed']
    value=dict(schema=1,reviewed_locations=744,chapters_sampled=124,changed_locations=99,
        newly_changed_pixel_locations_inspected=51,prior_changed_pixel_judgments_reused=48,
        unchanged_same_location_judgments_reused=645,metrics=metrics,explicit_judgment_revisions=revisions,
        sample_sha256=digest(folder/'sample.json'),followup_sample_sha256=digest(follow/'sample.json'),
        manual_sha256=digest(manual_path),previous_review_sha256=digest(previous_path),
        older_control_build='801201 OCR and frozen8011 NMT',current_application_build=False,
        strict_approval_requires_acceptable=True,onomatopoeia_may_remain_unchanged=True,
        overlaps_with_other_samples_do_not_add=True,all_chapter_words_visually_reviewed=False,
        population_accuracy_estimate=False,screen_attempt_failure_probability=None,entries=entries)
    atomic(ROOT/'benchmarks/full-comics/full8012-checkpoint02-semantic-review.json',json.dumps(value,ensure_ascii=False,indent=2))
    images=''.join(f'<img loading="lazy" src="sheet-{i:02d}.jpg" alt="Comparación {i}">' for i in range(1,14))
    atomic(follow/'index.html',f'''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luma · control ampliado</title><style>body{{font:17px system-ui;background:#f1f4ed;color:#243b2b;margin:24px}}img{{display:block;max-width:100%;margin:24px auto}}p{{max-width:1100px;line-height:1.6}}</style><h1>Control anterior completo · 744 ubicaciones</h1><p>Terminaron los archivos de los 124 capítulos del control congelado. Se inspeccionaron las 51 ubicaciones modificadas que faltaban; otras 48 conservan cotejos anteriores con los mismos píxeles y salidas, y 645 son idénticas en la misma ubicación. Hay {metrics['comparable_regions']} comparaciones válidas y {metrics['excluded_unresolved_regions']} excluidas por evidencia insuficiente.</p><p>Con aprobación estricta: <b>{metrics['before_not_approved']} → {metrics['after_not_approved']} sin aprobar</b>, {metrics['corrected']} correcciones completas y {metrics['regressed']} regresiones observadas. Se rectificó explícitamente un dictamen de la misma frase incorrecta antes y después; no es una regresión del código. Los agradecimientos y preguntas omitidos permanecen como errores.</p><p>Este es un control anterior de OCR8012 y traductor congelado8011; no mide Windows8018, no se suma a otros lotes que comparten ubicaciones ni aprueba todas las palabras de los capítulos. La probabilidad de fallo por pantalla sigue sin medirse.</p><p><a href="../../metrics/index.html">Resultados agregados</a></p>{images}</html>''')
    print(json.dumps({k:v for k,v in value.items() if k!='entries'}),flush=True)


if __name__=='__main__':main()
