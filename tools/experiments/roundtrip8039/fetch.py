"""Fetch a single pinned Spanish-to-English model, not another forward model."""
import hashlib
import json
import shutil
import urllib.request

from tools.experiments.stability8035.core import ROOT, sha, write_new

REPO = 'Helsinki-NLP/opus-mt-es-en'
REVISION = 'c96e2c5399ebfae4fc43d9669556b9afa74bb69d'
FILES = ['config.json', 'generation_config.json', 'source.spm', 'target.spm',
         'vocab.json', 'tokenizer_config.json', 'README.md', 'pytorch_model.bin']
OUT = ROOT / 'build/roundtrip8039/model'


def main():
    assert shutil.disk_usage(ROOT).free > 5 * 1024**3
    OUT.mkdir(parents=True, exist_ok=True)
    info = json.load(urllib.request.urlopen(f'https://huggingface.co/api/models/{REPO}/revision/{REVISION}?blobs=true', timeout=60))
    assert info['sha'] == REVISION
    siblings = {row['rfilename']: row for row in info['siblings']}
    evidence = []
    for name in FILES:
        path = OUT / name
        expected = siblings[name]
        if not path.exists():
            url = f'https://huggingface.co/{REPO}/resolve/{REVISION}/{name}?download=true'
            temporary = path.with_suffix(path.suffix + '.part')
            with urllib.request.urlopen(url, timeout=90) as response, temporary.open('xb') as stream:
                for block in iter(lambda: response.read(4 * 1024**2), b''):
                    stream.write(block)
            assert temporary.stat().st_size == expected['size']
            if 'lfs' in expected:
                assert sha(temporary) == expected['lfs']['sha256']
            else:
                raw = temporary.read_bytes()
                git_hash = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
                assert git_hash == expected['blobId']
            temporary.rename(path)
        evidence.append(dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size, sha256=sha(path)))
        print(json.dumps(dict(state='inverse_model_file_verified', name=name, bytes=path.stat().st_size)), flush=True)
    write_new(ROOT / 'benchmarks/roundtrip8039/model-provenance.json', dict(
        repo=REPO, revision=REVISION, license='Apache-2.0', files=evidence,
        user_text_uploaded=False, purpose='Conditional likelihood of original English given a Spanish alternative'))


if __name__ == '__main__':
    main()
