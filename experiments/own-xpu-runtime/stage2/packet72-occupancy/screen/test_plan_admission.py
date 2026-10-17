"""Plan the actual entry point against real admission, without taking leases."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import lane_admission as admission
import screen


class PlanAdmissionTests(unittest.TestCase):
    def plan(self, lane):
        with tempfile.TemporaryDirectory() as tmp, contextlib.ExitStack() as stack:
            here = Path(tmp)
            stack.enter_context(patch.object(screen, 'HERE', here))
            stack.enter_context(patch.object(screen, 'cpu_gate'))
            stack.enter_context(patch.object(screen, 'sealed', return_value={
                'placement': {'supported': True}}))
            stack.enter_context(patch.object(screen.D, 'oracle_inputs', return_value={
                'prompts': [{'prompt_id': 'incident-retrospective'}]}))
            # Planning must never acquire any lease, even on an admitted lane.
            stack.enter_context(patch.object(admission.Reservation, '__enter__',
                                            side_effect=AssertionError('plan acquired lease')))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(screen.main([
                    '--plan', '--lane', lane, '--lineage', str(here / 'lineage'),
                    '--output', str(here / 'evidence/fresh')]), 0)
            self.assertEqual(list(here.iterdir()), [])
            return json.loads(output.getvalue())

    def test_real_policy_for_both_job_lanes(self):
        for lane in ('A', 'B'):
            self.assertEqual(self.plan(lane)['reservation_scope'], 'lane-' + lane)

    def test_old_policy_fails_planning(self):
        with patch.object(admission, 'EXACT_WINDOWS', admission.EXACT_WINDOWS - {'screen'}):
            with self.assertRaisesRegex(ValueError, 'unregistered window policy'):
                self.plan('A')

    def test_timing_scope_and_unknown_policy_stay_closed(self):
        self.assertEqual(admission.Reservation('A', window='screen', timing_claim=True).scope,
                         'whole-host')
        self.assertEqual(admission.Reservation('A', window='WS128').scope, 'whole-host')
        with self.assertRaisesRegex(ValueError, 'unregistered window policy'):
            admission.Reservation('A', window='unregistered')


if __name__ == '__main__':
    unittest.main()
