import json
import math
import unittest
from bundle_selection import VIEWS, ELIGIBLE, choices, P
from screen_jobs import jobs, choose, command, WRAPPER


class ScreenTests(unittest.TestCase):
    def rows(self):
        return [dict(choice=c, exact=True, rate=r, acceptance=.78)
                for c, r in zip((*VIEWS, 'production'), (100, 100.2, 103, 100.5))]

    def test_both_lane_grids(self):
        for lane in ('A', 'B'):
            grid = jobs(lane)
            self.assertEqual([r['choice'] for r in grid], [*VIEWS, 'production'])
            self.assertEqual(len({r['out'] for r in grid}), 4)
            for row in grid:
                cmd = command(row, lane, plan=True)
                self.assertEqual(cmd[2], str(WRAPPER / 'screen.py'))
                self.assertNotIn('--authorized-device-window', cmd)

    def test_confirmation_only_real_candidate(self):
        for lane in ('A', 'B'):
            self.assertEqual([r['choice'] for r in jobs(lane, ELIGIBLE[0], 'confirm')],
                             ['production', 'rec-both-plus', 'production'])
            with self.assertRaises(ValueError):
                jobs(lane, 'rec-both', 'confirm')

    def test_winner(self):
        self.assertEqual(choose(self.rows())['choice'], 'rec-both-plus')

    def test_alias_cannot_win_on_noise(self):
        rows = self.rows()
        rows[1]['rate'] = 110
        with self.assertRaises(ValueError):
            choose(rows)

    def test_bad_screens_refuse(self):
        for mutation in ('inexact', 'missing', 'reordered', 'slow', 'nan', 'acceptance'):
            rows = self.rows()
            if mutation == 'inexact': rows[1]['exact'] = False
            if mutation == 'missing': rows.pop()
            if mutation == 'reordered': rows[1], rows[2] = rows[2], rows[1]
            if mutation == 'slow': rows[-1]['rate'] = 104
            if mutation == 'nan': rows[2]['rate'] = math.nan
            if mutation == 'acceptance': rows[1]['acceptance'] = math.nan
            with self.assertRaises(ValueError): choose(rows)

    def test_packet84_pins(self):
        self.assertEqual(choices('production'), json.loads((P/'selection.json').read_text())['choices'])
        for name in VIEWS:
            row = choices(name)
            self.assertEqual(row['hc_gate'], 'wide')
            self.assertEqual(row['host_retire'], 'ordered')
            self.assertEqual(row['experts'], 'wide64')
            self.assertEqual(row['hc_norm'], 'production')
            self.assertEqual(row['packed_dense'], 'production')
            self.assertEqual(row['route'], 'route-exp32-rank4')

    def test_original_arithmetic_body_and_alias(self):
        # The plus view changes the entry guard only. The complete token loop,
        # including both barriers/rounding between tokens, stays literal-identical.
        old = (P/'p82_recurrence.hpp').read_text()
        new = (P/'p82b_recurrence.hpp').read_text()
        begin = ' for(int r=0;r<s.tokens;++r) {'
        end = '\n}\n#endif'
        self.assertEqual(old.split(begin, 1)[1].split(end, 1)[0],
                         new.split(begin, 1)[1].split(end, 1)[0])
        parent = P.parent/'packet84-record-bundle'
        self.assertEqual((parent/'p82_recurrence.hpp').read_bytes(), (P/'p82_recurrence.hpp').read_bytes())
        submit = (P/'p49d_submit.cpp').read_text()
        self.assertIn('if(choice=="rec-both")return recurrence82<true>;', submit)
        self.assertIn('if(choice=="rec-parallel")return recurrence82<true>;', submit)


if __name__ == '__main__': unittest.main()
