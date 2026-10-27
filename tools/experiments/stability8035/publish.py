"""Publish every compared output; keep rejected variants and scoped counts visible."""
import html
from pathlib import Path

from .core import META, OUT, PRIOR, ROOT, read

STYLE = '''body{font:16px system-ui;line-height:1.6;margin:24px auto;padding:0 18px;max-width:1400px;background:#f3f5ef;color:#26352f}table{width:100%;border-collapse:collapse;background:white}td,th{padding:12px;border:1px solid #cbd3c4;text-align:left;vertical-align:top}td{min-width:150px;max-width:330px;overflow-wrap:anywhere}.scroll{overflow:auto}.warning{background:#fff0dd;border-left:5px solid #a05c26;padding:16px}.changed{background:#f0f6e7}a{color:#315a42}small{color:#4a594b}'''


def escape(value):
    return html.escape(str(value))


def page(title, body):
    return f'<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title><style>{STYLE}</style><h1>{escape(title)}</h1>{body}</html>'


def table(name, title, baseline, candidate, previous, decisions, references=None):
    body = '<p><a href="index.html">Volver al informe</a></p><p>Se muestran todas las salidas. Sin cambios o sin alerta no significa traducción aprobada.</p><div class="scroll"><table><tr><th>ID / revisión</th><th>Inglés de entrada</th>'
    if references:
        body += '<th>Referencia revisada</th>'
    body += '<th>Base OPUS</th><th>8034 completo</th><th>Candidato</th></tr>'
    for before, after, old in zip(baseline, candidate, previous):
        ident = before['id']
        assert before['source'] == after['source'] == old['source']
        verdict = decisions.get(ident)
        status = verdict['after'] if verdict else 'Sin nueva revisión'
        note = verdict.get('note', '') if verdict else 'No se recalifica por estar sin cambios.'
        body += f'<tr class="{"changed" if before["translation"] != after["translation"] else ""}"><td>{ident}: {escape(status)}<p><small>{escape(note)}</small></p></td><td>{escape(before["source"])}</td>'
        if references:
            body += f'<td>{escape(references[ident])}</td>'
        body += ''.join(f'<td>{escape(row["translation"])}</td>' for row in [before, old, after]) + '</tr>'
    body += '</table></div>'
    (OUT / f'{name}.html').write_text(page(title, body), encoding='utf-8')


def main():
    result = read(META / 'result.json')
    review = read(META / 'validation-review.json')
    data = read(ROOT / 'benchmarks/finetune8034/dataset.json')
    references = {row['id']: row['target'] for row in data['validation']}
    for name in review['variants']:
        table(name, f'8035 · Validación {name}', read(PRIOR / 'baseline-validation.json'),
              read(OUT / f'validation-{name}.json'), read(PRIOR / 'candidate-validation.json'),
              {row['id']: row for row in review['variants'][name]['entries']}, references)
    controls = read(META / 'control-meaning-review.json')
    for name in result['controls']:
        table(name, f'8035 · Control {name}', read(PRIOR / f'{name}-baseline.json'),
              read(OUT / f'{name}-candidate.json'), read(PRIOR / f'{name}-candidate.json'),
              {row['id']: row for row in controls['entries'] if row['name'] == name})
    body = '<p class="warning"><strong>8035 descartado.</strong> Reducir uniformemente la intensidad del adaptador evita una regresión de validación, pero conserva la generación formada solo por signos y añade otra omisión. No se modificaron los pesos instalados. No se ha acreditado menos del 5 % de fallos por uso.</p>'
    body += '<p>Este ensayo ajusta la intensidad de un adaptador ya entrenado; no entrena otro modelo ni repite captura/OCR. La validación se usó para seleccionar una variante antes de abrir los controles conocidos.</p>'
    body += '<h2>Comparaciones completas</h2><ul><li><a href="scale050.html">Validación: intensidad 50 %, 25 diálogos</a></li><li><a href="scale075.html">Validación: intensidad 75 %, 25 diálogos; variante seleccionada</a></li><li><a href="regression-core.html">229 regiones OCR guardadas</a></li><li><a href="known-test.html">16 diálogos de control conocidos</a></li><li><a href="early-known-test.html">13 diálogos de control conocidos</a></li></ul>'
    body += '<h2>Resultado de los controles</h2><div class="scroll"><table><tr><th>Conjunto</th><th>Correcciones completas</th><th>Regresiones completas nuevas</th><th>Pérdidas parciales adicionales</th><th>Artefactos nuevos</th></tr>'
    for name, summary in result['controls'].items():
        body += f'<tr><td>{escape(name)} ({summary["total_inputs"]})</td><td>{summary["complete_corrections"]}</td><td>{summary["new_complete_content_regressions"]}</td><td>{summary["additional_partial_losses"]}</td><td>{summary["new_source_artifacts"]}</td></tr>'
    body += '</table></div><p>Los recuentos comparan regiones/textos con el núcleo base. Las 229 regiones proceden de 124 vistas guardadas: no equivalen a 124 capítulos completos ni a usos independientes de la app. Las onomatopeyas no inflan las correcciones. La revisión se realizó por el asistente y no tiene certificación humana final.</p>'
    body += '<p><a href="../finetune8034/index.html">Informe anterior: 8034</a></p>'
    (OUT / 'index.html').write_text(page('Luma · Estabilidad 8035', body), encoding='utf-8')


if __name__ == '__main__':
    main()
