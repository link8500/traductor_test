"""Evidence checks for frozen routing experiments, not translation quality tests."""
import math
import unittest

from tools.experiments.stability8035.core import ROOT, read, sha
from tools.experiments.qe8038.evaluate import key
from tools.experiments.temporal8040.amend_counts import uncertainty
from .policy import choose


class RoutingEvidenceTest(unittest.TestCase):
    def test_all_frozen_protocol_inputs(self):
        for name in ['decoder8037', 'qe8038', 'roundtrip8039', 'temporal8040']:
            for row in read(ROOT / f'benchmarks/{name}/protocol.json')['immutable_inputs']:
                self.assertEqual(sha(ROOT / row['path']), row['sha256'], row['path'])

    def test_failed_experiments_not_promoted(self):
        for name in ['decoder8037', 'qe8038', 'roundtrip8039']:
            result = read(ROOT / f'benchmarks/{name}/result.json')
            self.assertFalse(result.get('promoted', False))
            self.assertFalse(result['target_achieved'])
        latest = read(ROOT / 'benchmarks/temporal8040/result-v2.json')
        self.assertFalse(latest['promoted'])
        self.assertFalse(latest['quality_gates_passed'])
        self.assertEqual(latest['controls']['new_partial_losses'], 2)
        self.assertEqual(latest['controls']['new_context_uncertainties'], 2)

    def test_validation_precedes_controls_and_passed(self):
        meta = ROOT / 'benchmarks/temporal8040'
        selection = read(meta / 'selection.json')
        self.assertTrue(selection['eligible'])
        self.assertTrue(selection['frozen_before_controls'])
        self.assertEqual(selection['protocol_sha256'], sha(meta / 'protocol.json'))
        self.assertEqual(selection['validation_review_sha256'], sha(meta / 'validation-review.json'))
        proof = read(ROOT / 'build/temporal8040/controls-scoring-proof.json')
        self.assertEqual(proof['selection_sha256'], sha(meta / 'selection.json'))
        self.assertTrue(proof['original_english_source_used_as_reverse_target'])
        self.assertFalse(proof['gold_spanish_reference_used'])

    def test_source_only_reverse_requests_and_scores(self):
        for folder, stage in [('roundtrip8039', 'validation'), ('temporal8040', 'controls')]:
            inputs = read(ROOT / f'build/{folder}/{stage}-inverse-input.json')
            scores = read(ROOT / f'build/{folder}/{stage}-inverse-scores.json')['scores']
            self.assertEqual(set(inputs), set(scores))
            per_source_tokens = {}
            for ident, sample in inputs.items():
                self.assertEqual(set(sample), {'src', 'mt'})
                self.assertEqual(ident, key(sample['src'], sample['mt']))
                value = scores[ident]
                tokens, logp = value['english_token_ids'], value['english_token_logprobs']
                self.assertEqual(len(tokens), len(logp))
                self.assertTrue(all(math.isfinite(v) and v <= 0 for v in logp))
                self.assertAlmostEqual(sum(logp) / len(logp), value['mean_log_probability'], places=5)
                self.assertEqual(per_source_tokens.setdefault(sample['src'], tokens), tokens)

    def test_all_routed_outputs_reproducible_and_unmodified(self):
        pools = {(row['group'], row['id']): row for row in read(ROOT / 'build/qe8038/candidate-pools.json')}
        seen = set()
        for stage, expected in [('validation', 25), ('controls', 258)]:
            rows = read(ROOT / f'build/temporal8040/{stage}-candidate.json')
            self.assertEqual(len(rows), expected)
            for row in rows:
                ident = row['group'], row['id']
                self.assertNotIn(ident, seen)
                seen.add(ident)
                pool = pools[ident]
                self.assertEqual(row['source'], pool['source'])
                result = choose(pool, row['inverse_scores'], row['profiles'])
                self.assertEqual(result['selected'], row['selected'])
                self.assertEqual(result['translation'], row['translation'])
                self.assertEqual(result['temporal_vetoes'], row['temporal_vetoes'])
                self.assertIn(row['translation'], [candidate['translation'] for candidate in pool['candidates']])
        self.assertEqual(seen, set(pools))

    def test_v2_preserves_all_semantic_verdicts(self):
        meta = ROOT / 'benchmarks/temporal8040'
        first = read(meta / 'control-meaning-review.json')
        second = read(meta / 'control-meaning-review-v2.json')
        self.assertEqual(first['entries'], second['entries'])
        self.assertEqual(second['summary']['unresolved_before'], sum(uncertainty(row['before']) for row in second['entries']))
        self.assertEqual(second['summary']['new_context_uncertainties'], sum(not uncertainty(row['before']) and uncertainty(row['after']) for row in second['entries']))

    def test_packaged_models_unchanged(self):
        path = ROOT / 'assets/models/opus-en-es'
        manifest = read(path / 'manifest.json')
        for name, expected in manifest['files'].items():
            self.assertEqual(sha(path / name), expected, name)

    def test_external_research_models_match_provenance(self):
        for name in ['roundtrip8039/model-provenance', 'temporal8040/grammar-provenance']:
            for entry in read(ROOT / f'benchmarks/{name}.json')['files']:
                self.assertEqual(sha(ROOT / entry['path']), entry['sha256'], entry['path'])
        qe = read(ROOT / 'benchmarks/qe8038/model-provenance.json')
        self.assertEqual(sha(ROOT / qe['checkpoint']), qe['checkpoint_sha256'])
        native = ROOT / 'build/full-comics/frozen-windows803001/traductor.exe'
        self.assertEqual(sha(native), 'cbefd6bb0a8712e0d680b16aef2c64c726385ed03ee1ddcbd0de6171d92f919e')


if __name__ == '__main__':
    unittest.main()
