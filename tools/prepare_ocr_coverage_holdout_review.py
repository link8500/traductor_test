"""Apply the frozen OCR coverage trial to a third uninspected set of pixels."""
import json
import pathlib
import subprocess
import textwrap
from PIL import Image,ImageDraw,ImageFont
from audit_corpus_quality import ROOT,QA,atomic,digest,read,records


def main():
    folder=QA/'ocr-coverage8017-holdout';out=folder/'coverage';out.mkdir(exist_ok=True)
    source=QA/'ocr-coverage8017-holdout-source';selection=read(source/'selection-provenance.json')
    sample=read(folder/'sample.json');frozen=QA/'ocr-coverage8017-development';binary=frozen/'native.exe'
    assert digest(binary)==selection['binary_sha256']
    assert digest(frozen/'ocr_coverage_candidate.h')==selection['policy_sha256']
    assert digest(source/'sample.json')==selection['selection_sha256']
    manifest=out/'input.jsonl';target=out/'output.jsonl'
    inputs=[dict(id=c['id'],base=c['readings']['current'],first=c['readings']['english-v5'],second=c['readings']['multilingual-v6-small']) for c in sample['cases']]
    atomic(manifest,''.join(json.dumps(r)+'\n' for r in inputs))
    with manifest.open('rb') as src,target.open('wb') as dest:
        subprocess.run([str(binary),str(ROOT/'assets/models/opus-en-es/tokenizer.json')],stdin=src,stdout=dest,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    actual=records(target);assert len(actual)==len(sample['cases'])==124
    changed=[]
    for case,row in zip(sample['cases'],actual):
        assert case['id']==row['id'] and case['readings']['current']==row['base']
        if row['base']!=row['selected']:changed.append(dict(case,id=len(changed)+1,original_id=case['id'],candidate=row,meaning_reviewed=False))
    value=dict(cases=changed,locations_inferred=124,changed_locations=len(changed),
        replacements=sum(r['replacements'] for r in actual),insertions=sum(r['insertions'] for r in actual),
        selection_provenance_sha256=digest(source/'selection-provenance.json'),native_sample_sha256=digest(folder/'sample.json'),
        input_sha256=digest(manifest),output_sha256=digest(target),policy_sha256=selection['policy_sha256'],binary_sha256=selection['binary_sha256'],
        manual_transcription_used_for_inference=False,all_locations_visually_reviewed=False,
        application_modified=False,screen_attempt_failure_probability=None)
    atomic(out/'sample.json',json.dumps(value,ensure_ascii=False,indent=2))
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',19);head=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',22)
    for start in range(0,len(changed),3):
        sheet=Image.new('RGB',(1500,2400),'#f1f4ed');draw=ImageDraw.Draw(sheet)
        for offset,case in enumerate(changed[start:start+3]):
            top=offset*800;draw.text((12,top+8),f'Caso {case["id"]} · Píxeles nuevos / lectura base y candidato congelado',font=head,fill='#243b2b')
            assert digest(pathlib.Path(case['preview']))==case['preview_sha256']
            with Image.open(case['preview']) as image:
                crop=image.convert('RGB');crop.thumbnail((600,720));sheet.paste(crop,(12+(600-crop.width)//2,top+50))
            y=top+50
            for label,key in [('Base','base'),('Candidato','selected'),('Inglés v5','first'),('Multilingüe v6','second')]:
                draw.text((640,y),label,font=head,fill='#243b2b');y+=29
                for line in textwrap.wrap(case['candidate'][key],width=72):draw.text((640,y),line,font=font,fill='#222');y+=24
                y+=12
            assert y<=top+800
        sheet.save(out/f'sheet-{start//3+1:02d}.jpg',quality=93)
    print(json.dumps({k:v for k,v in value.items() if k!='cases'}),flush=True)


if __name__=='__main__':main()
