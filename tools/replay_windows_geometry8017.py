"""Render only actual Windows inference output on its original ten changed crops."""
import argparse
import json
import subprocess
from PIL import Image, ImageDraw, ImageFont
from audit_corpus_quality import QA, atomic, digest, read, records


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--final',action='store_true');parser.add_argument('--render',action='store_true');parser.add_argument('--short-clauses',action='store_true');parser.add_argument('--guarded-short-clauses',action='store_true');args=parser.parse_args()
    folder = QA/('windows8019-heldout-pixels' if args.guarded_short_clauses else 'windows8018-heldout-pixels' if args.short_clauses else 'windows8017-render-heldout-pixels' if args.render else 'windows8017-final-heldout-pixels' if args.final else 'windows8017-preserve-heldout-pixels')
    sample = read((QA/'windows8018-heldout-pixels' if args.guarded_short_clauses else folder)/'visual-review/sample.json')
    inputs = {r['image']:r for r in records(folder/'input.jsonl')}
    rows = records(folder/'output.jsonl')
    paint = folder/'paint'
    paint.mkdir(exist_ok=True)
    manifest = []
    for case in sample['cases']:
        ident = case['location_id']
        manifest.append(dict(path=inputs[ident]['path'], rows=[r for r in rows if r['image']==ident],
            output=str((paint/f'{case["id"]:02d}.jpg').resolve())))
    path = paint/'input.jsonl'
    atomic(path, ''.join(json.dumps(row)+'\n' for row in manifest))
    build='801901' if args.guarded_short_clauses else '801801' if args.short_clauses else '801704' if args.render else '801703' if args.final else '801702'
    snapshot_path = QA/f'windows-engine{build}.json'
    binary = QA/f'frozen-windows{build}/traductor.exe'
    assert digest(binary) == read(snapshot_path)['binary_sha256']
    target = paint/'result.json'
    subprocess.run([str(binary),'--review-export',str(path),str(target)],
        creationflags=subprocess.CREATE_NO_WINDOW,check=True,timeout=180)
    count=len(sample['cases'])
    assert read(target)['success'] and read(target)['images']==count
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf',23)
    for start in range(0,count,2):
        sheet = Image.new('RGB',(1500,1700),'#f1f4ed')
        draw = ImageDraw.Draw(sheet)
        for offset,case in enumerate(sample['cases'][start:start+2]):
            top = offset*850
            draw.text((12,top+10),f'Vista {case["id"]} · píxeles originales / superposición real de Windows',font=font,fill='#243b2b')
            for x,p in [(12,inputs[case['location_id']]['path']),(760,paint/f'{case["id"]:02d}.jpg')]:
                with Image.open(p) as bitmap:
                    im=bitmap.convert('RGB');im.thumbnail((720,780))
                    sheet.paste(im,(x+(720-im.width)//2,top+55))
        sheet.save(paint/f'sheet-{start//2+1:02d}.jpg',quality=94)
    value = dict(actual_app_selected_crops=count, native_output_sha256=digest(folder/'output.jsonl'),
        binary_sha256=digest(binary), manifest_sha256=digest(path), render_result_sha256=digest(target),
        saved_pixels_not_live_desktop_capture=True, words_from_app_only=True,
        manual_translation_answers_used=False, layout_visually_reviewed=False)
    if not args.guarded_short_clauses:value['actual_app_changed_crops']=count
    atomic(paint/'provenance.json',json.dumps(value,indent=2))
    images=''.join(f'<img loading="lazy" src="sheet-{i:02d}.jpg" alt="Vista {i}">' for i in range(1,(count+1)//2+1))
    review_link='../index.html' if args.guarded_short_clauses else '../visual-review/index.html'
    atomic(paint/'index.html',f'<!doctype html><html lang="es"><meta charset="utf-8"><title>Luma · superposición</title><style>body{{font:17px system-ui;background:#f1f4ed;color:#243b2b}}img{{display:block;max-width:100%;margin:24px auto}}</style><h1>Superposición del motor real · {count} ubicaciones</h1><p>Los píxeles guardados originales y las salidas reales de Windows{build} se dibujaron con el exportador nativo. Son recortes de diálogo, no capturas de interacción en vivo.</p><p><a href="{review_link}">Cotejo del significado</a> · <a href="../../metrics/index.html">Resultados agregados</a></p>{images}</html>')
    print(json.dumps(value),flush=True)


if __name__=='__main__':main()
