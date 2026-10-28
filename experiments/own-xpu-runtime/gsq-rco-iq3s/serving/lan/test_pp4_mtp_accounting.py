"""CPU-only accounting test using minimal structure retained from the real seam."""
import json
from pathlib import Path
import unittest
import pp4_backend as backend


class MtpAccountingTests(unittest.TestCase):
    def test_real_seam_committed_proposals_not_issued_minus_rejected(self):
        fixture = Path(__file__).resolve().parents[3] / 'research/pp4-review-2026-10-28/seam-screen/mtp-structural-fixture.json'
        result = backend.mtp_accounting(json.loads(fixture.read_text()))
        self.assertEqual((result['guesses'], result['hits'], result['misses'],
                          result['unverified_discarded']), (142, 81, 26, 35))
        self.assertEqual(result['guesses'], result['hits'] + result['misses'] + result['unverified_discarded'])
