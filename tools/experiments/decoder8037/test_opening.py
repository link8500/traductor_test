"""Verify the opening constraint never encodes chapter answers or bans laughter."""
import unittest

import torch

from .opening import LexicalOpening, token_shape


class OpeningGuards(unittest.TestCase):
    tokens = ['<pad>', '</s>', '<unk>', '¡', '?', '...', '▁Hello', 'world', '▁123', '▁Sniff', '▁']

    def guard(self, sources, beams=1):
        return LexicalOpening(self.tokens, sources, beams=beams, eos=1, pad=0, unknown=2)

    def test_eos_requires_a_word_for_lexical_input(self):
        scores = torch.zeros(1, len(self.tokens))
        result = self.guard(['An example.'])(torch.tensor([[0]]), scores)
        self.assertTrue(torch.isneginf(result[0, 1]))
        self.assertTrue(torch.isfinite(result[0, 6]))
        self.assertTrue(torch.isfinite(scores).all())

    def test_repeated_punctuation_cannot_exceed_the_source_aware_budget(self):
        scores = torch.zeros(1, len(self.tokens))
        result = self.guard(['An example.'])(torch.tensor([[0, 3, 3, 3]]), scores)
        self.assertTrue(torch.isneginf(result[0, 3]))
        self.assertTrue(torch.isneginf(result[0, 5]))
        self.assertTrue(torch.isfinite(result[0, 6]))

    def test_punctuation_only_source_is_unchanged(self):
        scores = torch.randn(1, len(self.tokens))
        self.assertTrue(torch.equal(self.guard(['...?!'])(torch.tensor([[0, 3, 3, 3]]), scores), scores))

    def test_laughter_sound_effects_digits_and_words_are_lexical(self):
        for token in [6, 7, 8, 9]:
            scores = torch.randn(1, len(self.tokens))
            self.assertTrue(torch.equal(self.guard(['Sniff'])(torch.tensor([[0, token]]), scores), scores))
        self.assertEqual(token_shape('▁Fufufu'), (True, 0))

    def test_beam_expansion_keeps_distinct_source_policies(self):
        scores = torch.zeros(4, len(self.tokens))
        result = self.guard(['A sentence.', '...'], beams=2)(torch.tensor([[0], [0], [0], [0]]), scores)
        self.assertTrue(torch.isneginf(result[:2, 1]).all())
        self.assertTrue(torch.equal(result[2:], scores[2:]))

    def test_forced_eos_is_preserved_when_all_other_tokens_are_already_forbidden(self):
        scores = torch.full((1, len(self.tokens)), -torch.inf)
        scores[0, 1] = 0
        guard = self.guard(['A sentence.'])
        self.assertTrue(torch.equal(guard(torch.tensor([[0]]), scores), scores))
        self.assertEqual(guard.restore_all_masked, [1])


if __name__ == '__main__':
    unittest.main()
