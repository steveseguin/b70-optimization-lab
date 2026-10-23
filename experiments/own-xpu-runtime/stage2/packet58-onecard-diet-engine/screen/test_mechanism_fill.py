"""Packet182 fill-split readout: synthetic arithmetic plus the real packet171b spin streams."""
import json
import tempfile
import unittest
from pathlib import Path

import mechanism as M

P = Path(__file__).resolve().parent
REAL = P.parents[1] / 'packet171b-onecard-cqcopy/screen/evidence/card0-171b-v5-a/resident/WSCREEN/run/run'


def write_run(root, views):
    """views: label -> list of (wall, transfer, fill_mb_submitted_this_position)."""
    run = root / 'run'
    (root / 'suite-inputs.tsv').write_text('p0 /dev/null\n')
    cache, position, total = [], 1, 0
    for label, tokens in views.items():
        d = run / label / 'p0'
        d.mkdir(parents=True)
        (d / 'prefill-timings.jsonl').write_text('')
        rows = []
        for i, (wall, transfer, fill) in enumerate(tokens):
            total += int(fill * 1e6)
            cache.append(dict(position=position, state=2 if fill else 1, fill_bytes_total=total))
            position += 1
            rows.append(json.dumps(dict(kind='generated_token', generated_index=i, wall_ms=wall, transfer_wall_ms=transfer,
                                        wait_ms=wall - 5, enqueue_loop_ms=5.0, foreground_io='copy', copy_counts=[])))
        (d / 'timings.jsonl').write_text('\n'.join(rows) + '\n')
    (run / 'cache.jsonl').write_text('\n'.join(json.dumps(c) for c in cache) + '\n')
    return run


class FillSplit(unittest.TestCase):
    def test_synthetic_split_and_ceiling(self):
        # Alternate filled (60 MB, +2.0 ms transfer, +0.6 ms elsewhere) and unfilled tokens.
        tokens = [(27.0, 0.1, 0.0), (27.0, 0.1, 0.0)]
        for i in range(40):
            tokens.append((29.6, 2.1, 60.0) if i % 2 else (27.0, 0.1, 0.0))
        with tempfile.TemporaryDirectory() as tmp:
            run = write_run(Path(tmp), {'A0': tokens, 'B0': tokens, 'A1': tokens, 'B1': tokens, 'A2': tokens})
            r = M.readout(run, ['A0', 'B0', 'A1', 'B1', 'A2'])
        s = r['views']['A1']['fill_split']
        self.assertTrue(s['available'])
        self.assertAlmostEqual(s['means']['transfer_wall_ms']['filled_minus_unfilled'], 2.0, places=4)
        self.assertAlmostEqual(s['fill_attributable_outside_transfer_ms_per_filled_token'], 0.6, places=4)
        self.assertAlmostEqual(s['fill_attributable_outside_transfer_ms_per_token'], 0.6 * 20 / 40, places=3)
        self.assertIn('A1', r['fill_lever_price']['views'])
        # Original packet176 fields stay present and unchanged in meaning.
        self.assertIn('wall_ms_per_fill_mb', r['views']['A1'])
        self.assertIn('verdict', r)

    def test_no_unfilled_tokens_reports_unavailable(self):
        tokens = [(27.0, 0.1, 0.0), (27.0, 0.1, 0.0)] + [(29.0, 2.0, 60.0)] * 6
        with tempfile.TemporaryDirectory() as tmp:
            run = write_run(Path(tmp), {'A0': tokens})
            r = M.readout(run, ['A0'])
        self.assertFalse(r['views']['A0']['fill_split']['available'])

    @unittest.skipUnless((REAL / 'cache.jsonl').is_file(), 'packet171b real streams required')
    def test_real_packet171b_streams(self):
        r = M.readout(REAL, ['A0', 'B0', 'A1', 'B1', 'A2'])
        a1 = r['views']['A1']
        # packet176 readout fields reproduce on the real spin streams.
        self.assertAlmostEqual(a1['slow_readback_fraction'], 0.4009, places=4)
        self.assertAlmostEqual(a1['readback_ms_per_fill_mb'], 0.03488, places=5)
        self.assertAlmostEqual(a1['wall_ms_per_fill_mb'], 0.06656, places=5)
        s = a1['fill_split']
        self.assertEqual((s['filled_tokens'], s['unfilled_tokens']), (760, 764))
        # The same ~0.032 ms/MB outside-transfer slope appears on unfilled tokens vs the NEXT fill: miss intensity, not fill cost.
        inside, control = s['outside_transfer_ms_per_fill_mb_filled_tokens'], s['control_unfilled_outside_transfer_ms_per_next_fill_mb']
        self.assertLess(abs(inside - control), 0.002)
        # Filled-token excess outside the transfer window is ~0.63 ms -> ~0.31 ms/token -> ~1.1% of wall on every view.
        for label, price in r['fill_lever_price']['views'].items():
            self.assertLess(price['ceiling_fraction_of_wall'], 0.012, label)
            self.assertGreater(price['ceiling_ms_per_token'], 0.25, label)
        # packet176's moved_rule fires on 171b too (nothing moved there): it cannot identify a fill cost.
        self.assertTrue(r['fill_cost_moved'])


if __name__ == '__main__':
    unittest.main()
