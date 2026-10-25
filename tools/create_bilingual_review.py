"""Create a local visual review with explicit coverage and editable references."""
import collections,hashlib,html,json,pathlib,textwrap
from PIL import Image,ImageDraw,ImageFont

ROOT=pathlib.Path(__file__).resolve().parents[1]
QA=ROOT/'build/bilingual-quality'


def read(name):return json.loads((QA/name).read_text(encoding='utf-8'))
def lines(name):return [json.loads(line) for line in (QA/name).read_text(encoding='utf-8').splitlines()]
def escape(text):return html.escape(str(text),quote=True)


def main():
    samples={row['id']:row for row in read('samples.json')['records'] if row['language']=='en'}
    alignments={row['id']:row for row in read('alignments.json')}
    reviewed=read('reviewed-segments.json')
    baseline=lines('mobile-translations.jsonl');final=lines('final-mobile-translated-regions.jsonl')
    before={(row['chapter'],row['source'],tuple(row['bounds'])):row for row in baseline}
    grouped=collections.defaultdict(list)
    for row in final:grouped[row['chapter']].append(row)
    mobile=read('mobile-summary.json');desktop=read('desktop-summary.json');audit=read('repair-audit.json')
    reference_images=sum(len(row['images']) for row in read('references.json'))
    summary={'chapter_pairs':60,'source_links':120,'spanish_reference_images_downloaded':reference_images,
        'matched_scenes':sum(row['state']=='artwork_matched' for row in alignments.values()),
        'automatic_artwork_matches':sum(row['state']=='artwork_matched' and row.get('method')!='full_page_color_correlation_and_visual_confirmation' for row in alignments.values()),
        'visually_confirmed_alignment_overrides':sum(row.get('method')=='full_page_color_correlation_and_visual_confirmation' for row in alignments.values()),
        'alignment_pending':[row['id'] for row in alignments.values() if row['state']!='artwork_matched'],
        'assistant_reviewed_segments':len(reviewed),'user_verified_segments':0,'semantic_accuracy':None,
        'coverage':'One middle image per chapter, plus its middle 390x844 pixel viewport. Not full chapters.',
        'desktop':desktop,'narrow_windows_view':mobile,
        'training_performed':False,'weights_changed':False,
        'limitations':['Most regions have not been reviewed for meaning.','Automatic artwork matching is not an approved translation label.',
            'The Spanish edition can paraphrase or omit details; compare against the visible English as well.',
            'A narrow Windows image is not a full Android capture/OCR test.','Current chapters are development material; no independent semantic test score is claimed.']}
    (QA/'review-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    sections=[];export_rows=[]
    for id_,sample in sorted(samples.items()):
        alignment=alignments[id_];scene_reviewed=any(row['chapter']==id_ for row in reviewed) or alignment.get('alignment_reviewed',False)
        cells=[]
        for row in grouped[id_]:
            old=before[(id_,row['source'],tuple(row['bounds']))]
            annotation=next((item for item in reviewed if item['chapter']==id_ and item['source_contains'] in row['source']),{})
            key=hashlib.sha256((id_+row['source']+str(row['bounds'])).encode()).hexdigest()[:16]
            export_rows.append({'id':key,'chapter':id_,'bounds':row['bounds'],'ocr':row['source'],'translation':row['translation'],'assistant_review':annotation,'scene_reviewed_by_assistant':scene_reviewed})
            category=annotation.get('category','unreviewed')
            options={'unreviewed':'Sin revisar','correct':'Conserva el sentido','improved_ocr':'OCR mejorado; revisar redacción',
                'improved_measurement':'Medida corregida','remaining_ocr_error':'Error de lectura pendiente','remaining_meaning_error':'Error de sentido pendiente','reference_error':'Referencia española necesita revisión'}
            selector=''.join(f'<option value="{value}" {"selected" if category==value else ""}>{label}</option>' for value,label in options.items())
            cells.append(f'''<div class="region" data-id="{key}"><div><h4>Texto que leyó Luma</h4><p>{escape(row['source'])}</p><h4>Antes</h4><p>{escape(old.get('translation',''))}</p><h4>Ahora</h4><p>{escape(row['translation'])}</p></div>
<div><label>Inglés correcto<textarea class="source">{escape(annotation.get('source_correct',''))}</textarea></label><label>Español revisado<textarea class="target">{escape(annotation.get('target_reviewed',''))}</textarea></label>
<label>Resultado<select class="category">{selector}</select></label><p class="note">{escape(annotation.get('note','Pendiente de revisar contra las dos imágenes.'))}</p><label><input class="confirmed" type="checkbox"> Revisado por mí</label></div></div>''')
        es_id=id_.removesuffix('-en')+'-es'
        reference=f'<img src="{escape(alignment["reference_image"].replace(chr(92),"/"))}" alt="Referencia española">' if alignment.get('reference_image') else '<div class="missing">Emparejamiento pendiente. Revisa el capítulo original.</div>'
        state='Escena confirmada visualmente' if alignment.get('alignment_reviewed') else 'Escena emparejada automáticamente' if alignment['state']=='artwork_matched' else 'Emparejamiento pendiente'
        sections.append(f'''<article data-chapter="{id_}" data-reviewed="{str(scene_reviewed).lower()}"><h2>{escape(id_)}</h2><p>{state} · <a href="{escape(sample['url'])}" target="_blank" rel="noreferrer">Inglés</a> · <a href="{escape(alignment['reference_url'])}" target="_blank" rel="noreferrer">Español</a></p>
<label><input class="scene" type="checkbox"> Confirmo que las imágenes corresponden a la misma escena</label>
<div class="images"><figure><figcaption>Inglés · 390 × 844 píxeles</figcaption><img src="samples/{id_}/mobile.png" alt="Original inglés"></figure><figure><figcaption>Edición española de referencia</figcaption>{reference}</figure></div>
{''.join(cells) if cells else '<p>No se detectó texto en este recorte. Puede ser solo dibujo; requiere revisión visual antes de contar una omisión.</p>'}</article>''')
    data=json.dumps(export_rows,ensure_ascii=False).replace('<','\\u003c')
    template='''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luma · Revisión bilingüe</title>
<style>body{margin:0;background:#f2f4ef;color:#20332b;font:16px system-ui,sans-serif}header{padding:30px;max-width:1100px;margin:auto}h1{font-size:32px;margin:0 0 14px}.notice{background:#fff0cc;border-left:5px solid #bb7b17;padding:18px;line-height:1.6}.metrics{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0}.metrics span{background:white;padding:16px;border-radius:12px}button,select{padding:10px;font:inherit}button{border:0;border-radius:9px;background:#264e3c;color:white;cursor:pointer}main{max-width:1100px;margin:auto}article{background:white;padding:24px;margin:24px 10px;border:1px solid #d5ded3;border-radius:16px}.images{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:20px 0}figure{margin:0;text-align:center;background:#e9ece5;padding:10px}figcaption{margin:4px 0 12px}img{max-width:100%;max-height:844px;object-fit:contain}.region{display:grid;grid-template-columns:1fr 1fr;gap:24px;border-top:1px solid #d9e2d6;padding:20px 0}h4{margin:12px 0 6px}p{line-height:1.5}textarea{display:block;box-sizing:border-box;width:100%;min-height:70px;margin:8px 0 16px;padding:10px;font:inherit;border:1px solid #b7c9b8;border-radius:8px}label{display:block;margin:8px 0}.note{font-size:14px;color:#526653}.missing{padding:50px 10px;color:#8a4d16}a{color:#255744}footer{max-width:1060px;padding:30px;margin:auto}@media(max-width:650px){.images,.region{grid-template-columns:1fr}header{padding:20px}}</style>
<header><h1>Luma · Revisión inglés / español</h1><div class="notice"><b>Es una muestra de cada capítulo.</b> Se probaron 60 páginas centrales y sus recortes estrechos. Todavía hay errores de OCR y de sentido. Las coincidencias del dibujo y la ausencia de cierres no equivalen a traducciones correctas.</div>
<div class="metrics"><span><b>60</b> parejas de capítulos</span><span><b>__REFS__</b> imágenes españolas</span><span><b>__MATCHES__/60</b> escenas emparejadas</span><span><b>__REGIONS__</b> registros de regiones; pueden solaparse</span><span><b>__REVIEWED__</b> segmentos revisados visualmente</span></div>
<p>Las versiones españolas pueden adaptar el diálogo. Para aprobar una traducción, revisa también el inglés. Los textos escritos en los campos son propuestas de revisión del asistente hasta que los confirmes.</p><p><select id="filter"><option value="all">Todos los capítulos</option><option value="reviewed">Con revisión visual del asistente</option><option value="pending">Pendientes de revisión</option></select> <button id="export">Descargar mi revisión</button></p></header><main>__SECTIONS__</main>
<footer>OCR y traducción ejecutados localmente. No se entrenaron pesos nuevos con estos capítulos. Los informes técnicos están junto a este archivo.</footer>
<script id="records" type="application/json">__DATA__</script><script>
const records=JSON.parse(document.getElementById('records').textContent);document.getElementById('filter').onchange=e=>document.querySelectorAll('article').forEach(a=>a.hidden=e.target.value!=='all'&&(e.target.value==='reviewed')!==(a.dataset.reviewed==='true'));
document.getElementById('export').onclick=()=>{const result=records.map(r=>{const row=document.querySelector('[data-id="'+r.id+'"]');return {...r,source_correct:row.querySelector('.source').value,target_reviewed:row.querySelector('.target').value,category:row.querySelector('.category').value,user_confirmed:row.querySelector('.confirmed').checked,user_scene_confirmed:row.closest('article').querySelector('.scene').checked}});const blob=new Blob([JSON.stringify({created_at:new Date().toISOString(),records:result},null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='luma-bilingual-review.json';a.click();URL.revokeObjectURL(a.href)};
</script></html>'''
    template=template.replace('__REGIONS__',f"{desktop['regions']} + {mobile['regions']}").replace('__REVIEWED__',str(len(reviewed)))
    (QA/'review.html').write_text(template.replace('__REFS__',str(reference_images)).replace('__MATCHES__',str(summary['matched_scenes'])).replace('__SECTIONS__',''.join(sections)).replace('__DATA__',data),encoding='utf-8')
    comparison(final,baseline)
    print('Created review.html, review-summary.json and reviewed-comparison.png')


def comparison(final,baseline):
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',19)
    bold=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf',23)
    sheet=Image.new('RGB',(1120,860),'#f2f4ef');draw=ImageDraw.Draw(sheet)
    draw.text((24,18),'Luma · Dos errores comprobados con las viñetas',font=bold,fill='#20332b')
    for x,label in [(24,'Original inglés'),(389,'Referencia española'),(760,'Traducción de Luma')]:draw.text((x,55),label,font=font,fill='#526653')
    for index,(chapter,fragment) in enumerate([('absolute-regression-08-en','ANCE5TOR5'),('greatest-estate-developer-27-en','5OCM')]):
        row=next(r for r in final if r['chapter']==chapter and fragment in r['source'])
        old=next(r for r in baseline if r['chapter']==chapter and fragment in r['source'])
        top=max(0,row['bounds'][1]-55);bottom=min(844,row['bounds'][3]+55)
        y=98+index*350
        for col,path in enumerate([QA/'samples'/chapter/'mobile.png',QA/'aligned'/(chapter.removesuffix('-en')+'-es')/'reference-mobile.png']):
            with Image.open(path) as image:
                crop=image.crop((0,top,390,bottom));crop.thumbnail((350,290),Image.Resampling.LANCZOS)
                sheet.paste(crop,(24+col*365,y))
        draw.text((760,y),'Antes',font=bold,fill='#8a4d16')
        draw.multiline_text((760,y+36),textwrap.fill(old['translation'],30),font=font,fill='#20332b',spacing=5)
        draw.text((760,y+155),'Ahora',font=bold,fill='#315a38')
        draw.multiline_text((760,y+190),textwrap.fill(row['translation'],30),font=font,fill='#20332b',spacing=5)
    draw.text((24,815),'Ejemplos revisados de desarrollo. Quedan errores de lectura, contexto y redacción.',font=font,fill='#526653')
    sheet.save(QA/'reviewed-comparison.png')


if __name__=='__main__':main()
