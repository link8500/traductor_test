"""Reuse the verified native fixed control and replay remaining source-only inputs."""
import json
import subprocess

from tools.experiments.stability8035.core import ROOT, PRIOR, read, sha, write_new

OUT = ROOT / 'build/qe8038'
META = ROOT / 'benchmarks/qe8038'
SNAPSHOT = ROOT / 'build/full-comics/windows-engine803001.json'
EXECUTABLE = ROOT / 'build/full-comics/frozen-windows803001/traductor.exe'
NATIVE_FIXED = ROOT / 'build/full-comics/windows8030-tail-translation-replay/fixed-output.jsonl'


def records(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def main():
    snapshot = read(SNAPSHOT)
    assert sha(EXECUTABLE) == snapshot['binary_sha256']
    assert sha(ROOT / 'assets/models/opus-en-es/manifest.json') == snapshot['manifest_sha256']
    evidence = read(ROOT / 'build/full-comics/continuation8030.json')['evidence']
    expected = next(row['sha256'] for row in evidence if row['path'].endswith('windows8030-tail-translation-replay/fixed-output.jsonl'))
    assert sha(NATIVE_FIXED) == expected
    native = records(NATIVE_FIXED)
    floating = read(PRIOR / 'regression-core-baseline.json')
    assert len(native) == len(floating) == 229
    assert all(a['source'] == b['source'] and a['id'] == b['id'] for a, b in zip(native, floating))
    write_new(OUT / 'native-regression-core.json', native)
    write_new(OUT / 'native-baseline-input-proof.json', dict(
        snapshot_sha256=sha(SNAPSHOT), native_executable_sha256=sha(EXECUTABLE),
        reused_fixed_output_sha256=expected, fresh_ocr=False, fresh_capture=False,
        execution_script_sha256=sha(__file__), references_sent_to_native=False))
    validation = read(ROOT / 'benchmarks/finetune8034/dataset.json')['validation']
    for name in ['validation', 'known-test', 'early-known-test']:
        source = validation if name == 'validation' else read(PRIOR / f'{name}-baseline.json')
        inputs = [dict(id=row['id'], source=row['source']) for row in source]
        manifest = OUT / f'native-{name}-input.jsonl'
        manifest.parent.mkdir(parents=True, exist_ok=True)
        with manifest.open('x', encoding='utf-8') as stream:
            for row in inputs:
                stream.write(json.dumps(row) + '\n')
        output = OUT / f'native-{name}-output.jsonl'
        assert not output.exists()
        run = subprocess.run([str(EXECUTABLE), '--translation-replay', str(manifest), str(output)],
                             creationflags=subprocess.CREATE_NO_WINDOW, check=False)
        assert run.returncode == 0, f'Native replay failed: {name}'
        result = records(output)
        assert len(result) == len(inputs) and not any('error' in row for row in result)
        write_new(OUT / f'native-{name}.json', result)
        print(json.dumps(dict(state='native_baseline_complete', name=name, rows=len(result),
                              output_sha256=sha(OUT / f'native-{name}.json'))), flush=True)
    write_new(META / 'native-baseline-provenance.json', dict(
        production_engine='803001', native_executable_sha256=sha(EXECUTABLE),
        outputs={name: sha(OUT / f'native-{name}.json') for name in ['validation', 'regression-core', 'known-test', 'early-known-test']},
        full_production_translation_rules=True, same_english_sources=True,
        new_ocr_or_capture=False, production_model_weights_modified=False))


if __name__ == '__main__':
    main()
