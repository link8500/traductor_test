"""Provenance checks and scope-aware reporting for the opening recovery."""
import hashlib
import json
import pathlib

ROOT=pathlib.Path(__file__).resolve().parents[1];QA=ROOT/'build/full-comics'
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def records(path):return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def diagnostic():
    path=ROOT/'benchmarks/full-comics/windows8028-opening-semantic-review.json'
    if not path.exists():return None
    value=read(path);folder=QA/'windows8028-opening-translation-replay'
    for relative,key in [('fixed-output.jsonl','fixed_output_sha256'),('native-output.jsonl','native_output_sha256'),
                         ('summary.json','native_summary_sha256'),('provenance.json','native_provenance_sha256'),
                         ('expanded-changes.json','expanded_changes_sha256')]:assert digest(folder/relative)==value[key]
    for p,key in [(ROOT/'benchmarks/full-comics/windows8027-question-semantic-review.json','previous_review_sha256'),
                  (QA/'windows8027-question-translation-replay/output.jsonl','previous_native_output_sha256'),
                  (QA/'windows-engine802801.json','snapshot_sha256'),(QA/'windows8028-opening-runtime-checks.json','runtime_checks_sha256'),
                  (QA/'opening8028/core-equivalence.json','core_equivalence_sha256'),
                  (QA/'opening8028/review/sample.json','visual_review_sample_sha256'),
                  (ROOT/'benchmarks/full-comics/opening8028-meaning-decisions.json','decisions_sha256')]:assert digest(p)==value[key]
    snapshot=read(QA/'windows-engine802801.json');binary=QA/'frozen-windows802801/traductor.exe'
    assert digest(binary)==snapshot['binary_sha256']
    assert snapshot['manifest_sha256']==read(QA/'windows-engine802701.json')['manifest_sha256']
    assert read(QA/'opening8028/core-equivalence.json')['decoder_existing_coverage_and_ocr_unchanged']
    assert read(folder/'summary.json')['all_outputs_match_conservative_prediction']
    assert value['actual_native_output_records']==297 and value['opening_policy_guards']['guards']==28
    old=records(QA/'windows8027-question-translation-replay/output.jsonl');actual=records(folder/'native-output.jsonl')
    assert len(actual)==297 and len(old)==229
    fields=['source','translation','image','bounds','retained_original','sentence_recovered','question_recovered']
    assert all(all(a.get(k,False)==b.get(k,False) for k in fields) for a,b in zip(old,actual[:229]))
    assert not any(r['opening_recovered'] for r in actual[:229])
    decisions=read(ROOT/'benchmarks/full-comics/opening8028-meaning-decisions.json')['entries']
    changes=read(folder/'expanded-changes.json')
    assert {r['id'] for r in decisions}=={r['id'] for r in changes}=={r['id']-229 for r in actual[229:] if r['opening_recovered']}
    assert all(r['after'].endswith(' '+r['before']) for r in changes)
    assert sum(r['after']=='acceptable' for r in decisions)==11
    assert sum(r['after']=='needs_review' for r in decisions)==1
    assert all(r['before']!='acceptable' for r in decisions)
    for name,cohort in value['cohorts'].items():
        subset=[r for r in value['entries'] if name=='all124_fixed_reading_viewports' or not r['visible_dialogue_clipped']]
        assert len(subset)==cohort['viewports']
        assert sum(r['after']!='acceptable' for r in subset)==cohort['after_not_approved']
        assert all(r['before']==r['after'] for r in subset)
    manifest=records(folder/'input.jsonl')
    assert len(manifest)==297 and all(set(r)=={'id','image','bounds','source'} for r in manifest)
    assert value['fresh_translation_inference'] and not value['new_ocr_inference'] and not value['fresh_screen_capture']
    assert not value['all_chapter_words_visually_reviewed'] and value['screen_attempt_failure_probability'] is None and not value['target_achieved']
    if 'native_paint_provenance_sha256' in value:
        assert digest(folder/'paint/provenance.json')==value['native_paint_provenance_sha256']
        assert digest(folder/'paint/manual-review.json')==value['native_paint_manual_review_sha256']
        paint=read(folder/'paint/provenance.json')
        for r in paint['entries']:assert digest(folder/f'paint/{r["id"]:03d}.jpg')==r['paint_sha256']
    return dict(**{k:v for k,v in value.items() if k!='entries'},review_sha256=digest(path))


def review_html(value):
    m=value['cohorts']['all124_fixed_reading_viewports'];h=value['historical_baseline_comparison']['cohorts']['all124_fixed_reading_viewports']
    e=value['expanded_opening_diagnostic']
    return (f'<h2>Windows actual · recuperación de aperturas omitidas</h2><p>Un barrido de los124 capítulos del control encontró '
        f'<b>{e["candidates"]} candidatos</b>. Se cotejaron las <b>{e["changed_regions"]} salidas modificadas</b>: '
        f'<b>{e["complete_corrections"]} correcciones completas</b>, {e["partial_recoveries_with_confirmed_residual_defects"]} recuperaciones parciales '
        f'con otros defectos y {e["still_needs_review"]} ubicación pendiente. No se observaron regresiones completas nuevas en ese diagnóstico. '
        'Las aperturas y los cuerpos se traducen por separado; solo se añade la apertura si la traducción independiente del cuerpo '
        'conserva exactamente las mismas palabras. Se excluyen sonidos y fragmentos ambiguos de nombres o adjetivos.</p>'
        f'<p>Las229 regiones de las124 vistas fijas se tradujeron de nuevo y conservan su texto: <b>{m["before_not_approved"]} → {m["after_not_approved"]} '
        f'vistas sin aprobar</b>. La reducción histórica de esa muestra permanece en <b>{h["relative_unapproved_reduction_percent"]:.2f} %</b>. '
        'El diagnóstico de aperturas tiene otra selección y no se suma a esa cuenta ni produce un nuevo porcentaje global. '
        'La app actual pasó28 guardas de aperturas y37 de geometría, además de recuperación, barra y superposición.</p>'
        '<p>Son297 registros nativos reales sobre fuentes OCR guardadas. No se repitió la captura ni el reconocimiento; no se entrenaron pesos. '
        'Los17 renders nuevos se inspeccionaron: el texto cabe, pero quedan trazos originales y texto no detectado en algunos recortes. '
        'La revisión palabra por palabra del conjunto y menos del5 % de fallos por uso completo siguen pendientes. '
        '<a href="../windows8028-opening-translation-replay/index.html">Comparaciones nuevas y alcance</a>.</p>')
