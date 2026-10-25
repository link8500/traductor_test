"""Prepare all changed opening candidates with original bilingual pixels.

Artwork/region alignment remains a proposal until visually inspected.
"""
import collections
import argparse
import html
import json
import pathlib
import textwrap

from PIL import Image, ImageDraw, ImageFont
from audit_corpus_quality import ROOT, QA, atomic, digest, read, records
from prepare_corpus_review_sample import overlap


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--folder',default='opening8028');parser.add_argument('--changes',default='normalized-changes.json');parser.add_argument('--comparison',default='comparison');parser.add_argument('--reference-overrides',type=pathlib.Path);parser.add_argument('--title',default='Aperturas de diálogo · candidato, sin incorporar');args=parser.parse_args()
    assert pathlib.Path(args.folder).name==args.folder and pathlib.Path(args.changes).name==args.changes and pathlib.Path(args.comparison).name==args.comparison
    folder=QA/args.folder;out=folder/'review';out.mkdir(exist_ok=True)
    changes=read(folder/args.changes)
    overrides={r['id']:r['reference_region'] for r in read(args.reference_overrides)['entries']} if args.reference_overrides else {}
    pages={lang:{(r['chapter'],r['image']):r for r in read(QA/f'images-{lang}.json')} for lang in ['en','es']}
    cases=[]
    for case in changes:
        chapter=case['report'].removesuffix('-en.jsonl')
        metadata_path=QA/args.comparison/(chapter+'.json');metadata=read(metadata_path)
        alignment_report=QA/metadata['english_report_directory']/(chapter+'-en.jsonl')
        english=records(alignment_report);spanish_path=QA/'ocr-es'/(chapter+'-es.jsonl');spanish=records(spanish_path)
        linked={i for i,r in enumerate(english) if r['image']==case['image'] and overlap(r['bounds'],case['bounds'])>.65}
        votes=collections.Counter(r['reference_region'] for r in records(metadata_path.with_name(chapter+'.words.jsonl')) if r['luma_region'] in linked)
        refs=[spanish[i] for i,_ in votes.most_common()]
        reference=max(refs,key=lambda r:len(r['source'])) if refs else None
        if case['id'] in overrides:reference=spanish[overrides[case['id']]]
        source_page=pages['en'][(chapter+'-en',case['image'])]
        reference_page=pages['es'][(chapter+'-es',reference['image'])] if reference else None
        cases.append(dict(case,source_page=source_page,reference=reference,reference_page=reference_page,
                          reference_alignment_verified=False,meaning_reviewed=False,
                          reference_region_override=overrides.get(case['id']),
                          alignment_proof=dict(override_sha256=digest(args.reference_overrides) if args.reference_overrides else None,metadata_sha256=digest(metadata_path),report_sha256=digest(alignment_report),
                                               reference_report_sha256=digest(spanish_path))))
    sample=out/'sample.json';atomic(sample,json.dumps(cases,ensure_ascii=False,indent=2))
    normal=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',22)
    small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',19)
    title=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',25)
    for start in range(0,len(cases),2):
        image=Image.new('RGB',(2000,1200),'#f1f4ed');draw=ImageDraw.Draw(image)
        for slot,c in enumerate(cases[start:start+2]):
            top=slot*600
            draw.text((15,top+8),f"Caso {c['id']} · inglés / Olympus propuesto / traducción",font=title,fill='#243b2b')
            for x,page,box in [(12,c['source_page'],c['bounds']),
                               (620,c['reference_page'],c['reference']['bounds'] if c['reference'] else None)]:
                if not page:continue
                assert digest(pathlib.Path(page['path']))==page['sha256']
                with Image.open(page['path']) as source:
                    crop=source.crop((max(0,box[0]-65),max(0,box[1]-110),min(source.width,box[2]+65),min(source.height,box[3]+110))).convert('RGB')
                    crop.thumbnail((595,520));image.paste(crop,(x+(595-crop.width)//2,top+50))
            y=top+50
            for label,text in [('OCR EN',c['source']),('Anterior',c['policy']['translation']),('Candidato',c['policy']['candidate_translation'])]:
                draw.text((1235,y),label,font=title,fill='#243b2b');y+=31
                for line in textwrap.wrap(text,width=63):
                    draw.text((1235,y),line,font=small if label=='OCR EN' else normal,fill='#202520');y+=26
                y+=13
        image.save(out/f'sheet-{start//2+1:02d}.jpg',quality=93)
    atomic(out/'index.html','<!doctype html><meta charset="utf-8"><title>Luma · aperturas en prueba</title>'
        f'<h1>{html.escape(args.title)}</h1><p>Se muestran todas las salidas modificadas. '
        'La referencia y la alineación son propuestas pendientes de cotejo. No mide precisión global.</p>'
        +''.join(f'<p><a href="sheet-{i+1:02d}.jpg">Comparación {i+1}</a></p><img style="max-width:100%" src="sheet-{i+1:02d}.jpg">' for i in range((len(cases)+1)//2)))
    print(json.dumps(dict(changed_cases=len(cases),sheets=(len(cases)+1)//2,missing_reference_proposal=sum(c['reference'] is None for c in cases),
                         sample_sha256=digest(sample),meanings_reviewed=False)),flush=True)


if __name__=='__main__':main()
