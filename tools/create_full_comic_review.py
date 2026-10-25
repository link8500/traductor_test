"""Static local per-word review with every source page; no network or telemetry."""
import argparse,bisect,collections,hashlib,html,json,os,pathlib,re

ROOT=pathlib.Path(__file__).resolve().parents[1];QA=ROOT/'build/full-comics'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--comparisons',default='comparison');parser.add_argument('--output-name',default='review')
parser.add_argument('--english-reports')
parser.add_argument('--series',choices=['all','absolute-regression'],default='all')
args=parser.parse_args()
for name in [args.comparisons,args.output_name,args.english_reports]:
    if name and not re.fullmatch(r'[a-z][a-z0-9-]+',name):parser.error('Invalid QA directory name')
DEST=QA/args.output_name;DEST.mkdir(exist_ok=True)
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
records=lambda p:[json.loads(s) for s in p.read_text(encoding='utf-8').splitlines()]
escape=lambda s:html.escape(str(s),quote=True)
visual_checks=read(ROOT/'benchmarks/full-comics/reviewed-segments.json')
word_reviews={p.stem:read(p) for p in (ROOT/'benchmarks/full-comics/visual-reviews').glob('*.json')}

def checked_cases(chapter):
    cases=[r for r in visual_checks if r['chapter']==chapter]
    if not cases:return ''
    entries=[]
    for row in cases:
        entries.append('<li><p>Inglés verificado: <strong>'+escape(row.get('english_visual_text',''))+
            '</strong>. Referencia verificada: <strong>'+escape(row.get('reference_text',''))+
            '</strong>.</p><p>Salida de Luma: '+escape(row.get('luma_translation',row.get('ocr_reader_output','Sin lectura fiable')))+
            '</p><p>'+escape(row.get('review_note_es',row['remaining_issue']))+'</p></li>')
    return '<section class="note"><h2>Casos comprobados en las imágenes</h2><p>Revisión puntual del asistente. Estos casos también incluyen palabras que el OCR de referencia omitió; no aprueban el capítulo completo.</p><ul>'+''.join(entries)+'</ul></section>'
STYLE='''body{font:16px system-ui;margin:0;background:#f2f5ef;color:#24372b}header,main{padding:20px;max-width:1380px;margin:auto}h1{font-size:25px}a{color:#285f47}button,select,input{font:inherit;padding:8px;border:1px solid #b4c3b2;border-radius:8px}button{cursor:pointer}table{border-collapse:collapse;width:100%;background:white}td,th{text-align:left;vertical-align:top;padding:10px;border-bottom:1px solid #d5dfd1}th{position:sticky;top:0;background:#e5eddd}.note{padding:14px;border-left:4px solid #8b6b33;background:#fff8e9}.panels{display:grid;grid-template-columns:1fr 1fr;gap:18px}.page{position:relative;background:white;margin-bottom:12px}.page img{display:block;width:100%;height:auto}.page .box{position:absolute;border:2px solid #9b5a25;box-sizing:border-box;pointer-events:none}details{margin:14px 0;padding:12px;background:white}summary{cursor:pointer}#selection{white-space:pre-wrap;background:white;padding:16px;line-height:1.55;min-height:90px}.tools{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0}.pending{color:#925522}.tag{display:inline-block;background:#e6eddf;padding:4px 8px;border-radius:8px}.word{cursor:pointer}tr.selected{background:#e6f4cf}.small{font-size:13px;color:#4f6555}@media(max-width:800px){.panels{grid-template-columns:1fr}td,th{padding:6px}}'''
images={}
for language in ['en','es']:
    grouped=collections.defaultdict(list)
    for row in read(QA/f'images-{language}.json'):
        if args.series=='all' or row['series']==args.series:grouped[row['chapter'].removesuffix('-'+language)].append(row)
    images[language]=grouped

def page_category(row):
    name=row['url'].rsplit('/',1)[-1].casefold()
    return 'promotional_candidate' if any(s in name for s in ['(0).','cambio-de-discord','mejoras','recluta','zzz-','disquis']) else 'chapter_page'

index=[]
for chapter in sorted(images['en']):
    en_done=QA/(args.english_reports or 'translated-en')/(chapter+'-en.done.json');es_done=QA/'ocr-es'/(chapter+'-es.done.json');comparison=QA/args.comparisons/(chapter+'.json')
    status='Comparación automática lista' if comparison.exists() else 'Alineación pendiente' if en_done.exists() and es_done.exists() else 'Recorrido en proceso'
    summary=read(comparison) if comparison.exists() else None
    index.append(f'<tr><td>{escape(chapter)}</td><td>{len(images["en"][chapter])}</td><td>{len(images["es"][chapter])}</td><td>{escape(status)}</td><td>{summary["reference_ocr_tokens"] if summary else "—"}</td><td>'+ (f'<a href="{escape(chapter)}.html">Abrir comparación</a>' if summary else 'Pendiente')+'</td></tr>')
    if not summary:continue
    words_=records(QA/args.comparisons/(chapter+'.words.jsonl'))
    en=records(QA/summary.get('english_report_directory','translated-en')/(chapter+'-en.jsonl'));es=records(QA/'ocr-es'/(chapter+'-es.jsonl'))
    em=read(QA/'artwork'/(chapter+'-en.json'));sm=read(QA/'artwork'/(chapter+'-es.json'));anchors=summary['anchors'];ys=[a['es'] for a in anchors]
    for row in es:
        location=sm[str(row['image'])];sy=location['offset']+(row['bounds'][1]+row['bounds'][3])*location['scale']/2;i=bisect.bisect_left(ys,sy)
        row['_context']=None
        if not 0<i<len(anchors):continue
        first,second=anchors[i-1],anchors[i];gap=second['es']-first['es'];slope=(second['en']-first['en'])/gap
        if gap>1000 or not .75<slope<1.33:continue
        ey=first['en']+(sy-first['es'])*slope
        candidates=[(int(k),v) for k,v in em.items() if v['offset']<=ey]
        if not candidates:continue
        image,position=max(candidates,key=lambda pair:pair[1]['offset']);source=next(r for r in images['en'][chapter] if r['image']==image)
        y=(ey-position['offset'])/position['scale'];row['_context']={'image':image,'bounds':[0,max(0,round(y-280)),source['width'],min(source['height'],round(y+280))]}
    payload={'chapter':chapter,'words':[{'w':r['reference_word'],'r':r['reference_region'],'i':r['word_index'],'l':r['luma_region'],'s':r['state']} for r in words_],
        'en':en,'es':es,'categories':{str(r['image']):page_category(r) for r in images['es'][chapter]}}
    reference_sha=hashlib.sha256((QA/'ocr-es'/(chapter+'-es.jsonl')).read_bytes()).hexdigest()
    english_sha=hashlib.sha256((QA/summary.get('english_report_directory','translated-en')/(chapter+'-en.jsonl')).read_bytes()).hexdigest()
    if summary.get('ledger_format')=='region-indices-v1':
        assert reference_sha==summary['reference_report_sha256'],'Reference region indices point to a changed report'
        assert english_sha==summary['english_report_sha256'],'Luma region indices point to a changed report'
    visual=word_reviews.get(chapter);checked_regions=set()
    if visual and visual['reference_report_sha256']==reference_sha:
        checked_regions={r for entry in visual['entries'] if entry['visual_word_reading_checked'] for r in entry['reference_regions']}
    payload['visually_checked_reference_words']=[i for i,w in enumerate(words_) if w['reference_region'] in checked_regions]
    payload['review_storage_key']='luma-word-review:'+chapter+':'+reference_sha+':'+english_sha
    data=json.dumps(payload,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    columns=[]
    for language in ['en','es']:
        pages=[]
        for row in images[language][chapter]:
            src=os.path.relpath(row['path'],DEST).replace('\\','/')
            pages.append(f'<details id="{language}-{row["image"]}"><summary>Página {row["image"]+1} · {row["width"]} × {row["height"]}</summary><div class="page" data-language="{language}" data-image="{row["image"]}" data-width="{row["width"]}" data-height="{row["height"]}"><img loading="lazy" src="{escape(src)}" alt="{language}, página {row["image"]+1}"><div class="box" hidden></div></div></details>')
        columns.append('<section><h2>'+('Inglés y salida de Luma' if language=='en' else 'Edición española de Olympus')+'</h2>'+''.join(pages)+'</section>')
    document='''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luma · __CHAPTER__</title><style>__STYLE__</style><header><a href="index.html">← Todos los capítulos</a><h1>__CHAPTER__</h1><p class="note">Se recorrieron todas las imágenes de esta pareja. La lectura de Olympus y las correspondencias de escenas son propuestas automáticas. Una palabra coincidente no garantiza una traducción correcta. La revisión visual de cada palabra sigue pendiente.</p></header><main><div class="tools"><select id="filter"><option value="no_luma_region_nearby">Posibles omisiones</option><option value="different_wording">Redacción diferente</option><option value="alignment_pending">Sin alineación segura</option><option value="literal_token_present">Coincidencia literal</option><option value="all">Todas las palabras extraídas</option></select><input id="search" placeholder="Buscar palabra o frase"><label><input id="hideMarks" type="checkbox" checked> Ocultar posibles marcas/promoción</label><button id="export">Exportar revisión manual</button></div><p id="counts" class="small"></p><div id="selection">Selecciona una palabra para ver el original, la salida de Luma y las páginas correspondientes.</div><div style="max-height:410px;overflow:auto;margin:16px 0"><table><thead><tr><th>Palabra de referencia</th><th>Página ES</th><th>Estado automático</th><th>Revisada visualmente</th></tr></thead><tbody id="ledger"></tbody></table></div><div class="panels">__COLUMNS__</div></main><script type="application/json" id="data">__DATA__</script><script>
const data=JSON.parse(document.getElementById('data').textContent),reviewed=new Set(),labels={no_luma_region_nearby:'Sin región cercana de Luma',different_wording:'Otra redacción; por revisar',alignment_pending:'Escena sin alinear',literal_token_present:'Coincidencia literal'};
const watermark=/ZONA.?L[YI]MP|OLYMPUS|LEE\\s*ANTES/i;
function marked(r){if(data.categories[String(r.image)]==='promotional_candidate'||watermark.test(r.source))return true;return /^(LEE|ANTES|ANT|EE|ES|AN)$/i.test(r.source.trim())&&data.es.some(o=>o.image===r.image&&watermark.test(o.source)&&Math.abs(o.bounds[1]-r.bounds[1])<140);}
function render(){const body=document.getElementById('ledger');body.textContent='';const filter=document.getElementById('filter').value,search=document.getElementById('search').value.toLocaleLowerCase(),hide=document.getElementById('hideMarks').checked;let shown=0;
data.words.forEach((w,index)=>{const r=data.es[w.r];if(filter!=='all'&&filter!==w.s||hide&&marked(r)||search&&!r.source.toLocaleLowerCase().includes(search))return;shown++;const tr=document.createElement('tr');tr.className='word';for(const text of [w.w,String(r.image+1),labels[w.s]]){const td=document.createElement('td');td.textContent=text;tr.appendChild(td);}const td=document.createElement('td'),checkbox=document.createElement('input');checkbox.type='checkbox';checkbox.checked=reviewed.has(index);checkbox.onchange=()=>checkbox.checked?reviewed.add(index):reviewed.delete(index);td.appendChild(checkbox);tr.appendChild(td);tr.onclick=e=>{if(e.target!==checkbox)selectWord(index,tr);};body.appendChild(tr);});document.getElementById('counts').textContent=shown+' palabras visibles de '+data.words.length+' tokens extraídos. Las marcas ocultas siguen en el registro completo. Ningún token se marca como revisado automáticamente.';}
function showBox(language,image,bounds){const details=document.getElementById(language+'-'+image);if(!details)return;details.open=true;const page=details.querySelector('.page'),box=page.querySelector('.box');box.hidden=false;box.style.left=bounds[0]*100/Number(page.dataset.width)+'%';box.style.top=bounds[1]*100/Number(page.dataset.height)+'%';box.style.width=(bounds[2]-bounds[0])*100/Number(page.dataset.width)+'%';box.style.height=(bounds[3]-bounds[1])*100/Number(page.dataset.height)+'%';details.scrollIntoView({block:'nearest'});}
function selectWord(index,tr){document.querySelectorAll('tr.selected').forEach(r=>r.classList.remove('selected'));tr.classList.add('selected');const w=data.words[index],r=data.es[w.r],e=w.l===null?null:data.en[w.l];document.getElementById('selection').textContent='Olympus (lectura automática): '+r.source+'\\n\\nInglés detectado: '+(e?e.source:'Sin correspondencia propuesta')+'\\n\\nLuma: '+(e?e.translation:'Pendiente')+'\\n\\nEstado: '+labels[w.s];showBox('es',r.image,r.bounds);if(e)showBox('en',e.image,e.bounds);}
document.getElementById('filter').onchange=render;document.getElementById('search').oninput=render;document.getElementById('hideMarks').onchange=render;
document.getElementById('export').onclick=()=>{const result={chapter:data.chapter,automatic_approval:false,words:data.words.map((w,i)=>({...w,visually_reviewed:reviewed.has(i),meaning_approved:false}))};const url=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=data.chapter+'-review.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};render();
</script></html>'''
    document=document.replace('__CHAPTER__',escape(chapter)).replace('__STYLE__',STYLE).replace('__COLUMNS__',''.join(columns)).replace('__DATA__',data)
    document=document.replace('<main>','<main>'+checked_cases(chapter),1)
    if visual:
        document=document.replace('<main>',f'<main><p class="note"><a href="../word-review/{chapter}.html">{len(visual["entries"])} parejas de diálogo cotejadas visualmente, con las palabras corregidas del OCR y las observaciones de significado.</a> Evaluación de la pasada {escape(visual["evaluated_english_report_directory"])}; no aprueba automáticamente la salida de otra pasada.</p>',1)
    document=document.replace('reviewed=new Set(),labels=',"reviewed=new Set(data.visually_checked_reference_words||[]),labels=")
    document=document.replace('const watermark=',"try{const stored=JSON.parse(localStorage.getItem(data.review_storage_key)||'null');if(Array.isArray(stored)){reviewed.clear();for(const i of stored)if(Number.isInteger(i)&&i>=0&&i<data.words.length)reviewed.add(i);}}catch{}\nfunction saveReview(){try{localStorage.setItem(data.review_storage_key,JSON.stringify([...reviewed]));}catch{}}\nconst watermark=")
    document=document.replace('checkbox.onchange=()=>checkbox.checked?reviewed.add(index):reviewed.delete(index);', 'checkbox.onchange=()=>{checkbox.checked?reviewed.add(index):reviewed.delete(index);saveReview();};')
    document=document.replace("Ningún token se marca como revisado automáticamente.","Las casillas documentan la inspección visual y no aprueban el significado. Se conservan las revisiones de esta versión en el navegador.")
    document=document.replace('<div style="max-height:410px;', '<div class="panels"><section><p>Inglés: zona propuesta por el dibujo</p><canvas id="en-preview"></canvas></section><section><p>Olympus: zona de la palabra</p><canvas id="es-preview"></canvas></section></div><div style="max-height:410px;')
    document=document.replace("showBox('es',r.image,r.bounds);if(e)showBox('en',e.image,e.bounds);", "showCrop('es',r.image,r.bounds);if(e)showCrop('en',e.image,e.bounds);else if(r._context)showCrop('en',r._context.image,r._context.bounds);else{const c=document.getElementById('en-preview');c.width=1;c.height=1;}")
    crop_script="""function showCrop(language,image,bounds){const page=document.querySelector('.page[data-language="'+language+'"][data-image="'+image+'"]');if(!page)return;const source=page.querySelector('img'),canvas=document.getElementById(language+'-preview'),bitmap=new Image();bitmap.onload=()=>{const pad=22,x=Math.max(0,bounds[0]-pad),y=Math.max(0,bounds[1]-pad),w=Math.min(bitmap.naturalWidth-x,bounds[2]-bounds[0]+pad*2),h=Math.min(bitmap.naturalHeight-y,bounds[3]-bounds[1]+pad*2),scale=Math.min(540/w,420/h,2);canvas.width=Math.max(1,Math.round(w*scale));canvas.height=Math.max(1,Math.round(h*scale));canvas.getContext('2d').drawImage(bitmap,x,y,w,h,0,0,canvas.width,canvas.height);};bitmap.src=source.src;}"""
    document=document.replace('function showBox(',crop_script+'\nfunction showBox(')
    (DEST/(chapter+'.html')).write_text(document,encoding='utf-8')

paired=sum((QA/args.comparisons/(chapter+'.json')).exists() for chapter in images['en'])
expected=len(images['en'])
scope=f'{expected} parejas de Regresión Absoluta.' if args.series=='absolute-regression' else f'{expected} parejas: 124 de Regresión Absoluta y 30 de The Greatest Estate Developer.'
cover={language:sum((QA/((args.english_reports or 'translated-en') if language=='en' else 'ocr-es')/(chapter+'-'+language+'.done.json')).exists() for chapter in images[language]) for language in ['en','es']}
document=f'<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Evaluación de capítulos · Luma</title><style>{STYLE}</style><header><h1>Evaluación de capítulos · Luma</h1><p>{scope}</p><p class="note">Recorrido completo terminado: inglés {cover["en"]}/{expected}; español {cover["es"]}/{expected}. Comparación automática disponible: {paired}/{expected}. La revisión visual de todas las palabras y la precisión semántica no están establecidas.</p><p>Datos locales. Las imágenes del cómic no se incluyen en la aplicación.</p></header><main><table><thead><tr><th>Capítulo</th><th>Imágenes EN</th><th>Imágenes ES</th><th>Estado</th><th>Tokens ES extraídos</th><th>Visor</th></tr></thead><tbody>'+''.join(index)+'</tbody></table></main></html>'
(DEST/'index.html').write_text(document,encoding='utf-8');print('Review generated',cover,'paired',paired)
