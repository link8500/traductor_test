"""Download pinned public model/runtime files for an isolated offline comparison.

No comic text, screenshots, credentials or reference answers are uploaded.
All downloads stay under build; application dependencies are not replaced.
"""
import hashlib
import json
import pathlib
import shutil
import time
import urllib.request
import zipfile
from audit_corpus_quality import ROOT, atomic, digest


def download(url, target, expected, size):
    if target.exists():
        assert target.stat().st_size == size and digest(target) == expected
        return
    assert shutil.disk_usage(target.parent).free > size + 800_000_000, 'Insufficient reserve for isolated download'
    part = target.with_suffix(target.suffix + '.part')
    headers = {'User-Agent':'Luma-offline-local-evaluation/8021'}
    offset=part.stat().st_size if part.exists() else 0
    if offset:headers['Range']=f'bytes={offset}-'
    response=urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=60)
    if offset and response.status==206:
        assert response.headers.get('Content-Range','').startswith(f'bytes {offset}-'), 'Unexpected resume range'
        sha=hashlib.sha256()
        with part.open('rb') as prior:
            for block in iter(lambda:prior.read(4*1024*1024),b''):sha.update(block)
        mode='ab'
    else:offset=0;sha=hashlib.sha256();mode='wb'
    with response,part.open(mode) as out:
        count=offset;last=time.monotonic()
        while True:
            block=response.read(4*1024*1024)
            if not block:break
            out.write(block);sha.update(block);count+=len(block)
            if time.monotonic()-last>=10:
                print(json.dumps(dict(file=target.name,bytes=count,total=size)),flush=True);last=time.monotonic()
    assert count==size and sha.hexdigest()==expected, 'Downloaded artifact hash mismatch'
    part.replace(target)


def main():
    folder=ROOT/'build/llm-quality8021';folder.mkdir(exist_ok=True)
    runtime=dict(url='https://github.com/ggml-org/llama.cpp/releases/download/b11869/llama-b11869-bin-win-vulkan-x64.zip',
        sha256='62d6fe2a8614d9b8a5c1e0484350fd6d91779661f84220617ad296672ef640a0',size=36999274)
    model=dict(repository='Qwen/Qwen3-4B-GGUF',filename='Qwen3-4B-Q4_K_M.gguf',
        sha256='7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5',size=2497280256,
        license='Apache-2.0',source_card='https://huggingface.co/Qwen/Qwen3-4B-GGUF')
    with urllib.request.urlopen('https://huggingface.co/api/models/'+model['repository'],timeout=30) as response:
        info=json.load(response)
    model['revision']=info['sha']
    model['url']='https://huggingface.co/'+model['repository']+'/resolve/'+model['revision']+'/'+model['filename']+'?download=true'
    archive=folder/'llama-b11869-vulkan.zip'
    download(runtime['url'],archive,runtime['sha256'],runtime['size'])
    binaries=folder/'runtime';binaries.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as source:
        for item in source.infolist():
            destination=(binaries/item.filename).resolve()
            assert destination.is_relative_to(binaries.resolve()), 'Unexpected archive path'
        source.extractall(binaries)
    download(model['url'],folder/model['filename'],model['sha256'],model['size'])
    for name in ['LICENSE','README.md']:
        url='https://huggingface.co/'+model['repository']+'/resolve/'+model['revision']+'/'+name
        try:
            with urllib.request.urlopen(url,timeout=30) as response:data=response.read()
            (folder/('model-'+name)).write_bytes(data)
        except urllib.error.HTTPError as error:
            if error.code != 404:raise
    proof=dict(model=model,runtime=runtime,local_only_inference=True,app_dependencies_replaced=False,
        model_weights_trained=False,user_text_sent_to_remote_service=False,
        server_binaries={str(p.relative_to(binaries)):digest(p) for p in binaries.rglob('llama-server.exe')})
    atomic(folder/'download-provenance.json',json.dumps(proof,indent=2))
    print(json.dumps(dict(prepared=True,model=model['filename'],runtime='b11869 Vulkan',local_only=True)),flush=True)


if __name__=='__main__':main()
