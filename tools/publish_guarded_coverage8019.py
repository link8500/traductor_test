"""Publish safeguards only after fresh native production matches every planned result."""
import collections
import json
from audit_corpus_quality import ROOT,QA,atomic,digest,read,records


def main():
    source_path=ROOT/'benchmarks/full-comics/full-corpus-coverage8018-semantic-review.json';old=read(source_path)
    folder=QA/'full-corpus-coverage8019';production=QA/'production-coverage8019'
    summary=read(production/'summary.json');assert not summary['guard_plan_disagreements']
    output=production/'output.jsonl';assert digest(output)==summary['output_sha256']
    actual={r['source']:r for r in records(output)}
    guarded={r['source']:r for r in records(folder/'guarded-candidates.jsonl')}
    guard_pin=read(folder/'guard-provenance.json');proof=read(production/'provenance.json')
    assert guard_pin['policy_sha256']==proof['policy_sha256'] and digest(folder/'guarded-candidates.jsonl')==guard_pin['output_sha256']
    entries=[]
    for old_row in old['entries']:
        row=dict(old_row);source=row['source'];translation=actual[source]['translation']
        assert translation==guarded[source]['guarded_translation']
        assert translation in (row['before_translation'],row['translation'])
        if translation!=row['translation']:
            row.update(after=row['before'],translation=translation,unguarded_trial_after=old_row['after'],
                rejected_trial_translation=old_row['translation'],safeguard_rejected_retry=True,
                note_es='Se conserva la inferencia completa anterior: '+guarded[source]['guard_reason'],
                partial_content_worsening_observed=False)
        else:row.update(safeguard_rejected_retry=False)
        row.update(meaning_judgment_reused_for_identical_pinned_output=True)
        entries.append(row)
    before=collections.Counter(r['before'] for r in entries);after=collections.Counter(r['after'] for r in entries)
    b=len(entries)-before['acceptable'];a=len(entries)-after['acceptable']
    value=dict(schema=1,variant='801901',chapters_scanned=124,source_locations_scanned=18179,
        changed_locations_reviewed_in_original_trial=119,locations_with_translation_change_after_guard=sum(r['before_translation']!=r['translation'] for r in entries),
        guarded_trial_locations_reusing_exact_before_or_after_judgments=len(entries),
        fresh_native_validation_sources=summary['fresh_production_inferences'],
        native_guard_plan_disagreements=0,guards=summary['native_guards'],
        before_categories=dict(before),after_categories=dict(after),before_not_approved=b,after_not_approved=a,
        fully_corrected=sum(r['before']!='acceptable' and r['after']=='acceptable' for r in entries),
        full_region_regressions=sum(r['before']=='acceptable' and r['after']!='acceptable' for r in entries),
        partial_content_worsening_from_rejected_trial_remaining=sum(r['partial_content_worsening_observed'] for r in entries),
        recoveries_rejected=sum(r['safeguard_rejected_retry'] for r in entries),
        relative_unapproved_reduction_percent=100*(b-a)/b,entries=entries,
        original_trial_semantic_review_sha256=digest(source_path),guard_provenance_sha256=digest(folder/'guard-provenance.json'),
        production_summary_sha256=digest(production/'summary.json'),production_output_sha256=digest(output),
        source_ocr_is_older_fixed_control=True,original_ocr_preserved=True,model_weights_changed=False,
        all_chapter_words_visually_reviewed=False,unchanged_regions_automatically_approved=False,
        screen_attempt_failure_probability=None,target_achieved=False,ready_for_release=False)
    assert value['full_region_regressions']==0 and value['partial_content_worsening_from_rejected_trial_remaining']==0
    atomic(ROOT/'benchmarks/full-comics/full-corpus-coverage8019-semantic-review.json',json.dumps(value,ensure_ascii=False,indent=2))
    atomic(folder/'index.html',f'''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luma · recuperación protegida</title><style>body{{font:17px system-ui;max-width:1100px;margin:35px auto;padding:20px;background:#f1f4ed;color:#243b2b}}p{{line-height:1.6}}</style><h1>Recuperación protegida</h1><p>La comparación recorrió 18.179 regiones del control OCR de 124 capítulos. Se revisaron los 119 cambios del ensayo inicial. La nueva política retiene exactamente la salida anterior cuando el reintento altera demasiado texto existente o pierde una negación. Se verificaron {value['fresh_native_validation_sources']} inferencias nuevas del motor de producción contra esta política, sin desacuerdos.</p><p><b>{b} → {a} sin aprobar</b> dentro de los 119 cambios inspeccionados: {value['fully_corrected']} correcciones completas, cero regresiones completas observadas y el empeoramiento parcial del ensayo rechazado eliminado. Se rechazaron {value['recoveries_rejected']} recuperaciones, incluidas algunas que habrían sido correctas.</p><p>La reducción relativa es del {value['relative_unapproved_reduction_percent']:.1f} % en este subconjunto; no representa el riesgo de fallo por pantalla. No se han aprobado automáticamente las regiones sin cambios ni revisado todas las palabras de todos los capítulos. La comprobación en pantallas completas sigue pendiente.</p><p><a href="../full-corpus-coverage8018/visual-review-compact/index.html">Originales y ensayo previo conservado</a> · <a href="../metrics/index.html">Resultados agregados</a></p></html>''')
    print(json.dumps({k:v for k,v in value.items() if k!='entries'}),flush=True)


if __name__=='__main__':main()
