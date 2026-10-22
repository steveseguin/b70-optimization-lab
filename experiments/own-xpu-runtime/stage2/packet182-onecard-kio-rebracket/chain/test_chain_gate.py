"""chain_gate.py on real retained summaries and on the packet176 bracket numbers (CPU only)."""
import copy, json, tempfile, unittest
from pathlib import Path

import chain_gate as C

S = Path(__file__).resolve().parents[2]
AS = S / 'packet58as-onecard-spinwait/screen/evidence/card0-58as-v5-a/resident/WSCREEN/summary.json'
CQ = S / 'packet171b-onecard-cqcopy/screen/evidence/card0-171b-v5-a/resident/WSCREEN/summary.json'
P176_RATES = [34.20898070237056, 35.98180647418397, 34.62115621015788, 35.98079731582723, 34.64021031336306]


def with_rates(src, rates, gain, beats=True):
    s = json.loads(Path(src).read_text())
    s = copy.deepcopy(s)
    s.update(rates=rates, minimum_gain_vs_best_control=gain, candidate_beats_all_controls=beats,
             control_drift_passed=True, control_drift_fraction=0.00055, passed=True, device_executed=True)
    return s


class ChainGate(unittest.TestCase):
    def write(self, row):
        d = tempfile.mkdtemp()
        p = Path(d) / 'summary.json'
        p.write_text(json.dumps(row))
        return p

    @unittest.skipUnless(AS.is_file(), 'packet58as summary required')
    def test_packet176_numbers_chain(self):
        # Real 60 exact requests of the 58as bracket with packet176's measured rates and gain.
        out = C.decide(self.write(with_rates(AS, P176_RATES, 0.03870031360482287)))
        self.assertTrue(out.startswith('CHAIN '), out)

    @unittest.skipUnless(AS.is_file(), 'packet58as summary required')
    def test_packet58as_record_bracket_does_not_chain_again(self):
        # +8.58% over its poll controls, but its B views (34.577/34.568) are the record itself.
        out = C.decide(AS)
        self.assertTrue(out.startswith('NOCHAIN') and '1.02 x record' in out, out)

    @unittest.skipUnless(CQ.is_file(), 'packet171b summary required')
    def test_packet171b_neutral_does_not_chain(self):
        out = C.decide(CQ)
        self.assertTrue(out.startswith('NOCHAIN') and 'v5 gate failed' in out, out)

    @unittest.skipUnless(AS.is_file(), 'packet58as summary required')
    def test_below_two_percent_does_not_chain(self):
        rates = [34.2, 35.30, 34.62, 35.31, 34.64]
        out = C.decide(self.write(with_rates(AS, rates, 0.0193)))
        self.assertTrue(out.startswith('NOCHAIN') and 'below +2%' in out, out)

    @unittest.skipUnless(AS.is_file(), 'packet58as summary required')
    def test_inexact_request_does_not_chain(self):
        row = with_rates(AS, P176_RATES, 0.0387)
        row['views'][3]['requests'][5]['exact_oracle'] = False
        out = C.decide(self.write(row))
        self.assertTrue(out.startswith('NOCHAIN') and 'exact' in out, out)


if __name__ == '__main__':
    unittest.main()
