"""Download one pinned translation specialist for isolated local evaluation.

No login, private credentials or comic inputs are sent to the download host.
Preserve its own license. Outputs will not train or improve another AI model;
this experiment evaluates the specialist itself and does not distribute it.
"""
import hashlib
import json
import shutil
import time
import urllib.request
import urllib.error
from audit_corpus_quality import ROOT, atomic, digest, read
from prepare_local_llm8021 import download

REPO='tencent/HY-MT1.5-1.8B-GGUF'
REVISION='265b2e615a7dc9b06c435dc878829ad99a512ba2'
FILENAME='HY-MT1.5-1.8B-Q8_0.gguf'
SIZE=1908528288
SHA='6789b06d0902f2f5312c0e1703d56ccbddfcfb6c653d22519b7c720f7db9a98e'


def main():
    folder=ROOT/'build/llm-hy8024';folder.mkdir(exist_ok=True)
    assert shutil.disk_usage(ROOT).free>SIZE+4*1024**3,'Preserve 4GiB reserve'
    small=[('License.txt',16270,'1b502c594266512e3f80deb4e021b9b52024f671'),
           ('README.md',8088,'5c4200c70eb143ed7161d6aa90d87b47c7bb4c54')]
    for name,length,blob in small:
        target=folder/name
        if not target.exists():
            with urllib.request.urlopen(f'https://huggingface.co/{REPO}/resolve/{REVISION}/{name}?download=true',timeout=60) as response:data=response.read()
            assert len(data)==length and hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==blob
            target.write_bytes(data)
    proof=dict(repository=REPO,revision=REVISION,filename=FILENAME,bytes=SIZE,sha256=SHA,
        url=f'https://huggingface.co/{REPO}/resolve/{REVISION}/{FILENAME}?download=true',
        license='Tencent HY Community License Agreement; preserve License.txt; not an unrestricted Apache/MIT license',
        license_sha256=digest(folder/'License.txt'),model_card_sha256=digest(folder/'README.md'),
        research_evaluation_only=True,application_distribution_approved=False,
        outputs_not_used_to_train_other_models=True,reference_or_comic_content_sent_to_host=False)
    target=folder/'download-provenance.json'
    if target.exists():assert read(target)==proof
    else:atomic(target,json.dumps(proof,indent=2))
    for attempt in range(4):
        try:
            download(proof['url'],folder/FILENAME,SHA,SIZE)
            break
        except (TimeoutError,urllib.error.URLError,ConnectionError) as error:
            if attempt==3:raise
            partial=(folder/FILENAME).with_suffix('.gguf.part')
            print(json.dumps(dict(retry=attempt+1,error_type=type(error).__name__,
                resumable_bytes=partial.stat().st_size if partial.exists() else 0)),flush=True)
            time.sleep(3)
    print(json.dumps(dict(prepared=True,model=FILENAME,bytes=SIZE,local_only_inference=True)),flush=True)


if __name__=='__main__':main()
