"""Verify the latest Windows trial without upgrading partial review to success."""
import json
import pathlib
import urllib.request
from PIL import Image
from audit_corpus_quality import ROOT,QA,read,records,digest,atomic,latest_windows_diagnostics
from evaluate_ocr_reader_comparison import compare


def main():
    value=latest_windows_diagnostics();release=value['windows_release']
    assert release['version']=='1.0.0+8016' and release['archive_offline_assets_verified']
    assert digest(pathlib.Path(release['archive']))==release['archive_sha256']
    assert digest(QA/'frozen-windows801601/traductor.exe')==release['binary_sha256']
    assert digest(ROOT/'native/translation_coverage.h')==release['translation_policy_sha256']
    assert not release['target_achieved'] and release['screen_attempt_failure_probability'] is None
    assert not release['experimental_ocr_consensus_bundled'] and not release['ocr_weights_changed'] and not release['translation_weights_changed']
    assert not release['android_application_built']
    proof=read(QA/'production-coverage8016/provenance.json');actual=records(QA/'production-coverage8016/output.jsonl')
    assert digest(QA/'production-coverage8016/provenance.json')==read(QA/'production-coverage8016/summary.json')['provenance_sha256']
    assert proof['policy_sha256']==release['translation_policy_sha256']
    expected={r['source']:r for r in records(QA/'sentence-coverage8016/output.jsonl')}
    expected.update({r['source']:r for r in records(QA/'full-omission-candidate8016/inferences.jsonl')})
    assert len(actual)==len(expected)==len({r['source'] for r in actual})==850
    for row in actual:
        assert all(row.get(k)==expected[row['source']].get(k) for k in ['translation','prepared','raw_model','sentence_recovered','sentence_sources','sentence_translations','retained_original'])
    assert digest(QA/'production-coverage8016/summary.json')==release['production_parity_sha256']
    for name,folder in [('omission_candidate','sentence-coverage8016/visual-review'),('full_omission','full-omission-candidate8016/visual-review')]:
        report=value[name];assert digest(QA/folder/'manual-decisions.json')==report['manual_sha256']
        sample=read(QA/folder/'sample.json')
        for case in sample['cases']:
            for key in ['source_page','reference_page']:
                page=case[key]
                if page:assert digest(pathlib.Path(page['path']))==page['sha256']
    readers=read(ROOT/'benchmarks/full-comics/ocr8016-reader-comparison.json');manual_path=ROOT/'benchmarks/full-comics/ocr8016-manual-transcriptions.json'
    assert digest(manual_path)==readers['manual_transcriptions_sha256']
    sample=read(QA/'ocr-reader-comparison8016/sample.json');truth={r['id']:r['visible_english'] for r in read(manual_path)['entries']}
    assert len(sample['cases'])==len(truth)==124
    for case in sample['cases']:
        assert digest(pathlib.Path(case['source_page']['path']))==case['source_page']['sha256']
        assert digest(pathlib.Path(case['preview']))==case['preview_sha256']
    for name,sha in readers['native_outputs_sha256'].items():assert digest(QA/'ocr-reader-comparison8016'/(name+'.jsonl'))==sha
    consensus=read(ROOT/'benchmarks/full-comics/ocr8016-consensus-conservative-candidate.json')
    selected={r['id']:r for r in records(QA/'ocr-reader-comparison8016/consensus-conservative/output.jsonl')}
    assert digest(ROOT/'native/ocr_consensus_candidate.h')==consensus['policy_sha256']
    assert all(e['before']==compare(truth[e['id']],e['source']) and e['after']==compare(truth[e['id']],selected[e['id']]['selected']) for e in consensus['entries'])
    assert consensus['word_omissions_after']==10 and consensus['crops_regressed']==0
    heldout=value['ocr_consensus_heldout'];folder=QA/'ocr-reader-heldout8016/consensus';sample=read(folder/'sample.json')
    assert digest(folder/'manual-transcriptions.json')==heldout['manual_sha256']
    assert sample['policy_sha256']==consensus['policy_sha256']==heldout['policy_sha256']
    assert heldout['changed_locations_visually_reviewed']==12 and heldout['unchanged_locations_without_meaning_approval']==112
    assert heldout['changed_crops_fixed']==10 and heldout['changed_crops_regressed']==0 and heldout['changed_crops_still_have_word_errors']==2
    for case in sample['cases']:assert digest(pathlib.Path(case['preview']))==case['preview_sha256']
    sheets=[]
    for name,expected_count in [('sentence-coverage8016/visual-review',2),('full-omission-candidate8016/visual-review',16),('combined-recovery8016-checkpoint01',3),('ocr-reader-comparison8016',31),('ocr-reader-heldout8016/consensus',4)]:
        paths=sorted((QA/name).glob('sheet-*.jpg'));assert len(paths)==expected_count
        for path in paths:
            with Image.open(path) as bitmap:bitmap.verify()
            sheets.append(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest(path)))
    assert read(QA/'windows8016-real-pixels/manual-review.json')['viewports_visually_inspected']==4
    response=urllib.request.urlopen('http://127.0.0.1:8765/full-comics/metrics/index.html',timeout=20);page=response.read().decode('utf-8')
    assert response.status==200 and 'menos del 5 % de intentos fallidos' in page and 'todavía no está medida' in page
    assert '36 → 10' in page and '199 errores claros y el candidato 196' in page and '850 inferencias' in page
    assert 'Luma-Windows-1.0.0+8016.zip' in page and 'absolute-regression-' not in page
    for path in ['windows8016-real-pixels/index.html','full-omission-candidate8016/visual-review/index.html','ocr-reader-heldout8016/consensus/index.html']:
        assert urllib.request.urlopen('http://127.0.0.1:8765/full-comics/'+path,timeout=20).status==200
    result=dict(verified=True,windows_version='1.0.0+8016',fresh_production_inferences=850,production_differences=0,
        full_candidate_changed_regions=37,full_candidate_corrected_regions=26,full_candidate_regressed_regions=0,
        ocr_pixel_crops_fully_transcribed=124,ocr_words_transcribed=1562,heldout_changed_crops_inspected=12,evidence_sheets=sheets,
        screen_attempt_failure_probability=None,target_achieved=False,all_chapter_words_visually_reviewed=False,android_build_deferred=True,
        release_sha256=digest(QA/'release8016.json'),verification_source_sha256=digest(pathlib.Path(__file__)))
    atomic(QA/'metrics/verification8016.json',json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='evidence_sheets'}),flush=True)


if __name__=='__main__':main()
