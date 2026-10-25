from copy import deepcopy
import unittest
from wavefront_ring import Ring, Ticket


def issue(ring, token, *, tentative=False, identity=None):
    t = Ticket(identity or ring.last_identity + 1,
               ring.pending[-1].ticket.identity if ring.pending else ring.last_accepted,
               ring.generation, ring.physical['position'], token, tentative)
    ring.execute(t)
    return t


def verified(ring, token):
    t = issue(ring, token)
    ring.accept(t, verified_token=token)
    return t


class RingTests(unittest.TestCase):
    def test_all_hit_commit_does_not_rewind_eager_device_state(self):
        ring = Ring(first=True)
        verified(ring, 3)
        a, b = issue(ring, 4, tentative=True), issue(ring, 5, tentative=True)
        physical = deepcopy(ring.physical)
        ring.accept(a, verified_token=4)
        self.assertEqual(ring.physical, physical)
        self.assertEqual((ring.committed, ring.physical['position']), (2, 3))
        with self.assertRaisesRegex(ValueError, 'empty target ring'): ring.draft_admission()
        ring.accept(b, verified_token=5)
        self.assertEqual(ring.boundary(), physical)

    def test_every_miss_depth_restores_full_suffix_across_attention_and_banks(self):
        for capacity in (1, 2, 3):
            for first in (False, True):
                for miss in range(capacity):
                    with self.subTest(capacity=capacity, first=first, miss=miss):
                        ring, reference = Ring(capacity=capacity, first=first), Ring(first=first)
                        for pos in range(31):
                            verified(ring, pos % 9); verified(reference, pos % 9)
                        truth = [21 + i for i in range(capacity)]
                        guesses = truth[:]; guesses[miss] += 10
                        tickets = [issue(ring, x, tentative=True) for x in guesses]
                        for i in range(miss):
                            physical = deepcopy(ring.physical)
                            ring.accept(tickets[i], verified_token=truth[i]); verified(reference, truth[i])
                            self.assertEqual(ring.physical, physical)
                            self.assertEqual(ring.committed_view(), reference.boundary())
                        discarded = ring.reject_suffix(tickets[miss])
                        self.assertEqual(discarded, tuple(t.identity for t in tickets[miss:]))
                        self.assertEqual(ring.restores, 1)
                        self.assertEqual(ring.boundary(), reference.boundary())
                        for i in range(miss, capacity):
                            verified(ring, truth[i]); verified(reference, truth[i])
                        self.assertEqual(ring.boundary(), reference.boundary())

    def test_later_matching_guess_cannot_survive_earlier_miss(self):
        ring = Ring(first=True)
        a, b = issue(ring, 8, tentative=True), issue(ring, 9, tentative=True)
        self.assertEqual(ring.reject_suffix(a), (a.identity, b.identity))
        with self.assertRaises(ValueError): ring.accept(b, verified_token=9)
        with self.assertRaises(ValueError): ring.execute(b)
        verified(ring, 7); verified(ring, 9)
        self.assertEqual(ring.physical['history'], [7, 9])

    def test_wrong_parent_generation_order_and_capacity_fail_closed(self):
        ring = Ring()
        a, b = issue(ring, 8, tentative=True), issue(ring, 9, tentative=True)
        with self.assertRaisesRegex(ValueError, 'bounded'): issue(ring, 10, tentative=True)
        with self.assertRaisesRegex(ValueError, 'oldest'): ring.accept(b, verified_token=9)
        with self.assertRaisesRegex(ValueError, 'verified'): ring.accept(a, verified_token=7)
        with self.assertRaisesRegex(ValueError, 'oldest'): ring.reject_suffix(b)
        ring.reject_suffix(a)
        for parent, generation in ((a.identity, ring.generation), (ring.last_accepted, 0)):
            with self.assertRaises(ValueError): ring.execute(Ticket(9, parent, generation, 0, 3, True))

    def test_sticky_failure_never_rewound_by_rejection(self):
        ring = Ring()
        a = issue(ring, 8, tentative=True)
        ring.physical['error'] = 1
        before = deepcopy(ring.physical)
        with self.assertRaisesRegex(ValueError, 'sticky'): ring.reject_suffix(a)
        self.assertEqual(ring.physical, before)
        self.assertEqual(ring.pending[0].ticket, a)

    def test_final_stage_only_verified_input_and_output(self):
        ring = Ring(final=True)
        with self.assertRaisesRegex(ValueError, 'final'): issue(ring, 8, tentative=True)
        a = issue(ring, 8)
        ring.accept(a, verified_token=8, target_output=12)
        with self.assertRaisesRegex(ValueError, 'target output'): issue(ring, 9)
        b = issue(ring, 12)
        ring.accept(b, verified_token=12, target_output=4)
        self.assertEqual(ring.boundary()['history'], [8, 12])

    def test_eos_discards_entire_executed_unverified_suffix(self):
        ring, reference = Ring(first=True), Ring(first=True)
        verified(ring, 3); verified(reference, 3)
        a = issue(ring, 4, tentative=True); issue(ring, 5, tentative=True)
        with self.assertRaises(ValueError): ring.boundary()
        ring.reject_suffix(a)
        self.assertEqual(ring.boundary(), reference.boundary())


if __name__ == '__main__':
    unittest.main()
