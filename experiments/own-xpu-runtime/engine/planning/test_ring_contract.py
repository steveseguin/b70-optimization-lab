from dataclasses import replace
import unittest
from ring_contract import Proposals, ProposalBatch, append_prefix


def setup():
    r = Proposals(request=b'r'*32, epoch=2, prompt=[3, 5], vocab=97)
    r.register_verified_row(1, 10, r.hashes[-1])
    return r


def batch(registry, ticket, tokens, seed_length=None):
    n = len(registry.verified) if seed_length is None else seed_length
    return ProposalBatch(registry.request, registry.epoch, ticket, n,
                         registry.hashes[n], tuple(tokens), n-1, True)


class ContractTests(unittest.TestCase):
    def test_fresh_canonical_disagreement_does_not_replace_issued_recursive_row(self):
        r = setup(); r.publish(batch(r, 10, [7, 9]))
        first = r.choose(2, r.hashes[-1]); r.issue(11, 10, first)
        second = r.choose(3, first.after_digest); r.issue(12, 11, second)
        self.assertTrue(r.verify(7, commit_ticket=30)['hit'])
        r.publish(batch(r, 11, [8, 21]))  # New canonical d1 differs from issued recursive9.
        self.assertEqual(r.choose(3, r.hashes[-1]), second)
        self.assertIsNone(r.choose(4, second.after_digest))  # Fresh d2 assumes8, not issued9.
        self.assertTrue(r.verify(9, commit_ticket=31)['hit'])
        self.assertEqual(r.verified, [3, 5, 7, 9])

    def test_fresh_batch_can_replace_only_unissued_choice(self):
        r = setup(); r.publish(batch(r, 10, [7, 9]))
        r.verify(7, commit_ticket=30); r.publish(batch(r, 11, [8, 21]))
        chosen = r.choose(3, r.hashes[-1])
        self.assertEqual((chosen.token, chosen.depth), (8, 1))

    def test_wrong_first_parent_discards_matching_descendant(self):
        r = setup(); r.publish(batch(r, 10, [7, 9]))
        a = r.choose(2, r.hashes[-1]); r.issue(11, 10, a)
        b = r.choose(3, a.after_digest); r.issue(12, 11, b)
        self.assertEqual(r.verify(6, commit_ticket=30)['discard_row_ids'], (11, 12))
        self.assertIsNone(r.choose(3, r.hashes[-1]))  # d2=9 is not valid under corrected6.
        self.assertFalse(r.verify(9, commit_ticket=31)['hit'])

    def test_wrong_second_parent_discards_only_remaining_suffix(self):
        r = setup(); r.publish(batch(r, 10, [7, 9]))
        a = r.choose(2, r.hashes[-1]); r.issue(11, 10, a)
        b = r.choose(3, a.after_digest); r.issue(12, 11, b)
        r.verify(7, commit_ticket=30)
        self.assertEqual(r.verify(8, commit_ticket=31)['discard_row_ids'], (12,))

    def test_stale_epoch_seed_restore_ticket_and_parent_refused(self):
        r = setup(); original = batch(r, 10, [7, 9])
        for modified in (replace(original, epoch=1), replace(original, request=b's'*32),
                         replace(original, seed_digest=b'x'*32), replace(original, restored=False),
                         replace(original, restored_position=0), replace(original, tokens=(7, 9, 4))):
            with self.assertRaises(ValueError): r.publish(modified)
        r.publish(original)
        with self.assertRaises(ValueError): r.publish(original)
        a = r.choose(2, r.hashes[-1])
        with self.assertRaises(ValueError): r.issue(11, 99, a)
        r.issue(11, 10, a)
        b = r.choose(3, a.after_digest)
        with self.assertRaises(ValueError): r.issue(12, 99, b)
        with self.assertRaises(ValueError): r.choose(2, append_prefix(r.hashes[-1], 2, 11))

    def test_prompt_pair_and_context_censored_one_guess(self):
        r = setup(); r.publish(batch(r, 10, [7]))
        a = r.choose(2, r.hashes[-1]); self.assertEqual(a.token, 7)
        self.assertIsNone(r.choose(3, a.after_digest))
        self.assertEqual(r.verified, [3, 5])  # Publishing a proposal never commits it.


if __name__ == '__main__':
    unittest.main()
