"""Publish explicit visual word reviews; processing never implies approval."""
import collections,hashlib,html,json,pathlib,re

ROOT=pathlib.Path(__file__).resolve().parents[1];QA=ROOT/'build/full-comics';DEST=QA/'word-review'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
escape=lambda s:html.escape(str(s),quote=True)
tokens=lambda s:re.findall(r"[^\W_]+(?:['’\-][^\W_]+)*",s,re.UNICODE)
STYLE='body{font:16px system-ui;background:#f2f5ef;color:#253b2c;margin:0}main{padding:22px;max-width:1500px;margin:auto}p{line-height:1.6;max-width:1100px}table{width:100%;border-collapse:collapse;background:white}td,th{text-align:left;padding:12px;border-bottom:1px solid #d6dfd1;vertical-align:top}a{color:#226045}.note{background:#fff3d8;padding:16px}.small{font-size:13px}th{background:#e6eddc}tr{scroll-margin-top:20px}@media(max-width:750px){main{padding:8px}table{font-size:14px}td,th{padding:7px}}'
LABELS={'acceptable':'Sentido compatible','needs_improvement':'Necesita mejorar','incorrect':'Significado incorrecto','incomplete':'Texto incompleto','fragmented':'Frase fragmentada','edition_difference':'Diferencia entre ediciones'}

def publish():
    DEST.mkdir(exist_ok=True);reviews={}
    for path in (ROOT/'benchmarks/full-comics/visual-reviews').glob('*.json'):
        report=read(path);chapter=report['chapter']
        reference=QA/'ocr-es'/f'{chapter}-es.jsonl'
        english=QA/report['evaluated_english_report_directory']/f'{chapter}-en.jsonl'
        assert hashlib.sha256(reference.read_bytes()).hexdigest()==report['reference_report_sha256']
        assert hashlib.sha256(english.read_bytes()).hexdigest()==report['evaluated_english_report_sha256']
        checked={r for entry in report['entries'] if entry['visual_word_reading_checked'] for r in entry['reference_regions']}
        rows=[json.loads(s) for s in reference.read_text(encoding='utf-8').splitlines() if s.strip()]
        report['reference_ocr_tokens_inspected']=sum(len(tokens(rows[i]['source'])) for i in checked)
        report['reference_reading_tokens']=sum(len(tokens(e['reference_reading'])) for e in report['entries'])
        report['meaning_results']=dict(collections.Counter(e['meaning_result'] for e in report['entries']))
        reviews[chapter]=report;entries=[]
        review_folder=report['evaluated_english_report_directory'].replace('translated-en','review')
        for entry in report['entries']:
            n=entry['id'];evidence='../'+entry['evidence_sheet']
            entries.append(f'<tr id="dialogue-{n}"><td>{n}<p><a href="{evidence}">Imágenes cotejadas</a></p><a href="../chapter-photos/{chapter}.html#image-{entry["english_image"]}">Imagen completa</a></td><td>{escape(entry["english_reading"])}</td><td>{escape(entry["reference_reading"])}</td><td>{escape(entry["recorded_translation"])}<details><summary>OCR guardado</summary><p>EN: {escape(entry["recorded_english_ocr"])}</p><p>ES: {escape(entry["recorded_reference_ocr"])}</p></details></td><td><strong>{LABELS[entry["meaning_result"]]}</strong><p>{escape(entry["note_es"])}</p></td></tr>')
        document=f'<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{chapter} · Revisión de palabras</title><style>{STYLE}</style><main><a href="index.html">← Revisión de los 124 capítulos</a><h1>{chapter} · lectura y significado</h1><p>{len(report["entries"])} parejas de diálogo y narración cotejadas visualmente · {report["reference_ocr_tokens_inspected"]} tokens del OCR de referencia inspeccionados · {report["reference_reading_tokens"]} palabras en la transcripción española verificada.</p><p class="note">Evaluación del asistente sobre la pasada {escape(report["evaluated_english_report_directory"])}. Las transcripciones se contrastaron con los recortes originales; las lecturas erróneas del OCR de Olympus se muestran por separado. El resultado de cada diálogo se refiere a esa pasada guardada. Los créditos, marcas y palabras fuera de estos recortes siguen pendientes. El capítulo completo no está aprobado. Estos datos pertenecen a las pruebas y no son respuestas cargadas por Luma.</p><p><a href="../chapter-photos/{chapter}.html">Todas las imágenes</a> · <a href="../review8010/{chapter}.html">Comparación de palabras</a> · <a href="{chapter}.json">Registro y procedencia</a></p><div style="overflow:auto"><table><thead><tr><th>Diálogo</th><th>Inglés leído en la imagen</th><th>Olympus leído en la imagen</th><th>Salida guardada de Luma</th><th>Evaluación</th></tr></thead><tbody>'+''.join(entries)+'</tbody></table></div></main></html>'
        document=document.replace('../review8010/',f'../{review_folder}/')
        for suffix,value in [('json',json.dumps(report,ensure_ascii=False,indent=2)),('html',document)]:
            (DEST/f'{chapter}.{suffix}').write_text(value,encoding='utf-8')
    entries=[]
    for number in range(1,125):
        chapter=f'absolute-regression-{number:02d}';report=reviews.get(chapter)
        status=f'{len(report["entries"])} parejas; {report["reference_ocr_tokens_inspected"]} tokens inspeccionados' if report else 'Pendiente de revisión visual'
        link=f'<a href="{chapter}.html">Ver observaciones</a>' if report else f'<a href="../chapter-photos/{chapter}.html">Abrir imágenes</a>'
        entries.append(f'<tr><td>{number}</td><td>{status}</td><td>Pendiente</td><td>{link}</td></tr>')
    summary=dict(chapters_expected=124,chapters_with_partial_visual_review=len(reviews),chapters_fully_visually_reviewed=0,
        dialogue_pairs_checked=sum(len(r['entries']) for r in reviews.values()),reference_ocr_tokens_inspected=sum(r['reference_ocr_tokens_inspected'] for r in reviews.values()),semantic_accuracy=None)
    document=f'<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luma · Revisión palabra por palabra</title><style>{STYLE}</style><main><h1>Revisión palabra por palabra · 124 capítulos</h1><p>{summary["dialogue_pairs_checked"]} parejas de diálogo cotejadas · {summary["reference_ocr_tokens_inspected"]} tokens de referencia inspeccionados · 0 capítulos aprobados completos.</p><p class="note">Este registro cuenta únicamente las observaciones visuales documentadas. Recorrer imágenes, detectar palabras o encontrar coincidencias literales no marca un capítulo como revisado. Una palabra inspeccionada puede contener un error; su resultado se explica en el diálogo correspondiente.</p><p><a href="../chapter-photos/index.html">Imágenes originales y salidas de Luma</a></p><table><thead><tr><th>Capítulo</th><th>Trabajo visual documentado</th><th>Revisión completa</th><th>Comparación</th></tr></thead><tbody>'+''.join(entries)+'</tbody></table></main></html>'
    (DEST/'index.html').write_text(document,encoding='utf-8');(DEST/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))

if __name__=='__main__':publish()
