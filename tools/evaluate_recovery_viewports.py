"""Translate actual recovered production regions, preserving inference evidence.

Reference images are used only for review sheets after inference has finished.
The viewport set is a regression sample, not an exhaustive chapter review.
"""
import argparse
import collections
import json
import pathlib
import subprocess
import textwrap
import time

from PIL import Image, ImageDraw, ImageFont
from audit_corpus_quality import ROOT, QA, CURRENT, read, records, digest, atomic
from evaluate_paragraph_probe import matching
from prepare_corpus_review_sample import overlap
from translate_ocr_reports import translation_code


def render(case, seed, output):
    sheet = Image.new('RGB', (1560, 1100), '#f1f4ed')
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 19)
    heading = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 23)
    draw.text((16, 10), 'Región recuperada por la aplicación compilada · Original / referencia / inferencia real', font=heading, fill='#243b2b')
    for x, page, bounds in [(12, seed['source_page'], case['source_bounds']),
                            (525, seed['reference_page'], seed['reference_bounds'])]:
        assert digest(pathlib.Path(page['path'])) == page['sha256']
        with Image.open(page['path']) as bitmap:
            crop = bitmap.crop((max(0,bounds[0]-35), max(0,bounds[1]-35),
                min(bitmap.width,bounds[2]+35), min(bitmap.height,bounds[3]+35))).convert('RGB')
            crop.thumbnail((500, 800))
            sheet.paste(crop,(x+(500-crop.width)//2,60))
    y = 58
    controls = case['control_regions']
    pairs = [('Control OCR', ' '.join(c['source'] for c in controls)),
             ('Control traducción', ' '.join(c.get('translation','') for c in controls)),
             ('OCR recuperado', case['source']),
             ('Traducción recuperada', case['inference']['translation'])]
    for label, value in pairs:
        draw.text((1044,y),label,font=heading,fill='#243b2b');y+=30
        for line in textwrap.wrap(value,width=37):
            draw.text((1044,y),line,font=font,fill='#222222');y+=25
        y+=18
    draw.text((16,1040), 'Referencia propuesta automáticamente; debe comprobarse su correspondencia. No aprueba el capítulo completo.',font=font,fill='#243b2b')
    sheet.save(output,quality=94)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',default='801201')
    parser.add_argument('--watch',action='store_true')
    args=parser.parse_args()
    assert args.build.isdecimal()
    folder=QA/('recovery-viewports'+args.build)
    output=folder/'evaluation';output.mkdir(exist_ok=True)
    seeds={s['id']:s for s in read(QA/'corpus-review-sample/sample.json')['cases']}
    provenance=read(QA/CURRENT/'inference-provenance.json')
    assert digest(ROOT/'build/local-model/Release/onnxruntime.dll')==provenance['runtime_sha256']
    assert __import__('hashlib').sha256(translation_code((ROOT/'native/local_translation.cpp').read_bytes())).hexdigest()==provenance['translation_code_sha256']
    for name,sha in provenance['translation_assets'].items():
        assert digest(ROOT/'assets/models/opus-en-es'/name)==sha
    model=None
    previous=None
    try:
        while True:
            for status_path in sorted(folder.glob('*.done.json')):
                status=read(status_path);case_id=status['id']
                result_path=output/f'{case_id:03d}.json'
                if result_path.exists():
                    assert read(result_path)['ocr_output_sha256']==status['source_output_sha256']
                    continue
                source_path=status_path.with_name(f'{case_id:03d}.jsonl')
                assert digest(source_path)==status['source_output_sha256']
                control_path=QA/CURRENT/(status['chapter']+'-en.jsonl')
                assert digest(control_path)==status['baseline_report_sha256']
                control=records(control_path);seed=seeds[case_id];cases=[]
                for index,row in enumerate(records(source_path)):
                    if not row.get('paragraph_recovered'):continue
                    mapped=dict(row,image=status['source_image'],bounds=list(row['bounds']))
                    mapped['bounds'][1]+=status['viewport_top'];mapped['bounds'][3]+=status['viewport_top']
                    controls=matching(dict(source_image=mapped['image'],bounds=mapped['bounds']),control)
                    if model is None:
                        model=subprocess.Popen([str(ROOT/'build/local-model/Release/luma_translate.exe'),str(ROOT/'assets/models/opus-en-es')],
                            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
                    model.stdin.write(json.dumps(dict(source=row['source']))+'\n');model.stdin.flush()
                    line=model.stdout.readline();assert line,'Missing real model output'
                    inference=json.loads(line);assert 'error' not in inference,inference
                    case=dict(viewport_id=case_id,region_index=index,source=row['source'],source_bounds=mapped['bounds'],
                        inference=inference,control_regions=controls,control_match_ambiguous=len(controls)!=1,
                        reference_seed_overlap=overlap(seed['bounds'],mapped['bounds']),
                        reference_used_for_inference=False,meaning_reviewed=False)
                    cases.append(case)
                    render(case,seed,output/f'{case_id:03d}-{index:03d}.jpg')
                result=dict(viewport_id=case_id,ocr_output_sha256=status['source_output_sha256'],
                    engine=status['engine'],translation_signature=provenance['translation_signature'],
                    translator_weights_changed=False,cases=cases)
                atomic(result_path,json.dumps(result,ensure_ascii=False,indent=2))
            files=list(output.glob('[0-9][0-9][0-9].json'))
            cases=[c for p in files for c in read(p)['cases']]
            summary=dict(evaluated_viewports=len(files),expected_viewports=124,recovered_regions=len(cases),
                ambiguous_controls=sum(c['control_match_ambiguous'] for c in cases),
                source_changed=sum(len(c['control_regions'])==1 and c['source']!=c['control_regions'][0]['source'] for c in cases),
                translation_changed=sum(len(c['control_regions'])==1 and c['inference']['translation']!=c['control_regions'][0]['translation'] for c in cases),
                all_regions_visually_reviewed=False,semantic_accuracy=None,full_chapter_review=False)
            atomic(output/'summary.json',json.dumps(summary,indent=2))
            if summary!=previous:print(json.dumps(summary),flush=True);previous=summary
            if not args.watch or len(files)==124:break
            if model is not None:model.stdin.close();model.wait(timeout=30);model=None
            time.sleep(15)
    finally:
        if model is not None:model.stdin.close();model.wait(timeout=30)


if __name__=='__main__':main()
