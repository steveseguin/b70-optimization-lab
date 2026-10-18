"""CPU-only refusal and planning tests; never opens an accelerator."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import run_micro as runner


class MicroRunnerTest(unittest.TestCase):
    def test_runner_and_gate_use_fresh_b2(self):
        import micro_gate
        self.assertEqual(runner.OUTPUT, runner.P / micro_gate.MICRO_DIRECTORY)
        self.assertEqual(runner.OUTPUT.name, 'micro-B')

    def test_plan_never_enters_device_path(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(runner, 'OUTPUT', Path(tmp) / 'fresh'), patch.object(runner, 'cpu_gate') as cpu, patch.object(runner, 'build_gate', return_value={'binary_sha256': 'test'}), patch.object(runner, 'lane_gate') as device, patch.object(runner, 'Reservation') as lease, patch.object(runner.subprocess, 'Popen') as launch, patch.object(runner, 'memory_admit') as memory, patch.object(runner, 'storage_admit') as storage, patch.object(runner.fault_review, 'validate') as review, patch('builtins.print') as output:
            self.assertEqual(runner.main(['--run', '--plan', '--lane', 'B']), 0)
            cpu.assert_called_once()
            for mock in (device, lease, launch, memory, storage, review):
                mock.assert_not_called()
            row = json.loads(output.call_args.args[0])
            self.assertFalse(row['device_executed'])
            self.assertFalse(row['runnable'])
            self.assertEqual(row['physical_cards'], [2])
            self.assertEqual(row['native_card'], 0)
            self.assertEqual(row['device_mask']['FilterBdfPath'], '0000:43:00.0')
            self.assertEqual(row['command'], [str(runner.BINARY), '--coordinator-admitted-device-window'])
            self.assertEqual(row['required_host_available_bytes'], 10 * runner.GIB)

    def test_host_admission_has_micro_budget(self):
        with patch.object(runner.M, 'meminfo', return_value={'MemAvailable': 10 * runner.GIB}):
            self.assertEqual(runner.memory_admit()['required_bytes'], 10 * runner.GIB)
        with patch.object(runner.M, 'meminfo', return_value={'MemAvailable': 10 * runner.GIB - 1}):
            with self.assertRaisesRegex(ValueError, '10 GiB'): runner.memory_admit()
        with patch.object(runner.shutil, 'disk_usage', return_value=SimpleNamespace(free=12*runner.GIB-1)):
            with self.assertRaisesRegex(ValueError, 'root free'): runner.storage_admit()

    def test_run_refuses_missing_authorization_before_launch(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(runner, 'OUTPUT', Path(tmp) / 'fresh'), patch.object(runner, 'build_gate', return_value={}), patch.object(runner, 'lane_gate'), patch.object(runner, 'Reservation') as lease, patch.object(runner.subprocess, 'Popen') as launch:
            with self.assertRaisesRegex(ValueError, 'authorization'): runner.main(['--run'])
            lease.assert_not_called()
            launch.assert_not_called()

    def test_build_failure_refuses_before_admission(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(runner, 'OUTPUT', Path(tmp) / 'fresh'), patch.object(runner, 'build_gate', side_effect=ValueError('changed binary')), patch.object(runner, 'lane_gate') as gate, patch.object(runner.subprocess, 'Popen') as launch:
            with self.assertRaisesRegex(ValueError, 'changed binary'): runner.main(['--run'])
            gate.assert_not_called()
            launch.assert_not_called()

    def test_no_output_reuse(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(runner, 'OUTPUT', Path(tmp)), patch.object(runner, 'build_gate') as gate:
            with self.assertRaisesRegex(ValueError, 'fresh'): runner.main(['--plan'])
            gate.assert_not_called()

    def test_native_drain_and_full_shape_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'samples.jsonl'
            valid = dict(kind='summary', passed=True, drained=True, rows=640, columns=2560)
            path.write_text(json.dumps(valid) + '\n')
            self.assertEqual(runner.native_summary(path), valid)
            for key, value in (('drained', False), ('passed', False), ('rows', 17), ('kind', 'sample')):
                path.write_text(json.dumps(dict(valid, **{key: value})) + '\n')
                with self.subTest(key=key), self.assertRaises(ValueError): runner.native_summary(path)


if __name__ == '__main__':
    unittest.main()
