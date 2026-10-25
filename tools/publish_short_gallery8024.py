"""Reuse existing comparison photographs; render only the changed viewport."""
import html
import json
from audit_corpus_quality import ROOT, QA, atomic, digest, read


def main():
    folder=QA/'windows8024-short-full-viewports'
    report_path=ROOT/'benchmarks/full-comics/windows8024-short-full-viewports-semantic-review.json'
    report=read(report_path);review=read(folder/'paint/manual-review.json')
    assert review['native_paint_provenance_sha256']==digest(folder/'paint/provenance.json')
    changed={r['id']:r for r in review['entries']}
    assert len(changed)==report['changed_viewports_reviewed']
    old_paint={r['id'] for r in read(QA/'windows8021-full-viewports-full-agreement/paint/manual-review.json')['entries']}
    parts=[]
    for row in report['entries']:
        ident=row['id']
        paint=f'paint/{ident:03d}.jpg' if ident in changed else f'../windows8021-full-viewports-full-agreement/paint/{ident:03d}.jpg' if ident in old_paint else f'../windows8020-full-viewports-review/consensus/{ident:03d}.jpg'
        assert (folder/paint).exists()
        note=changed[ident]['observation'] if ident in changed else 'Dibujo anterior reutilizado por identidad de texto y coordenadas; no se añade una aprobación visual nueva.'
        parts.append(f'<details><summary>Vista {ident} · {row["before"]} → {row["after"]}</summary>'
            f'<p>Original: {html.escape(" / ".join(row["dialogue"]))}</p>'
            f'<p>Salida: {html.escape(" / ".join(r["translation"] for r in row["candidate_outputs"]))}</p>'
            f'<p>{html.escape(row["note"])}</p><p>{html.escape(note)}</p>'
            f'<div><img loading="lazy" src="../recovery-viewports801201/{ident:03d}.png" alt="Original">'
            f'<img loading="lazy" src="{paint}" alt="Superposición nativa"></div></details>')
    m=report['cohorts']['all124_fixed_reading_viewports'];word=report['dialogue_ocr']['all124_fixed_reading_viewports']
    atomic(folder/'index.html','<!doctype html><html lang="es"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>Luma · recuperación de diálogo corto</title>'
        '<style>body{font:17px system-ui;background:#f1f4ed;color:#243b2b;margin:24px}p{max-width:1100px;line-height:1.6}'
        'details{margin:18px 0;border:1px solid #abc;padding:15px}div{display:flex}img{width:48%;object-fit:contain;align-self:start}</style>'
        f'<h1>124 vistas fijas · recuperación de diálogo corto</h1><p><b>{m["before_not_approved"]} → {m["after_not_approved"]} sin aprobar</b>, '
        f'{m["corrected"]} correcciones y {m["regressed"]} regresiones completas. OCR: {word["before"]["word_errors"]} → {word["after"]["word_errors"]} '
        f'errores sobre {word["after"]["expected_dialogue_words"]} palabras.</p>'
        '<p>Se cotejaron todas las salidas en las mismas ubicaciones. Solo las vistas con cambios tienen un nuevo dictamen; las idénticas conservan su evaluación. '
        'Se conservan los cortes y errores pendientes. Las fotografías existentes se enlazan sin duplicarse.</p>'
        '<p>Una vista por capítulo no cubre todas sus palabras. No es una prueba de usos completos de la app y el objetivo de fallos inferior al 5 % sigue sin acreditarse. '
        'Esta variante combina la recuperación corta con lectores adicionales experimentales. La configuración normal tiene su propia comparación; no se certifican todas las pinturas.</p>'
        '<p><a href="../metrics/index.html">Métricas agregadas</a></p>'+''.join(parts)+'</html>')
    print(json.dumps(dict(page=str(folder/'index.html'),photographs_reused=124-len(changed),new_paintings=len(changed))),flush=True)


if __name__=='__main__':main()
