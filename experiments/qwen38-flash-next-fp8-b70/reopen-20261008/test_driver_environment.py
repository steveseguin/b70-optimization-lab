"""CPU-only NEO environment, conditional prediction and receipt regressions."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import calibration
import memory_plan as m
import screen


class DriverEnvironmentTests(unittest.TestCase):
    def command(self, mode='mtp1'):
        return screen.launch(SimpleNamespace(mode=mode, port=19988), Path('/tmp/unused-screen1b'))

    def test_all_modes_pin_both_values_despite_host_environment(self):
        with patch.dict(os.environ, {'NEOReadDebugKeys': '0', 'EnableDeferBacking': '1'}):
            for mode in ('mtp0', 'mtp1', 'mtp3', 'calibrate-load'):
                with self.subTest(mode=mode):
                    cmd = self.command(mode)
                    identity = m.launch_identity(cmd)
                    self.assertEqual(identity['driver_environment'], {
                        'NEOReadDebugKeys': ['1'], 'EnableDeferBacking': ['0']})
                    self.assertEqual(cmd.count('NEOReadDebugKeys=1'), 1)
                    self.assertEqual(cmd.count('EnableDeferBacking=0'), 1)
                    self.assertEqual(cmd[cmd.index('NEOReadDebugKeys=1')-1], '-e')
                    self.assertEqual(cmd[cmd.index('EnableDeferBacking=0')-1], '-e')

    def test_receipt_identity_keeps_driver_settings_and_matches_calibration(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name in ('config.json', 'model.safetensors.index.json'):
                (root/name).write_text('{}')
            a = calibration.identity(self.command(), screen.HERE, root)
            b = calibration.identity(self.command('calibrate-load'), screen.HERE, root)
            self.assertEqual(a, b)
            cmd = self.command()
            cmd[cmd.index('EnableDeferBacking=0')] = 'EnableDeferBacking=1'
            self.assertNotEqual(a, calibration.identity(cmd, screen.HERE, root))

    def test_credit_requires_both_explicit_unambiguous_values(self):
        contract = json.loads((m.HERE/'memory-contract.json').read_text())
        original = self.command()
        scenario, adjustment = m.adapter_scenario(contract, m.launch_identity(original))
        self.assertEqual(adjustment['subtracted_shadow_bytes'], 52_260_388_864)
        self.assertEqual(scenario['historical_unattributed_residual_bytes'], 0)
        self.assertEqual(scenario['runtime_difference_contingency_bytes'], 10_000_000_000)
        variants = []
        for key in ('NEOReadDebugKeys=1', 'EnableDeferBacking=0'):
            cmd = original.copy(); i = cmd.index(key); del cmd[i-1:i+1]; variants.append(cmd)
            cmd = original.copy(); cmd[cmd.index(key)] = key.split('=')[0] + '=wrong'; variants.append(cmd)
        variants.append(original + ['-e', 'EnableDeferBacking=1'])
        variants.append(original + ['-e', 'EnableDeferBacking=0'])
        for cmd in variants:
            with self.subTest(command=cmd):
                s, a = m.adapter_scenario(contract, m.launch_identity(cmd))
                self.assertEqual(a['subtracted_shadow_bytes'], 0)
                self.assertEqual(s['historical_unattributed_residual_bytes'], 52_260_388_864)

    def test_credit_cannot_subtract_real_host_buffers(self):
        contract = json.loads((m.HERE/'memory-contract.json').read_text())
        contract['deferred_backing_shadow_credit_bytes'] += 1
        with self.assertRaisesRegex(ValueError, 'exceeds historical residual'):
            m.adapter_scenario(contract, m.launch_identity(self.command()))

    def test_entrypoint_refuses_missing_or_wrong_values_before_any_runtime(self):
        for env in ({}, {'NEOReadDebugKeys':'1'}, {'EnableDeferBacking':'0'},
                    {'NEOReadDebugKeys':'0','EnableDeferBacking':'0'},
                    {'NEOReadDebugKeys':'1','EnableDeferBacking':'1'}):
            with self.subTest(env=env):
                result = subprocess.run(['/bin/bash', str(screen.HERE/'container-entrypoint.sh'),
                                         '--execute', 'serve', '/model'], env=env,
                                        capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 2)
                self.assertIn('requires NEOReadDebugKeys=1 EnableDeferBacking=0', result.stderr)

    def test_entrypoint_accepts_pair_then_reaches_existing_guard(self):
        result = subprocess.run(['/bin/bash', str(screen.HERE/'container-entrypoint.sh'),
                                 '--execute', 'serve', '/model'],
                                env={'NEOReadDebugKeys':'1','EnableDeferBacking':'0'},
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Screen 1b guard must be enabled', result.stderr)


if __name__ == '__main__': unittest.main()
