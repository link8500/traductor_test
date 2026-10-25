"""Publish per-chapter evidence for the 124 Absolute Regression chapters."""
import argparse,collections,datetime,hashlib,html,json,pathlib,re,time

ROOT=pathlib.Path(__file__).resolve().parents[1];QA=ROOT/'build/full-comics'
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def escape(value):return html.escape(str(value),quote=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ocr-reports',default='ocr-en8010');parser.add_argument('--english-reports',default='translated-en8010')
    parser.add_argument('--comparisons',default='comparison8010');parser.add_argument('--review',default='review8010')
    parser.add_argument('--output-name',default='coverage8008');parser.add_argument('--watch',action='store_true')
    args=parser.parse_args()
    for value in [args.ocr_reports,args.english_reports,args.comparisons,args.review,args.output_name]:
        if not re.fullmatch(r'[a-z][a-z0-9-]+',value):parser.error('Invalid QA directory name')
    destination=QA/args.output_name;destination.mkdir(exist_ok=True)
    images=collections.Counter()
    for language in ['en','es']:
        images.update(r['chapter'] for r in read(QA/f'images-{language}.json'))
    sources={r['id']:r['url'] for r in read(ROOT/'benchmarks/full-comics/sources.json')['records']}
    build=re.search(r'^version:.*\+(\d+)',(ROOT/'pubspec.yaml').read_text(encoding='utf-8'),re.M)[1]
    control=args.english_reports.removeprefix('translated-en')
    def completed(folder,chapter,language):
        name=chapter+'-'+language;status=QA/folder/(name+'.done.json')
        if not status.exists() or not (status.with_name(name+'.jsonl')).exists():return None
        record=read(status)
        if record.get('images')!=images[name] or not record.get('all_files_traversed'):return None
        return record
    previous=None
    while True:
        rows=[]
        for number in range(1,125):
            chapter=f'absolute-regression-{number:02d}'
            baseline=completed('translated-en-final',chapter,'en');reference=completed('ocr-es',chapter,'es')
            ocr=completed(args.ocr_reports,chapter,'en');translated=completed(args.english_reports,chapter,'en')
            latest=completed('translated-en'+build+'-context',chapter,'en') or completed('translated-en'+build,chapter,'en')
            comparison=QA/args.comparisons/(chapter+'.json')
            rows.append(dict(chapter=number,id=chapter,english_images=images[chapter+'-en'],spanish_images=images[chapter+'-es'],
                baseline_traversed=baseline is not None,reference_ocr_traversed=reference is not None,
                current_ocr_traversed=ocr is not None,current_translation_traversed=translated is not None,
                current_comparison_available=comparison.exists(),current_regions=translated.get('regions') if translated else None,
                latest_build=build,latest_build_traversed=latest is not None,
                review_images_available=(QA/'chapter-photos'/chapter/'provenance.json').exists(),
                runtime_errors=sum((r or {}).get('runtime_errors',0) for r in [ocr,translated]),
                all_words_visually_reviewed=False,semantic_accuracy=None,
                english_url=sources[chapter+'-en'],spanish_url=sources[chapter+'-es']))
        summary={'series':'absolute-regression','chapters_requested':124,
            'baseline_chapters':sum(r['baseline_traversed'] for r in rows),
            'reference_ocr_chapters':sum(r['reference_ocr_traversed'] for r in rows),
            'current_ocr_chapters':sum(r['current_ocr_traversed'] for r in rows),
            'current_translation_chapters':sum(r['current_translation_traversed'] for r in rows),
            'current_compared_chapters':sum(r['current_comparison_available'] for r in rows),
            'latest_build':build,'latest_build_chapters':sum(r['latest_build_traversed'] for r in rows),
            'all_words_visually_reviewed':False,'semantic_accuracy':None,
            'ocr_directory':args.ocr_reports,'translation_directory':args.english_reports,'comparison_directory':args.comparisons,'chapters':rows}
        signature=hashlib.sha256(json.dumps(summary,sort_keys=True).encode()).hexdigest()
        if signature!=previous:
            summary['generated_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
            body=[]
            for row in rows:
                chapter=row['id'];view=('../'+args.review+'/'+chapter+'.html') if row['current_comparison_available'] else ('../review/'+chapter+'.html')
                links=f'<a href="{escape(row["english_url"])}">Inglés</a> · <a href="{escape(row["spanish_url"])}">Olympus</a>'
                links+=f'<br><a href="{view}">'+('Comparación actual' if row['current_comparison_available'] else 'Comparación anterior')+'</a>'
                if row['current_translation_traversed']:links+=f'<br><a href="../{args.english_reports}/{chapter}-en.jsonl">Salida actual de Luma</a>'
                if row['latest_build_traversed']:links+=f'<br><a href="../review{build}/{chapter}.html">Prueba de compilación {build}</a>'
                if row['review_images_available']:links+=f'<br><a href="../chapter-photos/{chapter}.html">Todas las imágenes de revisión</a>'
                status='Traducido' if row['current_translation_traversed'] else 'Reconocido; traducción pendiente' if row['current_ocr_traversed'] else 'Pendiente'
                yes=lambda value:'Completo' if value else 'Pendiente'
                body.append(f'<tr><td>{row["chapter"]}</td><td>{row["english_images"]} / {row["spanish_images"]}</td><td>{yes(row["baseline_traversed"])}</td><td>{yes(row["reference_ocr_traversed"])}</td><td>{status}</td><td>{row["current_regions"] if row["current_regions"] is not None else "—"}</td><td>Pendiente</td><td>{links}</td></tr>')
            cards=''.join(f'<div><strong>{summary[key]}/124</strong><span>{label}</span></div>' for key,label in [
                ('baseline_chapters','Recorrido anterior'),('reference_ocr_chapters','Referencia ES leída por OCR'),('current_ocr_chapters','OCR · pasada 8007'),('current_translation_chapters','Traducción · pasada 8007'),('current_compared_chapters','Comparación · pasada 8007'),('latest_build_chapters','Prueba completa · compilación '+build)])
            cards=cards.replace('8007',control)
            document=f'''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="30"><title>Luma · Cobertura de 124 capítulos</title><style>
body{{margin:0;background:#f4f6f0;color:#23342b;font:16px system-ui}}main{{max-width:1420px;margin:auto;padding:26px}}h1{{font-size:28px}}.cards{{display:flex;gap:12px;flex-wrap:wrap;margin:24px 0}}.cards div{{background:white;border:1px solid #d5ddce;border-radius:14px;padding:16px;min-width:160px}}strong{{display:block;font-size:24px}}span{{font-size:14px}}p{{max-width:1050px;line-height:1.6}}table{{border-collapse:collapse;width:100%;background:white}}td,th{{padding:12px;text-align:left;border-bottom:1px solid #d9e0d4;vertical-align:top}}th{{background:#e6eddf;position:sticky;top:0}}a{{color:#255d41}}input{{font:inherit;padding:10px;margin-bottom:18px;width:250px}}.small{{font-size:13px;color:#546452}}
</style><main><h1>Regresión Absoluta: pruebas de los 124 capítulos</h1><p>Esta tabla corresponde a las imágenes reales de cada capítulo. Las pruebas de la barra y los gestos se comprueban por separado. El recorrido automático anterior y la nueva pasada aparecen en columnas distintas. La revisión visual de cada palabra y la precisión semántica siguen pendientes.</p><div class="cards">{cards}</div><p>«Completo» significa que se recorrieron todos los archivos previstos de ese capítulo. La referencia de Olympus se leyó automáticamente y también puede omitir palabras. «Traducido» indica que Luma produjo sus salidas; el significado todavía requiere revisión.</p><p class="small">Actualización UTC: {summary['generated_at_utc']} · La página se recarga cada 30 segundos. <a href="summary.json">Datos de cobertura</a></p><input id="search" aria-label="Filtrar capítulos" placeholder="Buscar capítulo o estado"><div style="overflow:auto"><table><thead><tr><th>Capítulo</th><th>Imágenes EN / ES</th><th>Recorrido anterior</th><th>Referencia ES OCR</th><th>Versión actual</th><th>Regiones actuales</th><th>Revisión palabra por palabra</th><th>Evidencias</th></tr></thead><tbody>{''.join(body)}</tbody></table></div></main><script>document.getElementById('search').oninput=e=>{{const q=e.target.value.toLowerCase();document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q));}};</script></html>'''
            for name,value in [('summary.json',json.dumps(summary,ensure_ascii=False,indent=2)),('index.html',document)]:
                if name=='index.html':
                    value=value.replace('<th>Versión actual</th><th>Regiones actuales</th>','<th>Pasada ampliada 8007</th><th>Regiones de esa pasada</th>')
                    value=value.replace('Salida actual de Luma','Salida de la pasada 8007').replace('Comparación actual','Comparación de la pasada 8007')
                    value=value.replace('<div class="cards">',f'<p>La compilación instalada es {build}. Su cobertura de capítulo completo se indica por separado; la pasada de control {control} continúa con su motor fijado.</p><div class="cards">')
                    value=value.replace('8007',control)
                pending=destination/(name+'.pending');pending.write_text(value,encoding='utf-8');pending.replace(destination/name)
            print('Coverage',summary['current_ocr_chapters'],'recognized,',summary['current_translation_chapters'],'translated,',summary['current_compared_chapters'],'compared of 124',flush=True)
            previous=signature
        if not args.watch or summary['current_compared_chapters']==124 and summary['latest_build_chapters']==124:break
        time.sleep(20)

if __name__=='__main__':main()
