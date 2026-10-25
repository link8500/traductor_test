"""Validate the frozen combined control, including pending/manual judgments."""
import json
import pathlib
from audit_corpus_quality import ROOT,QA,read,records,digest,atomic
from publish_coverage_regression import counts


def main():
    folder=QA/'combined-recovery8016-checkpoint01';sample=read(folder/'sample.json')
    manual=read(folder/'manual-decisions.json');decisions={r[0]:r for r in manual}
    assert len(manual)==len(decisions)==len(sample['cases']) and set(decisions)=={c['id'] for c in sample['cases']}
    base_path=ROOT/'benchmarks/full-comics/coverage8014-six-regions-semantic-review.json'
    assert digest(base_path)==sample['base_review_sha256']
    assert digest(ROOT/'benchmarks/full-comics/full8012-checkpoint01-semantic-review.json')==sample['previous_pixel_review_sha256']
    base={e['id']:e for e in read(base_path)['entries']};cases={c['original_id']:c for c in sample['cases']}
    reports={}
    for chapter,proof in sample['frozen_reports'].items():
        path=QA/'translated-en8014-recovery'/(chapter+'-en.jsonl')
        assert digest(path)==proof['report_sha256'] and digest(path.with_name(path.stem+'.done.json'))==proof['done_sha256']
        reports[chapter]=records(path)
    entries=[]
    for pair in sample['all_pairs']:
        assert base[pair['id']]['after']==pair['before']
        actual=[reports[pair['chapter']][i] for i in pair['selected_regions']]
        assert pair['source']==' '.join(r['source'] for r in actual) and pair['translation']==' '.join(r['translation'] for r in actual)
        after=pair['after'];note=pair['note_es']
        if pair['judgment_reuse'] is None:
            case=cases[pair['id']];_,after,note=decisions[case['id']]
            for key in ['source_page','reference_page']:
                page=case[key];assert digest(pathlib.Path(page['path']))==page['sha256']
        assert after is not None
        entries.append({**pair,'after':after,'note_es':note})
    value=dict(schema=1,**counts(entries),chapters_sampled=sample['chapters'],regions_per_chapter=6,
        new_changed_locations_visually_inspected=len(cases),identical_output_judgments_reused=sample['identical_output_judgments_reused'],
        sample_path=(folder/'sample.json').relative_to(ROOT).as_posix(),sample_sha256=digest(folder/'sample.json'),manual_sha256=digest(folder/'manual-decisions.json'),
        current_cohort='translated-en8014-recovery',previous_fixed_ocr_review_sha256=digest(base_path),
        previous_pixel_review_sha256=sample['previous_pixel_review_sha256'],all_chapter_words_visually_reviewed=False,
        population_accuracy_estimate=False,screen_attempt_failure_probability=None,overlaps_with_main_sample_do_not_add_counts=True,
        translator_weights_changed=False,app_uses_review_answers=False,entries=entries)
    target=ROOT/'benchmarks/full-comics/combined-recovery8016-checkpoint01-semantic-review.json'
    atomic(target,json.dumps(value,ensure_ascii=False,indent=2))
    pictures=''.join(f'<img loading="lazy" src="sheet-{i+1:02d}.jpg" alt="Comparación {i+1}">' for i in range((len(cases)+3)//4))
    atomic(folder/'index.html',f'<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luma · Reconocimiento y traducción combinados</title><style>body{{font:17px system-ui;background:#f1f4ed;color:#243b2b;margin:24px}}img{{display:block;width:100%;max-width:1440px;margin:24px auto}}p{{line-height:1.6;max-width:1000px}}</style><h1>Reconocimiento y traducción combinados</h1><p>{value["chapters_sampled"]} capítulos disponibles al congelar la revisión, {value["comparable_regions"]} ubicaciones comparables: {value["before_errors"]} → {value["after_errors"]} errores claros. Se inspeccionaron {len(cases)} ubicaciones nuevas modificadas. Las otras {value["identical_output_judgments_reused"]} conservan un dictamen sobre una fuente y salida idénticas en la misma ubicación. La reducción parcial es {value["relative_error_reduction_percent"]:.1f} %. La recuperación de una palabra no aprueba una frase si todavía omite otra. No mide la probabilidad de fallo de una pantalla completa.</p><p><a href="../metrics/index.html">Resultados agregados</a></p>'+pictures+'</html>')
    print(json.dumps({k:v for k,v in value.items() if k!='entries'}),flush=True)


if __name__=='__main__':main()
