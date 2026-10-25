"""Publish existing native paint and manual observations without duplicating images."""
import html
import json
from audit_corpus_quality import ROOT, QA, atomic, digest, read


def main():
    folder = QA / 'windows8021-full-viewports-full-agreement'
    report_path = ROOT / 'benchmarks/full-comics/windows8021-full-viewports-semantic-review.json'
    report = read(report_path)
    # All ten exported native paintings were inspected individually. These
    # observations concern appearance; semantic decisions live in their report.
    observations = {
        4: 'No conspicuous original-letter remnant at the inspected scale.',
        5: 'Original A remains left of the unchanged paint bounds.',
        37: 'No conspicuous original-letter remnant at the inspected scale.',
        42: 'Small original strokes remain outside some paint bounds.',
        44: 'Small original punctuation remains outside the paint bounds.',
        67: 'An original punctuation remnant remains.',
        83: 'No conspicuous original-letter remnant at the inspected scale.',
        88: 'No conspicuous original-letter remnant at the inspected scale.',
        100: 'A small original punctuation remnant remains.',
        101: 'Clear original J and B remnants. Original dialogue and Spanish output are clipped at the bottom.',
    }
    assert len(observations) == report['changed_viewports_reinspected'] == 10
    proof = dict(native_paint_provenance_sha256=digest(folder / 'paint/provenance.json'),
        semantic_review_sha256=digest(report_path), manually_inspected_native_paintings=10,
        all124_paintings_visually_reviewed=False, all_paintings_approved=False,
        entries=[dict(id=ident, png_or_jpeg_sha256=digest(folder / f'paint/{ident:03d}.jpg'),
            visually_reviewed=True, observation=note) for ident, note in observations.items()])
    atomic(folder / 'paint/manual-review.json', json.dumps(proof, indent=2))
    details = []
    for row in report['entries']:
        ident = row['id']
        paint = f'paint/{ident:03d}.jpg' if ident in observations else f'../windows8020-full-viewports-review/consensus/{ident:03d}.jpg'
        note = observations.get(ident, 'Native painting not visually reinspected; the complete text output is identical to the previous trial.')
        details.append(f'<details><summary>Vista {ident} · {row["before"]} → {row["after"]}</summary>'
            f'<p><b>Original inventariado:</b> {html.escape(" / ".join(row["dialogue"]))}</p>'
            f'<p><b>Anterior:</b> {html.escape(" / ".join(r["translation"] for r in row["baseline_outputs"]))}</p>'
            f'<p><b>Ensayo:</b> {html.escape(" / ".join(r["translation"] for r in row["consensus_outputs"]))}</p>'
            f'<p>{html.escape(row["note"])}</p><p>{html.escape(note)}</p>'
            f'<div><img loading="lazy" src="../recovery-viewports801201/{ident:03d}.png" alt="Original">'
            f'<img loading="lazy" src="{paint}" alt="Dibujo nativo de comparación"></div></details>')
    m = report['cohorts']['all124_fixed_reading_viewports']
    historical = report['historical_baseline_comparison']['cohorts']['all124_fixed_reading_viewports']
    atomic(folder / 'index.html', '<!doctype html><html lang="es"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>Luma · cotejo de 124 vistas</title>'
        '<style>body{font:17px system-ui;background:#f1f4ed;color:#243b2b;margin:24px}p{max-width:1100px;line-height:1.6}'
        'details{margin:18px 0;border:1px solid #abc;padding:15px}div{display:flex}img{width:48%;object-fit:contain;align-self:start}</style>'
        f'<h1>124 vistas guardadas · ensayo de lectura completa</h1><p><b>{m["before_not_approved"]} → {m["after_not_approved"]} sin aprobar</b>, '
        f'{m["corrected"]} correcciones completas y {m["regressed"]} regresiones nuevas. Frente al control anterior a ambos ensayos: '
        f'{historical["before_not_approved"]} → {historical["after_not_approved"]}; reducción relativa del '
        f'{historical["relative_unapproved_reduction_percent"]:.2f} % en estas mismas vistas.</p>'
        '<p>Se inventarió el diálogo visible de los 124 originales. Se revisaron los diez resultados nuevos y se conservaron '
        '114 dictámenes únicamente por identidad de todas sus salidas en la misma ubicación. Las onomatopeyas no requieren traducción.</p>'
        '<p>Se inspeccionaron los diez dibujos nativos nuevos: aún hay restos de letras originales fuera de algunas máscaras. '
        'La revisión visual de las 124 superposiciones sigue pendiente. La galería reutiliza las imágenes existentes sin duplicarlas.</p>'
        '<p>Estas vistas no cubren todas las palabras de los capítulos ni usos completos en vivo. Persisten omisiones y errores '
        'de significado; el ensayo permanece fuera del uso normal y no está listo para publicar. '
        'El objetivo inferior al 5 % de fallos por uso no está acreditado.</p>'
        '<p><a href="../metrics/index.html">Resultados agregados</a></p>' + ''.join(details) + '</html>')
    print(json.dumps(dict(page=str(folder / 'index.html'), native_paintings_reviewed=10, ready_for_release=False)))


if __name__ == '__main__':
    main()
