"""Show every fixed view, reusing identical pictures and keeping failed views."""
import html
import json
import argparse
from audit_corpus_quality import ROOT, QA, atomic, digest, read, records


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--question',action='store_true');args=parser.parse_args()
    folder=QA/('windows8027-question-translation-replay' if args.question else 'windows8026-inflection-full-viewports')
    report=read(ROOT/'benchmarks/full-comics'/('windows8027-question-semantic-review.json' if args.question else 'windows8026-inflection-full-viewports-semantic-review.json'))
    new=records(folder/'output.jsonl')
    review=read(folder/'paint/manual-review.json')
    assert review['native_paint_provenance_sha256']==digest(folder/'paint/provenance.json')
    changed={r['id']:r for r in review['entries']}
    assert len(changed)==report['changed_complete_location_meanings_reviewed' if args.question else 'changed_full_location_meanings_reviewed']
    previous_paint={r['id'] for r in read(QA/'windows8026-inflection-full-viewports/paint/manual-review.json')['entries']} if args.question else set()
    short_paint={r['id'] for r in read(QA/'windows8024-short-full-viewports/paint/manual-review.json')['entries']}
    older_paint={r['id'] for r in read(QA/'windows8021-full-viewports-full-agreement/paint/manual-review.json')['entries']}
    inventory={r['id']:r for r in read(ROOT/'benchmarks/full-comics/viewport8020-original-inventory.json')['entries']}
    parts=[]
    for row in report['entries']:
        ident=row['id']
        paint=f'paint/{ident:03d}.jpg' if ident in changed else f'../windows8026-inflection-full-viewports/paint/{ident:03d}.jpg' if ident in previous_paint else f'../windows8024-short-full-viewports/paint/{ident:03d}.jpg' if ident in short_paint else f'../windows8021-full-viewports-full-agreement/paint/{ident:03d}.jpg' if ident in older_paint else f'../windows8020-full-viewports-review/consensus/{ident:03d}.jpg'
        assert (folder/paint).exists()
        note=changed[ident]['observation'] if ident in changed else 'Fotografía anterior reutilizada por identidad de todos los campos mostrados. No añade una aprobación visual nueva.'
        text=' / '.join(r['translation'] for r in new if r['image']==ident)
        notes=''.join(f'<p>{html.escape(value)}</p>' for value in dict.fromkeys([row.get('note'),note]) if value)
        parts.append(f'<details><summary>Vista {ident} · {row["before"]} → {row["after"]}</summary><p>Original: {html.escape(" / ".join(inventory[ident]["dialogue"]))}</p><p>Salida: {html.escape(text)}</p>{notes}<div><img loading="lazy" src="../recovery-viewports801201/{ident:03d}.png" alt="Original"><img loading="lazy" src="{paint}" alt="Superposición nativa"></div></details>')
    m=report['cohorts']['all124_fixed_reading_viewports'];word=report['dialogue_ocr']['all124_fixed_reading_viewports']
    title='conservación de preguntas' if args.question else 'reconocimiento corroborado'
    scope='Se tradujeron de nuevo las 229 regiones con el ejecutable actual sobre las lecturas OCR conservadas. Se cotejó la ubicación modificada y se reutilizaron 123 dictámenes por identidad de todos los campos mostrados. El render nuevo conserva pequeños trazos del original: el significado está corregido, pero la superposición visual no se aprueba. No es una nueva captura ni un nuevo OCR.' if args.question else 'Se cotejaron las dos ubicaciones completas modificadas. Los otros 122 dictámenes se reutilizan solo tras comprobar identidad de fuente, traducción y coordenadas. Las dos fotografías nuevas se revisaron; las otras se enlazan sin duplicarse. No se certifican todas las superposiciones.'
    atomic(folder/'index.html',f'<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luma · {title}</title><style>body{{font:17px system-ui;background:#f1f4ed;color:#243b2b;margin:24px}}p{{max-width:1100px;line-height:1.6}}details{{margin:18px 0;border:1px solid #abc;padding:15px}}div{{display:flex}}img{{width:48%;object-fit:contain;align-self:start}}</style>'
        f'<h1>Windows {report["build"]} · 124 vistas fijas · {title}</h1><p><b>{m["before_not_approved"]} → {m["after_not_approved"]} vistas sin aprobar</b>. Correcciones completas: {m["corrected"]}; regresiones: {m["regressed"]}. OCR: {word["before"]["word_errors"]} → {word["after"]["word_errors"]} discrepancias sobre las mismas {word["after"]["expected_dialogue_words"]} palabras esperadas.</p>'
        f'<p>{scope}</p><p>Una captura por capítulo no cubre todas sus palabras. El objetivo de menos del 5 % de fallos por uso completo sigue sin acreditarse. Las onomatopeyas pueden permanecer sin traducir.</p><p><a href="../metrics/index.html">Métricas agregadas</a></p>'+''.join(parts)+'</html>')
    print(json.dumps(dict(views=124,new_pictures=len(changed),reused_pictures=124-len(changed))),flush=True)


if __name__=='__main__':main()
