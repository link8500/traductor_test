"""Fetch tokenizer/config only; the QE checkpoint already contains the encoder."""
import hashlib
import urllib.request

from tools.experiments.stability8035.core import ROOT, sha, write_new

REVISION = 'c23d21b0620b635a76227c604d44e43a9f0ee389'
FILES = ['config.json', 'tokenizer_config.json', 'tokenizer.json', 'sentencepiece.bpe.model']
OUT = ROOT / 'build/qe8038/tokenizer'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    entries = []
    for name in FILES:
        path = OUT / name
        if not path.exists():
            url = f'https://huggingface.co/FacebookAI/xlm-roberta-large/resolve/{REVISION}/{name}'
            with urllib.request.urlopen(url, timeout=60) as response:
                data = response.read(16 * 1024**2)
                assert not response.read(1), 'Unexpected file size; never download encoder weights'
            path.write_bytes(data)
        entries.append(dict(path=str(path.relative_to(ROOT)), sha256=sha(path), bytes=path.stat().st_size))
    assert sum(entry['bytes'] for entry in entries) < 32 * 1024**2
    write_new(ROOT / 'benchmarks/qe8038/tokenizer-provenance.json', dict(
        repo_id='FacebookAI/xlm-roberta-large', revision=REVISION, files=entries,
        encoder_model_weights_downloaded=False))


if __name__ == '__main__':
    main()
