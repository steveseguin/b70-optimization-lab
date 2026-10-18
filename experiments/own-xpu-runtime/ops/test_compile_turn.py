"""CPU-only gate tests: temporary markers/proc and lock, no live writes."""
import fcntl
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

import compile_turn as gate


class CompileTurnTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.owner = dict(scope='whole-host', lane='A', pid=100, start_ticks=50)
        self.rows = {100: dict(comm='python3', ppid=1, start_ticks=50),
                     200: dict(comm='python3', ppid=1, start_ticks=60),
                     201: dict(comm='own-rt-iq3', ppid=200, start_ticks=61)}

    def marker(self, name, row):
        (self.root / name).write_text(json.dumps(row))

    def hold(self):
        self.marker('hold-lane-B', self.owner)
        self.marker('active-lane-A.json', self.owner)
        self.marker('active-lane-B.json', dict(lane='B', pid=200))

    def test_26_minute_admission_wait_allows_compile_despite_b_device(self):
        self.hold()
        self.assertEqual(gate.whole_host_blockers(self.root, self.rows), [])

    def test_b_release_blocks_before_device_launch_and_through_drain(self):
        self.hold()
        (self.root / 'active-lane-B.json').unlink()
        self.assertEqual(gate.whole_host_blockers(self.root, self.rows), [(-1, 'hold-lane-B')])

    def test_own_device_child_blocks_even_with_b_marker(self):
        self.hold()
        self.rows[102] = dict(comm='own-rt-iq3', ppid=101, start_ticks=80)
        self.rows[101] = dict(comm='python3', ppid=100, start_ticks=70)
        self.assertTrue(gate.whole_host_blockers(self.root, self.rows))
        self.rows[100]['start_ticks'] = 51  # reused owner PID cannot own child
        self.assertEqual(gate.whole_host_blockers(self.root, self.rows), [])

    def test_lane_scoped_device_does_not_block(self):
        self.marker('active-lane-A.json', dict(self.owner, scope='lane-A'))
        self.rows[101] = dict(comm='own-rt-iq3', ppid=100, start_ticks=60)
        self.assertEqual(gate.whole_host_blockers(self.root, self.rows), [])

    def test_marker_release_race_and_malformed_hold_stay_conservative(self):
        self.marker('active-lane-A.json', self.owner)
        self.assertTrue(gate.whole_host_blockers(self.root, self.rows))
        self.hold()
        (self.root / 'hold-lane-B').write_text('{partial')
        self.assertTrue(gate.whole_host_blockers(self.root, self.rows))
        (self.root / 'hold-lane-B').unlink()
        (self.root / 'hold-lane-B').symlink_to(self.root / 'missing')
        self.assertTrue(gate.whole_host_blockers(self.root, self.rows))

    def test_foreign_compiler_detection_preserved(self):
        self.rows[300] = dict(comm='icpx', ppid=1, start_ticks=100)
        self.rows[301] = dict(comm='ninja', ppid=1, start_ticks=100)
        with patch.object(gate, 'process_table', return_value=self.rows), \
             patch.object(gate, 'COORD', self.root):
            self.assertEqual(gate.active(), [(300, 'icpx'), (301, 'ninja')])

    def test_process_table_handles_parentheses_zombies_and_disappeared_pid(self):
        for pid, state in ((10, 'S'), (11, 'Z'), (12, 'X')):
            p = self.root / str(pid)
            p.mkdir()
            (p / 'comm').write_text('own-rt-iq3\n')
            (p / 'stat').write_text(f'{pid} (name with ) parentheses) {state} 1 ' +
                                    '0 ' * 17 + '1234 0\n')
        (self.root / '13').mkdir()
        self.assertEqual(gate.process_table(self.root), {
            10: dict(comm='own-rt-iq3', ppid=1, start_ticks=1234)})

    def test_serial_lock_limits_and_exception_release(self):
        lock = self.root / 'compile.lock'
        calls = []
        module = types.SimpleNamespace(limits=lambda: calls.append('limits'))
        with patch.object(gate, 'LOCK', lock), patch.object(gate, 'active', return_value=[]), \
             patch.dict('sys.modules', build_engine=module):
            with self.assertRaisesRegex(ValueError, 'build failed'):
                with gate.turn():
                    self.assertEqual(calls, ['limits'])
                    with lock.open('a+') as other:
                        with self.assertRaises(BlockingIOError):
                            fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    raise ValueError('build failed')
            with lock.open('a+') as other:
                fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_timeout_never_runs_limits_or_body(self):
        with patch.object(gate, 'LOCK', self.root / 'compile.lock'), \
             patch.object(gate, 'active', return_value=[(42, 'icpx')]), \
             patch.object(gate.time, 'monotonic', side_effect=[0, 3601]), \
             patch.object(gate.time, 'sleep') as sleep:
            with self.assertRaises(TimeoutError):
                with gate.turn():
                    self.fail('timed out turn entered')
            sleep.assert_not_called()

    def test_poll_then_limits_failure_never_enters_body(self):
        def limits():
            raise RuntimeError('safety limit')
        with patch.object(gate, 'LOCK', self.root / 'compile.lock'), \
             patch.object(gate, 'active', side_effect=[[(42, 'icpx')], []]), \
             patch.object(gate.time, 'sleep') as sleep, \
             patch.dict('sys.modules', build_engine=types.SimpleNamespace(limits=limits)):
            with self.assertRaisesRegex(RuntimeError, 'safety limit'):
                with gate.turn():
                    self.fail('limits failed')
            sleep.assert_called_once_with(10)


if __name__ == '__main__':
    unittest.main()
