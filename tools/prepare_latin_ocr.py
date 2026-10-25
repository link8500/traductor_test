"""Pin the pretrained PP-OCRv5 Latin reader used for English comic lettering."""
import hashlib,json,pathlib,shutil
import onnxruntime as ort
import requests
import numpy as np

ROOT=pathlib.Path(__file__).resolve().parents[1]
URL='https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.10.0/onnx/PP-OCRv5/rec/latin_PP-OCRv5_rec_mobile.onnx'
SHA='b20bd37c168a570f583afbc8cd7925603890efbcdc000a59e22c269d160b5f5a'
FALLBACK_URL='https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2/onnx/PP-OCRv4/rec/en_PP-OCRv4_rec_mobile.onnx'
FALLBACK_SHA='e8770c967605983d1570cdf5352041dfb68fa0c21664f49f47b155abd3e0e318'

def prepare(directory):
    directory.mkdir(parents=True,exist_ok=True)
    cache=ROOT/'build/full-comics/reference-recognizer/english-ocr.onnx'
    if not cache.exists():
        response=requests.get(URL,timeout=(20,120));response.raise_for_status()
        assert hashlib.sha256(response.content).hexdigest()==SHA
        cache.parent.mkdir(parents=True,exist_ok=True);cache.write_bytes(response.content)
    assert hashlib.sha256(cache.read_bytes()).hexdigest()==SHA
    options=ort.SessionOptions();options.intra_op_num_threads=1
    session=ort.InferenceSession(str(cache),sess_options=options,providers=['CPUExecutionProvider'])
    characters=['blank']+session.get_modelmeta().custom_metadata_map['character'].splitlines()+[' ']
    output=session.run(None,{session.get_inputs()[0].name:np.zeros((1,3,48,320),dtype=np.float32)})[0]
    assert output.ndim==3 and output.shape[-1]==len(characters),'Reader is incompatible with the shared 48-pixel CTC pipeline'
    shutil.copy2(cache,directory/'english-ocr.onnx')
    (directory/'ocr-characters.json').write_text(json.dumps(characters,ensure_ascii=False),encoding='utf-8')
    legacy=ROOT/'build/full-comics/frozen-windows6005/data/flutter_assets/assets/models/opus-en-es/english-ocr.onnx'
    if not legacy.exists():
        legacy=ROOT/'build/model-cache/english-ocr-v4.onnx'
        if not legacy.exists():
            response=requests.get(FALLBACK_URL,timeout=(20,120));response.raise_for_status()
            assert hashlib.sha256(response.content).hexdigest()==FALLBACK_SHA
            legacy.parent.mkdir(parents=True,exist_ok=True);legacy.write_bytes(response.content)
    assert hashlib.sha256(legacy.read_bytes()).hexdigest()==FALLBACK_SHA
    legacy_session=ort.InferenceSession(str(legacy),sess_options=options,providers=['CPUExecutionProvider'])
    legacy_characters=['blank']+legacy_session.get_modelmeta().custom_metadata_map['character'].splitlines()+[' ']
    legacy_output=legacy_session.run(None,{legacy_session.get_inputs()[0].name:np.zeros((1,3,48,320),dtype=np.float32)})[0]
    assert legacy_output.ndim==3 and legacy_output.shape[-1]==len(legacy_characters)
    shutil.copy2(legacy,directory/'english-ocr-fallback.onnx')
    (directory/'ocr-characters-fallback.json').write_text(json.dumps(legacy_characters,ensure_ascii=False),encoding='utf-8')
    return {'upstream':'PaddlePaddle/PaddleOCR','conversion':'RapidAI/RapidOCR','revision':'v3.10.0',
        'license':'Apache-2.0','url':URL,'architecture':'Latin PP-OCRv5 mobile',
        'purpose':'English and Latin-script line recognition, including comic lettering; pretrained weights, no chapter answer lookup',
        'fallback':{'architecture':'English PP-OCRv4 mobile','revision':'v3.9.2','url':FALLBACK_URL,'license':'Apache-2.0',
            'purpose':'Lazy specialist for uncertain decorative words; requires higher confidence and agreement for padding retries'}}

def main():
    directory=ROOT/'assets/models/opus-en-es'
    metadata=prepare(directory)
    manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    for name in ['english-ocr.onnx','ocr-characters.json','english-ocr-fallback.onnx','ocr-characters-fallback.json']:
        manifest['files'][name]=hashlib.sha256((directory/name).read_bytes()).hexdigest()
    manifest['ocr']=metadata
    (directory/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Pinned Latin reader:',(directory/'english-ocr.onnx').stat().st_size,'bytes')

if __name__=='__main__':main()
