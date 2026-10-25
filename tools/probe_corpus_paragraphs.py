"""Re-read frozen corpus regions with the unchanged production Windows engine.

Only original pixels are passed to OCR. This is an experimental comparison,
not a modification to the shipped application or a semantic approval.
"""
import collections
import json
import pathlib
import subprocess

from PIL import Image

from audit_corpus_quality import ROOT, QA, read, records, digest, atomic

OUT = QA / 'paragraph-probe8011'
BINARY = QA / 'frozen-windows801101/traductor.exe'


def prepare():
    OUT.mkdir(exist_ok=True)
    source_path = QA / 'corpus-review-sample/sample.json'
    sample = read(source_path)
    manifest, cases = [], []
    for case in sample['cases']:
        page = case['source_page']
        assert digest(pathlib.Path(page['path'])) == page['sha256']
        with Image.open(page['path']) as image:
            for variant, dx, dy in [('near', 30, 24), ('context', 80, 80)]:
                bounds = case['bounds']
                crop_bounds = [max(0, bounds[0]-dx), max(0, bounds[1]-dy),
                               min(image.width, bounds[2]+dx), min(image.height, bounds[3]+dy)]
                path = OUT / f'{case["id"]:03d}-{variant}.png'
                image.crop(crop_bounds).convert('RGB').save(path, compress_level=1)
                name = f'case-{case["id"]:03d}-{variant}'
                manifest.append(dict(chapter=name, image=case['id'], path=str(path.resolve()),
                                     ocr_only=True, augment_detection=True, all_candidates=True))
                cases.append(dict(id=case['id'], variant=variant, chapter=name, crop_bounds=crop_bounds,
                    original_sha256=page['sha256'], crop_sha256=digest(path),
                    frozen_source=case['source'], frozen_translation=case['translation']))
    atomic(OUT / 'input.jsonl', ''.join(json.dumps(row)+'\n' for row in manifest))
    snapshot = read(QA / 'windows-engine801101.json')
    assert digest(BINARY) == snapshot['binary_sha256']
    proof = dict(sample_sha256=digest(source_path), binary_sha256=digest(BINARY),
                 expected_transcriptions_passed_to_ocr=False, application_modified=False, cases=cases)
    atomic(OUT / 'input-provenance.json', json.dumps(proof, ensure_ascii=False, indent=2))
    return proof


def run():
    proof = prepare()
    report = OUT / 'production-ocr.jsonl'
    status = pathlib.Path(str(report)+'.summary.json')
    if not status.exists() or read(status).get('images') != len(proof['cases']):
        result = subprocess.run([str(BINARY.resolve()), '--comic-benchmark',
            str((OUT/'input.jsonl').resolve()), str(report.resolve())],
            creationflags=subprocess.CREATE_NO_WINDOW)
        assert result.returncode == 0, 'Paragraph OCR failed; inspect .error.txt'
    assert read(status)['images'] == len(proof['cases'])
    grouped = collections.defaultdict(list)
    for row in records(report):
        grouped[row['chapter']].append(row)
    cases = []
    for case in proof['cases']:
        rows = grouped[case['chapter']]
        cases.append(dict(**case, regions=rows,
            source=' '.join(row['source'] for row in rows),
            native_source=' '.join(row['native_source'] for row in rows)))
    atomic(OUT / 'results.json', json.dumps(dict(**{k:v for k,v in proof.items() if k!='cases'},
        regions_requested=len(proof['cases']), regions_with_output=sum(bool(c['regions']) for c in cases),
        semantic_review_complete=False, cases=cases), ensure_ascii=False, indent=2))
    print(json.dumps(dict(original_regions=len(cases)//2, crop_variants=len(cases),
        crops_with_output=sum(bool(c['regions']) for c in cases), runtime_errors=read(status)['runtime_errors'])))


if __name__ == '__main__':
    run()
