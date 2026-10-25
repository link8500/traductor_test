"""Publish inspected omission proposals without treating every alert as a miss."""
import collections
import json
from pathlib import Path
from audit_corpus_quality import ROOT, QA, CURRENT, read, digest, atomic


def main():
    folder=QA/'undetected-review8011'
    sample_path=folder/'sample.json';manual_path=folder/'manual-decisions.json'
    sample=read(sample_path);decisions=read(manual_path)
    cases={c['id']:c for c in sample['cases']}
    assert len(decisions)==len({d[0] for d in decisions})==len(cases)==47
    entries=[];verified=set()
    for case_id,result,note in decisions:
        assert result!='pending_context'
        case=cases[case_id]
        for path,sha in [(QA/CURRENT/(case['chapter']+'-en.jsonl'),case['current_report_sha256']),
                         (QA/'ocr-es'/(case['chapter']+'-es.jsonl'),case['reference_report_sha256']),
                         (QA/'comparison8011-context'/(case['chapter']+'.json'),case['comparison_sha256']),
                         (QA/'comparison8011-context'/(case['chapter']+'.words.jsonl'),case['ledger_sha256'])]:
            if path not in verified:
                assert digest(path)==sha
                verified.add(path)
        for key in ['source_page','reference_page']:
            assert digest(Path(case[key]['path']))==case[key]['sha256']
        detail=folder/f'detail-{case_id:03d}.jpg'
        entries.append(dict(id=case_id,result=result,note_es=note,source_pixels_inspected=True,
            reference_pixels_inspected=True,expanded_context_inspected=case_id in [12,13,21,27,39],
            expanded_context_sha256=digest(detail) if case_id in [12,13,21,27,39] else None,
            chapter_words_approved=False))
    counts=dict(collections.Counter(e['result'] for e in entries))
    value=dict(schema=1,reviewer='assistant',sample_path=str(sample_path.relative_to(ROOT)).replace('\\','/'),
        sample_sha256=digest(sample_path),manual_decisions_sha256=digest(manual_path),engine=CURRENT,
        chapters_checked_for_proposals=sample['chapters_checked'],candidate_chapters_reviewed=len(cases),reviewed_regions=len(entries),
        result_counts=counts,complete_or_partial_english_detection_failures=counts.get('missing_text',0)+counts.get('partial_detection',0),
        other_english_translation_defects=sum(counts.get(k,0) for k in ['translation_omission','fragmented_translation','reference_duplicate_translation_defect']),
        unsupported_source_script_regions=counts.get('unsupported_source_script',0),
        spurious_nontext_detection_regions=counts.get('reference_ocr_artifact',0),
        global_omission_rate=None,all_chapter_words_visually_reviewed=False,app_uses_review_answers=False,
        limitation='Diagnostic sample of automatically mapped missing-region proposals. Counts are separate from the distributed semantic sample and must not be added without deduplication.',entries=entries)
    atomic(ROOT/'benchmarks/full-comics/undetected-semantic-review8011.json',json.dumps(value,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in value.items() if k!='entries'}))


if __name__=='__main__':main()
