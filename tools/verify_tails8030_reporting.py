"""Check every current reference token survives compact comparison and serving."""
import json
import pathlib
import urllib.request
from audit_corpus_quality import QA,atomic,digest,read,records
from compare_full_comics import words


def main():
    comparison=QA/'comparison8030-tails';summary=read(comparison/'summary.json');checked=0
    for c in summary['chapters']:
        name=c['chapter'];actual=read(comparison/(name+'.json'));assert actual==c
        assert actual['ledger_format']=='region-indices-v1' and actual['display_build']=='803001'
        assert actual['native_core_build']=='802601'
        assert actual['english_execution_kind']=='cached_pixel_reads_with_native_mt_on_tail_candidates'
        english=QA/actual['english_report_directory']/(name+'-en.jsonl');reference=QA/'ocr-es'/(name+'-es.jsonl')
        assert digest(english)==actual['english_report_sha256'] and digest(reference)==actual['reference_report_sha256']
        expected=[(i,j,w) for i,r in enumerate(records(reference)) for j,w in enumerate(words(r['source']))]
        ledger=records(comparison/(name+'.words.jsonl'))
        assert [(r['reference_region'],r['word_index'],r['reference_word']) for r in ledger]==expected
        n=len(records(english))
        assert all((r['luma_region'] is None or 0<=r['luma_region']<n) and not r['word_reviewed'] and not r['meaning_approved'] for r in ledger)
        assert len(ledger)==actual['reference_ocr_tokens'];checked+=len(ledger)
    assert checked==summary['reference_ocr_tokens'] and len(summary['chapters'])==summary['pairs_compared']
    assert not summary['all_words_visually_reviewed'] and summary['semantic_accuracy'] is None
    urls={'metrics':'metrics','replay':'windows8030-tail-translation-replay','reference_review':'review8030-tails'};served={}
    for kind,folder in urls.items():
        url=f'http://127.0.0.1:8765/full-comics/{folder}/index.html'
        with urllib.request.urlopen(url,timeout=10) as response:
            assert response.status==200;body=response.read().decode('utf-8')
        served[kind]=dict(url=url,status=200,bytes=len(body.encode('utf-8')))
        if kind=='metrics':
            assert 'Windows actual · recuperación de frases finales' in body and '56 → 56 vistas sin aprobar' in body
            assert 'no se acredita menos del 5 %' in body
        if kind=='replay':assert '803001' in body and 'cuatro son mejoras parciales' in body
    proof=dict(chapter_pairs_checked=len(summary['chapters']),reference_tokens_preserved_in_order=checked,
               missing_or_changed_reference_tokens=0,raw_report_hashes_verified=True,region_indices_valid=True,
               derived_execution_scope_explicit=True,local_pages=served,all_chapter_words_visually_reviewed=False,
               semantic_accuracy=None,screen_attempt_failure_probability=None,target_achieved=False,
               comparison_summary_sha256=digest(comparison/'summary.json'),verification_script_sha256=digest(pathlib.Path(__file__)))
    atomic(QA/'windows8030-tail-translation-replay/reporting-proof.json',json.dumps(proof,indent=2));print(json.dumps(proof),flush=True)


if __name__=='__main__':main()
