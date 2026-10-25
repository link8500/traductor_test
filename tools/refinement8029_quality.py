"""Validate fresh native refinement evidence and keep diagnostic counts scoped."""
from opening8028_quality import ROOT, QA, read, digest, records


def diagnostic():
    path=ROOT/'benchmarks/full-comics/windows8029-refinement-semantic-review.json'
    if not path.exists():return None
    value=read(path);folder=QA/'windows8029-refinement-full-viewports'
    for name,key in [('output.jsonl','native_output_sha256'),('summary.json','native_summary_sha256'),
                     ('provenance.json','native_provenance_sha256'),('broad-selected.json','broad_selected_sha256')]:assert digest(folder/name)==value[key]
    for p,key in [(ROOT/'benchmarks/full-comics/windows8028-opening-semantic-review.json','previous_review_sha256'),
                  (QA/'windows8028-opening-translation-replay/fixed-output.jsonl','previous_native_output_sha256'),
                  (QA/'windows-engine802901.json','snapshot_sha256'),(QA/'windows8029-refinement-runtime-checks.json','runtime_checks_sha256'),
                  (ROOT/'benchmarks/full-comics/refinement8029-meaning-decisions.json','decisions_sha256'),
                  (QA/'ocr-morph-edit8029/summary.json','selector_summary_sha256'),
                  (QA/'refinement8029/review/sample.json','original_and_olympus_review_sample_sha256')]:assert digest(p)==value[key]
    snapshot=read(QA/'windows-engine802901.json');assert digest(QA/'frozen-windows802901/traductor.exe')==snapshot['binary_sha256']
    assert snapshot['manifest_sha256']==read(QA/'windows-engine802801.json')['manifest_sha256']
    proof=read(folder/'provenance.json');assert proof['fresh_native_ocr'] and not proof['source_and_reference_text_supplied']
    assert len(proof['pixels'])==131
    import pathlib
    for p in proof['pixels']:assert digest(pathlib.Path(p['path']))==p['sha256']
    for n in range(5):
        for item in records(folder/f'part-{n}.input.jsonl'):
            assert not any(k in item for k in ['source','translation','reference','inventory','reader_consensus','consensus_first_directory','consensus_second_directory'])
    old=records(QA/'windows8028-opening-translation-replay/fixed-output.jsonl');new=records(folder/'output.jsonl')
    predicted=records(QA/'ocr-morph-edit8029/fixed124_views-output.jsonl');assert len(old)==len(new)==len(predicted)==229
    assert [(r['image'],r['bounds']) for r in old]==[(r['image'],r['bounds']) for r in new]
    assert [r['source'] for r in new]==[r['selected'] for r in predicted]
    manual=read(ROOT/'benchmarks/full-comics/refinement8029-meaning-decisions.json')
    assert {r['id'] for r in read(folder/'changes.json')}=={manual['fixed_changed_view']['id']}
    for label,m in value['cohorts'].items():
        entries=[r for r in value['entries'] if label=='all124_fixed_reading_viewports' or not r['visible_dialogue_clipped']]
        assert len(entries)==m['viewports']
        assert sum(r['after']!='acceptable' for r in entries)==m['after_not_approved']
    words=value['dialogue_ocr']['all124_fixed_reading_viewports']
    assert (words['before']['word_errors'],words['after']['word_errors'])==(45,44)
    assert words['before']['expected_dialogue_words']==words['after']['expected_dialogue_words']==2265
    assert value['unique_control_crop_pixels']==372 and value['control_cohorts_overlap_not_added']
    broad=read(folder/'broad-selected.json');assert len(broad)==len(manual['entries'])==7
    assert sum(r['after']=='acceptable' for r in manual['entries'])==3
    assert all(r['before']!='acceptable' for r in manual['entries'])
    assert value['fresh_native_ocr'] and value['fresh_translation_inference'] and not value['fresh_screen_capture']
    if 'native_paint_provenance_sha256' in value:
        assert digest(folder/'paint/provenance.json')==value['native_paint_provenance_sha256']
        assert digest(folder/'paint/manual-review.json')==value['native_paint_manual_review_sha256']
        for p in read(folder/'paint/provenance.json')['entries']:assert digest(folder/'paint'/p['output'])==p['paint_sha256']
    assert not value['all_chapter_words_visually_reviewed'] and not value['target_achieved'] and value['screen_attempt_failure_probability'] is None
    return dict(**{k:v for k,v in value.items() if k!='entries'},review_sha256=digest(path))


def review_html(value):
    d=value['expanded_refinement_diagnostic'];m=value['cohorts']['all124_fixed_reading_viewports'];h=value['historical_baseline_comparison']['cohorts']['all124_fixed_reading_viewports'];w=value['dialogue_ocr']['all124_fixed_reading_viewports']
    return (f'<h2>Windows actual · reconocimiento y preguntas breves</h2><p>Se cotejaron las <b>{d["changed_physical_locations"]} ubicaciones modificadas</b> '
        f'contra los originales y Olympus: <b>{d["complete_corrections"]} correcciones completas de significado</b> y '
        f'{d["partial_improvements_with_residual_errors"]} mejoras parciales que siguen sin aprobar. Se corrigen seis lecturas de una palabra y se recupera '
        'una pregunta inicial. No se observaron regresiones completas nuevas en este diagnóstico. Una ubicación se solapa con el control fijo: las cuentas no se suman.</p>'
        f'<p>El ejecutable nuevo repitió OCR y traducción sobre las <b>124 vistas guardadas</b> y siete estados de lectura originales. '
        f'En las124 vistas: <b>{m["before_not_approved"]} → {m["after_not_approved"]} sin aprobar</b>. El cambio de reconocimiento es parcial en esa muestra, '
        f'por lo que su reducción semántica histórica permanece en <b>{h["relative_unapproved_reduction_percent"]:.2f} %</b>. '
        f'OCR: <b>{w["before"]["word_errors"]} → {w["after"]["word_errors"]} discrepancias</b> sobre las mismas '
        f'{w["after"]["expected_dialogue_words"]} palabras, sin retirar palabras no detectadas.</p>'
        '<p>Pasaron12 guardas de selección de letras,17 de preguntas y37 de geometría, además de recuperación, barra y superposición. '
        'La selección de letras no empeora ninguno de los372 recortes de control distintos. No se entrenaron ni descargaron pesos. '
        'Se inspeccionaron ocho renders: el texto traducido cabe, pero quedan palabras originales fuera de algunas regiones y pequeños trazos sin borrar. '
        'Las pruebas usan píxeles guardados: no son usos nuevos completos de captura, barra y movimiento en vivo. '
        'La revisión de cada palabra de los124 capítulos y menos del5 % de fallos por uso siguen pendientes. '
        '<a href="../windows8029-refinement-full-viewports/index.html">Fotografías y alcance del control nuevo</a>.</p>')
