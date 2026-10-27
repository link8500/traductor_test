"""Fix alternatives before QE predictions; no references in scoring inputs."""
from tools.experiments.stability8035.core import ROOT, PRIOR, read, sha, write_new

OUT = ROOT / 'build/qe8038'
META = ROOT / 'benchmarks/qe8038'


def main():
    provenance = read(META / 'native-baseline-provenance.json')
    pools = []
    evidence = []
    for group in ['validation', 'regression-core', 'known-test', 'early-known-test']:
        native_path = OUT / f'native-{group}.json'
        assert sha(native_path) == provenance['outputs'][group]
        base_path = PRIOR / ('baseline-validation.json' if group == 'validation' else f'{group}-baseline.json')
        adapter_path = PRIOR / ('candidate-validation.json' if group == 'validation' else f'{group}-candidate.json')
        for path in [native_path, base_path, adapter_path]:
            evidence.append(dict(path=str(path.relative_to(ROOT)), sha256=sha(path)))
        native, base, adapter = read(native_path), read(base_path), read(adapter_path)
        assert len(native) == len(base) == len(adapter)
        for a, b, c in zip(native, base, adapter):
            assert a['id'] == b['id'] == c['id'] and a['source'] == b['source'] == c['source']
            pools.append(dict(group=group, id=a['id'], source=a['source'], candidates=[
                dict(name='native', translation=a['translation']),
                dict(name='base', translation=b['translation']),
                dict(name='adapter', translation=c['translation'])]))
    assert len(pools) == 283
    write_new(OUT / 'candidate-pools.json', pools)
    write_new(META / 'candidate-pool-provenance.json', dict(
        inputs=283, alternatives_per_input=3, native_production_baseline=True,
        candidate_pool_sha256=sha(OUT / 'candidate-pools.json'), evidence=evidence,
        references_in_pool=False, validation_targets_sent_to_qe=False))


if __name__ == '__main__':
    main()
