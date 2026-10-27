"""Artifacts, provenance and source-only inputs, independent of GPU inference."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
META = ROOT / 'benchmarks/stability8035'
OUT = ROOT / 'build/stability8035'
PRIOR = ROOT / 'build/finetune8034/lora-pilot'
BASE = ROOT / 'build/finetune8031/base-model'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def source_only(rows):
    return [dict(id=row['id'], source=row['source'],
                 prepared_source=row['prepared_source']) for row in rows]


def text_outputs(rows):
    return [dict(id=row['id'], source=row['source'],
                 prepared_source=row['prepared_source'], translation=row['translation'])
            for row in rows]


def validate_provenance():
    protocol = read(META / 'protocol.json')
    for entry in protocol['immutable_inputs']:
        assert sha(ROOT / entry['path']) == entry['sha256'], entry['path']
    report = read(ROOT / 'benchmarks/finetune8034/pilot-review.json')
    for entry in report['evidence']:
        assert sha(ROOT / entry['path']) == entry['sha256'], entry['path']
    assert sha(PRIOR / 'adapter/adapter_model.safetensors') == report['adapter_sha256']
    provenance = read(ROOT / 'build/finetune8031/base-model-provenance.json')
    for entry in provenance['files']:
        assert sha(BASE / entry['path']) == entry['sha256'], entry['path']
    data = read(ROOT / 'benchmarks/finetune8034/dataset.json')
    assert len(data['validation']) == 25
    training = data['original_training'] + data['packed_training']
    assert not {row['id'] for row in training} & {row['id'] for row in data['validation']}
    return protocol, data


def format_issues(source, translation):
    """Format alerts never certify semantic completeness or count as approval."""
    issues = []
    if any(char.isalpha() for char in source) and not any(char.isalpha() for char in translation):
        issues.append('alphabetic_source_without_alphabetic_translation')
    if not translation.strip():
        issues.append('empty_translation')
    return issues
