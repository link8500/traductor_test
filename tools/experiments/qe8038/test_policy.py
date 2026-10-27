"""Routing must not confuse shape checks or QE scores with semantic approval."""
import unittest

from .policy import choose


class RoutingGuards(unittest.TestCase):
    def test_invalid_candidate_cannot_win_with_a_high_score(self):
        self.assertEqual(choose('A sentence', 'Una frase', '!!!!', .1, .99, 0)['selected'], 'base')

    def test_margin_is_strict_and_missing_estimates_remain_unresolved(self):
        self.assertEqual(choose('A', 'a', 'b', .5, .52, .02)['selected'], 'base')
        self.assertEqual(choose('A', 'a', 'b', .5, .521, .02)['selected'], 'candidate')
        self.assertTrue(choose('A', 'a', 'b', None, .6, .02)['unresolved'])

    def test_neither_bad_output_can_be_reported_as_resolved(self):
        self.assertTrue(choose('A meaningful sentence', '...', '!!!', .5, .6, 0)['unresolved'])

    def test_identical_output_and_sound_effects_do_not_require_scoring(self):
        result = choose('Sniff', 'Sniff', 'Sniff', None, None, 0)
        self.assertFalse(result['unresolved'])
        self.assertEqual(result['reason'], 'identical_outputs')

    def test_source_and_target_punctuation_only_are_permitted(self):
        self.assertFalse(choose('...', '...', '...', None, None, 0)['unresolved'])


if __name__ == '__main__':
    unittest.main()
