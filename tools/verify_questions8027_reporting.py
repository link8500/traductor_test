"""Validate actual compact reference ledgers and locally served scope labels.

This checks preservation and provenance, not the meaning of the reference OCR.
It does not run a translator or mark any word as human-reviewed.
"""
import hashlib
import argparse
import json
import pathlib
import urllib.request

from audit_corpus_quality import QA, atomic, digest, read, records
from compare_full_comics import words


def main():
    parser=argparse.ArgumentParser(description=__doc__);variants=parser.add_mutually_exclusive_group();variants.add_argument('--opening',action='store_true');variants.add_argument('--refinement',action='store_true');args=parser.parse_args()
    comparison = QA / ('comparison8029-refinement' if args.refinement else 'comparison8028-opening' if args.opening else 'comparison8027-question')
    summary_bytes = (comparison / 'summary.json').read_bytes()
    summary = json.loads(summary_bytes)
    checked = 0
    for chapter in summary['chapters']:
        name = chapter['chapter']
        actual = read(comparison / (name + '.json'))
        assert actual == chapter
        assert actual['ledger_format'] == 'region-indices-v1'
        assert actual['display_build'] == ('802901' if args.refinement else '802801' if args.opening else '802701')
        assert actual['native_core_build'] == '802601'
        assert actual['english_execution_kind'] == ('cached_independent_pixel_reads_with_new_word_selection_and_native_candidate_mt' if args.refinement else 'frozen_native_core_plus_question_rule_and_native_opening_replay' if args.opening else 'frozen_native_core_plus_validated_final_question_rule')
        english_path = QA / actual['english_report_directory'] / (name + '-en.jsonl')
        reference_path = QA / 'ocr-es' / (name + '-es.jsonl')
        assert digest(english_path) == actual['english_report_sha256']
        assert digest(reference_path) == actual['reference_report_sha256']
        english, reference = records(english_path), records(reference_path)
        expected = [(region, index, word) for region, row in enumerate(reference)
                    for index, word in enumerate(words(row['source']))]
        ledger = records(comparison / (name + '.words.jsonl'))
        observed = [(row['reference_region'], row['word_index'], row['reference_word']) for row in ledger]
        assert observed == expected, 'A reference word was lost, changed, repeated or reordered'
        assert len(ledger) == actual['reference_ocr_tokens']
        for row in ledger:
            assert row['luma_region'] is None or 0 <= row['luma_region'] < len(english)
            assert row['word_reviewed'] is False and row['meaning_approved'] is False
        checked += len(ledger)
    assert checked == summary['reference_ocr_tokens']
    assert len(summary['chapters']) == summary['pairs_compared']
    assert summary['all_words_visually_reviewed'] is False
    assert summary['semantic_accuracy'] is None
    urls = {
        'metrics': 'http://127.0.0.1:8765/full-comics/metrics/index.html',
        'replay': 'http://127.0.0.1:8765/full-comics/'+('windows8029-refinement-full-viewports' if args.refinement else 'windows8028-opening-translation-replay' if args.opening else 'windows8027-question-translation-replay')+'/index.html',
        'reference_review': 'http://127.0.0.1:8765/full-comics/'+('review8029-refinement' if args.refinement else 'review8028-opening' if args.opening else 'review8027-question')+'/index.html',
    }
    served = {}
    for kind, url in urls.items():
        with urllib.request.urlopen(url, timeout=10) as response:
            assert response.status == 200
            body = response.read().decode('utf-8')
        served[kind] = dict(url=url, status=200, bytes=len(body.encode('utf-8')))
        if kind == 'metrics':
            assert ('Windows actual · reconocimiento y preguntas breves' if args.refinement else 'recuperación de aperturas omitidas' if args.opening else 'conservación de preguntas') in body
            assert ('56 → 56 sin aprobar' if args.refinement else '56 → 56 vistas sin aprobar' if args.opening else '57 → 56 traducciones sin aprobar') in body
            assert 'Recorrido nativo de base' in body
            assert 'no se acredita menos del 5 %' in body
        if kind == 'replay':
            assert ('8029' in body and '123' in body) if args.refinement else ('8028' in body and '17' in body) if args.opening else ('8027' in body and '123' in body)
    proof = dict(chapter_pairs_checked=len(summary['chapters']),
                 reference_tokens_preserved_in_order=checked, missing_or_changed_reference_tokens=0,
                 raw_report_hashes_verified=True, region_indices_valid=True,
                 derived_execution_scope_explicit=True, local_pages=served,
                 all_chapter_words_visually_reviewed=False, semantic_accuracy=None,
                 screen_attempt_failure_probability=None, target_achieved=False,
                 comparison_summary_sha256=hashlib.sha256(summary_bytes).hexdigest(),
                 verification_script_sha256=digest(pathlib.Path(__file__)))
    atomic(QA / ('windows8029-refinement-full-viewports' if args.refinement else 'windows8028-opening-translation-replay' if args.opening else 'windows8027-question-translation-replay') / 'reporting-proof.json', json.dumps(proof, indent=2))
    print(json.dumps(proof), flush=True)


if __name__ == '__main__':
    main()
