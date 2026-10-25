"""Publish an inspected candidate; do not relabel historical evidence silently."""
import json
import pathlib
from audit_corpus_quality import ROOT,QA,read,records,digest,atomic,CLEAR_ERRORS
from publish_coverage_regression import counts


def main():
    out=QA/'sentence-coverage8016';sample=read(out/'visual-review/sample.json');status=read(out/'summary.json')
    manual_path=out/'visual-review/manual-decisions.json';manual=read(manual_path);decisions={r[0]:r for r in manual}
    assert len(manual)==len(decisions)==len(sample['cases']) and set(decisions)=={c['id'] for c in sample['cases']}
    base_path=ROOT/'benchmarks/full-comics/coverage8014-six-regions-semantic-review.json';base=read(base_path)
    assert digest(base_path)==sample['base_review_sha256']==status['base_review_sha256']
    assert digest(out/'output.jsonl')==sample['native_output_sha256']==status['output_sha256']
    assert status['native_errors']==0 and status['locations']==744 and status['unique_fresh_native_inferences']==744
    rows={r['source']:r for r in records(out/'output.jsonl')};changed={c['original_id']:c for c in sample['cases']}
    entries=[];revised=[];legacy=[]
    for old in base['entries']:
        row=rows[old['source']];before=old['after'];after=before;note='Salida idéntica en la misma ubicación; conserva el dictamen histórico, sin aprobar la pantalla completa.'
        if old['id'] in changed:
            case=changed[old['id']];_,before,after,note=decisions[case['id']]
            assert row['translation']==case['translation'] and case['before_translation']==old['translation']
            for key in ['source_page','reference_page']:
                page=case[key];assert digest(pathlib.Path(page['path']))==page['sha256']
            if before!=old['after']:revised.append(dict(id=old['id'],historical=old['after'],revised=before,note_es=note))
        else:assert row['translation']==old['translation']
        entries.append(dict(id=old['id'],source=old['source'],before_translation=old['translation'],translation=row['translation'],before=before,after=after,
            historical_before=old['after'],comparison_excluded=old['comparison_excluded'],note_es=note,judgment_reused=old['id'] not in changed))
        legacy.append(dict(before=old['after'],after=after,comparison_excluded=old['comparison_excluded']))
    value=dict(schema=1,**counts(entries),chapters_sampled=124,changed_locations_visually_reinspected=len(changed),identical_output_judgments_reused=744-len(changed),
        explicit_historical_judgment_corrections=revised,historical_threshold_comparison=counts(legacy),
        recovered_missing_clauses_in_changed_subset=7,remaining_clear_errors_in_changed_subset=sum(e['after'] in CLEAR_ERRORS for e in entries if e['id'] in changed),
        all_chapter_words_visually_reviewed=False,screen_attempt_failure_probability=None,population_accuracy_estimate=False,
        source_review_sha256=digest(base_path),output_sha256=digest(out/'output.jsonl'),provenance_sha256=digest(out/'provenance.json'),
        manual_sha256=digest(manual_path),application_modified=False,translator_weights_changed=False,app_uses_review_answers=False,
        omissions_stricter_reviewed_only_in_changed_locations=True,entries=entries)
    atomic(ROOT/'benchmarks/full-comics/coverage8016-candidate-semantic-review.json',json.dumps(value,ensure_ascii=False,indent=2))
    pictures=''.join(f'<img loading="lazy" src="sheet-{i:02d}.jpg" alt="Comparación {i}">' for i in range(1,3))
    atomic(out/'visual-review/index.html',f'<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luma · Recuperación de omisiones</title><style>body{{font:17px system-ui;background:#f1f4ed;color:#243b2b;margin:24px}}img{{display:block;width:100%;max-width:1440px;margin:24px auto}}p{{line-height:1.6;max-width:1000px}}</style><h1>Recuperación de frases omitidas · candidato nativo</h1><p>744 inferencias nativas nuevas, cero errores de ejecución, siete traducciones modificadas cotejadas contra los píxeles originales. Se recuperan siete fragmentos omitidos, pero cuatro globos modificados conservan otro error claro y no se aprueban. Dos dictámenes históricos demasiado permisivos se rectifican explícitamente: el control con el criterio revisado tiene {value["before_errors"]} errores y el candidato {value["after_errors"]}, con {value["corrected_regions"]} correcciones completas y {value["regressed_regions"]} regresiones. Esta prueba usa OCR fijo, no equivale a aprobar pantallas completas y todavía no cambia la aplicación distribuida.</p><p><a href="../../metrics/index.html">Resultados agregados</a></p>'+pictures+'</html>')
    print(json.dumps({k:v for k,v in value.items() if k!='entries'}),flush=True)


if __name__=='__main__':main()
