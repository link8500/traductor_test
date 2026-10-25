"""Freeze a deterministic bilingual sample distributed over all 124 chapters.

Original pixels, inference hashes and automatic alignment proposals are kept.
Preparing a sheet never marks its contents as reviewed or correct.
"""
import argparse
import collections
import hashlib
import json
import pathlib
import textwrap

from PIL import Image, ImageDraw, ImageFont

from audit_corpus_quality import QA, ROOT, CHAPTERS, BASELINE, COHORTS, complete, records, read, digest, atomic
from translation_quality_signals import PROMOTION, tokens, signals

OUT = QA / 'corpus-review-sample'


def overlap(a, b):
    area = lambda box: max(0, box[2]-box[0])*max(0, box[3]-box[1])
    intersection = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    return intersection / max(1, min(area(a), area(b)))


def build(per_chapter=1, exclude_sample=None, min_words=7, max_words=32, min_reference_words=5, max_reference_words=40):
    OUT.mkdir(exist_ok=True)
    target = OUT / 'sample.json'
    if target.exists():
        print('Preserved frozen sample:', len(read(target)['cases']))
        return read(target)
    pages = {language: {(r['chapter'].removesuffix('-'+language), r['image']): r
                        for r in read(QA / f'images-{language}.json')}
             for language in ['en', 'es']}
    excluded = read(exclude_sample)['cases'] if exclude_sample else []
    cases = []
    for chapter in CHAPTERS:
        folder = next(name for name in COHORTS if complete(name, chapter))
        current_path = QA / folder / (chapter+'-en.jsonl')
        current = records(current_path)
        baseline_path = QA / BASELINE / (chapter+'-en.jsonl')
        baseline = records(baseline_path)
        candidate_comparisons = [folder.replace('translated-en', 'comparison'), 'comparison']
        comparator = next((QA / name / (chapter+'.json') for name in candidate_comparisons
                           if (QA / name / (chapter+'.json')).exists()), None)
        assert comparator, chapter
        metadata = read(comparator)
        alignment_folder = metadata['english_report_directory']
        alignment_rows = records(QA / alignment_folder / (chapter+'-en.jsonl'))
        ledger = records(comparator.with_name(chapter+'.words.jsonl'))
        reference_path = QA / 'ocr-es' / (chapter+'-es.jsonl')
        reference = records(reference_path)
        proposals = collections.defaultdict(set)
        for row in ledger:
            if row['luma_region'] is not None:
                proposals[row['luma_region']].add(row['reference_region'])
        candidates = []
        for region, proposed in proposals.items():
            anchor = alignment_rows[region]
            if any(e['chapter']==chapter and e['source_image']==anchor['image'] and overlap(e['bounds'],anchor['bounds'])>.5 for e in excluded):
                continue
            n = len(tokens(anchor['source']))
            if not min_words <= n <= max_words or PROMOTION.search(anchor['source']):
                continue
            # Single dialogue crops keep manual alignment review feasible. The
            # original Spanish crop can still disagree; adjudication must say so.
            refs = [reference[i] for i in proposed]
            ref = max(refs, key=lambda r: len(tokens(r['source'])))
            if PROMOTION.search(ref['source']) or not min_reference_words <= len(tokens(ref['source'])) <= max_reference_words:
                continue
            nearby = [(i, r) for i, r in enumerate(current) if r['image']==anchor['image'] and overlap(r['bounds'], anchor['bounds']) > .65]
            if len(nearby) != 1:
                continue
            current_index, selected = nearby[0]
            old = [r for r in baseline if r['image']==selected['image'] and overlap(r['bounds'], selected['bounds'])>.65]
            if not old:
                continue
            stable = hashlib.sha256((chapter+':'+str(region)).encode()).hexdigest()
            candidates.append((stable, current_index, selected, reference.index(ref), ref, old))
        assert len(candidates)>=per_chapter, (chapter, len(candidates))
        chosen = []
        for candidate in sorted(candidates, key=lambda value: value[0]):
            if any(candidate[2]['image']==old[2]['image'] and overlap(candidate[2]['bounds'],old[2]['bounds'])>.5 for old in chosen):
                continue
            chosen.append(candidate)
            if len(chosen)==per_chapter:break
        assert len(chosen)==per_chapter, chapter
        for _, index, selected, ref_index, ref, before in chosen:
            source_page = pages['en'][(chapter, selected['image'])]
            reference_page = pages['es'][(chapter, ref['image'])]
            cases.append(dict(id=len(cases)+1, chapter=chapter, sampling=f'{per_chapter} hashed eligible aligned regions per chapter; not selected by translation outcome',
                current_folder=folder, current_report_sha256=digest(current_path), current_region=index,
                baseline_folder=BASELINE, baseline_report_sha256=digest(baseline_path),
                source=selected['source'], translation=selected.get('translation', ''),
                before_source=' '.join(r['source'] for r in before),
                before_translation=' '.join(r.get('translation', '') for r in before),
                bounds=selected['bounds'], source_image=selected['image'],
                reference_source=ref['source'], reference_region=ref_index, reference_bounds=ref['bounds'], reference_image=ref['image'],
                source_page=source_page, reference_page=reference_page,
                signals=signals(selected), artwork_alignment_human_verified=False,
                meaning_reviewed=False, meaning_result=None))
    result=dict(schema=1, chapters=124, regions_per_chapter=per_chapter,
                source_word_range=[min_words,max_words],reference_word_range=[min_reference_words,max_reference_words],
                excluded_sample_sha256=digest(exclude_sample) if exclude_sample else None,
                cases=cases, full_chapter_review=False,
                reference_text_used_by_application=False, selection_program_sha256=digest(pathlib.Path(__file__)))
    atomic(target, json.dumps(result, ensure_ascii=False, indent=2))
    return result


def render(sample,pad_x=30,pad_y=24):
    font_path = pathlib.Path('C:/Windows/Fonts/arial.ttf')
    font = ImageFont.truetype(str(font_path), 19)
    small = ImageFont.truetype(str(font_path), 17)
    heading = ImageFont.truetype(str(font_path), 22)
    for start in range(0, len(sample['cases']), 4):
        sheet = Image.new('RGB', (1440, 2240), '#f1f4ed')
        draw = ImageDraw.Draw(sheet)
        for offset, case in enumerate(sample['cases'][start:start+4]):
            top = offset*560
            draw.text((16, top+8), f'Caso {case["id"]} · EN original / ES referencia / salida anterior y actual', font=heading, fill='#243b2b')
            for x, page, bounds in [(12, case['source_page'], case['bounds']), (485, case['reference_page'], case['reference_bounds'])]:
                assert digest(pathlib.Path(page['path'])) == page['sha256']
                with Image.open(page['path']) as image:
                    box = (max(0, bounds[0]-pad_x), max(0, bounds[1]-pad_y),
                           min(image.width, bounds[2]+pad_x), min(image.height, bounds[3]+pad_y))
                    crop = image.crop(box).convert('RGB')
                    crop.thumbnail((460, 480))
                    sheet.paste(crop, (x+(460-crop.width)//2, top+48))
            y = top+48
            for label, text in [('Antes', case['before_translation']), ('Actual', case['translation']), ('OCR actual', case['source'])]:
                draw.text((965, y), label, font=heading, fill='#243b2b'); y += 27
                for line in textwrap.wrap(text, width=43):
                    draw.text((965, y), line, font=font if label!='OCR actual' else small, fill='#222222');y += 24
                y += 15
        output = OUT / f'sheet-{start//4+1:02d}.jpg'
        sheet.save(output, quality=93)
    print('Frozen sample:', len(sample['cases']), 'pairs across', sample['chapters'], 'chapters; sheets', (len(sample['cases'])+3)//4)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-name', default='corpus-review-sample')
    parser.add_argument('--per-chapter', type=int, default=1)
    parser.add_argument('--exclude-sample', type=pathlib.Path)
    parser.add_argument('--min-words',type=int,default=7)
    parser.add_argument('--max-words',type=int,default=32)
    parser.add_argument('--min-reference-words',type=int,default=5)
    parser.add_argument('--max-reference-words',type=int,default=40)
    parser.add_argument('--horizontal-context',type=int,default=30)
    parser.add_argument('--vertical-context',type=int,default=24)
    args = parser.parse_args()
    assert 1<=args.per_chapter<=5
    assert 1<=args.min_words<=args.max_words<=150
    assert 1<=args.min_reference_words<=args.max_reference_words<=150
    assert args.output_name.isascii() and all(c.isalnum() or c=='-' for c in args.output_name)
    OUT = QA/args.output_name
    assert 0<=args.horizontal_context<=1000 and 0<=args.vertical_context<=1000
    render(build(args.per_chapter,args.exclude_sample,args.min_words,args.max_words,args.min_reference_words,args.max_reference_words),args.horizontal_context,args.vertical_context)
