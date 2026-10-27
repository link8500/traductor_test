"""Regression checks for the strength experiment and its evidence boundaries."""
import copy
import tempfile
import unittest
from pathlib import Path

from .core import META, OUT, read, sha, source_only, validate_provenance, write_new, format_issues
from .review import validation_counts, validation_gates


class StrengthGuards(unittest.TestCase):
    def test_generation_inputs_never_include_references(self):
        rows = source_only([dict(id=1, source='A', prepared_source='A', target='B', note='private reference')])
        self.assertEqual(rows, [dict(id=1, source='A', prepared_source='A')])

    def test_artifacts_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'failed-output.json'
            write_new(path, {'failure': True})
            with self.assertRaises(FileExistsError):
                write_new(path, {'failure': False})
            self.assertTrue(read(path)['failure'])

    def test_format_alert_is_not_an_onomatopoeia_error(self):
        self.assertEqual(format_issues('SNIFF', 'Sniff'), [])
        self.assertEqual(format_issues('...', '...'), [])
        self.assertTrue(format_issues('A complete sentence', '!!!!'))
        self.assertTrue(format_issues('A complete sentence', ''))

    def test_all_references_and_original_adapter_remain_identical(self):
        protocol, data = validate_provenance()
        self.assertEqual(len(protocol['variants']), 2)
        self.assertEqual(len(data['validation']), 25)

    def test_unreviewed_rows_cannot_become_passing_validation(self):
        review = read(META / 'validation-review.json')
        rows = copy.deepcopy(review['variants']['scale075']['entries'])
        rows[0]['reviewed'] = False
        with self.assertRaises(AssertionError):
            validation_counts(rows)

    def test_high_automatic_score_cannot_override_a_new_semantic_regression(self):
        protocol = read(META / 'protocol.json')
        counts = copy.deepcopy(read(META / 'validation-review.json')['variants']['scale075']['counts'])
        counts['new']['new_content_regressions'] = 1
        self.assertFalse(all(validation_gates(protocol, counts, 0).values()))

    def test_selection_was_frozen_before_controls(self):
        selection = read(META / 'selection.json')
        proof = read(OUT / 'controls-selection-proof.json')
        self.assertEqual(sha(META / 'selection.json'), proof['selection_sha256'])
        self.assertEqual(selection, proof['selection'])
        self.assertFalse(selection['selection_uses_controls_or_test_outputs'])
        self.assertTrue(selection['all_selection_gates_passed'])

    def test_rejection_preserves_the_generation_failure(self):
        result = read(META / 'result.json')
        self.assertFalse(result['quality_gates_passed'])
        self.assertFalse(result['promoted'])
        self.assertEqual(result['controls']['early-known-test']['format_alerts'], 1)
        self.assertIsNone(result['app_failure_probability'])


if __name__ == '__main__':
    unittest.main()
