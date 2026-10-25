"""Check OCR repairs and protected identifiers through the real native engine."""
import json,pathlib,subprocess

ROOT=pathlib.Path(__file__).resolve().parents[1]
cases=json.loads((ROOT/'benchmarks/bilingual-comics/ocr-normalization-cases.json').read_text(encoding='utf-8'))
process=subprocess.Popen([str(ROOT/'build/local-model/Release/luma_translate.exe'),str(ROOT/'assets/models/opus-en-es')],
    stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',bufsize=1)
results=[]
try:
    for case in cases:
        process.stdin.write(json.dumps({'source':case['source']})+'\n');process.stdin.flush()
        response=process.stdout.readline()
        if not response:raise RuntimeError(process.stderr.read())
        actual=json.loads(response)
        assert 'error' not in actual,actual
        assert actual['prepared']==case['prepared'],(case,actual)
        assert bool(actual['source_corrections'])==case['correction'],(case,actual)
        if 'target_any' in case:assert any(fragment in actual['translation'].lower() for fragment in case['target_any']),(case,actual)
        results.append(actual)
finally:
    process.stdin.close();process.wait()
destination=ROOT/'build/bilingual-quality/ocr-normalization-results.json'
destination.parent.mkdir(parents=True,exist_ok=True)
destination.write_text(json.dumps({'passed':len(results),'results':results},ensure_ascii=False,indent=2),encoding='utf-8')
print('OCR normalization checks passed:',len(results))
