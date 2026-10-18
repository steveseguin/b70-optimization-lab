"""CPU tests for micro admission, exact winner, and both direction boundaries."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from screen_jobs import jobs, command, choose, winner, lanes, DIRECTIONS, WRAPPER, P, VIEWS, candidates
from compare import confirmed, compare_direction


def metric(choice, rate):
    return dict(choice=choice, rate=rate, exact=True, acceptance_counts=[(100, 127)] * 12)


class ScreenTest(unittest.TestCase):
    def test_grids(self):
        for selected in (VIEWS[1:], (VIEWS[1],), (VIEWS[2],)):
            for direction in DIRECTIONS:
                source, other = lanes(direction)
                self.assertEqual([row['choice'] for row in jobs(source, direction=direction, qualified=selected)],
                                 ['production', *selected, 'production'])
                for choice in selected:
                    rows = jobs(other, choice, direction, selected)
                    self.assertEqual([row['choice'] for row in rows], ['production', choice, 'production'])
                    for row in rows:
                        cmd = command(row, other, plan=True)
                        self.assertEqual(cmd[2], str(WRAPPER / 'screen.py'))
                        self.assertEqual(row['placement'], '1')
                        self.assertIn('--plan', cmd)
                        self.assertNotIn('--authorized-device-window', cmd)
        for invalid in ((), ('unknown',), ('head-plane', 'head-plane'), tuple(reversed(VIEWS[1:]))):
            with self.assertRaises(ValueError):
                candidates(invalid)
        with self.assertRaises(ValueError):
            jobs('A', 'head-transpose', 'B-grid', ('head-plane',))

    def test_winner_refusals(self):
        rows = [metric(choice, rate) for choice, rate in zip((*VIEWS, 'production'), (40, 42, 43, 41))]
        self.assertEqual(choose(rows)['choice'], 'head-transpose')
        for mutation in ('inexact', 'slow', 'missing', 'reordered', 'acceptance', 'nonfinite'):
            changed = [dict(row) for row in rows]
            if mutation == 'inexact': changed[2]['exact'] = False
            if mutation == 'slow': changed[-1]['rate'] = 45
            if mutation == 'missing': changed.pop()
            if mutation == 'reordered': changed[1], changed[2] = changed[2], changed[1]
            if mutation == 'acceptance': changed[1]['acceptance_counts'] = [(99, 127)] * 12
            if mutation == 'nonfinite': changed[1]['rate'] = float('nan')
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                choose(changed)

    def test_both_directions_and_micro_subsets(self):
        outputs = []
        for direction in DIRECTIONS:
            source, other = lanes(direction)
            grid = jobs(source, direction=direction)
            confirmation = jobs(other, 'head-transpose', direction)
            outputs.extend(row['out'] for row in grid + confirmation)
            def loaded(row, lane):
                self.assertIn('-' + direction + '-' + lane + '-', row['out'])
                return metric(row['choice'], {'production': 40, 'head-plane': 41, 'head-transpose': 42}[row['choice']])
            for selected in (VIEWS[1:], ('head-plane',), ('head-transpose',)):
                with patch('compare.load', side_effect=loaded), patch('compare.qualified_candidates', return_value=selected), patch('screen_jobs.qualified_candidates', return_value=selected):
                    best = 'head-transpose' if 'head-transpose' in selected else 'head-plane'
                    self.assertEqual(winner(direction)['choice'], best)
                    result = compare_direction(direction)
                    self.assertEqual(result['source_lane'], source)
                    self.assertEqual(result['confirmation_lane'], other)
                    self.assertEqual(result['winner']['choice'], best)
        self.assertEqual(len(outputs), len(set(outputs)))
        with self.assertRaises(ValueError): lanes('C-grid')

    def test_confirmation_refusals(self):
        grid = [metric(choice, rate) for choice, rate in zip((*VIEWS, 'production'), (40, 42, 43, 41))]
        baseline = [metric(choice, rate) for choice, rate in zip(('production', 'head-transpose', 'production'), (40, 43, 41))]
        self.assertEqual(confirmed(grid, baseline)['choice'], 'head-transpose')
        for mutation in ('different-winner', 'inexact', 'acceptance', 'slow-first', 'slow-last', 'missing', 'nonfinite'):
            rows = [dict(row) for row in baseline]
            if mutation == 'different-winner': rows[1]['choice'] = 'head-plane'
            if mutation == 'inexact': rows[0]['exact'] = False
            if mutation == 'acceptance': rows[1]['acceptance_counts'] = [(99, 127)] * 12
            if mutation == 'slow-first': rows[0]['rate'] = 43
            if mutation == 'slow-last': rows[-1]['rate'] = 44
            if mutation == 'missing': rows.pop()
            if mutation == 'nonfinite': rows[1]['rate'] = float('nan')
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                confirmed(grid, rows)

    def test_missing_micro_refuses_before_launch(self):
        import run_screens
        for lane in ('A', 'B'):
            argv = ['run_screens.py', '--lane', lane, '--run', '--authorized-device-window', '--fault-review', 'unused']
            with patch('sys.argv', argv), patch.object(run_screens, 'verify'), patch.object(run_screens, 'qualified_candidates', side_effect=ValueError('micro pending')), patch.object(run_screens, 'lane_gate') as gate, patch.object(run_screens.subprocess, 'Popen') as launch:
                with self.assertRaisesRegex(ValueError, 'micro pending'): run_screens.main()
                gate.assert_not_called()
                launch.assert_not_called()

    def test_plan_overrides_run_without_micro_or_device(self):
        import run_screens
        argv = ['run_screens.py', '--lane', 'B', '--run', '--plan']
        result = subprocess.CompletedProcess([], 0, '{}', '')
        with patch('sys.argv', argv), patch.object(run_screens, 'verify'), patch.object(run_screens, 'cpu_gate'), patch.object(run_screens, 'lane_gate') as device_gate, patch.object(run_screens, 'qualified_candidates') as micro, patch.object(run_screens.subprocess, 'run', return_value=result) as plan, patch('builtins.print') as output:
            self.assertEqual(run_screens.main(), 0)
            micro.assert_not_called()
            device_gate.assert_not_called()
            self.assertEqual(plan.call_count, 4)
            document = json.loads(output.call_args.args[0])
            self.assertFalse(document['runnable'])
            self.assertFalse(document['device_executed'])
            for call in plan.call_args_list:
                self.assertIn('--plan', call.args[0])
                self.assertNotIn('--authorized-device-window', call.args[0])

    def test_driver_rechecks_winner(self):
        import run_screens
        for direction in DIRECTIONS:
            _, other = lanes(direction)
            argv = ['run_screens.py', '--lane', other, '--direction', direction, '--run', '--authorized-device-window', '--fault-review', 'unused']
            with patch('sys.argv', argv), patch.object(run_screens, 'lane_gate'), patch.object(run_screens, 'verify'), patch.object(run_screens, 'qualified_candidates', return_value=VIEWS[1:]), patch.object(run_screens.screen, 'unit_gate'), patch.object(run_screens.screen, 'unit_conditions'), patch.object(run_screens, 'winner', side_effect=[{'choice': 'head-transpose'}, {'choice': 'head-plane'}]), patch.object(run_screens.subprocess, 'Popen') as launch:
                with self.assertRaisesRegex(ValueError, 'confirmation selection differs'): run_screens.main()
                launch.assert_not_called()

    def test_proposals(self):
        queue = P.parents[1] / 'ops/lane-queue'
        for label, lane, direction in (('B-grid', 'B', 'B-grid'), ('A-confirm', 'A', 'B-grid'), ('A-grid', 'A', 'A-grid'), ('B-confirm', 'B', 'A-grid')):
            row = json.loads((queue / f'proposed-p93-{label}.txt').read_text())
            self.assertEqual(row['lane'], lane)
            args = row['argv']
            self.assertEqual(args[args.index('--direction') + 1], direction)
            self.assertIn('--run', args)
            self.assertIn('{REVIEW}', args)


if __name__ == '__main__':
    unittest.main()
