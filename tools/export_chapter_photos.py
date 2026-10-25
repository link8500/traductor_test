"""Export every source image with recorded Luma output for visual review.

The native production text painter is reused. These are review renders of
saved inference, not fresh OCR passes or screenshots of a physical phone.
All source pages, including pages with no detections, remain visible.
"""
import argparse,collections,concurrent.futures,datetime,hashlib,html,json,os,pathlib,re,subprocess,tempfile
from PIL import Image

ROOT=pathlib.Path(__file__).resolve().parents[1];QA=ROOT/'build/full-comics'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
escape=lambda s:html.escape(str(s),quote=True)
STYLE='''body{font:16px system-ui;margin:0;background:#f1f4ed;color:#26382b}main{max-width:1600px;margin:auto;padding:22px}a{color:#216044}p{max-width:1050px;line-height:1.6}.note{background:#fff5da;border-left:4px solid #937035;padding:14px}table{border-collapse:collapse;width:100%;background:white}td,th{padding:10px;vertical-align:top;text-align:left;border-bottom:1px solid #d5dfce}.pair{display:grid;grid-template-columns:1fr 1fr;gap:8px}.pair img{width:100%;height:auto;display:block}section{background:white;padding:12px;margin:20px 0;scroll-margin-top:100px}details{margin:12px 0}summary{cursor:pointer}header{position:sticky;top:0;background:#f1f4ed;z-index:2;padding:10px}button,input{font:inherit;padding:8px}.pending{color:#85551e}@media(max-width:700px){main{padding:8px}.pair{gap:12px;grid-template-columns:1fr}td,th{padding:6px}header h1{font-size:18px;margin:6px 0}header{font-size:13px;padding:4px}}'''

def relative(path,destination):return os.path.relpath(path,destination).replace('\\','/')

def cohort(folder):
    return 'Recorrido anterior' if folder=='translated-en-final' else 'Reconocimiento '+folder.removeprefix('translated-en').replace('-context',' · selección de capturas por contexto')

def comparison_view(chapter,folder):
    version=folder.removeprefix('translated-en')
    candidate='review'+version
    return candidate if version!='-final' and (QA/candidate/(chapter+'.html')).exists() else 'review'

def write_chapter(destination,chapter,pages,rows,folder,record,spanish):
    sections=[]
    recorded_files={p['image']:p['file'] for p in record.get('pages',[])}
    for page in pages:
        photo=destination/chapter/recorded_files.get(page['image'],f'{page["image"]:03d}.jpg')
        original=relative(pathlib.Path(page['path']),destination)
        table=[]
        for row in rows:
            if row['image']!=page['image']:continue
            table.append('<tr><td>'+escape(row['source'])+'</td><td>'+escape(row.get('translation',row.get('error','Sin salida')))+
                '</td><td>'+escape(', '.join(map(str,row['bounds'])))+'</td></tr>')
        sections.append(f'<section id="image-{page["image"]}"><h2>Imagen {page["image"]+1} de {len(pages)}</h2><p><a href="{escape(original)}">Original completo</a> · <a href="{escape(relative(photo,destination))}">Salida completa de Luma</a></p><div class="pair"><div>Inglés<img loading="lazy" src="{escape(original)}" width="{page["width"]}" height="{page["height"]}" alt="Original, imagen {page["image"]+1}"></div><div>Luma · salida guardada<img loading="lazy" src="{escape(relative(photo,destination))}" width="{page["width"]}" height="{page["height"]}" alt="Luma, imagen {page["image"]+1}"></div></div><details><summary>{len(table)} regiones reconocidas y traducidas</summary><table><thead><tr><th>Inglés reconocido</th><th>Salida real de Luma</th><th>Coordenadas</th></tr></thead><tbody>'+''.join(table)+'</tbody></table></details></section>')
        sections[-1]=sections[-1].replace('<div>Luma · salida guardada',f'<div id="translation-{page["image"]}" style="scroll-margin-top:100px">Luma · salida guardada')
    refs=''.join(f'<details><summary>Olympus · imagen {p["image"]+1}</summary><img loading="lazy" style="max-width:100%" src="{escape(relative(pathlib.Path(p["path"]),destination))}" alt="Referencia española, imagen {p["image"]+1}"></details>' for p in spanish)
    description=cohort(folder)
    view=comparison_view(chapter,folder)
    document=f'<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(chapter)} · Fotos de revisión</title><style>{STYLE}</style><main><header><a href="index.html">← 124 capítulos</a> · <a href="../review/{chapter}.html">Comparación por palabras con Olympus</a><h1>{escape(chapter)}</h1></header><p class="note">{description}. Estas imágenes reproducen las salidas guardadas de Luma con el pintor de texto de Windows. No son capturas nuevas del teléfono. Se mantienen todas las imágenes originales para que también se vean los textos omitidos. La alineación centrada y el fondo muestreado se reconstruyen para la revisión; la presentación de Android puede variar. Ninguna página queda aprobada automáticamente.</p><p>{len(pages)} imágenes inglesas completas · {len(rows)} regiones · <a href="{chapter}/provenance.json">Procedencia y huellas</a> · <a href="../{folder}/{chapter}-en.jsonl">Lecturas y traducciones sin editar</a></p>'+''.join(sections)+f'<section><h2>Edición española de Olympus · {len(spanish)} imágenes</h2><p>La edición humana tiene otra paginación. Estas imágenes se conservan completas como referencia.</p>'+refs+'</section></main></html>'
    document=document.replace(f'../review/{chapter}.html',f'../{view}/{chapter}.html')
    document=document.replace('Lecturas y traducciones sin editar</a></p>',f'Lecturas y traducciones sin editar</a> · <a href="../chapter-audit/{chapter}.html">Alertas para revisar</a></p>')
    visual=ROOT/'benchmarks/full-comics/visual-reviews'/(chapter+'.json')
    if visual.exists():
        report=read(visual)
        document=document.replace('<section id=',f'<p class="note"><a href="../word-review/{chapter}.html">Revisión detallada: {len(report["entries"])} parejas de diálogo cotejadas palabra por palabra</a>. Las observaciones identifican su pasada; otras palabras del capítulo siguen pendientes.</p><section id=',1)
        evaluation=folder.replace('translated-en','visual-evaluation')
        if (QA/evaluation/(chapter+'.html')).exists():
            document=document.replace('<section id=',f'<p><a href="../{evaluation}/{chapter}.html">Cada palabra del OCR actual frente a la lectura visual verificada</a></p><section id=',1)
    (destination/(chapter+'.html')).write_text(document,encoding='utf-8')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start',type=int,default=1);parser.add_argument('--end',type=int,default=124)
    parser.add_argument('--workers',type=int,default=2);parser.add_argument('--output-name',default='chapter-photos')
    parser.add_argument('--html-only',action='store_true',help='Refresh the viewer without rendering or changing recorded inference')
    parser.add_argument('--current-reports',default='translated-en8007')
    parser.add_argument('--binary',type=pathlib.Path,default=QA/'frozen-windows8009/traductor.exe')
    parser.add_argument('--preserve-existing',action='store_true',help='Resume the recorded inference cohort of completed photos')
    args=parser.parse_args()
    assert 1<=args.start<=args.end<=124 and 1<=args.workers<=3
    for name in [args.output_name,args.current_reports]:assert re.fullmatch(r'[a-z][a-z0-9-]+',name)
    destination=QA/args.output_name;destination.mkdir(exist_ok=True)
    binary=args.binary.resolve();binary_sha=digest(binary)
    source_sha={name:digest(ROOT/name) for name in ['windows/runner/screen_translator.cpp','windows/runner/review_export.cpp']}
    grouped=collections.defaultdict(list);spanish=collections.defaultdict(list)
    for page in read(QA/'images-en.json'):
        if page['series']=='absolute-regression':grouped[page['chapter'].removesuffix('-en')].append(page)
    for page in read(QA/'images-es.json'):
        if page['series']=='absolute-regression':spanish[page['chapter'].removesuffix('-es')].append(page)
    def render(number):
        chapter=f'absolute-regression-{number:02d}';pages=grouped[chapter]
        target=destination/chapter;target.mkdir(exist_ok=True);proof=target/'provenance.json'
        current=QA/args.current_reports/(chapter+'-en.done.json')
        folder=args.current_reports if current.exists() and read(current).get('all_files_traversed') else 'translated-en-final'
        if args.preserve_existing and proof.exists():folder=read(proof)['report_directory']
        report=QA/folder/(chapter+'-en.jsonl');status=read(report.with_name(chapter+'-en.done.json'))
        assert status['images']==len(pages) and status.get('all_files_traversed'),chapter
        report_sha=digest(report);rows=[json.loads(s) for s in report.read_text(encoding='utf-8').splitlines() if s.strip()]
        if proof.exists():
            old=read(proof)
            if old.get('report_sha256')==report_sha and old.get('renderer_binary_sha256')==binary_sha and len(old.get('pages',[]))==len(pages) and all((target/p['file']).exists() for p in old['pages']):
                write_chapter(destination,chapter,pages,rows,folder,old,spanish[chapter]);return old
        # A later OCR/NMT pass must not overwrite pictures still displayed
        # with the preceding pass's provenance. Publish a new immutable set.
        rendered=target/report_sha[:16];rendered.mkdir(exist_ok=True)
        output=[]
        with tempfile.TemporaryDirectory(prefix=chapter+'-',dir=destination) as temporary:
            temporary=pathlib.Path(temporary);manifest=[]
            for page in pages:
                original=pathlib.Path(page['path']);assert digest(original)==page['sha256'],original
                png=temporary/f'{page["image"]:03d}.png'
                with Image.open(original) as image:image.convert('RGB').save(png,compress_level=1)
                manifest.append(dict(path=str(png),output=str(rendered/f'{page["image"]:03d}.jpg'),rows=[r for r in rows if r['image']==page['image']]))
            inputs=temporary/'input.jsonl';inputs.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in manifest),encoding='utf-8')
            summary=temporary/'result.json'
            subprocess.run([str(binary),'--review-export',str(inputs),str(summary)],check=True,timeout=600,creationflags=subprocess.CREATE_NO_WINDOW)
            native=read(summary);assert native.get('success') and native['images']==len(pages),native
            for page in pages:
                photo=rendered/f'{page["image"]:03d}.jpg'
                with Image.open(photo) as image:assert image.size==(page['width'],page['height']);image.verify()
                output.append(dict(image=page['image'],original_sha256=page['sha256'],output_sha256=digest(photo),file=photo.relative_to(target).as_posix(),width=page['width'],height=page['height']))
        value=dict(chapter=chapter,images=len(pages),regions=len(rows),report_directory=folder,report_sha256=report_sha,
            recorded_inference_engine=status['engine'],renderer_binary_sha256=binary_sha,renderer_sources=source_sha,
            fresh_capture=False,fresh_ocr=False,all_words_visually_reviewed=False,meaning_approved=False,
            render_scope='Saved model outputs; production Windows text painter with reconstructed centered layout and sampled backgrounds; not Android screenshots',
            pages=output,generated_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        pending=proof.with_suffix('.pending');pending.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');pending.replace(proof)
        write_chapter(destination,chapter,pages,rows,folder,value,spanish[chapter])
        print('Photos',number,len(pages),folder,flush=True);return value
    def index():
        statuses=[]
        for number in range(1,125):
            chapter=f'absolute-regression-{number:02d}';path=destination/chapter/'provenance.json'
            if path.exists():statuses.append(read(path))
        count=sum(r['images'] for r in statuses);rows=[]
        for r in sorted(statuses,key=lambda r:int(r['chapter'].split('-')[-1])):
            rows.append(f'<tr><td><a href="{r["chapter"]}.html">{int(r["chapter"].split("-")[-1])}</a></td><td>{r["images"]}</td><td>{r["regions"]}</td><td>'+cohort(r['report_directory'])+'</td><td class="pending">Pendiente</td></tr>')
        summary=dict(chapters_exported=len(statuses),chapters_expected=124,source_images_rendered=count,
            current_engine_chapters=sum(r['report_directory']!='translated-en-final' for r in statuses),
            all_words_visually_reviewed=False,semantic_accuracy=None,chapters=[dict(chapter=r['chapter'],images=r['images'],report_directory=r['report_directory']) for r in statuses])
        latest_build=re.search(r'^version:.*\+(\d+)',(ROOT/'pubspec.yaml').read_text(encoding='utf-8'),re.M)[1]
        summary['latest_build']=int(latest_build)
        summary['latest_build_chapters']=sum(r['report_directory'] in ['translated-en'+latest_build,'translated-en'+latest_build+'-context'] for r in statuses)
        document=f'<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="60"><title>Luma · Imágenes por capítulo</title><style>{STYLE}</style><main><h1>Regresión Absoluta · imágenes de los 124 capítulos</h1><p>{len(statuses)}/124 capítulos exportados · {count} imágenes completas · {summary["current_engine_chapters"]} capítulos con la nueva pasada.</p><p class="note">Original y salida real guardada de Luma, sin corregir sus frases para la foto. Son imágenes de revisión generadas con el pintor de Windows; no son nuevas capturas del teléfono. «Anterior» identifica los capítulos cuya nueva pasada todavía no termina. Todas las zonas del original aparecen, incluso sin texto detectado. La revisión visual completa y la precisión semántica siguen pendientes.</p><p><a href="../coverage8008/index.html">Cobertura de reconocimiento actual</a> · <a href="../review/index.html">Comparación con Olympus</a> · <a href="../poco8008-underwater/translated.png">Captura real del fallo UNDERWATER en el teléfono</a> · <a href="summary.json">Datos de cobertura de imágenes</a></p><table><thead><tr><th>Capítulo</th><th>Imágenes completas</th><th>Regiones</th><th>Pasada</th><th>Revisión visual completa</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></main></html>'
        for name,value in [('summary.json',json.dumps(summary,ensure_ascii=False,indent=2)),('index.html',document)]:
            if name=='index.html':value=value.replace('<a href="summary.json">Datos de cobertura de imágenes</a>', '<a href="../metrics/index.html">Totales de errores y reducción entre pasadas</a> · <a href="../chapter-audit/index.html">Alertas de los 124 capítulos</a> · <a href="../word-review/index.html">Avance de revisión visual por palabras</a> · <a href="summary.json">Datos de cobertura de imágenes</a>')
            if name=='index.html':value=value.replace(f'{summary["current_engine_chapters"]} capítulos con la nueva pasada.',f'{summary["current_engine_chapters"]} capítulos con OCR renovado. Compilación {latest_build}: {summary["latest_build_chapters"]}/124 capítulos publicados.')
            pending=destination/(name+'.pending');pending.write_text(value,encoding='utf-8');pending.replace(destination/name)
    if args.html_only:
        for proof in destination.glob('absolute-regression-*/provenance.json'):
            record=read(proof);chapter=record['chapter'];folder=record['report_directory']
            report=QA/folder/(chapter+'-en.jsonl')
            assert digest(report)==record['report_sha256'],'Recorded inference changed'
            rows=[json.loads(s) for s in report.read_text(encoding='utf-8').splitlines() if s.strip()]
            write_chapter(destination,chapter,grouped[chapter],rows,folder,record,spanish[chapter])
        index();return
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        order=([124] if args.start<=124<=args.end else [])+[n for n in range(args.start,args.end+1) if n!=124]
        for task in concurrent.futures.as_completed([pool.submit(render,n) for n in order]):task.result();index()
    index()

if __name__=='__main__':main()
