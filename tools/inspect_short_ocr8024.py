"""Audit rejected short OCR detections across all 124 original viewports.

Use one small temporary pixel buffer at a time. No reference text enters OCR.
The reader still returns every detector box, including negative controls.
"""
import json
import pathlib
import shutil
import subprocess
import tempfile
from PIL import Image
from audit_corpus_quality import ROOT, QA, atomic, digest, read, records


def main():
    folder=QA/'short-ocr8024';folder.mkdir(exist_ok=True)
    binary=ROOT/'build/local-model/Release/luma_ocr.exe'
    models=ROOT/'assets/models/opus-en-es'
    proof=dict(binary_sha256=digest(binary),source_sha256=digest(ROOT/'native/ocr_cli.cpp'),
        assets={name:digest(models/name) for name in ['english-ocr.onnx','english-ocr-fallback.onnx',
            'ocr-characters.json','ocr-characters-fallback.json','text-detector.onnx']},
        no_reference_or_inventory_inputs=True,original_viewports=124,all_detector_boxes_retained=True,
        application_modified=False,temporary_pixel_buffers_not_retained=True)
    pin=folder/'provenance.json'
    if pin.exists():assert read(pin)==proof
    else:atomic(pin,json.dumps(proof,indent=2))
    with tempfile.TemporaryDirectory(prefix='pixels-',dir=folder) as scratch,(folder/'native.log').open('ab') as log:
        child=subprocess.Popen([str(binary),str(models),str(models)],stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            for ident in range(1,125):
                saved=folder/f'{ident:03d}.json'
                if saved.exists():continue
                item=records(QA/f'recovery-viewports801201/{ident:03d}.input.jsonl')[0]
                original=pathlib.Path(item['path']);status=read(QA/f'recovery-viewports801201/{ident:03d}.done.json')
                assert digest(original)==status['viewport_png_sha256']
                assert shutil.disk_usage(folder).free>4*1024**3
                with Image.open(original) as image:
                    width,height=image.size;pixels=image.convert('RGBA').tobytes('raw','BGRA')
                raw=pathlib.Path(scratch)/'current.bgra';raw.write_bytes(pixels)
                request=dict(id=ident,path=str(raw),width=width,height=height,include_short_evidence=True)
                child.stdin.write((json.dumps(request)+'\n').encode());child.stdin.flush()
                line=child.stdout.readline();assert line,'OCR process exited without result'
                result=json.loads(line);assert 'error' not in result,result.get('error')
                result.pop('path');result['original_pixels_sha256']=digest(original)
                atomic(saved,json.dumps(result,ensure_ascii=False,indent=2))
                print(json.dumps(dict(completed=ident,requested=124)),flush=True)
            child.stdin.close();assert child.wait(timeout=30)==0
        finally:
            if child.poll() is None:child.terminate();child.wait(timeout=30)
    results=[read(folder/f'{ident:03d}.json') for ident in range(1,125)]
    short=[dict(id=r['id'],**line) for r in results for line in r['lines'] if 'first_text' in line]
    atomic(folder/'short-detections.json',json.dumps(short,ensure_ascii=False,indent=2))
    atomic(folder/'summary.json',json.dumps(dict(viewports=124,short_detections=len(short),
        native_box_count=sum(len(r['lines']) for r in results),provenance_sha256=digest(pin),
        short_detections_sha256=digest(folder/'short-detections.json'),
        accepted_policy=False,screen_attempt_failure_probability=None,target_achieved=False),indent=2))


if __name__=='__main__':main()
