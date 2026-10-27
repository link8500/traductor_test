"""Download one pinned public checkpoint without an extra encoder-weight copy."""
import hashlib
import json
import shutil
import urllib.request

from tools.experiments.stability8035.core import ROOT, sha, write_new

REVISION = '2e7ffc84fb67d99cf92506611766463bb9230cfb'
MODEL = ROOT / 'build/qe8038/model'
EXPECTED_SIZE = 2277497201
EXPECTED_SHA = '05d892bf4a3e34b9a4de239109387d43107b2a8c55ad34b73a929ca6c1ede24e'


def main():
    assert shutil.disk_usage(ROOT).free > EXPECTED_SIZE + 5 * 1024**3
    target = MODEL / 'checkpoints/model.ckpt'
    if target.exists():
        assert target.stat().st_size == EXPECTED_SIZE and sha(target) == EXPECTED_SHA
        print('Pinned checkpoint already verified', flush=True)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    for name in ['hparams.yaml', 'README.md']:
        path = MODEL / name
        if not path.exists():
            url = f'https://huggingface.co/Unbabel/wmt20-comet-qe-da/resolve/{REVISION}/{name}'
            with urllib.request.urlopen(url, timeout=60) as response:
                path.write_bytes(response.read())
    url = f'https://huggingface.co/Unbabel/wmt20-comet-qe-da/resolve/{REVISION}/checkpoints/model.ckpt?download=true'
    temporary = target.with_suffix('.part')
    digest = hashlib.sha256()
    count = 0
    milestone = 256 * 1024**2
    with urllib.request.urlopen(url, timeout=90) as response, temporary.open('xb') as output:
        for chunk in iter(lambda: response.read(4 * 1024**2), b''):
            output.write(chunk)
            digest.update(chunk)
            count += len(chunk)
            if count >= milestone:
                print(json.dumps(dict(state='downloading_qe_checkpoint', bytes=count, expected=EXPECTED_SIZE)), flush=True)
                milestone += 256 * 1024**2
    assert count == EXPECTED_SIZE and digest.hexdigest() == EXPECTED_SHA
    temporary.rename(target)
    write_new(ROOT / 'benchmarks/qe8038/model-provenance.json', dict(
        repo_id='Unbabel/wmt20-comet-qe-da', revision=REVISION, license='Apache-2.0',
        checkpoint=str(target.relative_to(ROOT)), checkpoint_bytes=count, checkpoint_sha256=EXPECTED_SHA,
        hparams_sha256=sha(MODEL / 'hparams.yaml'), readme_sha256=sha(MODEL / 'README.md'),
        public_pretrained_model=True, task='Reference-free translation quality estimation',
        user_text_uploaded=False, full_encoder_weights_downloaded_separately=False))
    print('Pinned public QE checkpoint verified', flush=True)


if __name__ == '__main__':
    main()
