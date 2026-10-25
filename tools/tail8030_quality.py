"""Keep tail recovery evidence separate from complete-screen failure estimates."""
from refinement8029_quality import ROOT,QA,read,digest,records


def diagnostic():
    path=ROOT/'benchmarks/full-comics/windows8030-tail-semantic-review.json'
    if not path.exists():return None
    value=read(path);folder=QA/'windows8030-tail-translation-replay'
    for name,key in [('summary.json','native_summary_sha256'),('provenance.json','native_provenance_sha256'),
                     ('fixed-output.jsonl','fixed_output_sha256'),('prior-diagnostic-output.jsonl','previous_diagnostic_output_sha256'),
                     ('tail-output.jsonl','tail_output_sha256'),('changes.json','native_changes_sha256'),
                     ('paint/provenance.json','native_paint_provenance_sha256'),('paint/manual-review.json','native_paint_manual_review_sha256')]:
        assert digest(folder/name)==value[key]
    for p,key in [(ROOT/'benchmarks/full-comics/windows8029-refinement-semantic-review.json','previous_review_sha256'),
                  (ROOT/'benchmarks/full-comics/tail8030-meaning-decisions.json','decisions_sha256'),
                  (QA/'windows-engine803001.json','snapshot_sha256'),(QA/'windows8030-tail-runtime-checks.json','runtime_checks_sha256'),
                  (QA/'tail8030/review/sample.json','original_and_olympus_review_sample_sha256')]:assert digest(p)==value[key]
    snapshot=read(QA/'windows-engine803001.json');assert digest(QA/'frozen-windows803001/traductor.exe')==snapshot['binary_sha256']
    assert snapshot['manifest_sha256']==read(QA/'windows-engine802901.json')['manifest_sha256']
    proof=read(folder/'provenance.json');assert proof['actual_native_translation'] and proof['source_only_model_input']
    assert not proof['fresh_ocr_inference'] and not proof['fresh_screen_capture'] and not proof['manual_or_reference_answers_supplied']
    total=0
    for n in range(6):
        for item in records(folder/f'part-{n:02d}.input.jsonl'):
            assert set(item)=={'id','image','bounds','source'};total+=1
    assert total==value['actual_native_output_records']==334
    old=records(QA/'windows8029-refinement-full-viewports/output.jsonl');new=records(folder/'fixed-output.jsonl')
    shown=lambda rows:[(r['image'],r['bounds'],r['source'],r['translation'],r['retained_original']) for r in rows]
    assert len(old)==len(new)==229 and shown(old)==shown(new)
    before_broad=[r['after'] for r in read(QA/'windows8029-refinement-full-viewports/broad-selected.json')]
    assert shown(before_broad)==shown(records(folder/'prior-diagnostic-output.jsonl'))
    manual=read(ROOT/'benchmarks/full-comics/tail8030-meaning-decisions.json');changes=read(folder/'changes.json')
    assert len(changes)==10 and {r['id'] for r in changes}=={r['id'] for r in manual['entries'] if r['tail_accepted']}
    assert sum(r['complete_correction'] for r in manual['entries'])==6
    for c in changes:
        assert c['actual_native']['translation']==c['policy']['candidate_translation']
        assert c['actual_native']['translation'].startswith(c['policy']['translation'])
    for m in value['cohorts'].values():assert m['before_not_approved']==m['after_not_approved'] and not m['corrected'] and not m['regressed']
    assert value['cohorts']['all124_fixed_reading_viewports']['after_not_approved']==56
    assert value['dialogue_ocr']['all124_fixed_reading_viewports']['after']['word_errors']==44
    assert value['native_tail_guards']['guards']==18
    for p in read(folder/'paint/provenance.json')['entries']:assert digest(folder/'paint'/p['output'])==p['paint_sha256']
    assert not value['all_chapter_words_visually_reviewed'] and not value['target_achieved'] and value['screen_attempt_failure_probability'] is None
    return dict(**{k:v for k,v in value.items() if k!='entries'},review_sha256=digest(path))


def review_html(value):
    d=value['tail_diagnostic'];m=value['cohorts']['all124_fixed_reading_viewports'];h=value['historical_baseline_comparison']['cohorts']['all124_fixed_reading_viewports']
    return (f'<h2>Windows actual · recuperación de frases finales</h2><p>El barrido de los <b>{d["source_reports_scanned"]} informes completos guardados</b> '
        f'examinó {d["nonpromotional_rows_scanned"]} regiones sin promoción, incluidas salidas sin alerta. Se probaron <b>{d["candidates"]} candidatos</b>; '
        f'{d["candidates_without_automatic_alert"]} no tenían alerta automática. Tras cotejar los cambios con los píxeles ingleses y Olympus: '
        f'<b>{d["complete_corrections"]} correcciones completas de contenido</b>, <b>{d["partial_improvements_with_residual_errors"]} mejoras parciales</b> '
        f'que siguen sin aprobar y <b>{d["rejected_additions"]} adición rechazada</b> por cambiar el número de destinatarios. '
        'Las diez adiciones aceptadas conservan intactas las palabras previas. Dos adiciones mantienen defectos gramaticales y siguen sin aprobar.</p>'
        f'<p>El ejecutable volvió a traducir <b>{value["actual_native_output_records"]} fuentes</b>. Se conserva por identidad el dictamen del control fijo: '
        f'<b>{m["before_not_approved"]} → {m["after_not_approved"]} vistas sin aprobar</b> entre124; sus229 regiones y las siete ubicaciones de control anteriores no cambian. '
        f'La reducción semántica histórica del control permanece en <b>{h["relative_unapproved_reduction_percent"]:.2f} %</b>. '
        'El diagnóstico adicional tiene una selección distinta: sus correcciones no se suman al control fijo ni representan un porcentaje global de fallo.</p>'
        '<p>Pasaron18 comprobaciones de recuperación de frases finales,37 de geometría y las comprobaciones de barra y superposición. '
        'No se entrenaron ni descargaron pesos. Se reutilizan las fuentes OCR guardadas; no son capturas nuevas ni usos completos en vivo. '
        'Quedan fallos de contenido y de superposición. La revisión de cada palabra de los124 capítulos y menos del5 % de fallos por uso siguen pendientes. '
        '<a href="../windows8030-tail-translation-replay/index.html">Comparaciones y renders actuales</a>.</p>')
