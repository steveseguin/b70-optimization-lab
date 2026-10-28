"""CPU-only launcher path ownership regression; never starts native workers."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import pp4_start as start


class ExecReached(Exception):
    pass


class StartTests(unittest.TestCase):
    def exercise(self, qualification=False, occupy=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            def mapped_path(value):
                if str(value).startswith('/dev/shm/sc117-pp4-262k-'):
                    return root / 'controls'
                return Path(value)
            def planner(command, check):
                self.assertTrue(check)
                config = json.loads(Path(command[command.index('--config')+1]).read_text())
                output = Path(config['output'])
                self.assertFalse(output.exists())
                plan = Path(command[command.index('--plan')+1])
                self.assertEqual(plan.parent, output.parent)
                self.assertNotEqual(plan.parent, output)
                plan.write_text(json.dumps(config))
                if occupy:
                    output.mkdir()
            def execute(executable, command):
                self.assertIn('--run', command)
                plan_path = Path(command[command.index('--plan')+1])
                plan = json.loads(plan_path.read_text())
                output = Path(plan['output'])
                self.assertFalse(output.exists())
                self.assertTrue((output.parent/'admission.json').is_file())
                self.assertTrue((output.parent/'baseline.json').is_file())
                self.assertEqual(output.parent.stat().st_mode & 0o777, 0o700)
                raise ExecReached()
            args = ['pp4_start.py', '--unit', 'test.service']
            if qualification:
                args.append('--qualification')
            with mock.patch.object(start, 'Path', side_effect=mapped_path), \
                 mock.patch.object(start.subprocess, 'run', side_effect=planner), \
                 mock.patch.object(start, 'load', return_value=mock.Mock(observe=lambda: {'cpu_fixture': True})), \
                 mock.patch.object(start.os, 'execv', side_effect=execute) as execv, \
                 mock.patch.dict(os.environ, SC117_PP4_SERVICE='1', SC117_CONTEXT='262144'), \
                 mock.patch.object(start.sys, 'argv', args):
                if occupy:
                    with self.assertRaisesRegex(Exception, 'remain absent'):
                        start.main()
                    execv.assert_not_called()
                else:
                    with self.assertRaises(ExecReached):
                        start.main()
                    execv.assert_called_once()

    def test_measured_output_absent_at_exec(self):
        self.exercise()

    def test_qualification_output_absent_at_exec(self):
        self.exercise(qualification=True)

    def test_output_created_during_planning_refuses_exec(self):
        self.exercise(occupy=True)


if __name__ == '__main__':
    unittest.main()
