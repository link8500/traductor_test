"""Check every completed 8014 translation against the exact saved OCR control.

This verifies execution and bounded changes, not all-word semantic accuracy.
Semantic diagnostic reuse requires the same location, source and output.
"""
import argparse
import collections
import datetime
import json
import time
from audit_corpus_quality import ROOT, QA, read, records, digest, atomic


def publish():
    folder=QA/'translated-en8014-fixed-ocr';proof=read(folder/'inference-provenance.json')
    previous=QA/'translated-en8011-context'
    diagnostic_path=ROOT/'benchmarks/full-comics/coverage8014-omission-diagnostic-semantic-review.json'
    diagnostic=read(diagnostic_path);known={(e['chapter'],e['region_index']):e for e in diagnostic['entries']}
    verified=[];changes=[];unmatched=[];fresh=reused=0
    for done in sorted(folder.glob('absolute-regression-*-en.done.json')):
        status=read(done);path=done.with_name(status['chapter']+'.jsonl');old=previous/path.name
        assert status['all_files_traversed'] and not status['runtime_errors']
        assert status['translation_signature']==proof['translation_signature']
        assert digest(path)==status['report_sha256']
        assert digest(QA/proof['capture_directory']/path.name)==status['source_ocr_sha256']
        before=records(old);after=records(path);assert len(before)==len(after)==status['regions']
        for i,(left,right) in enumerate(zip(before,after)):
            assert all(left[k]==right[k] for k in ['source','image','bounds']),('OCR drift',status['chapter'],i)
            if left['translation']==right['translation']:continue
            assert right.get('sentence_recovered') and right['whole_translation']==left['translation'],('Unexpected inference change',status['chapter'],i)
            key=(status['chapter'],i);prior=known.get(key)
            same=prior is not None and prior['source']==right['source'] and prior['before_translation']==left['translation'] and prior['translation']==right['translation']
            entry=dict(chapter=status['chapter'],region_index=i,source=right['source'],before_translation=left['translation'],translation=right['translation'],
                diagnostic_same_location_and_output_verified=same)
            if same:entry.update(before_judgment=prior['before'],after_judgment=prior['after'])
            else:unmatched.append(entry)
            changes.append(entry)
        fresh+=status['fresh_inference_records'];reused+=status['reused_identical_source_records']
        verified.append(dict(chapter=status['chapter'],regions=len(after),control_report_sha256=digest(old),new_report_sha256=digest(path),status_sha256=digest(done)))
    result=dict(generated_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),chapters_verified=len(verified),chapters_expected=124,
        all_requested_chapters_processed=len(verified)==124,regions_verified=sum(r['regions'] for r in verified),changed_regions=len(changes),
        unchanged_regions=sum(r['regions'] for r in verified)-len(changes),unexpected_inference_changes=0,
        changed_regions_with_same_location_diagnostic=sum(e['diagnostic_same_location_and_output_verified'] for e in changes),
        changed_regions_awaiting_semantic_review=len(unmatched),fresh_inference_records=fresh,reused_identical_8014_source_records=reused,
        all_chapter_words_visually_reviewed=False,semantic_accuracy=None,translator_weights_changed=False,
        inference_provenance_sha256=digest(folder/'inference-provenance.json'),diagnostic_review_sha256=digest(diagnostic_path),reports=verified,changes=changes)
    atomic(QA/'full-corpus-translation8014-validation.json',json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k not in ['reports','changes']}),flush=True)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--watch',action='store_true');args=parser.parse_args();state=None
    while True:
        next_state=tuple((p.name,p.stat().st_mtime_ns) for p in sorted((QA/'translated-en8014-fixed-ocr').glob('*.done.json')))
        if next_state!=state:result=publish();state=next_state
        if not args.watch or result['all_requested_chapters_processed']:break
        time.sleep(20)


if __name__=='__main__':main()
