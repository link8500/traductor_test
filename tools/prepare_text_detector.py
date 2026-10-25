"""Download a pinned Apache-2.0 DB text detector for local evaluation."""
import argparse,hashlib,json,pathlib
import requests

ROOT=pathlib.Path(__file__).resolve().parents[1]
URL='https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.10.0/onnx/PP-OCRv4/det/ch_PP-OCRv4_det_mobile.onnx'
SHA='d2a7720d45a54257208b1e13e36a8479894cb74155a5efe29462512d42f49da9'
def prepare(directory):
    directory.mkdir(parents=True,exist_ok=True);target=directory/'text-detector.onnx'
    if not target.exists():
        response=requests.get(URL,timeout=(20,120));response.raise_for_status()
        if hashlib.sha256(response.content).hexdigest()!=SHA:raise RuntimeError('Detector checksum mismatch')
        target.write_bytes(response.content)
    assert hashlib.sha256(target.read_bytes()).hexdigest()==SHA
    return {'upstream':'PaddlePaddle/PaddleOCR','conversion':'RapidAI/RapidOCR','revision':'v3.10.0','license':'Apache-2.0','url':URL,
        'purpose':'Find additional text lines independently of the operating-system OCR; input retains RGB colour.'}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--package',action='store_true');args=parser.parse_args()
    directory=ROOT/('assets/models/opus-en-es' if args.package else 'build/full-comics/candidate')
    metadata=prepare(directory);target=directory/'text-detector.onnx'
    if args.package:
        manifest=directory/'manifest.json';data=json.loads(manifest.read_text(encoding='utf-8'))
        data['files']['text-detector.onnx']=SHA
        data['text_detector']=metadata
        manifest.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(target,target.stat().st_size,'bytes, checksum verified')
