"""Verify replay provenance for the new gallery, without semantic approval."""
import argparse
import datetime
import json
import pathlib
import urllib.request
from PIL import Image
from audit_corpus_quality import QA, read, records, digest, atomic
from export_coverage_photos import paint_inputs


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--require-complete',action='store_true');args=parser.parse_args()
    folder=QA/'chapter-photos8014-fixed-ocr';expected={}
    for page in read(QA/'images-en.json'):
        if page['series']=='absolute-regression':expected.setdefault(page['chapter'].removesuffix('-en'),{})[page['image']]=page
    binary_sha=digest(QA/'frozen-windows8009/traductor.exe');checked={};chapters=images=linked=fresh=0
    def checked_digest(path):
        stat=path.stat();key=(stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns)
        if key not in checked:checked[key]=digest(path)
        return checked[key]
    for proof in sorted(folder.glob('absolute-regression-*/provenance.json')):
        value=read(proof);chapter=value['chapter'];target=proof.parent
        assert value['report_directory']=='translated-en8014-fixed-ocr' and value['renderer_binary_sha256']==binary_sha
        report=QA/value['report_directory']/(chapter+'-en.jsonl');assert digest(report)==value['report_sha256']
        assert set(expected[chapter])=={p['image'] for p in value['pages']} and value['images']==len(expected[chapter])
        actual=records(report);old=read(QA/'chapter-photos'/chapter/'provenance.json')
        old_rows=records(QA/old['report_directory']/(chapter+'-en.jsonl'))
        assert old['renderer_binary_sha256']==binary_sha
        reused_here=fresh_here=0
        for page in value['pages']:
            original=expected[chapter][page['image']];photo=target/page['file']
            assert checked_digest(pathlib.Path(original['path']))==original['sha256']==page['original_sha256']
            assert checked_digest(photo)==page['output_sha256']
            with Image.open(photo) as image:
                assert image.size==(original['width'],original['height']);image.verify()
            current_inputs=paint_inputs([r for r in actual if r['image']==page['image']])
            previous_inputs=paint_inputs([r for r in old_rows if r['image']==page['image']])
            if page['reused_identical_painter_inputs']:
                assert current_inputs==previous_inputs
                prior=pathlib.Path(page['reused_output_path']);assert checked_digest(prior)==page['output_sha256']
                assert digest(QA/'chapter-photos'/chapter/'provenance.json')==page['reused_provenance_sha256']
                reused_here+=1
            else:assert current_inputs!=previous_inputs;fresh_here+=1
        assert reused_here==value['reused_identical_painter_input_images'] and fresh_here==value['fresh_replay_images']
        linked+=reused_here;fresh+=fresh_here;images+=value['images'];chapters+=1
    if args.require_complete:assert chapters==len(expected)==124 and images==sum(len(v) for v in expected.values())
    response=urllib.request.urlopen('http://127.0.0.1:8765/full-comics/chapter-photos8014-fixed-ocr/index.html',timeout=20)
    assert response.status==200 and 'No son capturas del teléfono' in response.read().decode('utf-8')
    result=dict(verified_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),chapters_verified=chapters,chapters_expected=124,
        all_source_images_present=chapters==124,images_verified=images,reused_identical_painter_inputs=linked,fresh_native_replay_images=fresh,
        all_chapter_words_visually_reviewed=False,semantic_accuracy=None,reference_answers_substituted=False,
        renderer_binary_sha256=binary_sha,index_sha256=digest(folder/'index.html'),gallery_http_status=200)
    atomic(QA/'photos8014-verification.json',json.dumps(result,indent=2));print(json.dumps(result))


if __name__=='__main__':main()
