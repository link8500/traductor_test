"""Freeze review evidence for conservative complete-sentence retry candidates."""
import collections
import json
import pathlib
import re
import prepare_corpus_review_sample as sheets
from audit_corpus_quality import ROOT, QA, CURRENT, read, records, digest, atomic


def eligible(case):
    parts=case['parts']
    # Do not invent a continuation for a captured fragment or hanging clause.
    return all(re.search(r'[.!?]["\']?$',p) and not re.search(r'\.{2,}$',p) for p in parts)


def main():
    out=QA/'omission-review8011';out.mkdir(exist_ok=True)
    target=out/'sample.json'
    if target.exists():
        sample=read(target)
    else:
        pages={lang:{(r['chapter'].removesuffix('-'+lang),r['image']):r for r in read(QA/f'images-{lang}.json')} for lang in ['en','es']}
        cases=[];unavailable=0;excluded=0
        for path in sorted((QA/'sentence-coverage-probe8011').glob('absolute-regression-*-en.json')):
            report=read(path);chapter=report['chapter'].removesuffix('-en')
            comparison=QA/'comparison8011-context'/(chapter+'.json')
            if not comparison.exists() or read(comparison)['english_report_directory']!=CURRENT:
                unavailable+=len(report['cases']);continue
            assert digest(QA/CURRENT/(chapter+'-en.jsonl'))==report['source_report_sha256']
            proposals=collections.defaultdict(set)
            for row in records(comparison.with_name(chapter+'.words.jsonl')):
                if row['luma_region'] is not None:proposals[row['luma_region']].add(row['reference_region'])
            refs=records(QA/'ocr-es'/(chapter+'-es.jsonl'))
            for case in report['cases']:
                if not eligible(case):excluded+=1;continue
                indices=proposals[case['region_index']]
                if not indices:unavailable+=1;continue
                reference=max((refs[i] for i in indices),key=lambda r:len(r['source']))
                cases.append(dict(id=len(cases)+1,chapter=chapter,probe_report_sha256=digest(path),
                    current_report_sha256=report['source_report_sha256'],region_index=case['region_index'],source=case['source'],
                    translation=case['candidate_translation'],before_translation=case['control_translation'],bounds=case['bounds'],source_image=case['image'],
                    source_page=pages['en'][(chapter,case['image'])],reference_page=pages['es'][(chapter,reference['image'])],
                    reference_bounds=reference['bounds'],reference_source=reference['source'],parts=case['parts'],
                    source_pixels_inspected=False,reference_pixels_inspected=False,meaning_result=None))
        sample=dict(cases=cases,chapters=len({c['chapter'] for c in cases}),regions=len(cases),
            automatic_candidate_selection=True,unbiased_population_sample=False,full_chapter_review=False,
            reference_text_used_by_application=False,excluded_incomplete_source_candidates=excluded,
            candidates_without_reference_evidence=unavailable)
        atomic(target,json.dumps(sample,ensure_ascii=False,indent=2))
    sheets.OUT=out;sheets.render(sample)
    print(json.dumps({k:v for k,v in sample.items() if k!='cases'}))


if __name__=='__main__':main()
