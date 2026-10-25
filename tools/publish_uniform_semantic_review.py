"""Pin refreshed visual judgments to one completed, uniform OCR/NMT cohort.

Old judgments are reusable only for identical output at one matching region.
Every changed output requires a separate saved visual decision. References are
evaluation inputs only. This does not approve all words in any chapter.
"""
import collections
import json

from audit_corpus_quality import ROOT, QA, CURRENT, read, records, digest, atomic, CLEAR_ERRORS, reduction
from evaluate_paragraph_probe import matching


def publish():
    entries, inputs, validated, chapters = [], [], set(), set()
    engines, signatures = set(), set()

    def verify(path, expected):
        key = (str(path), expected)
        if key not in validated:
            assert digest(path) == expected, f'Changed evidence: {path}'
            validated.add(key)

    for group, original_folder, original_review in [
        ('a', 'corpus-review-sample', 'corpus-semantic-review.json'),
        ('b', 'corpus-review-sample-b', 'corpus-semantic-review-b.json'),
    ]:
        folder = QA / f'current8011-full-{group}'
        sample_path, manual_path = folder/'sample.json', folder/'manual-decisions.json'
        source_path = QA/original_folder/'sample.json'
        review_path = ROOT/'benchmarks/full-comics'/original_review
        sample, review, original = read(sample_path), read(review_path), read(source_path)
        verify(source_path, sample['original_sample_sha256'])
        verify(review_path, sample['original_review_sha256'])
        assert review['sample_sha256'] == sample['original_sample_sha256']
        assert sample['current_engine'] == CURRENT and not sample['unavailable_ids']
        old = {e['id']: e for e in review['entries']}
        original_cases = {c['id']: c for c in original['cases']}
        manual_rows = read(manual_path)
        manual = {row[0]: row for row in manual_rows}
        assert len(manual) == len(manual_rows)
        assert set(manual) == {c['id'] for c in sample['cases'] if c['needs_visual_review']}
        inputs.append(dict(group=group, sample_path=str(sample_path.relative_to(ROOT)).replace('\\','/'),
            sample_sha256=digest(sample_path), manual_decisions_path=str(manual_path.relative_to(ROOT)).replace('\\','/'),
            manual_decisions_sha256=digest(manual_path), original_review_path=str(review_path.relative_to(ROOT)).replace('\\','/'),
            original_review_sha256=digest(review_path)))
        for case in sample['cases']:
            before = old[case['id']]
            assert before['source_pixels_inspected'] and before['reference_pixels_inspected']
            assert case['before_translation'] == original_cases[case['id']]['before_translation']
            report = QA/CURRENT/(case['chapter']+'-en.jsonl')
            verify(report, case['full_engine_report_sha256'])
            verify(QA/case['baseline_folder']/(case['chapter']+'-en.jsonl'), case['baseline_report_sha256'])
            for key in ['source_page', 'reference_page']:
                page = case[key]
                from pathlib import Path
                verify(Path(page['path']), page['sha256'])
            rows = sorted(matching(case, records(report)), key=lambda r:(r['bounds'][1],r['bounds'][0]))
            assert rows == case['refreshed_regions']
            translation = ' '.join(r.get('translation','') for r in rows)
            assert translation == case['refreshed_translation']
            done = read(report.with_name(case['chapter']+'-en.done.json'))
            assert done['all_files_traversed'] and done['runtime_errors'] == 0
            engines.add(done['native_engine']); signatures.add(done['translation_signature'])
            reused = case['assessment_reused_for_identical_output_and_unambiguous_geometry']
            if reused:
                assert len(rows) == 1 and translation == case['translation']
                after, note = before['after'], before['note_es']
            else:
                _, after, note = manual[case['id']]
            assert after in {'acceptable','needs_improvement','incorrect','incomplete','fragmented','unresolved'}
            entries.append(dict(id=f'{group}-{case["id"]}', group=group, original_id=case['id'],
                chapter=case['chapter'], source_image=case['source_image'], bounds=case['bounds'],
                before=before['before'], after=after, note_es=note,
                source=case['refreshed_source'], translation=translation,
                baseline_report_sha256=case['baseline_report_sha256'], current_report_sha256=case['full_engine_report_sha256'],
                source_pixels_inspected=True, reference_pixels_inspected=True,
                assessment_reused_for_identical_output_and_unambiguous_geometry=reused,
                whole_balloon_completeness_approved=False))
            chapters.add(case['chapter'])
    assert len(chapters) == 124 and len(engines) == 1 and len(signatures) == 1
    assert len(entries) == 372 and len({(e['chapter'], e['source_image'], tuple(e['bounds'])) for e in entries}) == 372
    comparable = [e for e in entries if 'unresolved' not in [e['before'],e['after']]]
    before = collections.Counter(e['before'] for e in comparable)
    after = collections.Counter(e['after'] for e in comparable)
    old_errors = sum(before[c] for c in CLEAR_ERRORS)
    new_errors = sum(after[c] for c in CLEAR_ERRORS)
    value = dict(schema=1,reviewer='assistant',current_engine=CURRENT,native_engine=next(iter(engines)),
        translation_signature=next(iter(signatures)),inputs=inputs,chapters_sampled=len(chapters),
        reviewed_regions=len(entries),comparable_regions=len(comparable),excluded_unresolved_regions=len(entries)-len(comparable),
        before_errors=old_errors,after_errors=new_errors,relative_error_reduction_percent=reduction(old_errors,new_errors),
        corrected_regions=sum(e['before'] in CLEAR_ERRORS and e['after'] not in CLEAR_ERRORS for e in comparable),
        regressed_regions=sum(e['before'] not in CLEAR_ERRORS and e['after'] in CLEAR_ERRORS for e in comparable),
        reused_identical_output_judgments=sum(e['assessment_reused_for_identical_output_and_unambiguous_geometry'] for e in entries),
        changed_outputs_visually_reinspected=sum(not e['assessment_reused_for_identical_output_and_unambiguous_geometry'] for e in entries),
        before_categories=dict(before),after_categories=dict(after),single_build_comparison=True,
        clear_error_unit='One region with a clear meaning, lexical or completeness defect; minor style issues separate.',
        all_chapter_words_visually_reviewed=False,population_accuracy_estimate=False,app_uses_review_answers=False,
        limitation='Three previously selected aligned regions per chapter. Undetected text and whole-chapter completeness are not measured.',
        entries=entries)
    path=ROOT/'benchmarks/full-comics/current8011-full-semantic-review.json'
    atomic(path,json.dumps(value,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in value.items() if k not in ['entries','inputs']},ensure_ascii=True))
    return value


if __name__ == '__main__':
    publish()
