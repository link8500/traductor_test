"""Scan all recorded chapters for review candidates, never approve meaning."""
import collections,hashlib,html,json,pathlib,re

ROOT=pathlib.Path(__file__).resolve().parents[1];QA=ROOT/'build/full-comics';DEST=QA/'chapter-audit';DEST.mkdir(exist_ok=True)
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
escape=lambda s:html.escape(str(s),quote=True)
words=lambda s:re.findall(r"[A-Za-zÀ-ÿ]+(?:['’][A-Za-zÀ-ÿ]+)?",s.lower())
common=set('porque aunque cuando donde mientras entonces incluso siempre puedes podría puede quiero tienen tiene esta estas estos antes después contra sobre nuestra nuestros nuestro ustedes usted'.split())
credit=re.compile(r'asura|olympus|discord|patreon|https?[:/]|scanlation|translator|typesetter|proofreader|redraw|cleaner',re.I)
STYLE='body{font:16px system-ui;background:#f3f5ef;color:#273c2c;margin:0}main{max-width:1400px;padding:22px;margin:auto}p{line-height:1.6;max-width:1000px}table{border-collapse:collapse;width:100%;background:white}td,th{padding:10px;text-align:left;vertical-align:top;border-bottom:1px solid #d5dfce}a{color:#216044}.note{background:#fff3d7;padding:14px}.small{font-size:13px}'
reviewed=read(ROOT/'benchmarks/full-comics/reviewed-segments.json')

def visual_cases(chapter):
    cases=[case for case in reviewed if case['chapter']==chapter]
    if not cases:return '',cases
    entries=[]
    for case in cases:
        image=case.get('english_image')
        anchor=f'#image-{image}' if image is not None else ''
        link=f'../chapter-photos/{chapter}.html{anchor}'
        observed=case.get('luma_translation',case.get('ocr_reader_output',''))
        note=case.get('review_note_es',case['remaining_issue'])
        build=f'Compilación {case["tested_build"]}' if case.get('tested_build') else 'Pasada anterior registrada'
        entries.append(f'<tr><td><a href="{link}">{escape(case["english_visual_text"])}</a><p class="small">{build}</p></td><td>{escape(observed)}</td><td>{escape(case["reference_text"])}</td><td>{escape(note)}</td></tr>')
    section='<section id="visually-reviewed"><h2>Casos comprobados visualmente</h2><p>Observaciones de las pasadas indicadas, conservadas para verificar las correcciones. La referencia humana puede adaptar el diálogo; estos casos no aprueban el resto del capítulo ni se convierten en respuestas de la aplicación.</p><table><thead><tr><th>Original inglés</th><th>Salida observada de Luma</th><th>Referencia de Olympus</th><th>Resultado y problema pendiente</th></tr></thead><tbody>'+''.join(entries)+'</tbody></table></section>'
    return section,cases

summaries=[]
for number in range(1,125):
    chapter=f'absolute-regression-{number:02d}'
    folder=next((name for name in ['translated-en8011-context','translated-en8011','translated-en8010','translated-en8009','translated-en8007','translated-en-final'] if (QA/name/(chapter+'-en.done.json')).exists()),None)
    assert folder,chapter
    path=QA/folder/(chapter+'-en.jsonl');rows=[json.loads(s) for s in path.read_text(encoding='utf-8').splitlines() if s.strip()]
    findings=[]
    for index,row in enumerate(rows):
        source=row['source'];target=row.get('translation','');reasons=[]
        promotional=bool(credit.search(source))
        if 'error' in row or not target:reasons.append('No produjo traducción')
        if not promotional:
            if re.search(r'[A-Za-z][&$|{}][A-Za-z]|[&$|{}][A-Za-z]{3}',source):reasons.append('Símbolo dentro de una palabra reconocida')
            if re.search(r'[A-Za-z][&$|{}][A-Za-z]|[&$|{}][A-Za-z]{3}',target):reasons.append('Símbolo dentro de una palabra de salida')
            if row.get('retained_original'):reasons.append('Región conservada por el motor')
            shared=sorted({s for s in words(source) if len(s)>=6}-common & set(words(target)))
            if shared:reasons.append('Palabras conservadas: '+', '.join(shared))
        if reasons:findings.append(dict(region=index,image=row['image'],bounds=row['bounds'],source=source,translation=target,reasons=reasons,
            semantic_error_confirmed=False,visually_reviewed=False))
    manual_html,manual_cases=visual_cases(chapter)
    report=dict(chapter=chapter,report_directory=folder,report_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        regions_checked=len(rows),review_candidates=len(findings),findings=findings,all_words_visually_reviewed=False,semantic_accuracy=None,
        visually_checked_cases=manual_cases,
        scope='Mechanical risk scan over saved outputs, including retained source tokens and malformed symbols. Proper names and Spanish cognates can be flagged. Unflagged regions are not approved.')
    (DEST/(chapter+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    entries=[]
    for finding in findings:
        image=finding['image'];link=f'../chapter-photos/{chapter}.html#image-{image}'
        entries.append(f'<tr><td><a href="{link}">Imagen {image+1}, región {finding["region"]+1}</a><p class="small">{escape(finding["bounds"])}</p></td><td>{escape(finding["source"])}</td><td>{escape(finding["translation"])}</td><td>{escape(" · ".join(finding["reasons"]))}</td></tr>')
    doc=f'<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{chapter} · Revisión</title><style>{STYLE}</style><main><a href="index.html">← 124 capítulos</a><h1>{chapter}</h1><p class="note">{len(rows)} regiones examinadas automáticamente; {len(findings)} candidatos para revisión. Versión del informe: {folder}. Los nombres propios y palabras parecidas en ambos idiomas pueden estar marcados. Ninguna ausencia de alertas certifica el significado. Las imágenes pueden corresponder a otra pasada; su versión figura en el visor.</p><p><a href="../chapter-photos/{chapter}.html">Todas las imágenes del capítulo</a> · <a href="../review/{chapter}.html">Comparar con Olympus</a> · <a href="{chapter}.json">Datos completos</a></p><table><thead><tr><th>Zona</th><th>Inglés reconocido</th><th>Salida de Luma</th><th>Motivo para revisar</th></tr></thead><tbody>'+''.join(entries)+'</tbody></table></main></html>'
    doc=doc.replace('<table><thead><tr><th>Zona</th>',manual_html+'<h2>Candidatos automáticos</h2><table><thead><tr><th>Zona</th>',1)
    (DEST/(chapter+'.html')).write_text(doc,encoding='utf-8');summaries.append(dict(chapter=chapter,number=number,report_directory=folder,regions=len(rows),candidates=len(findings),visually_checked_cases=len(manual_cases)))
summary=dict(chapter_count=len(summaries),regions_checked=sum(r['regions'] for r in summaries),review_candidates=sum(r['candidates'] for r in summaries),
    all_words_visually_reviewed=False,semantic_accuracy=None,visually_checked_case_count=len(reviewed),cohorts=dict(collections.Counter(r['report_directory'] for r in summaries)),chapters=summaries)
(DEST/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
entries=''.join(f'<tr><td><a href="{r["chapter"]}.html">{r["number"]}</a></td><td>{r["regions"]}</td><td>{r["candidates"]}</td><td>{r["report_directory"]}</td><td>Pendiente</td></tr>' for r in summaries)
doc=f'<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luma · Revisión de errores</title><style>{STYLE}</style><main><h1>Regresión Absoluta · revisión de las salidas de los 124 capítulos</h1><p>{summary["regions_checked"]} regiones examinadas automáticamente · {summary["review_candidates"]} candidatos para revisión.</p><p class="note">Esta comprobación busca símbolos extraños y palabras del inglés conservadas en la salida. No mide toda la calidad del OCR ni decide si el significado está bien traducido. Una misma palabra puede ser correcta en ambos idiomas. La revisión visual completa sigue pendiente.</p><p><a href="../chapter-photos/index.html">Imágenes originales y salidas por capítulo</a> · <a href="summary.json">Datos de la comprobación</a></p><table><thead><tr><th>Capítulo</th><th>Regiones examinadas</th><th>Candidatos</th><th>Pasada examinada</th><th>Revisión visual completa</th></tr></thead><tbody>{entries}</tbody></table></main></html>'
(DEST/'index.html').write_text(doc,encoding='utf-8');print(json.dumps({k:v for k,v in summary.items() if k!='chapters'}))
