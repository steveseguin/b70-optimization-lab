#!/usr/bin/env python3
"""CPU checks for cycle labeling, command union and conditional projections."""
import unittest
import timeline as t


def command(rank, op, pos, start, end, spec=False):
    return dict(rank=rank, op=op, position=pos, speculative=spec,
                sent=start, rank_received=start, rank_completed=end)


def receipt():
    def draft(pos, hit, stamp):
        return dict(position=pos, hit=hit, target_completed_monotonic=stamp,
                    draft_wall_ms=2.0, rank0_idle_waiting_for_guess_ms=0.01)
    return dict(generated_token_completion_timestamps=[1.,1.020,1.055],
      draft_rows=[draft(10,True,1.),draft(11,False,1.020),draft(12,None,1.055)],
      rank_trace=[command(1,9,10,1.,1.002),command(1,1,10,1.002,1.019),
                  command(0,1,11,1.002,1.020,True),
                  command(1,9,11,1.020,1.022),command(0,3,11,1.020,1.021,True),
                  command(0,1,11,1.021,1.035),command(1,1,11,1.035,1.055)])


class TimelineTests(unittest.TestCase):
    def test_clipped_union(self):
        self.assertAlmostEqual(t.union_ms([(0,2),(1,3),(3,4),(6,8)],1,7),4000)

    def test_previous_guess_labels_next_interval(self):
        cycles=t.extract(receipt())
        self.assertTrue(cycles[0]['hit'])
        self.assertFalse(cycles[1]['hit'])
        self.assertAlmostEqual(cycles[0]['cycle_ms'],20)
        self.assertAlmostEqual(cycles[1]['cycle_ms'],35)
        self.assertAlmostEqual(cycles[1]['R_ms'],1)
        self.assertAlmostEqual(cycles[1]['A_ms'],14)

    def test_terminal_cycle_has_no_invented_speculative_half(self):
        cycles=t.extract(receipt())
        self.assertIsNone(cycles[-1]['S_ms'])
        self.assertEqual(t.summarize(cycles)['counts']['full_model_cycles'],1)

    def test_missing_correction_is_rejected(self):
        r=receipt();r['rank_trace']=[x for x in r['rank_trace'] if x['op']!=3]
        with self.assertRaises(ValueError):t.extract(r)

    def test_duplicate_command_is_rejected(self):
        r=receipt();r['rank_trace'].append(r['rank_trace'][0])
        with self.assertRaises(ValueError):t.extract(r)

    def test_draft_saving_hidden_on_miss(self):
        c=dict(hit=False,D_wall_ms=2,S_ms=16,B_ms=15,R_ms=1.6,A_ms=14.7)
        self.assertAlmostEqual(t.model(c),32.3)
        self.assertAlmostEqual(t.model(c,draft=0),32.3)
        c['hit']=True
        self.assertAlmostEqual(t.model(c)-t.model(c,draft=0),2)

    def test_host_uncovered_is_not_wait_or_gpu_idle(self):
        c=t.extract(receipt())[0]
        self.assertAlmostEqual(c['rank0_host_uncovered_ms'],2)
        self.assertAlmostEqual(c['rank1_host_uncovered_ms'],1)


if __name__=='__main__':unittest.main()
