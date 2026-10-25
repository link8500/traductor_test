"""Word alignment against 124 pixel-inspected English crops, kept out of models."""
import collections
import html
import json
import pathlib
import re
from audit_corpus_quality import ROOT,QA,read,records,digest,atomic
from paragraph_recovery import alignment


def tokens(text):
    return [re.sub("['’]",'',word).casefold() for word in re.findall(r"[^\W_]+(?:['’][^\W_]+)*",text,re.UNICODE)]


def compare(expected,actual):
    a,b=tokens(expected),tokens(actual);distance,trace=alignment(a,b)
    edits=[];categories=collections.Counter()
    for i,j in trace:
        if i is None:kind='inserted_word'
        elif j is None:kind='omitted_word'
        elif a[i]!=b[j]:kind='wrong_word'
        else:continue
        categories[kind]+=1;edits.append(dict(kind=kind,expected=a[i] if i is not None else None,actual=b[j] if j is not None else None))
    assert sum(categories.values())==distance
    return dict(expected_words=len(a),word_errors=distance,exact_word_sequence=distance==0,edit_categories=dict(categories),edits=edits)


def main():
    folder=QA/'ocr-reader-comparison8016';sample_path=folder/'sample.json';sample=read(sample_path)
    manual_path=ROOT/'benchmarks/full-comics/ocr8016-manual-transcriptions.json';manual=read(manual_path)
    transcriptions={r['id']:r['visible_english'] for r in manual['entries']}
    assert len(transcriptions)==len(sample['cases'])==124 and len(list(folder.glob('sheet-*.jpg')))==manual['sheets_visually_inspected']==31
    assert set(transcriptions)=={c['id'] for c in sample['cases']}
    assert digest(folder/'provenance.json')==sample['provenance_sha256']
    native={}
    for name,sha in sample['native_outputs_sha256'].items():
        path=folder/(name+'.jsonl');assert digest(path)==sha;native[name]={r['id']:r for r in records(path)}
    entries=[]
    for case in sample['cases']:
        assert digest(pathlib.Path(case['source_page']['path']))==case['source_page']['sha256']
        assert digest(pathlib.Path(case['preview']))==case['preview_sha256']
        assert digest(folder/f'{case["id"]:03d}.bgra')==case['pixels_sha256']
        assert all(case['readings'][name]==native[name][case['id']]['grouped_reading'] for name in native)
        entries.append(dict(id=case['id'],expected_visible_english=transcriptions[case['id']],edge_clipped=case['id'] in manual['edge_clipped_crops'],
            models={name:compare(transcriptions[case['id']],text) for name,text in case['readings'].items()}))
    cohorts={}
    for name,selected in [('all_124_including_clipped_edges',entries),('uncut_119', [e for e in entries if not e['edge_clipped']])]:
        metrics={}
        for model in native:
            words=sum(e['models'][model]['expected_words'] for e in selected);errors=sum(e['models'][model]['word_errors'] for e in selected)
            failed=sum(e['models'][model]['word_errors']>0 for e in selected)
            types=collections.Counter()
            for e in selected:types.update(e['models'][model]['edit_categories'])
            fixed=sum(e['models']['current']['word_errors']>0 and e['models'][model]['word_errors']==0 for e in selected)
            regressed=sum(e['models']['current']['word_errors']==0 and e['models'][model]['word_errors']>0 for e in selected)
            metrics[model]=dict(expected_words=words,word_errors=errors,word_error_rate_percent=100*errors/words,crops_with_word_error=failed,
                crop_error_rate_percent=100*failed/len(selected),edit_categories=dict(types),crops_fixed_vs_current=fixed,crops_regressed_vs_current=regressed)
        cohorts[name]=dict(crops=len(selected),models=metrics)
    result=dict(schema=1,crops_visually_reviewed=124,real_native_executions=372,manual_transcriptions_sha256=digest(manual_path),sample_sha256=digest(sample_path),
        native_provenance_sha256=digest(folder/'provenance.json'),native_outputs_sha256=sample['native_outputs_sha256'],cohorts=cohorts,
        normalization='Unicode alphanumeric words; case/punctuation ignored; apostrophes joined; numbers preserved',
        captured_pixels_fixed=True,english_transcription_supplied_to_models=False,all_chapter_words_visually_reviewed=False,
        screen_attempt_failure_probability=None,application_modified=False,entries=entries)
    atomic(ROOT/'benchmarks/full-comics/ocr8016-reader-comparison.json',json.dumps(result,ensure_ascii=False,indent=2))
    table=''.join(f'<tr><td>{html.escape(name)}</td><td>{m["word_errors"]} / {m["expected_words"]}</td><td>{m["word_error_rate_percent"]:.2f} %</td><td>{m["crops_with_word_error"]} / 124</td><td>{m["crops_fixed_vs_current"]} / {m["crops_regressed_vs_current"]}</td></tr>' for name,m in cohorts['all_124_including_clipped_edges']['models'].items())
    sheets=''.join(f'<img loading="lazy" src="sheet-{i:02d}.jpg" alt="Lecturas cotejadas {i}">' for i in range(1,32))
    atomic(folder/'index.html',f'<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luma · Cotejo de lectores OCR</title><style>body{{font:17px system-ui;background:#f1f4ed;color:#243b2b;margin:24px}}img{{display:block;width:100%;max-width:1600px;margin:24px auto}}p{{line-height:1.6;max-width:1100px}}table{{border-collapse:collapse;background:white}}td,th{{border:1px solid #bbb;padding:12px}}</style><h1>Lectores OCR · píxeles fijos de 124 capítulos</h1><p>Una ubicación congelada por capítulo, 372 ejecuciones nativas y 124 transcripciones cotejadas visualmente. Se compara la misma detección y agrupación de líneas, con el lector primario indicado y el respaldo inglés anterior. Las respuestas no entraron al motor. Mayúsculas y puntuación no cambian la cuenta de palabras; números y palabras omitidas sí.</p><table><tr><th>Lector</th><th>Errores / palabras</th><th>Tasa por palabra</th><th>Recortes con algún error</th><th>Corregidos / empeorados frente al actual</th></tr>{table}</table><p>Se conservan cinco recortes con una línea parcialmente cortada por el borde; el informe JSON separa también los otros 119. Es una prueba de lectura de recortes, no una tasa de fallo de la aplicación ni una aprobación de pantallas o capítulos completos. Un promedio bajo por palabra puede coexistir con muchos recortes defectuosos. No se modificó el paquete de la aplicación.</p><p><a href="../metrics/index.html">Resultados agregados y alcance</a></p>'+sheets+'</html>')
    print(json.dumps({k:v for k,v in result.items() if k!='entries'}),flush=True)


if __name__=='__main__':main()
