"""Planning must exercise the live policy without taking a device lease."""
import unittest
from unittest.mock import patch

import lane_admission as admission
import screen


class PlanAdmissionTests(unittest.TestCase):
    def test_screen_scopes_match_live_reservation(self):
        for lane in ('A', 'B'):
            self.assertEqual(admission.admission_scope(lane, 'screen'),
                             admission.Reservation(lane, window='screen').scope)
            self.assertEqual(admission.admission_scope(lane, 'screen'), 'lane-' + lane)

    def test_timing_still_holds_whole_host(self):
        self.assertEqual(admission.admission_scope('A', 'WS128'), 'whole-host')
        self.assertEqual(admission.admission_scope('A', 'screen', timing_claim=True),
                         'whole-host')
        with self.assertRaisesRegex(ValueError, 'unregistered window policy'):
            admission.admission_scope('A', 'unknown')

    def test_plan_catches_missing_screen_registration_before_inputs_or_lease(self):
        argv = ['--lane', 'A', '--lineage', '/unused', '--output', '/unused', '--plan']
        with patch.object(admission, 'EXACT_WINDOWS', admission.EXACT_WINDOWS - {'screen'}), \
             patch.object(screen, 'cpu_gate'), patch.object(screen, 'sealed') as sealed, \
             patch.object(screen, 'Reservation') as lease:
            with self.assertRaisesRegex(ValueError, 'unregistered window policy'):
                screen.main(argv)
            sealed.assert_not_called()
            lease.assert_not_called()


if __name__ == '__main__':
    unittest.main()
