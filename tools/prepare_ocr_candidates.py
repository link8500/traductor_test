"""Prepare pinned, offline OCR candidates outside the app's model directory."""
import concurrent.futures
import json
import os
import requests
import numpy as np
import onnxruntime as ort
from audit_corpus_quality import ROOT,QA,digest,atomic

MODELS={
    'english-v5':('PP-OCRv5/rec/en_PP-OCRv5_rec_mobile.onnx','c3461add59bb4323ecba96a492ab75e06dda42467c9e3d0c18db5d1d21924be8'),
    'multilingual-v6-small':('PP-OCRv6/rec/PP-OCRv6_rec_small.onnx','6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884')
}


def prepare(item):
    name,(remote,sha)=item;folder=QA/'ocr-candidates8016'/name;folder.mkdir(parents=True,exist_ok=True)
    path=folder/'english-ocr.onnx';url='https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.10.0/onnx/'+remote
    if not path.exists():
        pending=path.with_suffix('.part')
        with requests.get(url,stream=True,timeout=(30,120)) as response:
            response.raise_for_status()
            with pending.open('wb') as handle:
                for block in response.iter_content(1024*1024):handle.write(block)
        assert digest(pending)==sha,'Upstream model hash mismatch';pending.replace(path)
    assert digest(path)==sha
    options=ort.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1
    session=ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider'])
    characters=['blank']+session.get_modelmeta().custom_metadata_map['character'].splitlines()+[' ']
    result=session.run(None,{session.get_inputs()[0].name:np.zeros((1,3,48,320),dtype=np.float32)})[0]
    assert result.ndim==3 and result.shape[-1]==len(characters)
    atomic(folder/'ocr-characters.json',json.dumps(characters,ensure_ascii=False))
    for filename in ['english-ocr-fallback.onnx','ocr-characters-fallback.json']:
        dest=folder/filename
        if not dest.exists():os.link(ROOT/'assets/models/opus-en-es'/filename,dest)
    value=dict(name=name,url=url,sha256=sha,bytes=path.stat().st_size,input_shape=session.get_inputs()[0].shape,
        output_shape=list(result.shape),characters_sha256=digest(folder/'ocr-characters.json'),upstream='PaddlePaddle/PaddleOCR',
        conversion='RapidAI/RapidOCR',revision='v3.10.0',license='Apache-2.0',upstream_registry='https://github.com/RapidAI/RapidOCR/blob/main/python/rapidocr/default_models.yaml',
        native_48_pixel_ctc_compatibility=True,application_assets_modified=False,trained_for_this_project=False,chapter_answers_supplied=False)
    atomic(folder/'provenance.json',json.dumps(value,indent=2));print(json.dumps(value),flush=True)


def main():
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for future in [pool.submit(prepare,item) for item in MODELS.items()]:future.result()


if __name__=='__main__':main()
