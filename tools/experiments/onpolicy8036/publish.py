"""Build complete local comparisons for all checkpoints and the selected control run."""
import html

from tools.experiments.stability8035.core import ROOT, PRIOR, read
from .select_checkpoint import META, OUT

STYLE = '''body{font:16px system-ui;line-height:1.6;max-width:1400px;margin:28px auto;padding:0 18px;background:#f2f5ed;color:#26352f}table{width:100%;border-collapse:collapse;background:white}td,th{border:1px solid #c5cfbd;padding:12px;text-align:left;vertical-align:top}td{min-width:160px;max-width:320px;overflow-wrap:anywhere}.scroll{overflow:auto}.changed{background:#eef5e5}.warning{background:#fff0de;border-left:5px solid #995020;padding:16px}a{color:#315a42}small{color:#596151}'''


def esc(value):
    return html.escape(str(value))


def save(name, title, body):
    (OUT / name).write_text(f'<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title><style>{STYLE}</style><h1>{esc(title)}</h1>{body}</html>', encoding='utf-8')


def compare(name, title, baseline, candidate, previous, decisions, references=None):
    body = '<p><a href="index.html">Volver al informe</a></p><p>Todos los resultados, incluidos los fallidos. Sin cambios no significa aprobado.</p><div class="scroll"><table><tr><th>ID / dictamen</th><th>Fuente</th>'
    if references:
        body += '<th>Referencia revisada</th>'
    body += '<th>Base</th><th>8034 completo</th><th>8036</th></tr>'
    for before, after, prior in zip(baseline, candidate, previous):
        ident = before['id']
        assert ident == after['id'] == prior['id']
        assert before['source'] == after['source'] == prior['source']
        decision = decisions.get(ident)
        status = decision['after'] if decision else 'Sin nueva revisión'
        note = decision.get('note') or '' if decision else 'La salida sin cambios no se recalifica.'
        body += f'<tr class="{"changed" if before["translation"] != after["translation"] else ""}"><td>{ident}: {esc(status)}<p><small>{esc(note)}</small></p></td><td>{esc(before["source"])}</td>'
        if references:
            body += f'<td>{esc(references[ident])}</td>'
        body += ''.join(f'<td>{esc(row["translation"])}</td>' for row in [before, prior, after]) + '</tr>'
    body += '</table></div>'
    save(name + '.html', title, body)


def main():
    result = read(META / 'result.json')
    summary = read(OUT / 'summary.json')
    reviews = read(META / 'validation-review.json')['checkpoints']
    refs = {row['id']: row['target'] for row in read(ROOT / 'benchmarks/finetune8034/dataset.json')['validation']}
    for checkpoint in summary['checkpoints']:
        name = checkpoint['name']
        compare(name, f'8036 · Validación {name}', read(PRIOR / 'baseline-validation.json'),
                read(OUT / name / 'validation-candidate.json'), read(PRIOR / 'candidate-validation.json'),
                {row['id']: row for row in reviews[name]['entries']}, refs)
    control_reviews = read(META / 'control-meaning-review.json')
    for name in result['controls']:
        compare(name, f'8036 · Control {name}', read(PRIOR / f'{name}-baseline.json'),
                read(OUT / f'{name}-candidate.json'), read(PRIOR / f'{name}-candidate.json'),
                {row['id']: row for row in control_reviews['entries'] if row['name'] == name})
    body = '<p class="warning"><strong>El 8036 tampoco está aprobado.</strong> Se entrenó un adaptador real y se contrastaron tres puntos de control. El seleccionado conserva omisiones, una salida formada solo por signos y otras regresiones. La app sigue usando sus pesos anteriores. No se acredita menos del 5 % de fallos.</p>'
    body += '<p>Objetivo: comparar al modelo con su base congelada mientras genera sus propias frases de entrenamiento, además de usar referencias correctas. Se actualizaron 294.912 parámetros en 312 pasos. Las 163 etiquetas originales y las 254 concatenaciones son las mismas del 8034; no son datos nuevos ni 417 diálogos independientes. Las fuentes de validación/prueba no entran en los gradientes.</p>'
    body += '<h2>Selección previa a los controles</h2><div class="scroll"><table><tr><th>Punto</th><th>Errores conocidos, de 14</th><th>Errores nuevos, de 11</th><th>chrF++</th><th>Elegible</th></tr>'
    for checkpoint in summary['checkpoints']:
        row = reviews[checkpoint['name']]
        body += f'<tr><td><a href="{checkpoint["name"]}.html">{checkpoint["name"]}</a></td><td>{row["counts"]["known"]["confirmed_errors_after"]}</td><td>{row["counts"]["new"]["confirmed_errors_after"]}</td><td>{checkpoint["validation_chrfpp"]:.2f}</td><td>{"Sí" if row["eligible"] else "No"}</td></tr>'
    body += '</table></div><p>La base tiene cinco errores confirmados en los 14 diálogos y cuatro en los 11. Permanecen tres casos de contexto en el primer conjunto y uno en el segundo. Se seleccionó step104 antes de los demás controles; el mayor chrF++ no anuló los criterios semánticos. La validación es un conjunto de desarrollo conocido.</p>'
    body += '<h2>Controles del candidato seleccionado</h2><div class="scroll"><table><tr><th>Conjunto</th><th>Correcciones completas</th><th>Regresiones nuevas</th><th>Pérdidas parciales adicionales</th><th>Artefactos nuevos</th></tr>'
    for name, row in result['controls'].items():
        body += f'<tr><td><a href="{name}.html">{esc(name)} ({row["total_inputs"]})</a></td><td>{row["complete_corrections"]}</td><td>{row["new_complete_content_regressions"]}</td><td>{row["additional_partial_losses"]}</td><td>{row["new_source_artifacts"]}</td></tr>'
    body += '</table></div><p>Se revisaron los 65 cambios: 55 dictámenes se reutilizaron por identidad exacta de fuente y salida y 10 variantes nuevas fueron cotejadas por significado. Las otras 193 salidas de los controles no se aprobaron por estar sin cambios. Las onomatopeyas no inflan las mejoras. Las revisiones del asistente no tienen certificación humana final.</p>'
    body += '<p>Las 229 regiones OCR proceden de 124 vistas guardadas. Esta prueba no vuelve a capturar la pantalla, no ejecuta OCR y no revisa cada palabra de 124 capítulos completos. Quedan 41 capítulos de prueba reservados sin abrir.</p><p><a href="../stability8035/index.html">Ensayo 8035: reducción de intensidad, también descartado</a> · <a href="../finetune8034/index.html">8034</a></p>'
    save('index.html', 'Luma · Estabilidad y selección 8036', body)


if __name__ == '__main__':
    main()
