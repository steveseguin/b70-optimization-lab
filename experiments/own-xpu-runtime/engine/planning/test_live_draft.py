import hashlib
import unittest
from live_draft import HEADER, MAGIC, VERSION, decode, bind, CanonicalSequence


def pair(position=0, head=0, next_token=-1, seq=2):
    raw = bytes(range(16))
    header = HEADER.pack(MAGIC, VERSION, len(raw), position, 3, 4, seq-1, seq,
                         7, next_token, head, 0, hashlib.sha256(raw).hexdigest().encode())
    return decode(header, raw, stream_bytes=16, stages=4, vocab=97)


class LiveDraftTests(unittest.TestCase):
    def test_copy_is_owned_and_bound_to_commit(self):
        h = pair()
        raw = bytearray(h.hidden)
        owned = decode(bytearray(h.header), raw, stream_bytes=16, stages=4, vocab=97)
        raw[0] ^= 255
        self.assertEqual(owned.hidden, h.hidden)
        self.assertIs(bind(h, position=0, input_token=7, row_ticket=1,
                           commit_sequence=2, output_token=None, fixture=0), h)
        with self.assertRaisesRegex(ValueError, 'commit'):
            bind(h, position=0, input_token=7, row_ticket=1,
                 commit_sequence=3, output_token=None, fixture=0)

    def test_corruption_extent_role_and_uncommitted_handoff_refused(self):
        h = pair()
        for index, value in ((0, 0), (2, 20), (4, 2), (7, 1), (10, 2), (11, 1)):
            values = list(HEADER.unpack(h.header)); values[index] = value
            with self.subTest(index=index), self.assertRaises(ValueError):
                decode(HEADER.pack(*values), h.hidden, stream_bytes=16, stages=4, vocab=97)
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            decode(h.header, bytes(16), stream_bytes=16, stages=4, vocab=97)

    def test_prompt_bootstrap_head_independent_of_target_head(self):
        s = CanonicalSequence(97)
        request = s.begin(pair(), 9, head=True)
        self.assertEqual(request, dict(op=23, token=9, position=1, fixture=1))
        s.complete(21)
        self.assertEqual(s.proposal(2), 21)
        self.assertIsNone(s.proposal(1))

    def test_contiguous_true_pairs_no_skip_duplicate_or_guessed_input(self):
        s = CanonicalSequence(97)
        s.begin(pair(), 9, head=False)
        with self.assertRaises(ValueError): s.begin(pair(), 9, head=False)
        s.complete(-1)
        with self.assertRaises(ValueError): s.complete(-1)
        with self.assertRaises(ValueError): s.begin(pair(), 9, head=False)
        with self.assertRaises(ValueError): s.begin(pair(2, 1, 25, 6), 25, head=True)
        h = pair(1, 1, 25, 4)
        with self.assertRaisesRegex(ValueError, 'unverified'): s.begin(h, 26, head=True)
        s.begin(h, 25, head=True)
        with self.assertRaisesRegex(ValueError, 'bounds'): s.complete(-1)
        s.complete(71)
        self.assertEqual(s.proposal(3), 71)


if __name__ == '__main__':
    unittest.main()
