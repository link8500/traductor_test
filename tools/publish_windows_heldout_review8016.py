"""Publish full manual meaning review of124 paired real Windows crop results."""
import collections
import json
import pathlib
from audit_corpus_quality import ROOT,QA,CLEAR_ERRORS,atomic,digest,read,records


def main():
    folder=QA/'windows8016-heldout-pixels';review=folder/'visual-review'
    sample=read(review/'sample.json');manual_path=review/'manual-decisions.json'
    manual={row[0]:row for row in read(manual_path)}
    old_manual_path=review/'baseline-change-decisions.json'
    old_manual={row[0]:row for row in read(old_manual_path)}
    app=read(folder/'summary.json');assert digest(folder/'summary.json')==sample['windows_summary_sha256']
    before_path=QA/'windows8015-heldout-pixels/output.jsonl';after_path=folder/'output.jsonl'
    before=records(before_path);after=records(after_path)
    assert len(before)==len(after)==158 and set(manual)==set(range(1,125))
    old=collections.defaultdict(list);new=collections.defaultdict(list)
    for a,b in zip(before,after):
        assert all(a[k]==b[k] for k in ['image','source','bounds'])
        old[a['image']].append(a['translation']);new[b['image']].append(b['translation'])
    changed={key for key in old if old[key]!=new[key]};assert changed==set(old_manual)
    assert len(list(review.glob('sheet-*.jpg')))==31
    entries=[]
    for case in sample['cases']:
        ident,judgment,alignment,note=manual[case['id']]
        assert judgment in {'acceptable','incorrect','incomplete','fragmented','needs_improvement'}
        for key in ['source_page','reference_page']:
            page=case[key];assert digest(pathlib.Path(page['path']))==page['sha256']
        previous=old_manual[ident][1] if ident in changed else judgment
        entries.append(dict(id=ident,chapter=case['chapter'],source_image=case['source_image'],bounds=case['bounds'],
            original_pixels_inspected=True,reference_pixels_inspected=True,
            reference_artwork_alignment_verified=True,reference_translation_edition_difference=alignment=='aligned_edition_difference',
            before=previous,after=judgment,before_translation=' '.join(old[ident]),translation=' '.join(new[ident]),
            current_source=case['actual_windows']['source'],note_es=note,
            before_judgment_reused_only_when_actual_output_identical=ident not in changed,
            edge_clipped=ident in [7,51,79,87]))
    cohorts={}
    for name,selected in [('all_124_including_clipped_edges',entries),('uncut_120',[e for e in entries if not e['edge_clipped']])]:
        b=collections.Counter(e['before'] for e in selected);a=collections.Counter(e['after'] for e in selected)
        cohorts[name]=dict(locations=len(selected),before_categories=dict(b),after_categories=dict(a),
            before_clear_errors=sum(b[k] for k in CLEAR_ERRORS),after_clear_errors=sum(a[k] for k in CLEAR_ERRORS),
            before_not_approved=len(selected)-b['acceptable'],after_not_approved=len(selected)-a['acceptable'],
            corrected=sum(e['before']!='acceptable' and e['after']=='acceptable' for e in selected),
            regressed=sum(e['before']=='acceptable' and e['after']!='acceptable' for e in selected))
    value=dict(schema=1,platform='Windows',before_build='801501',after_build='801601',
        reviewed_locations=124,chapters_sampled=124,original_and_reference_sheets_inspected=31,
        unchanged_location_judgments_visually_inspected=124-len(changed),changed_locations_reinspected=len(changed),
        cohorts=cohorts,strict_approval_requires_acceptable=True,minor_style_differences_allowed=True,
        onomatopoeia_may_remain_unchanged=True,reference_numbers_do_not_override_original_pixels=True,
        manual_sha256=digest(manual_path),baseline_manual_sha256=digest(old_manual_path),sample_sha256=digest(review/'sample.json'),
        native_before_output_sha256=digest(before_path),native_after_output_sha256=digest(after_path),
        model_weights_changed=False,screen_attempt_failure_probability=None,
        all_chapter_words_visually_reviewed=False,population_accuracy_estimate=False,entries=entries)
    atomic(ROOT/'benchmarks/full-comics/windows8016-heldout-semantic-review.json',json.dumps(value,ensure_ascii=False,indent=2))
    metrics=cohorts['all_124_including_clipped_edges']
    images=''.join(f'<img loading="lazy" src="sheet-{i:02d}.jpg" alt="Comparación {i}">' for i in range(1,32))
    atomic(review/'index.html',f'''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luma · Traducciones reales de Windows</title><style>body{{font:17px system-ui;background:#f1f4ed;color:#243b2b;margin:24px}}img{{display:block;width:100%;max-width:1600px;margin:24px auto}}p{{line-height:1.6;max-width:1100px}}</style><h1>Windows · 124 ubicaciones nuevas cotejadas con los originales</h1><p>Ambos binarios reales procesaron los mismos píxeles originales sin recibir referencias ni respuestas. Se inspeccionaron todas las salidas de Windows8016 junto al original y la propuesta de Olympus, incluidas las salidas sin cambios. El único cambio frente a Windows8015 se cotejó también con su salida anterior.</p><p>Con aprobación estricta del contenido: <b>{metrics['before_not_approved']} → {metrics['after_not_approved']} traducciones sin aprobar de 124</b>, {metrics['corrected']} corregidas y {metrics['regressed']} regresiones. Dentro de las actuales hay {metrics['after_clear_errors']} errores claros y {metrics['after_categories'].get('needs_improvement',0)} casos que requieren mejora; ambos grupos quedan pendientes. Las variaciones menores de estilo no se penalizan. Las palabras visibles de diálogo o narración, los nombres y el significado sí cuentan; las onomatopeyas pueden permanecer.</p><p>Los números y contenido de la edición inglesa visible prevalecen si Olympus cambia la edición. Cuatro recortes tienen texto cortado por un borde, y el JSON separa también las otras 120 ubicaciones. Son recortes de diálogo, no pantallas de escritorio completas: la probabilidad de fallo por uso sigue sin establecerse y la revisión de todos los capítulos no está terminada.</p><p><a href="../../metrics/index.html">Resultados agregados</a></p>{images}</html>''')
    print(json.dumps({k:v for k,v in value.items() if k!='entries'}),flush=True)


if __name__=='__main__':main()
