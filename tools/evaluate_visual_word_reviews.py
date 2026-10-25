"""Compare every transcribed English word to saved OCR in inspected dialogues.

This is an OCR regression measure, not semantic accuracy or chapter approval.
Ground truth is used only in this QA tool, never to generate app translations.
"""
import argparse,collections,hashlib,html,json,pathlib,re

ROOT=pathlib.Path(__file__).resolve().parents[1];QA=ROOT/'build/full-comics'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
records=lambda p:[json.loads(s) for s in p.read_text(encoding='utf-8').splitlines() if s.strip()]
words=lambda s:re.findall(r"[^\W_]+(?:['’\-][^\W_]+)*",s.casefold().replace('’',"'"),re.UNICODE)
escape=lambda s:html.escape(str(s),quote=True)

def align(expected,actual):
    costs=[[0]*(len(actual)+1) for _ in range(len(expected)+1)]
    for i in range(len(expected)+1):costs[i][0]=i
    for j in range(len(actual)+1):costs[0][j]=j
    for i,a in enumerate(expected,1):
        for j,b in enumerate(actual,1):costs[i][j]=min(costs[i-1][j]+1,costs[i][j-1]+1,costs[i-1][j-1]+(a!=b))
    trace=[];i=len(expected);j=len(actual)
    while i or j:
        if i and j and costs[i][j]==costs[i-1][j-1]+(expected[i-1]!=actual[j-1]):
            trace.append(dict(expected=expected[i-1],actual=actual[j-1],state='same' if expected[i-1]==actual[j-1] else 'substituted'));i-=1;j-=1
        elif i and costs[i][j]==costs[i-1][j]+1:
            trace.append(dict(expected=expected[i-1],actual=None,state='missing'));i-=1
        else:trace.append(dict(expected=None,actual=actual[j-1],state='added'));j-=1
    return costs[-1][-1],list(reversed(trace))

def intersects(a,b):
    def area(r):return max(0,r[2]-r[0])*max(0,r[3]-r[1])
    intersection=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    return intersection>.6*min(area(a),area(b))

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--english-reports',required=True);parser.add_argument('--output-name',required=True);args=parser.parse_args()
    for name in [args.english_reports,args.output_name]:assert re.fullmatch(r'[a-z][a-z0-9-]+',name)
    output=QA/args.output_name;output.mkdir(exist_ok=True);summaries=[]
    for path in (ROOT/'benchmarks/full-comics/visual-reviews').glob('*.json'):
        truth=read(path);chapter=truth['chapter'];report=QA/args.english_reports/f'{chapter}-en.jsonl'
        if not report.with_name(f'{chapter}-en.done.json').exists():continue
        original=QA/truth.get('anchor_english_report_directory',truth['evaluated_english_report_directory'])/f'{chapter}-en.jsonl'
        assert hashlib.sha256(original.read_bytes()).hexdigest()==truth.get('anchor_english_report_sha256',truth['evaluated_english_report_sha256'])
        original_rows=records(original);rows=records(report);assessments=[]
        for entry in truth['entries']:
            known=[original_rows[i]['bounds'] for i in entry['english_regions']]
            candidates=[row for row in rows if row['image']==entry['english_image'] and any(intersects(box,row['bounds']) for box in known)]
            actual=' '.join(row['source'] for row in candidates);expected=entry['english_reading']
            distance,trace=align(words(expected),words(actual))
            assessments.append(dict(dialogue=entry['id'],image=entry['english_image'],expected=expected,actual=actual,
                translations=[row.get('translation') for row in candidates],expected_words=len(words(expected)),word_edits=distance,words=trace,
                association='Spatial overlap with inspected source regions; review proposed links if grouping changes across balloons',meaning_approved=False))
        summary=dict(chapter=chapter,english_reports=args.english_reports,report_sha256=hashlib.sha256(report.read_bytes()).hexdigest(),
            dialogue_pairs=len(assessments),expected_english_words=sum(a['expected_words'] for a in assessments),ocr_word_edits=sum(a['word_edits'] for a in assessments),
            complete_chapter_visually_reviewed=False,semantic_accuracy=None,assessments=assessments)
        (output/f'{chapter}.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');summaries.append({k:v for k,v in summary.items() if k!='assessments'})
        entries=[]
        for a in assessments:
            expected=' '.join(f'<span class="{w["state"]}" title="{escape(w["actual"] or "No detectada")}">{escape(w["expected"])}</span>' for w in a['words'] if w['expected'] is not None)
            entries.append(f'<tr><td><a href="../word-review/{chapter}.html#dialogue-{a["dialogue"]}">{a["dialogue"]}</a></td><td>{expected}</td><td>{escape(a["actual"])}</td><td>{a["word_edits"]}</td></tr>')
        document=f'<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{chapter} · Cada palabra del OCR</title><style>body{{font:16px system-ui;background:#f3f6ef;color:#253b2c;margin:24px}}table{{width:100%;border-collapse:collapse;background:white}}td,th{{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid #d6dfd1}}.missing{{background:#ffd2d2}}.substituted{{background:#ffe7af}}a{{color:#226045}}p{{max-width:1050px;line-height:1.6}}</style><h1>{chapter} · comparación de cada palabra del OCR</h1><p>Pasada {args.english_reports}: {summary["expected_english_words"]} palabras inglesas en {len(assessments)} parejas inspeccionadas; {summary["ocr_word_edits"]} inserciones, pérdidas o sustituciones. Rojo: palabra omitida; amarillo: palabra diferente. No es una medida de calidad semántica ni aprueba el capítulo completo. Las asociaciones con nuevas cajas son propuestas por geometría.</p><p><a href="../word-review/{chapter}.html">Observaciones visuales y Olympus</a> · <a href="{chapter}.json">Datos por palabra</a></p><table><thead><tr><th>Diálogo</th><th>Lectura visual inglesa</th><th>OCR real guardado</th><th>Ediciones de palabras</th></tr></thead><tbody>'+''.join(entries)+'</tbody></table>'
        (output/f'{chapter}.html').write_text(document,encoding='utf-8')
    (output/'summary.json').write_text(json.dumps(summaries,indent=2),encoding='utf-8');print(json.dumps(summaries))

if __name__=='__main__':main()
