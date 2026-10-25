"""Freeze current-engine outputs at the already inspected corpus locations.

Only byte-identical translations with unambiguous geometry reuse a semantic
judgment. Changed text is left pending for visual assessment.
"""
import argparse
import collections
import json
import pathlib
import textwrap

from PIL import Image, ImageDraw, ImageFont

from audit_corpus_quality import ROOT, QA, CURRENT, read, records, digest, atomic
from evaluate_paragraph_probe import matching


def prepare(out, original_path=None, review_path=None, reports=CURRENT):
    target = out/'sample.json'
    if target.exists():
        return read(target)
    original_path = original_path or QA/'corpus-review-sample/sample.json'
    original = read(original_path)
    review_path = review_path or ROOT/'benchmarks/full-comics/corpus-semantic-review.json'
    review = read(review_path)
    assert digest(original_path)==review['sample_sha256']
    previous = {r['id']: r for r in review['entries']}
    cases, unavailable = [], []
    for case in original['cases']:
        report = QA/reports/(case['chapter']+'-en.jsonl')
        done = report.with_name(case['chapter']+'-en.done.json')
        if not done.exists():
            unavailable.append(case['id']);continue
        rows = matching(case, records(report))
        ordered = sorted(rows, key=lambda r:(r['bounds'][1], r['bounds'][0]))
        translation = ' '.join(r.get('translation', '') for r in ordered)
        same = len(ordered) == 1 and translation == case['translation']
        box = case['bounds']
        if ordered:
            box = [min([box[0]]+[r['bounds'][0] for r in ordered]), min([box[1]]+[r['bounds'][1] for r in ordered]),
                   max([box[2]]+[r['bounds'][2] for r in ordered]), max([box[3]]+[r['bounds'][3] for r in ordered])]
        cases.append(dict(**case, full_engine_report=reports, full_engine_report_sha256=digest(report),
            refreshed_source=' '.join(r['source'] for r in ordered), refreshed_translation=translation,
            refreshed_regions=ordered, refreshed_bounds=box,
            full_engine_judgment=previous[case['id']]['after'] if same else None,
            assessment_reused_for_identical_output_and_unambiguous_geometry=same,
            previous_frozen_judgment=previous[case['id']]['after'], needs_visual_review=not same))
    value = dict(original_sample_sha256=digest(original_path), original_review_sha256=digest(review_path), current_engine=reports,
        current_chapters=len({c['chapter'] for c in cases}), regions=len(cases), chapters_expected=124, unavailable_ids=unavailable,
        changed_outputs_requiring_review=sum(c['needs_visual_review'] for c in cases),
        all_chapter_words_visually_reviewed=False, cases=cases)
    atomic(target, json.dumps(value, ensure_ascii=False, indent=2))
    return value


def render(out, sample):
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 19)
    small = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 17)
    heading = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 22)
    pending = [c for c in sample['cases'] if c['needs_visual_review']]
    for start in range(0, len(pending), 4):
        sheet = Image.new('RGB', (1440, 2240), '#f1f4ed');draw = ImageDraw.Draw(sheet)
        for position, case in enumerate(pending[start:start+4]):
            top = position*560
            draw.text((16, top+8), f'Caso {case["id"]} · original EN / referencia ES / salida de la pasada nueva', font=heading, fill='#243b2b')
            for x, page, box in [(12, case['source_page'], case['refreshed_bounds']), (485, case['reference_page'], case['reference_bounds'])]:
                assert digest(pathlib.Path(page['path'])) == page['sha256']
                with Image.open(page['path']) as image:
                    crop = image.crop((max(0,box[0]-40), max(0,box[1]-40),
                                       min(image.width,box[2]+40), min(image.height,box[3]+70))).convert('RGB')
                    crop.thumbnail((460, 480));sheet.paste(crop, (x+(460-crop.width)//2, top+48))
            y = top+48
            for label, text in [('Actual', case['refreshed_translation']), ('OCR actual', case['refreshed_source']), ('Anterior', case['translation'])]:
                draw.text((965, y), label, font=heading, fill='#243b2b');y += 27
                for line in textwrap.wrap(text, width=43):
                    draw.text((965,y), line, font=small if label=='OCR actual' else font, fill='#222222');y += 24
                y += 12
        sheet.save(out/f'sheet-{start//4+1:02d}.jpg', quality=93)
    print(json.dumps(dict(chapters_in_current_pass=sample['current_chapters'],
        reused_unchanged_semantic_assessments=len(sample['cases'])-len(pending),
        changed_outputs_pending_visual_review=len(pending), evidence_sheets=(len(pending)+3)//4)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-name', required=True)
    parser.add_argument('--sample',type=pathlib.Path)
    parser.add_argument('--review',type=pathlib.Path)
    parser.add_argument('--reports',default=CURRENT)
    args = parser.parse_args()
    assert args.output_name.isascii() and all(c.isalnum() or c=='-' for c in args.output_name)
    out = QA/args.output_name;out.mkdir(exist_ok=True)
    render(out, prepare(out,args.sample,args.review,args.reports))


if __name__ == '__main__':
    main()
