"""Selection invariants independent of comic dialogue or expected answers."""
import unittest

from paragraph_recovery import decide, alignment, key


class RecoveryPolicyTest(unittest.TestCase):
    def test_small_corrupt_word_supported_by_both_system_reads(self):
        old = 'THE DOOR IS BR0KEN'
        new = 'THE DOOR IS BROKEN'
        self.assertTrue(decide(old, old, new, new, new, new)[0])

    def test_independent_system_evidence_is_required(self):
        old = 'THE DOOR IS BR0KEN'
        new = 'THE DOOR IS BROKEN'
        self.assertFalse(decide(old, old, new, old, new, old)[0])

    def test_disagreeing_crops_cannot_replace_a_paragraph(self):
        self.assertFalse(decide('THE DOOR IS BR0KEN', '', 'THE DOOR IS BROKEN', '', 'THE DOOR IS OPEN', '')[0])

    def test_protect_negation_and_content_words(self):
        for old, new in [('DO NOT OPEN THE DOOR', 'DO OPEN THE DOOR'),
                         ('THE RED BIRD CAN FLY', 'THE BIRD CAN FLY')]:
            with self.subTest(old=old):
                self.assertFalse(decide(old, old, new, new, new, new)[0])

    def test_numeric_changes_are_rejected(self):
        old, new = 'IT WAS IN 2040', 'IT WAS IN 2041'
        self.assertFalse(decide(old, old, new, new, new, new)[0])

    def test_already_corroborated_valid_word_is_preserved(self):
        old, new = 'THE BIRD IS RED', 'THE BIRD IS BLUE'
        self.assertFalse(decide(old, old, new, new, new, new)[0])

    def test_new_nonword_is_rejected(self):
        old, new = 'THE DOOR IS XQZJ', 'THE DOOR IS XQZK'
        self.assertFalse(decide(old, old, new, new, new, new)[0])

    def test_large_change_is_not_recovery(self):
        old, new = 'THE DOOR IS OPEN', 'SHE WENT TO ANOTHER COUNTRY'
        self.assertFalse(decide(old, old, new, new, new, new)[0])

    def test_equivalent_formatting_does_not_trigger_changes(self):
        self.assertEqual(decide('Open the door.', '', 'OPEN THE DOOR!', '', 'open the door', '')[1], 'unchanged')
        self.assertEqual(key("CAN'T"), 'CANT')


if __name__ == '__main__':
    unittest.main()
