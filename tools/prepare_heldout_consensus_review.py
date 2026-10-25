"""Run the frozen consensus on new locations, then render changed outputs."""
import json
import pathlib
import subprocess
import textwrap
from PIL import Image,ImageDraw,ImageFont
from audit_corpus_quality import ROOT,QA,read,records,digest,atomic


def main():
    folder=QA/'ocr-reader-heldout8016';out=folder/'consensus';out.mkdir(exist_ok=True)
    selection=read(QA/'ocr-reader-heldout8016-source/selection-provenance.json');sample=read(folder/'sample.json')
    binary=ROOT/'build/ocr8016/Release/luma_ocr_consensus_candidate.exe'
    assert digest(binary)==selection['frozen_binary_sha256'] and digest(ROOT/'native/ocr_consensus_candidate.h')==selection['frozen_policy_sha256']
    manifest=out/'input.jsonl';target=out/'output.jsonl';inputs=[]
    for case in sample['cases']:
        r=case['readings'];inputs.append(dict(id=case['id'],base=r['current'],first=r['english-v5'],second=r['multilingual-v6-small']))
    atomic(manifest,''.join(json.dumps(r)+'\n' for r in inputs))
    with manifest.open('rb') as src,target.open('wb') as dest:subprocess.run([str(binary),str(ROOT/'assets/models/opus-en-es/tokenizer.json')],stdin=src,stdout=dest,creationflags=subprocess.CREATE_NO_WINDOW,check=True)
    rows=records(target);assert len(rows)==124
    changed=[]
    for case,row in zip(sample['cases'],rows):
        assert case['id']==row['id'] and case['readings']['current']==row['base']
        if row['replacements']:changed.append(dict(case,id=len(changed)+1,original_id=case['id'],consensus=row,meaning_reviewed=False))
    value=dict(cases=changed,locations_tested=124,changed_locations=len(changed),word_replacements=sum(c['consensus']['replacements'] for c in changed),
        selection_provenance_sha256=digest(QA/'ocr-reader-heldout8016-source/selection-provenance.json'),native_sample_sha256=digest(folder/'sample.json'),
        input_sha256=digest(manifest),output_sha256=digest(target),binary_sha256=digest(binary),policy_sha256=digest(ROOT/'native/ocr_consensus_candidate.h'),
        all_chapter_words_visually_reviewed=False,screen_attempt_failure_probability=None,application_modified=False)
    atomic(out/'sample.json',json.dumps(value,ensure_ascii=False,indent=2))
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',19);head=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',22)
    for start in range(0,len(changed),3):
        sheet=Image.new('RGB',(1500,2460),'#f1f4ed');draw=ImageDraw.Draw(sheet)
        for j,case in enumerate(changed[start:start+3]):
            top=j*820;draw.text((12,top+8),f'Caso {case["id"]} · Nueva ubicación · Original y lectores reales',font=head,fill='#243b2b')
            assert digest(pathlib.Path(case['preview']))==case['preview_sha256']
            with Image.open(case['preview']) as bitmap:
                crop=bitmap.convert('RGB');crop.thumbnail((590,750));sheet.paste(crop,(12+(590-crop.width)//2,top+50))
            y=top+50
            for label,key in [('Base','base'),('Consenso congelado','selected'),('Lector inglés v5','first'),('Lector multilingüe v6','second')]:
                draw.text((630,y),label,font=head,fill='#243b2b');y+=30
                for line in textwrap.wrap(case['consensus'][key],width=76):draw.text((630,y),line,font=font,fill='#222');y+=24
                y+=12
            assert y<=top+820
        sheet.save(out/f'sheet-{start//3+1:02d}.jpg',quality=93)
    print(json.dumps({k:v for k,v in value.items() if k!='cases'}),flush=True)


if __name__=='__main__':main()
