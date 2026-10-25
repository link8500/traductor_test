"""Paint every changed expanded output through the production Windows painter."""
import html
import json
import pathlib
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFont
from audit_corpus_quality import QA, ROOT, atomic, digest, read


def main():
    folder=QA/'windows8028-opening-translation-replay';paint=folder/'paint';paint.mkdir(exist_ok=True)
    assert shutil.disk_usage(folder).free>=4*1024**3
    changes=read(folder/'expanded-changes.json');cases={r['id']:r for r in read(QA/'opening8028/review/sample.json')}
    decisions={r['id']:r for r in read(ROOT/'benchmarks/full-comics/opening8028-meaning-decisions.json')['entries']}
    manifest=[];proof=[]
    for change in changes:
        c=cases[change['id']];page=c['source_page'];source=pathlib.Path(page['path'])
        assert digest(source)==page['sha256']
        b=c['bounds'];left=max(0,b[0]-65);top=max(0,b[1]-110)
        original=paint/f'{c["id"]:03d}-source.png';target=paint/f'{c["id"]:03d}.jpg'
        with Image.open(source) as image:
            image.crop((left,top,min(image.width,b[2]+65),min(image.height,b[3]+110))).save(original)
        row=dict(bounds=[b[0]-left,b[1]-top,b[2]-left,b[3]-top],translation=change['after'],retained_original=False)
        manifest.append(dict(path=str(original),rows=[row],output=str(target)))
        proof.append(dict(id=c['id'],original_image_sha256=page['sha256'],crop_offset=[left,top],
                          crop_sha256=digest(original),translation=change['after'],whole_meaning=decisions[c['id']]['after']))
    inputs=paint/'input.jsonl';atomic(inputs,''.join(json.dumps(r)+'\n' for r in manifest))
    result=paint/'result.json';binary=QA/'frozen-windows802801/traductor.exe'
    subprocess.run([str(binary),'--review-export',str(inputs),str(result)],check=True,
                   creationflags=subprocess.CREATE_NO_WINDOW,timeout=180)
    assert read(result)['success'] and read(result)['images']==17
    for entry in proof:entry['paint_sha256']=digest(paint/f'{entry["id"]:03d}.jpg')
    atomic(paint/'provenance.json',json.dumps(dict(binary_sha256=digest(binary),manifest_sha256=digest(inputs),
           result_sha256=digest(result),changes_sha256=digest(folder/'expanded-changes.json'),entries=proof,
           native_renderer=True,new_ocr_inference=False,fresh_screen_capture=False,visual_approval=False),indent=2))
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',24)
    for start in range(0,len(proof),4):
        sheet=Image.new('RGB',(1440,1200),'#f1f4ed');draw=ImageDraw.Draw(sheet)
        for offset,c in enumerate(proof[start:start+4]):
            x=(offset%2)*720;y=(offset//2)*600
            draw.text((x+12,y+10),f"Caso {c['id']} · render nativo",font=font,fill='#243b2b')
            with Image.open(paint/f'{c["id"]:03d}.jpg') as image:
                crop=image.copy();crop.thumbnail((700,540));sheet.paste(crop,(x+(720-crop.width)//2,y+50))
        sheet.save(paint/f'contact-{start//4+1:02d}.jpg',quality=93)
    body=[]
    for change in changes:
        i=change['id'];body.append(f'<details><summary>Comparación {i} · {html.escape(decisions[i]["after"])}</summary>'
            f'<p>{html.escape(decisions[i]["note"])}</p><p>Antes: {html.escape(change["before"])}</p>'
            f'<p>Actual: {html.escape(change["after"])}</p><div><img loading="lazy" src="paint/{i:03d}-source.png" alt="Original">'
            f'<img loading="lazy" src="paint/{i:03d}.jpg" alt="Render nativo actual"></div></details>')
    atomic(folder/'index.html','<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Luma · aperturas conservadas</title><style>body{font:17px system-ui;background:#f1f4ed;color:#243b2b;margin:24px}p{max-width:1100px;line-height:1.6}details{margin:18px 0;border:1px solid #abc;padding:15px}div{display:flex}img{width:48%;object-fit:contain;align-self:start}</style>'
        '<h1>Windows802801 · aperturas de diálogo</h1><p>Se buscaron candidatos en los124 capítulos del control:68 bloques. '
        'Se cotejaron las17 salidas modificadas:11 correcciones completas, cinco recuperaciones parciales con otros defectos y una ubicación pendiente. '
        'Los otros51 candidatos conservan sus salidas; no reciben una aprobación semántica nueva. No se suman estos recuentos a las124 vistas fijas.</p>'
        '<p>Las229 regiones de las124 vistas fijas se tradujeron de nuevo y conservan exactamente su texto:56 vistas sin aprobar. '
        'El OCR y la captura se reutilizan. Estos renders usan el pintor nativo sobre recortes originales; no son capturas de un uso completo en vivo. '
        'La revisión de todas las palabras y menos del5 % de fallos por uso siguen pendientes.</p>'
        '<p><a href="../metrics/index.html">Métricas agregadas</a> · <a href="../opening8028/review/index.html">Cotejo con Olympus, con propuestas de alineación</a> · '
        '<a href="../windows8027-question-translation-replay/index.html">124 fotografías fijas reutilizadas por identidad</a></p>'
        +''.join(body)+'</html>')
    print(json.dumps(dict(native_paints=17,contact_sheets=5,new_ocr=False,fresh_capture=False,visual_approval=False)),flush=True)


if __name__=='__main__':main()
