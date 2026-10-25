"""Publish the inspected full-chapter OCR checkpoint without mixing cohorts."""
import json
import pathlib
from audit_corpus_quality import ROOT, QA, read, records, digest, atomic
from publish_coverage_regression import counts


def main():
    folder=QA/'full8012-review-checkpoint01';sample_path=folder/'sample.json';manual_path=folder/'manual-decisions.json'
    sample=read(sample_path);manual=read(manual_path);decisions={r[0]:r for r in manual}
    assert len(decisions)==len(manual)==len(sample['cases']) and set(decisions)=={c['id'] for c in sample['cases']}
    previous_path=ROOT/'benchmarks/full-comics/current8011-six-regions-semantic-review.json'
    assert digest(previous_path)==sample['previous_review_sha256']
    previous={e['id']:e for e in read(previous_path)['entries']}
    changed={c['original_id']:c for c in sample['cases']};reports={};entries=[]
    for chapter,proof in sample['frozen_reports'].items():
        path=QA/'translated-en8012-recovery'/(chapter+'-en.jsonl')
        assert digest(path)==proof['report_sha256'] and digest(path.with_name(path.stem+'.done.json'))==proof['done_sha256']
        reports[chapter]=records(path)
    for pair in sample['all_pairs']:
        old=previous[pair['id']];assert old['translation']==pair['before_translation'] and old['after']==pair['before_judgment']
        actual=[reports[pair['chapter']][i] for i in pair['selected_regions']]
        assert pair['source']==' '.join(r['source'] for r in actual) and pair['translation']==' '.join(r['translation'] for r in actual)
        after=pair['before_judgment'];note='Fuente y traducción idénticas en una región inequívoca; se conserva el dictamen.'
        if not pair['judgment_reused_for_identical_output']:
            case=changed[pair['id']];_,after,note=decisions[case['id']]
            for key in ['source_page','reference_page']:
                page=case[key];assert digest(pathlib.Path(page['path']))==page['sha256']
        else:assert len(actual)==1 and actual[0]['source']==old['source'] and pair['translation']==old['translation']
        entries.append(dict(**pair,before=pair['before_judgment'],after=after,note_es=note))
    value=dict(schema=1,reviewer='assistant',**counts(entries),chapters_sampled=sample['chapters'],regions_per_chapter=6,
        changed_outputs_visually_reinspected=len(changed),identical_output_judgments_reused=sample['identical_output_judgments_reused'],
        sample_path=sample_path.relative_to(ROOT).as_posix(),sample_sha256=digest(sample_path),manual_decisions_sha256=digest(manual_path),
        previous_review_sha256=digest(previous_path),source_cohort='translated-en8011-context',current_cohort='translated-en8012-recovery',
        translation_weights_changed=False,population_accuracy_estimate=False,all_chapter_words_visually_reviewed=False,
        app_uses_review_answers=False,partial_full_chapter_ocr_checkpoint=True,overlaps_with_main_sample_do_not_add_counts=True,entries=entries)
    assert len(entries)==sample['reviewed_locations']
    target=ROOT/'benchmarks/full-comics/full8012-checkpoint01-semantic-review.json'
    atomic(target,json.dumps(value,ensure_ascii=False,indent=2))
    pictures=''.join(f'<img loading="lazy" src="sheet-{i:02d}.jpg" alt="Hoja {i}">' for i in range(1,13))
    atomic(folder/'index.html',f'<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luma · OCR mejorado, punto de control</title><style>body{{font:17px system-ui;background:#f1f4ed;color:#243b2b;margin:24px}}img{{display:block;width:100%;max-width:1440px;margin:24px auto}}p{{line-height:1.6;max-width:1000px}}</style><h1>OCR mejorado · punto de control parcial</h1><p>{value["chapters_sampled"]} capítulos con recorrido completo disponible al fijar esta comparación. {value["comparable_regions"]} ubicaciones comparables de {value["reviewed_regions"]}: {value["before_errors"]} → {value["after_errors"]} errores. Se inspeccionaron las {len(changed)} salidas o fuentes modificadas y se conservaron {value["identical_output_judgments_reused"]} dictámenes de salidas idénticas. No es una revisión de todas las palabras y no se suma a la muestra principal.</p><p><a href="../metrics/index.html">Resultados agregados</a></p>'+pictures+'</html>')
    print(json.dumps({k:v for k,v in value.items() if k!='entries'}))


if __name__=='__main__':main()
