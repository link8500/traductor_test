"""Paint actual accepted tail outputs over their original pixels."""
import html
import json
import pathlib
import subprocess

from PIL import Image,ImageDraw,ImageFont
from audit_corpus_quality import ROOT,QA,atomic,digest,read


def main():
    folder=QA/'windows8030-tail-translation-replay';paint=folder/'paint';paint.mkdir(exist_ok=True)
    changes=read(folder/'changes.json');assert len(changes)==10
    sample={r['id']:r for r in read(QA/'tail8030/review/sample.json')}
    decisions={r['id']:r for r in read(ROOT/'benchmarks/full-comics/tail8030-meaning-decisions.json')['entries']}
    manifests=[];entries=[]
    for c in changes:
        page=sample[c['id']]['source_page'];source=pathlib.Path(page['path']);assert digest(source)==page['sha256']
        b=c['bounds'];left=max(0,b[0]-65);top=max(0,b[1]-110);original=paint/f'case-{c["id"]:03d}-source.png'
        with Image.open(source) as image:image.crop((left,top,min(image.width,b[2]+65),min(image.height,b[3]+110))).save(original)
        actual=c['actual_native'];assert actual['translation']==c['policy']['candidate_translation']
        row=dict(actual,bounds=[b[0]-left,b[1]-top,b[2]-left,b[3]-top]);output=f'case-{c["id"]:03d}.jpg'
        manifests.append(dict(path=str(original),rows=[row],output=str(paint/output)))
        entries.append(dict(id=c['id'],source_frame_sha256=digest(source),crop_sha256=digest(original),
                            crop_offset=[left,top],output=output,translation=actual['translation']))
    manifest=paint/'input.jsonl';atomic(manifest,''.join(json.dumps(r)+'\n' for r in manifests))
    result=paint/'result.json';binary=QA/'frozen-windows803001/traductor.exe'
    subprocess.run([str(binary),'--review-export',str(manifest),str(result)],check=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=180)
    assert read(result)['success'] and read(result)['images']==10
    for r in entries:r['paint_sha256']=digest(paint/r['output'])
    atomic(paint/'provenance.json',json.dumps(dict(binary_sha256=digest(binary),manifest_sha256=digest(manifest),
        result_sha256=digest(result),native_changes_sha256=digest(folder/'changes.json'),
        entries=entries,production_painter=True,new_ocr_inference=False,new_translation_inference=False,
        fresh_screen_capture=False,all_paints_visually_approved=False),indent=2))
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',24)
    for start in range(0,len(entries),4):
        sheet=Image.new('RGB',(1440,1200),'#f1f4ed');draw=ImageDraw.Draw(sheet)
        for offset,c in enumerate(entries[start:start+4]):
            x=offset%2*720;y=offset//2*600
            draw.text((x+12,y+10),f'Comparación {c["id"]} · render nativo',font=font,fill='#243b2b')
            with Image.open(paint/c['output']) as image:
                crop=image.copy();crop.thumbnail((700,540));sheet.paste(crop,(x+(720-crop.width)//2,y+50))
        sheet.save(paint/f'contact-{start//4+1:02d}.jpg',quality=93)
    body=[]
    for c in entries:
        d=decisions[c['id']]
        body.append(f'<details><summary>Comparación {c["id"]} · {html.escape(d["after"])}</summary><p>{html.escape(d["note"])}</p>'
                    f'<div><img loading="lazy" src="paint/case-{c["id"]:03d}-source.png" alt="Original">'
                    f'<img loading="lazy" src="paint/{c["output"]}" alt="Pintor nativo"></div></details>')
    atomic(folder/'index.html','<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Luma · frases finales</title><style>body{font:17px system-ui;background:#f1f4ed;color:#243b2b;margin:24px}p{max-width:1100px;line-height:1.6}details{margin:18px 0;border:1px solid #abc;padding:15px}div{display:flex}img{width:48%;object-fit:contain;align-self:start}</style>'
        '<h1>Windows803001 · recuperación de frases finales</h1><p>Se examinaron los124 informes completos guardados, incluidas salidas sin alerta. '
        'Se ensayaron98 candidatos; diez cambios sobreviven las comprobaciones. Seis son correcciones completas de contenido y cuatro son mejoras parciales que siguen sin aprobar. '
        'Una adición inicial se rechazó por cambiar varios destinatarios a uno. No se cuenta como corrección.</p>'
        '<p>El ejecutable volvió a traducir334 fuentes:229 regiones del control fijo, siete ubicaciones de control anteriores y98 candidatos. '
        'Se reutiliza el reconocimiento de píxeles; no son capturas nuevas del escritorio. Los controles fijos permanecen idénticos y conservan56 vistas sin aprobar. '
        'Las cuentas del diagnóstico no se suman a las vistas fijas ni permiten estimar menos del5 % de fallos por uso.</p>'
        '<p>Se muestran renders del pintor de producción. Persisten defectos de significado y de superposición; los renders no aprueban un uso completo de la app. '
        '<a href="../tail8030/review/index.html">Comparación bilingüe de los once cambios iniciales, incluido el rechazado</a> · '
        '<a href="../metrics/index.html">Métricas agregadas</a>.</p>'+''.join(body)+'</html>')
    print(json.dumps(dict(native_paints=len(entries),fresh_capture=False,visual_approval=False)),flush=True)


if __name__=='__main__':main()
