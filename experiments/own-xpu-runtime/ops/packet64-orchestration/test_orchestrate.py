"""CPU-only mock orchestration and adversarial selection tests."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import orchestrate as o


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + '\n')


def fixture(root, speeds=((50, 52, 53), (60, 63, 62))):
    for lane, values in zip('AB', speeds):
        for choice, speed in zip(o.CHOICES, values):
            selection = root / o.PACKET / 'selections' / choice
            save(selection / 'selection.json', {'name': choice})
            base = root / o.screen_path(lane, choice)
            receipts = []
            for prompt in ('incident64', *o.PROMPTS):
                path = base / 'run' / prompt / 'receipt.json'
                save(path, dict(exact_oracle=True))
                receipts.append(path)
            save(base / 'summary.json', dict(passed=True, lane=lane, request_count=12,
                 cached_tokens=0, kv_dtype='BF16', device_isolation={'passed': True},
                 incident64={'passed': True}, requests=[{'prompt_id': p} for p in o.PROMPTS],
                 **{o.METRIC: {'median': speed}}))
            save(base / 'window.json', dict(passed=True, device_executed=True,
                 child_still_running=False, lane=lane, boot_id='mock-boot',
                 identity=dict(lineage=str(selection), selection_sha256=o.digest(selection / 'selection.json')),
                 files={str(p.relative_to(base)): o.digest(p) for p in [base / 'summary.json', *receipts]}))
    for leaf in ('screen.py', 'window_adapter.py', 'lane_admission.py', 'placement-validation/wrapper-seal.json'):
        path = root / o.LANES / leaf
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    save(root / o.SCREEN / 'evidence/review-window-04.json', {'mock': True})
    save(root / 'mock.json', {'boot_id': 'mock-boot'})


def edit_receipt(root, lane, choice, leaf, update, rehash=True):
    base = root / o.screen_path(lane, choice)
    path = base / leaf
    row = o.read(path)
    row.update(update)
    save(path, row)
    if rehash:
        window = o.read(base / 'window.json')
        window['files'][leaf] = o.digest(path)
        save(base / 'window.json', window)


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        fixture(self.root)
        self.logs = []

    def choose(self):
        return o.select(self.root, 'mock-boot', self.logs.append)['choice']

    def test_same_lane_maximin(self):
        # HC gains 4%,5%; batch gains 6%,3.33%: HC wins the weaker lane.
        self.assertEqual(self.choose(), '1-draft-hc-control')

    def test_batch_wins_both(self):
        fixture(self.root, ((50, 51, 54), (60, 61, 66)))
        self.assertEqual(self.choose(), '1-draft-hc-batch')

    def test_one_lane_win_is_not_enough(self):
        fixture(self.root, ((50, 55, 49), (60, 59, 70)))
        self.assertEqual(self.choose(), '1-production-control')

    def test_equal_is_not_a_win(self):
        fixture(self.root, ((50, 50, 50), (60, 61, 62)))
        self.assertEqual(self.choose(), '1-production-control')

    def test_equal_candidates_prefer_fewer_changes(self):
        fixture(self.root, ((50, 55, 55), (60, 66, 66)))
        self.assertEqual(self.choose(), '1-draft-hc-control')

    def test_any_inexact_candidate_forces_production(self):
        edit_receipt(self.root, 'B', o.CHOICES[2], 'run/incident64/receipt.json', {'exact_oracle': False})
        self.assertEqual(self.choose(), '1-production-control')

    def test_non_boolean_exact_is_rejected(self):
        edit_receipt(self.root, 'A', o.CHOICES[1], 'run/code-review/receipt.json', {'exact_oracle': 1})
        self.assertEqual(self.choose(), '1-production-control')

    def test_invalid_control_aborts(self):
        edit_receipt(self.root, 'A', o.CHOICES[0], 'run/incident64/receipt.json', {'exact_oracle': False})
        with self.assertRaisesRegex(ValueError, 'production evidence invalid'):
            self.choose()

    def test_missing_or_tampered_receipt(self):
        (self.root / o.screen_path('B', o.CHOICES[2]) / 'run/code-review/receipt.json').unlink()
        self.assertEqual(self.choose(), o.CHOICES[0])
        fixture(self.root)
        edit_receipt(self.root, 'A', o.CHOICES[1], 'summary.json', {o.METRIC: {'median': 900}}, rehash=False)
        self.assertEqual(self.choose(), o.CHOICES[0])

    def test_nan_metric_and_wrong_boot(self):
        edit_receipt(self.root, 'A', o.CHOICES[1], 'summary.json', {o.METRIC: {'median': float('nan')}})
        self.assertEqual(self.choose(), o.CHOICES[0])
        with self.assertRaisesRegex(ValueError, 'production evidence invalid'):
            o.select(self.root, 'old-boot', self.logs.append)

    def backend(self, **extra):
        return o.Backend(self.root, self.logs.append, dict(boot_id='mock-boot', **extra))

    def test_complete_mock_never_executes_external_programs(self):
        backend = self.backend()
        with patch.object(o.subprocess, 'run', side_effect=AssertionError('external execution forbidden')):
            o.orchestrate(backend, self.logs.append)
        self.assertEqual(list(backend.launched), ['packet64-chain',
            'screen-packet64-orchestration-1-split23-production-control',
            'screen-packet64-orchestration-1-production-control'])
        commands = [line for line in self.logs if line.startswith('MOCK RUN')]
        scripts = ['fast_reseal.py', 'chain_seal.py', 'check_inputs.py', 'storage_precheck.py',
                   'plan_gate.py', 'queue_runner.py']
        self.assertTrue(all(script in commands[i] for i, script in enumerate(scripts)))
        self.assertIn('--draft draft-hc --miss control', commands[0])
        self.assertIn('--verify', commands[1])
        self.assertIn('--plan', commands[5])
        launches = [line for line in commands if 'systemd-run' in line]
        for line in launches:
            for prop in ('KillMode=process', 'SendSIGKILL=no', 'Nice=0', 'Restart=no', 'ExitType=cgroup'):
                self.assertIn(prop, line)
        self.assertIn("--property=CPUAffinity=0-3 16-19", launches[0])

    def test_fault_change_and_precheck_failure_no_launch(self):
        for extra in ({'fault_counts': [2, 3]}, {'fail_command': 'storage_precheck.py'}):
            with self.subTest(extra=extra):
                backend = self.backend(**extra)
                with self.assertRaises(ValueError):
                    o.orchestrate(backend, self.logs.append)
                self.assertFalse(backend.launched)

    def test_missing_protocol_skips_companion(self):
        (self.root / o.LANES / 'window_adapter.py').unlink()
        backend = self.backend()
        o.orchestrate(backend, self.logs.append)
        self.assertEqual(list(backend.launched), ['packet64-chain'])
        self.assertTrue(any('COMPANION SKIP' in s for s in self.logs))

    def test_companion_preflight_failure_skips_without_blocking_chain(self):
        backend = self.backend(fail_command='check_companion.py')
        o.orchestrate(backend, self.logs.append)
        self.assertEqual(list(backend.launched), ['packet64-chain'])
        self.assertTrue(any('preflight refused' in s for s in self.logs))

    def test_inactive_before_any_screens_does_not_launch(self):
        for lane in 'AB':
            for choice in o.CHOICES:
                (self.root / o.screen_path(lane, choice) / 'window.json').unlink()
        backend = self.backend(lane_states=['inactive'])
        with self.assertRaisesRegex(ValueError, 'deadline'):
            o.orchestrate(backend, self.logs.append, wait_seconds=0)
        self.assertFalse(backend.launched)

    def test_active_child_blocks_even_after_drivers_end(self):
        backend = self.backend()
        original = backend.state
        backend.state = lambda unit: dict(LoadState='loaded', ActiveState='active') if unit.startswith('screen-v3') else original(unit)
        with self.assertRaisesRegex(ValueError, 'still owns work'):
            o.orchestrate(backend, self.logs.append)
        self.assertFalse(backend.launched)

    def test_main_error_always_logs_exit(self):
        save(self.root / 'mock.json', {'boot_id': 'mock-boot', 'fault_counts': [3]})
        output = io.StringIO()
        with patch('sys.argv', ['orchestrate.py', '--dry-run', str(self.root / 'mock.json')]), contextlib.redirect_stdout(output):
            self.assertEqual(o.main(), 1)
        self.assertIn('EXIT rc=1', output.getvalue())

    def test_empty_dry_fixture_cannot_fall_through_to_live(self):
        save(self.root / 'mock.json', {})
        output = io.StringIO()
        with patch('sys.argv', ['orchestrate.py', '--dry-run', str(self.root / 'mock.json')]), \
             patch.object(o.subprocess, 'run', side_effect=AssertionError('external execution forbidden')), \
             contextlib.redirect_stdout(output):
            self.assertEqual(o.main(), 1)
        self.assertIn('mode=MOCK', output.getvalue())
        self.assertIn('EXIT rc=1', output.getvalue())

    def test_actual_shell_dry_run(self):
        # Only this owned CPU shell/Python process runs. Backend is all mocks.
        result = subprocess.run(['bash', str(o.HERE / 'orchestrate.sh'), '--dry-run', str(self.root / 'mock.json')],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('EXIT rc=0', result.stdout)
        self.assertIn('COMPANION COMPLETE screen-packet64-orchestration-1-production-control', result.stdout)
        (o.HERE / 'dry-run.log').write_text(result.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
