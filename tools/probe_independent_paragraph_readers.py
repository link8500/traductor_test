"""Read both pixel-crop variants with each bundled OCR family independently."""
import json
import pathlib
import subprocess

from PIL import Image

from audit_corpus_quality import ROOT, QA, read, records, digest, atomic
from probe_reviewed_lettering import ordered

OUT = QA / 'paragraph-probe8011'


def main():
    proof = read(OUT/'input-provenance.json')
    inputs = records(OUT/'input.jsonl')
    requests = []
    for entry in inputs:
        image_path = pathlib.Path(entry['path'])
        pixel_path = image_path.with_suffix('.bgra')
        with Image.open(image_path) as bitmap:
            pixels = bitmap.convert('RGBA')
            pixel_path.write_bytes(pixels.tobytes('raw', 'BGRA'))
            requests.append(dict(path=str(pixel_path), width=pixels.width, height=pixels.height,
                                 chapter=entry['chapter'], image=entry['image']))
    binary = ROOT/'build/local-model/Release/luma_ocr.exe'
    for family in ['latin-v5', 'english-v4']:
        destination = OUT/(family+'.jsonl')
        directory = QA/'ocr-reader-probe8011'/family
        assert not (directory/'english-ocr-fallback.onnx').exists(), 'Reader must run independently'
        if destination.exists() and len(records(destination)) == len(requests):
            continue
        process = subprocess.Popen([str(binary), str(directory), str(ROOT/'assets/models/opus-en-es')],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            with destination.open('w', encoding='utf-8') as handle:
                for i, request in enumerate(requests, 1):
                    process.stdin.write(json.dumps(request)+'\n');process.stdin.flush()
                    line = process.stdout.readline()
                    assert line, 'Reader exited'
                    result = json.loads(line)
                    assert 'error' not in result, result.get('error')
                    result['ordered_text'] = ordered(result['lines'])
                    result['reader'] = family
                    handle.write(json.dumps(result, ensure_ascii=False)+'\n');handle.flush()
                    if i % 40 == 0:
                        print(family, i, '/', len(requests), flush=True)
        finally:
            process.stdin.close();process.wait(timeout=30)
        assert process.returncode == 0
    atomic(OUT/'independent-readers-provenance.json', json.dumps(dict(
        binary_sha256=digest(binary), input_provenance_sha256=digest(OUT/'input-provenance.json'),
        readers={family:dict(model_sha256=digest(QA/'ocr-reader-probe8011'/family/'english-ocr.onnx'),
            dictionary_sha256=digest(QA/'ocr-reader-probe8011'/family/'ocr-characters.json'),
            result_sha256=digest(OUT/(family+'.jsonl'))) for family in ['latin-v5', 'english-v4']},
        expected_answers_passed_to_ocr=False, app_models_changed=False), indent=2))
    print('Independent crop reads complete:', len(requests)*2, flush=True)


if __name__ == '__main__':
    main()
