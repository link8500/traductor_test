"""Reference-only Latin OCR; no scanlation transcription is assumed correct."""
import hashlib,json,pathlib
import onnxruntime as ort
import requests

ROOT=pathlib.Path(__file__).resolve().parents[1];directory=ROOT/'build/full-comics/reference-recognizer';directory.mkdir(parents=True,exist_ok=True)
URL='https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.10.0/onnx/PP-OCRv5/rec/latin_PP-OCRv5_rec_mobile.onnx'
SHA='b20bd37c168a570f583afbc8cd7925603890efbcdc000a59e22c269d160b5f5a'
target=directory/'english-ocr.onnx'
if not target.exists():
    response=requests.get(URL,timeout=(20,120));response.raise_for_status();assert hashlib.sha256(response.content).hexdigest()==SHA
    target.write_bytes(response.content)
assert hashlib.sha256(target.read_bytes()).hexdigest()==SHA
session=ort.InferenceSession(str(target),providers=['CPUExecutionProvider'])
characters=['blank']+session.get_modelmeta().custom_metadata_map['character'].splitlines()+[' ']
(directory/'ocr-characters.json').write_text(json.dumps(characters,ensure_ascii=False),encoding='utf-8')
(directory/'provenance.json').write_text(json.dumps({'url':URL,'sha256':SHA,'license':'Apache-2.0','packaged_in_app':False,'human_verified':False}),encoding='utf-8')
print('Reference-only Latin recognizer',target.stat().st_size,'bytes',session.get_inputs()[0].shape)
