"""Build a standalone local comparison without a server or external requests."""
import html
import json

from tools.experiments.stability8035.core import ROOT, read, sha, write_new


def escape(value):
    return html.escape(str(value if value is not None else ''))


def main():
    meta = ROOT / 'benchmarks/temporal8040'
    out = ROOT / 'build/temporal8040'
    result = read(meta / 'result-v2.json')
    pools = {(row['group'], row['id']): row for row in read(ROOT / 'build/qe8038/candidate-pools.json')}
    sections = []
    for stage, label, reviews in [
        ('validation', 'Validación conocida · 25 diálogos', read(meta / 'validation-review.json')['entries']),
        ('controls', 'Controles · 258 diálogos', read(meta / 'control-meaning-review-v2.json')['entries']),
    ]:
        verdicts = {row['id'] if stage == 'validation' else (row['group'], row['id']): row for row in reviews}
        articles = []
        for row in read(out / f'{stage}-candidate.json'):
            pool = pools[row['group'], row['id']]
            decision = verdicts[row['id'] if stage == 'validation' else (row['group'], row['id'])]
            changed = row['selected'] != 'native'
            articles.append(f'''<article data-changed="{str(changed).lower()}"><header><b>{escape(row['group'])} · {row['id']}</b>
<span>{escape(decision['before'])} → {escape(decision['after'])}</span></header>
<p class="source" lang="en">{escape(row['source'])}</p><div class="columns">
<div><h3>Motor actual 803001</h3><p>{escape(pool['candidates'][0]['translation'])}</p></div>
<div><h3>Selección experimental 8040 · {escape(row['selected'])}</h3><p>{escape(row['translation'])}</p></div></div>
<p class="note">{escape(decision.get('note'))}</p><details><summary>Alternativas, puntuaciones y protección temporal</summary><pre>{escape(json.dumps(dict(candidates=pool['candidates'], inverse_scores=row['inverse_scores'], temporal_vetoes=row['temporal_vetoes'], profiles=row['profiles']), ensure_ascii=False, indent=2))}</pre></details></article>''')
        sections.append(f'<section><h2>{label}</h2>' + ''.join(articles) + '</section>')
    content = f'''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Luma · evaluación 8037–8040</title><style>
*{{box-sizing:border-box}}body{{font:16px/1.55 system-ui,sans-serif;max-width:1180px;margin:auto;padding:24px;background:#f5f6f8;color:#17232e}}h1,h2,h3{{line-height:1.25}}h3{{font-size:15px;color:#465c6c}}article,.intro{{background:white;border:1px solid #ccd5dc;border-radius:12px;padding:20px;margin:18px 0}}header{{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap}}header span{{font-size:14px}}.source{{border-left:4px solid #7192ac;padding-left:14px}}.columns{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}.note{{color:#53616e;font-size:14px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.5 monospace}}table{{border-collapse:collapse;width:100%}}th,td{{text-align:left;border-bottom:1px solid #d4dce3;padding:10px}}label{{display:block;margin:14px 0}}input[type=search]{{width:100%;padding:12px;border:1px solid #a8b6c2;border-radius:8px;font:inherit}}[hidden]{{display:none!important}}@media(max-width:700px){{.columns{{grid-template-columns:1fr}}body{{padding:12px}}}}
</style><h1>Luma · selección de traducciones</h1><div class="intro">
<p><b>8040 sigue experimental y fue rechazado para producción.</b> Se conservaron los pesos de la aplicación. No se acredita menos del 5 % de fallos por pantalla.</p>
<table><tr><th>Revisión</th><th>Validación (25)</th><th>Controles (258)</th></tr>
<tr><td>Errores confirmados: actual → candidato</td><td>10 → 3</td><td>39 → 28</td></tr>
<tr><td>Correcciones completas</td><td>7</td><td>10</td></tr>
<tr><td>Regresiones completas nuevas</td><td>0</td><td>0</td></tr>
<tr><td>Empeoramientos parciales nuevos</td><td>0</td><td>2</td></tr>
<tr><td>Incertidumbres nuevas</td><td>0</td><td>2</td></tr></table>
<p>Una salida que pasa de error confirmado a incierta no cuenta como corrección completa. Los controles conservan 24 entradas inciertas o con OCR no fiable. Las onomatopeyas no aumentan las correcciones.</p>
<p>Fuentes de texto ya conservadas; no se repitieron captura, OCR ni superposición. Se revisa lo escrito en esas fuentes, sin certificar cada palabra de los capítulos completos. No se abrieron los 41 capítulos reservados. Revisión del asistente, pendiente de certificación humana final.</p>
<p>8037: búsqueda de decodificación rechazada por generaciones añadidas. 8038: COMET recuperó 2 diálogos pero empeoró 2. 8039: el criterio inverso recuperó 7 con una duda temporal nueva. 8040 protege tiempos verbales y conserva esas 7 mejoras en validación; sus controles todavía fallan.</p>
<p>Las puntuaciones son log-verosimilitudes del inglés original según OPUS español→inglés. No son probabilidades de que una traducción sea correcta.</p></div>
<input id="search" type="search" aria-label="Buscar texto" placeholder="Buscar en inglés, español o dictamen">
<label><input id="changed" type="checkbox"> Mostrar solo traducciones modificadas</label><p id="count" aria-live="polite"></p>
{''.join(sections)}<script>
const search=document.querySelector('#search'),changed=document.querySelector('#changed'),cards=[...document.querySelectorAll('article')];function update(){{let shown=0;const needle=search.value.toLocaleLowerCase();for(const card of cards){{card.hidden=(changed.checked&&card.dataset.changed!=='true')||!card.textContent.toLocaleLowerCase().includes(needle);if(!card.hidden)shown++}}document.querySelector('#count').textContent=`${{shown}} de ${{cards.length}} comparaciones visibles`;}}search.addEventListener('input',update);changed.addEventListener('change',update);update();
</script></html>'''
    destination = out / 'index.html'
    with destination.open('x', encoding='utf-8') as stream:
        stream.write(content)
    evidence = []
    for experiment in ['decoder8037', 'qe8038', 'roundtrip8039', 'temporal8040']:
        directory = ROOT / f'benchmarks/{experiment}'
        for path in sorted(directory.glob('*.json')):
            evidence.append(dict(path=str(path.relative_to(ROOT)), sha256=sha(path)))
    continuation = dict(app_build='803001', experiment='8040', quality_gates_passed=False,
                        production_weights_modified=False, target_achieved=False, app_failure_probability=None,
                        validation=result['validation'], controls=result['controls'],
                        local_report=str(destination.relative_to(ROOT)), report_sha256=sha(destination),
                        evidence=evidence, new_blind_test_chapters_opened=0)
    write_new(ROOT / 'build/full-comics/continuation8040.json', continuation)
    latest = ROOT / 'build/full-comics/continuation-latest.json'
    latest.write_text(json.dumps(dict(path='continuation8040.json', app_build='803001', experiment='8040', target_achieved=False), indent=2), encoding='utf-8')
    print(json.dumps(dict(report=str(destination), rows=len(pools), bytes=destination.stat().st_size)))


if __name__ == '__main__':
    main()
