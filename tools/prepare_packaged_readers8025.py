"""Package the already evaluated OCR readers for Windows only; no new weights."""
import json
import shutil
from audit_corpus_quality import ROOT, QA, atomic, digest, read


def main():
    target=ROOT/'assets/windows-ocr-readers';target.mkdir(exist_ok=True)
    assert shutil.disk_usage(target).free>4*1024**3+50*1024**2
    sources={};files={}
    for name in ['english-v5','multilingual-v6-small']:
        source=QA/'ocr-candidates8016'/name;proof=read(source/'provenance.json')
        assert digest(source/'english-ocr.onnx')==proof['sha256']
        assert digest(source/'ocr-characters.json')==proof['characters_sha256']
        folder=target/name;folder.mkdir(exist_ok=True)
        for part in ['english-ocr.onnx','ocr-characters.json','english-ocr-fallback.onnx','ocr-characters-fallback.json']:
            origin=source/part;dest=folder/part
            if not dest.exists() or digest(dest)!=digest(origin):shutil.copy2(origin,dest)
            files[f'{name}/{part}']=digest(dest)
        sources[name]=proof
    license_path=target/'LICENSE.Apache-2.0.txt'
    shutil.copy2(ROOT/'assets/models/opus-en-es/LICENSE.OCR.Apache-2.0.txt',license_path)
    files[license_path.name]=digest(license_path)
    value=dict(schema=1,license='Apache-2.0',sources=sources,files=files,platform='Windows',
        role='Corroborate existing English text blocks; never supplies chapter answers',
        human_or_reference_text_supplied=False,model_weights_trained=False)
    atomic(target/'manifest.json',json.dumps(value,indent=2))
    print(json.dumps(dict(prepared=True,logical_bytes=sum((target/n).stat().st_size for n in files),new_downloads=0)),flush=True)


if __name__=='__main__':main()
