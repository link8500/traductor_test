"""Render changed real outputs with the production painter; no OCR/MT rerun."""
import html
import json
import pathlib
import subprocess

from PIL import Image, ImageDraw, ImageFont
from audit_corpus_quality import ROOT, QA, atomic, digest, read, records


def main():
    folder=QA/'windows8029-refinement-full-viewports';paint=folder/'paint';paint.mkdir(exist_ok=True)
    summary=read(folder/'summary.json');assert summary['total_native_images']==131 and not summary['runtime_errors']
    fixed=records(folder/'output.jsonl');broad=read(folder/'broad-selected.json')
    pixels={r['image']:r for r in read(folder/'provenance.json')['pixels']}
    manifests=[];entries=[]
    original=QA/'recovery-viewports801201/111.png'
    manifests.append(dict(path=str(original),rows=[r for r in fixed if r['image']==111],output=str(paint/'fixed-111.jpg')))
    entries.append(dict(id=111,cohort='fixed',source_sha256=digest(original),output='fixed-111.jpg'))
    for r in broad:
        source=pathlib.Path(pixels[r['image']]['path']);assert digest(source)==pixels[r['image']]['sha256']
        b=r['bounds'];left=max(0,b[0]-65);top=max(0,b[1]-110);original=paint/f'broad-{r["case_id"]:03d}-source.png'
        with Image.open(source) as image:image.crop((left,top,min(image.width,b[2]+65),min(image.height,b[3]+110))).save(original)
        row=dict(r['after'],bounds=[b[0]-left,b[1]-top,b[2]-left,b[3]-top])
        output=f'broad-{r["case_id"]:03d}.jpg'
        manifests.append(dict(path=str(original),rows=[row],output=str(paint/output)))
        entries.append(dict(id=r['case_id'],cohort='broad',source_frame_sha256=digest(source),
                            crop_sha256=digest(original),crop_offset=[left,top],output=output))
    manifest=paint/'input.jsonl';atomic(manifest,''.join(json.dumps(r)+'\n' for r in manifests))
    result=paint/'result.json';binary=QA/'frozen-windows802901/traductor.exe'
    subprocess.run([str(binary),'--review-export',str(manifest),str(result)],check=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=180)
    assert read(result)['success'] and read(result)['images']==8
    for r in entries:r['paint_sha256']=digest(paint/r['output'])
    atomic(paint/'provenance.json',json.dumps(dict(binary_sha256=digest(binary),manifest_sha256=digest(manifest),
        result_sha256=digest(result),native_output_sha256=digest(folder/'output.jsonl'),broad_selected_sha256=digest(folder/'broad-selected.json'),
        entries=entries,production_painter=True,new_ocr_inference=False,new_translation_inference=False,
        fresh_screen_capture=False,all_paints_visually_approved=False),indent=2))
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',24)
    broad_entries=[r for r in entries if r['cohort']=='broad']
    for start in range(0,7,4):
        sheet=Image.new('RGB',(1440,1200),'#f1f4ed');draw=ImageDraw.Draw(sheet)
        for offset,c in enumerate(broad_entries[start:start+4]):
            x=offset%2*720;y=offset//2*600
            draw.text((x+12,y+10),f'Comparación {c["id"]} · render nativo',font=font,fill='#243b2b')
            with Image.open(paint/c['output']) as image:
                crop=image.copy();crop.thumbnail((700,540));sheet.paste(crop,(x+(720-crop.width)//2,y+50))
        sheet.save(paint/f'contact-{start//4+1:02d}.jpg',quality=93)
    decisions={r['id']:r for r in read(ROOT/'benchmarks/full-comics/refinement8029-meaning-decisions.json')['entries']}
    body=[]
    for c in broad_entries:
        d=decisions[c['id']]
        body.append(f'<details><summary>Comparación {c["id"]} · {html.escape(d["after"])}</summary><p>{html.escape(d["note"])}</p>'
                    f'<div><img loading="lazy" src="paint/broad-{c["id"]:03d}-source.png" alt="Original">'
                    f'<img loading="lazy" src="paint/{c["output"]}" alt="Pintor nativo"></div></details>')
    atomic(folder/'index.html','<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Luma · reconocimiento y preguntas</title><style>body{font:17px system-ui;background:#f1f4ed;color:#243b2b;margin:24px}p{max-width:1100px;line-height:1.6}details{margin:18px 0;border:1px solid #abc;padding:15px}div{display:flex}img{width:48%;object-fit:contain;align-self:start}</style>'
        '<h1>Windows802901 · reconocimiento y preguntas breves</h1><p>Se cotejaron las siete ubicaciones modificadas con los originales y Olympus: '
        'tres correcciones completas de significado y cuatro mejoras parciales que siguen sin aprobar. Hay un solapamiento con la muestra fija; las cuentas no se suman.</p>'
        '<p>La nueva prueba nativa repitió OCR y traducción sobre124 vistas guardadas y siete estados de lectura originales. '
        'El control fijo conserva56 ubicaciones sin aprobar. El OCR pasa de45 a44 discrepancias sobre las mismas2.265 palabras; no es una probabilidad de fallo por uso.</p>'
        '<p>Se muestran renders del pintor de producción, sin tomar nuevas capturas del escritorio. La revisión de cada palabra de todos los capítulos y menos del5 % de fallos por uso siguen pendientes. '
        '<a href="../refinement8029/review/index.html">Cotejo completo con Olympus</a> · <a href="../metrics/index.html">Métricas agregadas</a> · '
        '<a href="../windows8027-question-translation-replay/index.html">Fotografías fijas anteriores reutilizadas por identidad en las123 vistas sin cambios</a>.</p>'
        '<details><summary>Vista fija modificada · mejora parcial</summary><p>La palabra recuperada no corrige otro verbo defectuoso. Sigue sin aprobar.</p>'
        '<div><img src="../recovery-viewports801201/111.png" alt="Original fijo"><img src="paint/fixed-111.jpg" alt="Render fijo actual"></div></details>'
        +''.join(body)+'</html>')
    print(json.dumps(dict(native_paints=8,fresh_capture=False,visual_approval=False)),flush=True)


if __name__=='__main__':main()
