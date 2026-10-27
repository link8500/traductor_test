"""Small mathematical checks; no GPU, generation or training references needed."""
import unittest

import torch

from .losses import decoder_prefixes, token_kl


class PrefixLossGuards(unittest.TestCase):
    def test_equal_distributions_have_zero_kl_and_a_student_gradient(self):
        student = torch.tensor([[[1.0, 2.0, -1.0]]], requires_grad=True)
        teacher = student.detach().clone().requires_grad_()
        loss = token_kl(student, teacher, torch.tensor([[True]]))
        self.assertAlmostEqual(loss.item(), 0, places=6)
        loss.backward()
        self.assertIsNotNone(student.grad)
        self.assertIsNone(teacher.grad)

    def test_padding_is_excluded_without_dividing_by_the_vocabulary(self):
        student = torch.tensor([[[2.0, -2.0], [300.0, -300.0]]], requires_grad=True)
        teacher = torch.zeros_like(student)
        mask = torch.tensor([[True, False]])
        expected = (torch.softmax(teacher[0, 0], -1) * (
            torch.log_softmax(teacher[0, 0], -1) - torch.log_softmax(student[0, 0], -1))).sum()
        loss = token_kl(student, teacher, mask)
        self.assertAlmostEqual(loss.item(), expected.item(), places=6)
        loss.backward()
        self.assertEqual(student.grad[0, 1].abs().sum().item(), 0)

    def test_marian_start_pad_is_attended_but_tail_padding_is_masked(self):
        sequences = torch.tensor([[9, 2, 3, 0, 9], [9, 4, 0, 9, 9]])
        prefixes, attention, mask = decoder_prefixes(sequences, 9)
        self.assertEqual(prefixes.tolist(), [[9, 2, 3, 0], [9, 4, 0, 9]])
        self.assertEqual(attention.tolist(), [[1, 1, 1, 1], [1, 1, 1, 0]])
        self.assertEqual(mask.tolist(), [[True, True, True, False], [True, True, False, False]])
        self.assertFalse(prefixes.requires_grad)

    def test_empty_masks_are_rejected(self):
        with self.assertRaises(AssertionError):
            token_kl(torch.zeros(1, 1, 3), torch.zeros(1, 1, 3), torch.tensor([[False]]))


if __name__ == '__main__':
    torch.set_num_threads(1)
    unittest.main()
