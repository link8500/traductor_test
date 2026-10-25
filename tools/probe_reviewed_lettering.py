"""Compare the two bundled OCR readers on inspected original comic pixels.

Experimental QA only. Reference transcriptions never enter either OCR process.
The shipped models, application settings and running corpus engines are untouched.
"""
import hashlib,json,pathlib,shutil,subprocess,sys
from PIL import Image
from evaluate_visual_word_reviews import intersects,align,words

ROOT=pathlib.Path(__file__).resolve().parents[1];QA=ROOT/'build/full-comics';OUT=QA/'ocr-reader-probe8011'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
records=lambda p:[json.loads(s) for s in p.read_text(encoding='utf-8').splitlines() if s.strip()]
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def ordered(lines):
    rows=[]
    for line in sorted(lines,key=lambda r:min(r['quad'][1::2])):
        q=line['quad'];left=min(q[::2]);top=min(q[1::2]);bottom=max(q[1::2]);height=bottom-top
        group=next((g for g in rows if min(g['bottom'],bottom)-max(g['top'],top)>.6*min(g['height'],height)),None)
        if group is None:group=dict(top=top,bottom=bottom,height=height,parts=[]);rows.append(group)
        group['parts'].append((left,line['text']))
    return ' '.join(text for group in rows for _,text in sorted(group['parts']))

def main():
    OUT.mkdir(exist_ok=True);models=ROOT/'assets/models/opus-en-es';manifest=read(models/'manifest.json')
    truth=read(ROOT/'benchmarks/full-comics/visual-reviews/absolute-regression-124.json')
    anchors=records(QA/truth['anchor_english_report_directory']/'absolute-regression-124-en.jsonl')
    current=records(QA/truth['evaluated_english_report_directory']/'absolute-regression-124-en.jsonl')
    pages={p['image']:p for p in read(QA/'images-en.json') if p['chapter']=='absolute-regression-124-en'}
    selected={2,3,19,20,23,38,53,55,65,66};cases=[];requests=[]
    for entry in truth['entries']:
        if entry['id'] not in selected:continue
        old=[anchors[i]['bounds'] for i in entry['english_regions']]
        rows=[r for r in current if r['image']==entry['english_image'] and any(intersects(b,r['bounds']) for b in old)]
        assert rows,entry['id'];page=pages[entry['english_image']];original=pathlib.Path(page['path'])
        assert digest(original)==page['sha256']
        with Image.open(original) as image:
            box=(max(0,min(r['bounds'][0] for r in rows)-80),max(0,min(r['bounds'][1] for r in rows)-60),
                min(image.width,max(r['bounds'][2] for r in rows)+80),min(image.height,max(r['bounds'][3] for r in rows)+100))
            crop=image.crop(box).convert('RGBA');path=OUT/f'{entry["id"]:02d}.bgra';path.write_bytes(crop.tobytes('raw','BGRA'))
            width,height=crop.size
        cases.append(dict(dialogue=entry['id'],expected=entry['english_reading'],original_sha256=page['sha256'],crop_bounds=box,pixels_sha256=digest(path)))
        requests.append(dict(path=str(path),width=width,height=height))
    results={};binary=ROOT/'build/local-model/Release/luma_ocr.exe';assert binary.exists()
    for family,model,dictionary in [('latin-v5','english-ocr.onnx','ocr-characters.json'),('english-v4','english-ocr-fallback.onnx','ocr-characters-fallback.json')]:
        directory=OUT/family;directory.mkdir(exist_ok=True)
        for original,name in [(model,'english-ocr.onnx'),(dictionary,'ocr-characters.json')]:
            assert digest(models/original)==manifest['files'][original]
            shutil.copy2(models/original,directory/name);assert digest(directory/name)==manifest['files'][original]
        process=subprocess.Popen([str(binary),str(directory),str(models)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
        raw,error=process.communicate(''.join(json.dumps(r)+'\n' for r in requests),timeout=900)
        assert process.returncode==0,error
        values=[json.loads(s) for s in raw.splitlines() if s.strip()];assert len(values)==len(cases)
        summaries=[]
        for case,value in zip(cases,values):
            assert 'error' not in value,value.get('error');actual=ordered(value['lines']);distance,trace=align(words(case['expected']),words(actual))
            summaries.append(dict(**case,actual=actual,word_edits=distance,lines=value['lines'],milliseconds=value['milliseconds']))
        report=dict(reader=family,detector='Same bundled DB detector on the same paragraph crops',
            binary_sha256=digest(binary),model_sha256=manifest['files'][model],dictionary_sha256=manifest['files'][dictionary],
            reference_transcriptions_passed_to_ocr=False,application_models_modified=False,cases=summaries)
        (OUT/(family+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');results[family]=summaries
        print(family,sum(r['word_edits'] for r in summaries),'word edits on',len(summaries),'inspected paragraph crops',flush=True)
    comparison=[dict(dialogue=c['dialogue'],expected=c['expected'],readers={family:dict(actual=values[i]['actual'],word_edits=values[i]['word_edits']) for family,values in results.items()}) for i,c in enumerate(cases)]
    (OUT/'comparison.json').write_text(json.dumps(comparison,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
