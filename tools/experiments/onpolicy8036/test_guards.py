"""Validate the actual trained artifacts, training-only rollouts and selection."""
import unittest

import torch
from safetensors import safe_open

from tools.experiments.stability8035.core import ROOT, read, sha
from tools.experiments.stability8035.review import validation_counts, validation_gates
from .select_checkpoint import META, OUT, verified_run


class TrainingGuards(unittest.TestCase):
    def test_executed_training_code_and_checkpoints_are_unchanged(self):
        _, summary = verified_run()
        self.assertEqual(summary['optimizer_steps'], 312)
        self.assertEqual(len(summary['checkpoints']), 3)
        self.assertEqual(summary['trainable_parameters'], 294912)

    def test_every_gradient_and_rollout_id_is_training_only(self):
        proof = read(OUT / 'run-input-proof.json')
        training = set(proof['training_ids'])
        originals = set(proof['rollout_ids'])
        validation = set(proof['validation_ids'])
        self.assertFalse(training & validation)
        self.assertTrue(originals <= training)
        logs = read(OUT / 'training-log.json')
        rollouts = read(OUT / 'rollout-log.json')
        self.assertEqual(len(logs), 312)
        self.assertEqual(len(rollouts), 312)
        for row in logs:
            self.assertTrue(set(row['training_ids']) <= training)
        for row in rollouts:
            self.assertTrue(set(row['training_ids']) <= originals)
            self.assertFalse(row['references_used_for_generation'])
            self.assertTrue(row['generated_token_ids'])

    def test_all_adapters_are_finite_nonzero_and_distinct(self):
        fingerprints = set()
        for step in [104, 208, 312]:
            path = OUT / f'step{step:03d}/adapter/adapter_model.safetensors'
            fingerprints.add(sha(path))
            changed = False
            with safe_open(path, framework='pt') as tensors:
                for name in tensors.keys():
                    tensor = tensors.get_tensor(name)
                    self.assertTrue(torch.isfinite(tensor).all())
                    if 'lora_B' in name and torch.count_nonzero(tensor):
                        changed = True
            self.assertTrue(changed)
        self.assertEqual(len(fingerprints), 3)

    def test_selection_uses_semantic_gates_instead_of_the_highest_chrf(self):
        selection = read(META / 'selection.json')
        protocol = read(META / 'protocol.json')
        reviews = read(META / 'validation-review.json')['checkpoints']
        for review in reviews.values():
            counts = validation_counts(review['entries'])
            self.assertEqual(counts, review['counts'])
            self.assertEqual(validation_gates(protocol, counts, 0), review['gates'])
        self.assertEqual(selection['selected_checkpoint'], 'step104')
        self.assertFalse(reviews['step312']['eligible'])
        self.assertFalse(selection['controls_used_for_selection'])

    def test_reload_is_exact_and_controls_use_the_frozen_selection(self):
        parity = read(OUT / 'selected-checkpoint-reload-parity.json')
        proof = read(OUT / 'controls-input-proof.json')
        self.assertTrue(parity['exact'])
        self.assertEqual(proof['selection_sha256'], sha(META / 'selection.json'))
        self.assertEqual(proof['selection'], read(META / 'selection.json'))
        for name, count in [('regression-core', 229), ('known-test', 16), ('early-known-test', 13)]:
            rows = read(OUT / f'{name}-source-only-input.json')
            self.assertEqual(len(rows), count)
            self.assertTrue(all(set(row) == {'id', 'source', 'prepared_source'} for row in rows))

    def test_complete_changed_output_coverage_and_rejection_are_preserved(self):
        review = read(META / 'control-meaning-review.json')
        result = read(META / 'result.json')
        self.assertEqual(review['new_variants_reviewed'] + review['reused_exact_verdicts'], len(review['entries']))
        self.assertEqual(len(review['entries']), 65)
        self.assertFalse(result['quality_gates_passed'])
        self.assertFalse(result['promoted'])
        self.assertIsNone(result['app_failure_probability'])
        self.assertEqual(result['remaining_uninspected_test_chapters'], 41)


if __name__ == '__main__':
    torch.set_num_threads(1)
    unittest.main()
