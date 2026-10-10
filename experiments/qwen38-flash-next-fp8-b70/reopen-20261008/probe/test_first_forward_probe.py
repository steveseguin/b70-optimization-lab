"""CPU-only contracts. No Torch, device calls, process signals or containers."""
import argparse
import ast
import importlib.util
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import single_rank_first_forward_probe as probe
import first_forward_command as printer


class FirstForwardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.pin = probe.harness.digest((probe.PACKAGE / 'overlay-manifest.json').read_bytes())

    def test_production_geometry_and_exact_host_bytes(self):
        resident, host = probe.geometry()
        self.assertEqual((len(resident), len(host)), (101, 27))
        self.assertEqual(sorted(resident + host), list(range(128)))
        self.assertEqual(host, json.loads((probe.PACKAGE / 'placement-attempt6-v5.json').read_text())['0']['0'])
        self.assertEqual([27 * shape[1] * shape[2] for shape in probe.SHAPES.values()], [88473600, 44236800])

    def test_routes_cover_every_host_row_and_both_placements(self):
        resident, host = probe.geometry()
        rows = probe.routes(resident, host)
        self.assertEqual(len(rows), 64)
        for row in rows:
            self.assertEqual(len(row), 10)
            self.assertEqual(len(set(row)), 10)
            self.assertEqual(len(set(row) & set(host)), 5)
            self.assertEqual(len(set(row) & set(resident)), 5)
        self.assertEqual({e for row in rows for e in row} & set(host), set(host))

    def test_overlay_pin_and_closed_payload(self):
        _, manifest = probe.verify_overlay(self.pin)
        self.assertIn('vllm/screen1b_teardown.py', manifest['files'])

    def test_overlay_pin_refuses_before_loader_import(self):
        with patch.object(probe, 'load_stdlib') as loader:
            with self.assertRaisesRegex(RuntimeError, 'SHA-256'):
                probe.verify_overlay('0' * 64)
            loader.assert_not_called()

    def test_missing_teardown_refuses(self):
        application = Mock()
        application.verify_package.return_value = {'files': {}}
        with patch.object(probe, 'load_stdlib', return_value=application):
            with self.assertRaisesRegex(RuntimeError, 'teardown patch'):
                probe.verify_overlay(self.pin)

    def test_control_failure_never_runs_mixed(self):
        run = Mock(side_effect=RuntimeError('control failed'))
        with self.assertRaisesRegex(RuntimeError, 'control failed'):
            probe.execute_arms(run, Mock(), Mock())
        self.assertEqual([call.args[0] for call in run.call_args_list], ['control'])

    def test_journal_fault_after_control_prevents_mixed(self):
        run = Mock(return_value=b'control')
        check = Mock(side_effect=[None, RuntimeError('STOP')])
        with self.assertRaisesRegex(RuntimeError, 'STOP'):
            probe.execute_arms(run, Mock(), check)
        self.assertEqual([call.args[0] for call in run.call_args_list], ['control'])

    def test_initial_fault_prevents_all_work(self):
        run = Mock()
        with self.assertRaisesRegex(RuntimeError, 'STOP'):
            probe.execute_arms(run, Mock(), Mock(side_effect=RuntimeError('STOP')))
        run.assert_not_called()

    def test_mixed_mismatch_fails_exact_gate(self):
        run = Mock(side_effect=[b'control', b'mixed'])
        with self.assertRaisesRegex(RuntimeError, 'differs'):
            probe.execute_arms(run, lambda x, y: x == y, Mock())
        self.assertEqual(run.call_count, 2)

    def test_exact_pair_finishes_once(self):
        run = Mock(return_value=b'bytes')
        self.assertEqual(probe.execute_arms(run, lambda x, y: x == y, Mock()), (b'bytes', b'bytes'))
        self.assertEqual([call.args[0] for call in run.call_args_list], ['control', 'mixed'])

    def test_fault_after_mixed_never_compares(self):
        compare = Mock()
        with self.assertRaisesRegex(RuntimeError, 'STOP'):
            probe.execute_arms(Mock(), compare, Mock(side_effect=[None, None, RuntimeError('STOP')]))
        compare.assert_not_called()

    def test_event_flushes_both_clocks_and_pid(self):
        row = probe.event(self.directory, 'control.w13.before', marker=3)
        self.assertEqual(json.loads((self.directory / 'stages.jsonl').read_text()), row)
        self.assertGreater(row['monotonic_ns'], 0)
        self.assertIn('+00:00', row['utc'])
        self.assertEqual(row['pid'], os.getpid())

    def test_first_stop_reason_is_preserved(self):
        probe.stop(self.directory, 'first fault')
        probe.stop(self.directory, 'later timeout')
        self.assertEqual((self.directory / 'STOP').read_text(), 'first fault\n')

    def test_preservation_never_signals_or_exits(self):
        with patch.object(probe.time, 'sleep', side_effect=RuntimeError('test stops wait')):
            with self.assertRaisesRegex(RuntimeError, 'test stops wait'):
                probe.preserve(self.directory, 'native ownership')
        self.assertTrue((self.directory / 'STOP').exists())
        self.assertEqual(json.loads((self.directory / 'stages.jsonl').read_text())['phase'], 'preserved_no_retry')

    def test_teardown_calls_reviewed_shutdown_then_release(self):
        calls = []
        runner, proc, torch = object(), SimpleNamespace(), object()
        guard = object()
        teardown = SimpleNamespace(_complete=False)
        def release(*args):
            self.assertEqual(args, (runner, guard, torch))
            calls.append('release')
        def shutdown(*args):
            self.assertEqual(args[:3], (proc, guard, torch))
            self.assertIsNone(args[3]())
            self.assertIsNone(args[4]())
            calls.append('shutdown')
            proc.worker.shutdown()
            teardown._complete = True
        teardown.release_runner, teardown.shutdown_rank = release, shutdown
        probe.teardown_owned(runner, proc, guard, torch, teardown)
        self.assertEqual(calls, ['shutdown', 'release'])

    def test_failed_release_does_not_report_success(self):
        proc = SimpleNamespace()
        teardown = SimpleNamespace(_complete=False,
            release_runner=Mock(side_effect=RuntimeError('drain failed')),
            shutdown_rank=lambda *args: proc.worker.shutdown())
        with self.assertRaisesRegex(RuntimeError, 'drain failed'):
            probe.teardown_owned(None, proc, Mock(), Mock(), teardown)
        self.assertFalse(teardown._complete)

    def test_incomplete_shutdown_refuses(self):
        teardown = SimpleNamespace(release_runner=Mock(), shutdown_rank=Mock(), _complete=False)
        with self.assertRaisesRegex(RuntimeError, 'did not complete'):
            probe.teardown_owned(None, SimpleNamespace(), Mock(), Mock(), teardown)

    def test_missing_rank_receipt_cannot_pass(self):
        (self.directory / 'teardown').mkdir()
        result = probe.validate_teardown(self.directory)
        self.assertFalse(result['passed'])
        self.assertEqual(result['expected_ranks'], [0])

    def test_exception_object_is_not_retained_during_teardown(self):
        # Regression for traceback frames retaining the failed kernel's tensors.
        tree = ast.parse((HERE / 'single_rank_first_forward_probe.py').read_text())
        assignments = [node for node in ast.walk(tree) if isinstance(node, ast.Assign)
                       and any(isinstance(target, ast.Name) and target.id == 'error' for target in node.targets)]
        self.assertTrue(assignments)
        self.assertTrue(all(isinstance(node.value, (ast.Constant, ast.JoinedStr)) for node in assignments))

    def fake_moe(self):
        class Kernel:
            def __getitem__(self, grid):
                return lambda *args, **kwargs: SimpleNamespace(asm={'ttir': 'IR', 'spv': b'bin'})
        return SimpleNamespace(**{name: Mock(return_value=None) for name in (
            'moe_kernel_quantize_input', '_prepare_expert_assignment', 'dispatch_fused_moe_kernel',
            'apply_moe_activation')}, ops=SimpleNamespace(moe_sum=Mock()), fused_moe_kernel=Kernel())

    def test_instrumentation_calls_real_stage_and_restores(self):
        module = self.fake_moe()
        original = module.dispatch_fused_moe_kernel
        torch = SimpleNamespace(xpu=SimpleNamespace(synchronize=Mock()))
        with probe.instrument(module, torch, self.directory, Mock(), 'control'):
            module.dispatch_fused_moe_kernel('operand')
        original.assert_called_once_with('operand')
        self.assertIs(module.dispatch_fused_moe_kernel, original)
        self.assertEqual(torch.xpu.synchronize.call_count, 2)
        rows = [json.loads(line) for line in (self.directory / 'stages.jsonl').read_text().splitlines()]
        self.assertEqual([row['phase'] for row in rows], ['control.dispatch_fused_moe_kernel.0.before',
                                                        'control.dispatch_fused_moe_kernel.0.after'])

    def test_instrumentation_restores_even_on_failure(self):
        module = self.fake_moe()
        original = module.fused_moe_kernel
        with self.assertRaisesRegex(RuntimeError, 'failed'):
            with probe.instrument(module, Mock(), self.directory, Mock(), 'control'):
                raise RuntimeError('failed')
        self.assertIs(module.fused_moe_kernel, original)

    def test_pre_stage_fault_never_calls_kernel(self):
        module = self.fake_moe()
        original = module.dispatch_fused_moe_kernel
        with probe.instrument(module, Mock(), self.directory, Mock(side_effect=RuntimeError('STOP')), 'control'):
            with self.assertRaisesRegex(RuntimeError, 'STOP'):
                module.dispatch_fused_moe_kernel()
        original.assert_not_called()

    def test_kernel_ir_is_saved_and_hashed(self):
        module = self.fake_moe()
        with probe.instrument(module, Mock(), self.directory, Mock(), 'mixed'):
            module.fused_moe_kernel[(1,)]('operand')
        self.assertEqual((self.directory / 'ir/mixed-0.ttir').read_text(), 'IR')
        rows = [json.loads(line) for line in (self.directory / 'stages.jsonl').read_text().splitlines()]
        self.assertEqual(rows[-1]['files']['mixed-0.ttir'], probe.harness.digest(b'IR'))

    def test_printed_command_keeps_single_device_and_pin(self):
        with patch('container_command.os.path.realpath', return_value='/dev/dri/renderD128'):
            command = printer.command('/dev/dri/by-path/pci-0000:23:00.0-render',
                                      '<FRESH-HEALTH>', '/tmp/new receipt', self.pin)
        self.assertEqual(sum(x.startswith('--device=') for x in command), 1)
        self.assertIn('--network=none', command)
        self.assertIn('--restart=no', command)
        self.assertIn('--stop-timeout=-1', command)
        self.assertIn('/probe/single_rank_first_forward_probe.py', command)
        self.assertIn('B70_SCREEN1B_STATE_DIR=/receipts/teardown', command)
        self.assertEqual(command[-2:], ['--overlay-sha256', self.pin])
        self.assertNotIn('--clean-exit', command)
        self.assertNotIn('--exit-after-sleep', command)

    def test_printer_requires_sha256(self):
        for pin in ('', 'latest', 'a' * 63, 'A' * 64):
            with self.assertRaises(ValueError):
                printer.command('', '', '', pin)

    def test_import_and_help_do_not_import_torch(self):
        blocker = self.directory / 'torch.py'
        blocker.write_text("raise AssertionError('Torch import is forbidden')\n")
        result = subprocess.run([sys.executable, '-B', str(HERE / 'single_rank_first_forward_probe.py'), '--help'],
                                env=dict(os.environ, PYTHONPATH=str(self.directory)),
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_refusal_does_not_spawn_or_import_torch(self):
        args = ['--health-receipt', str(self.directory / 'missing.json'), '--receipt-dir', str(self.directory),
                '--overlay-sha256', self.pin]
        with patch.dict(os.environ, {'FLASHNEXT_PROBE_ADMIT': '0'}), patch.object(probe, 'guardian') as guardian:
            self.assertEqual(probe.main(args), 2)
        guardian.assert_not_called()
        receipt = json.loads((self.directory / 'receipt.json').read_text())
        self.assertFalse(receipt['passed'])
        self.assertIn('ADMIT', receipt['exception']['message'])

    def test_container_mount_layout_admits_without_runtime_or_worker(self):
        # Mirror the mounts below a temporary root, never mount a container or
        # touch host /probe, /repo, /receipts, /health.json (or any device).
        root = self.directory
        package = root / 'repo/experiments/qwen38-flash-next-fp8-b70/reopen-20261008'
        mounted_probe = root / 'probe'
        receipts = root / 'receipts'
        for directory in (package, mounted_probe, receipts):
            directory.mkdir(parents=True)
        manifest = json.loads((probe.PACKAGE / 'overlay-manifest.json').read_text())
        files = set(manifest['support_files']) | {'overlay-manifest.json', 'image-plan.json'}
        files.update(path.name for path in probe.PACKAGE.glob('*.py'))
        files.update(manifest['source'] + '/' + name for name in manifest['files'])
        for name in files:
            destination = package / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(probe.PACKAGE / name, destination)
        for path in HERE.iterdir():
            if path.suffix in ('.py', '.sh'):
                shutil.copyfile(path, mounted_probe / path.name)
        lane = probe.harness.lane()
        acceptance = root / 'repo' / lane.OWNER_ACCEPTANCE_RELATIVE
        acceptance.parent.mkdir(parents=True)
        shutil.copyfile(lane.REPO / lane.OWNER_ACCEPTANCE_RELATIVE, acceptance)
        script = r"""
import builtins
import datetime as dt
import json
import os
from pathlib import Path
import sys
from unittest.mock import Mock, patch
root = Path(sys.argv[1])
sys.path.insert(0, str(root / 'probe'))
def deny_device(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes)):
        path = os.fsdecode(args[0])
        if path == '/dev/dri' or path.startswith('/dev/dri/'):
            raise AssertionError('device open forbidden')
sys.addaudithook(deny_device)
original_import = builtins.__import__
def cpu_import(name, *args, **kwargs):
    if name.split('.')[0] in ('torch', 'triton', 'vllm'):
        raise AssertionError('runtime import forbidden: ' + name)
    return original_import(name, *args, **kwargs)
builtins.__import__ = cpu_import
import single_rank_first_forward_probe as mounted
assert mounted.HERE == root / 'probe'
assert not mounted.HERE.is_relative_to(mounted.PACKAGE)
lane = mounted.harness.lane()
acceptance = root / 'repo' / lane.OWNER_ACCEPTANCE_RELATIVE
boot = json.loads(acceptance.read_text())['boot_id']
now = dt.datetime(2026, 10, 10, 18, tzinfo=dt.timezone.utc)
class Clock(dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return now
stamp = now.strftime('%Y-%m-%d %H:%M:%S UTC')
health = dict(schema='ltx.four-card-health.v1', passed=True, kernel='fixture', torch='fixture',
    boot_id=boot, start_utc=stamp, end_utc=stamp, journal_fault_lines_during_probe=[], device_count=4,
    cards=[dict(device=f'xpu:{i}', name='fixture', **{'pass': True},
                copy_roundtrip_exact=True, gemm_repeat_exact=True, gemm_fp32_max_abs_err=0.,
                gemm_bf16_max_abs_err=0., staged_from_previous_exact=True) for i in range(4)])
health_path = root / 'health.json'
health_path.write_text(json.dumps(health))
receipts = root / 'receipts'
mounted.harness.atomic_json(receipts / 'watcher.json', dict(passed=True, boot_id=boot,
    health_sha256=mounted.harness.digest(health_path.read_bytes()), updated_unix=now.timestamp(),
    journal_admission={'owner_acceptance_sha256': lane.OWNER_ACCEPTANCE_SHA256}))
read_text = Path.read_text
def fixture_read(path, *args, **kwargs):
    if path == Path('/proc/sys/kernel/random/boot_id'):
        return boot
    return read_text(path, *args, **kwargs)
guardian = Mock(return_value=0)
with patch.object(Path, 'read_text', fixture_read), patch.object(dt, 'datetime', Clock), \
     patch.object(mounted, 'guardian', guardian):
    code = mounted.main(['--health-receipt', str(health_path), '--receipt-dir', str(receipts),
                         '--overlay-sha256', sys.argv[2], '--owner-acceptance', str(acceptance)])
assert code == 0, (receipts / 'receipt.json').read_text()
guardian.assert_called_once()
receipt = json.loads((receipts / 'receipt.json').read_text())
assert receipt['stage'] == 'admitted'
assert receipt['owner_acceptance_sha256'] == lane.OWNER_ACCEPTANCE_SHA256
for name, digest in receipt['support_source_sha256'].items():
    source = root / name if name.startswith('probe/') else mounted.PACKAGE / name
    assert mounted.harness.digest(source.read_bytes()) == digest
assert len(receipt['support_source_sha256']) == 7
assert not any(name in sys.modules for name in ('torch', 'triton', 'vllm'))
"""
        env = dict(os.environ, FLASHNEXT_PROBE_PACKAGE=str(package), FLASHNEXT_PROBE_ADMIT='1',
                   NEOReadDebugKeys='1', EnableDeferBacking='0', PYTHONDONTWRITEBYTECODE='1',
                   **{name: probe.harness.CONF for name in probe.harness.ALIASES})
        result = subprocess.run([sys.executable, '-B', '-c', script, str(root), self.pin],
                                env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_source_hash_failure_is_terminal_before_spawn(self):
        with patch.object(probe, 'HERE', self.directory / 'missing-probe'), \
             patch.object(probe, 'guardian') as guardian:
            code = probe.main(['--health-receipt', '/missing', '--receipt-dir', str(self.directory),
                               '--overlay-sha256', self.pin])
        self.assertEqual(code, 2)
        guardian.assert_not_called()
        receipt = json.loads((self.directory / 'receipt.json').read_text())
        self.assertEqual(receipt['stage'], 'admission_refused')
        self.assertFalse(receipt['worker_started'])
        self.assertEqual(receipt['exception']['type'], 'FileNotFoundError')
        self.assertGreater(receipt['admission_refused_unix'], 0)
        self.assertIn('harness refused before device work', (self.directory / 'STOP').read_text())

    def test_existing_receipt_is_never_overwritten(self):
        path = self.directory / 'receipt.json'
        path.write_text('saved evidence')
        with self.assertRaises(FileExistsError):
            probe.main(['--health-receipt', '/missing', '--receipt-dir', str(self.directory),
                        '--overlay-sha256', self.pin])
        self.assertEqual(path.read_text(), 'saved evidence')

    def guardian_fixture(self, returncode=0, validation=True, timeout=False):
        receipt = {'boot_id': 'test', 'health_sha256': 'test', 'passed': False,
                   'bytes_equal': True, 'teardown_complete': True}
        (self.directory / 'receipt.json').write_text(json.dumps(receipt))
        args = SimpleNamespace(receipt_dir=self.directory, health_receipt=self.directory / 'health.json',
                               overlay_sha256=self.pin)
        child = SimpleNamespace(pid=999999999, returncode=returncode,
                                poll=Mock(side_effect=[None, returncode] if timeout else [returncode]))
        with patch.object(probe.subprocess, 'Popen', return_value=child), \
             patch.object(probe.signal, 'signal'), patch.object(probe.time, 'sleep'), \
             patch.object(probe.time, 'monotonic', side_effect=[0, 121] if timeout else [0]), \
             patch.object(probe.harness, 'wait_postflight', return_value={'passed': True}), \
             patch.object(probe, 'validate_teardown', return_value={'passed': validation}):
            code = probe.guardian(args, receipt)
        return code, json.loads((self.directory / 'receipt.json').read_text())

    def test_guardian_pass_requires_valid_rank_receipt(self):
        code, receipt = self.guardian_fixture(validation=False)
        self.assertEqual(code, 2)
        self.assertFalse(receipt['passed'])

    def test_guardian_exact_clean_exit_passes_with_postflight(self):
        code, receipt = self.guardian_fixture()
        self.assertEqual(code, 0)
        self.assertTrue(receipt['passed'])
        self.assertEqual(receipt['worker_wait_status'], 0)

    def test_guardian_native_crash_latches_stop(self):
        code, receipt = self.guardian_fixture(returncode=-11)
        self.assertEqual(code, 2)
        self.assertEqual(receipt['worker_wait_status'], 11)
        self.assertTrue((self.directory / 'STOP').exists())

    def test_guardian_timeout_latches_stop_without_killing(self):
        code, receipt = self.guardian_fixture(timeout=True)
        self.assertEqual(code, 2)
        self.assertTrue(receipt['guardian_timeout'])
        self.assertIn('no kill', (self.directory / 'STOP').read_text())

    def test_absent_native_trace_is_explicitly_unavailable(self):
        result = probe.native_trace_status(self.directory / 'not-mounted')
        self.assertEqual(result['status'], 'unavailable')
        self.assertFalse(result['causal_separation_complete'])
        self.assertEqual(len(result['settings']), 5)
        self.assertTrue(all(value['unavailable'] == 'FileNotFoundError' for value in result['settings'].values()))

    def test_guardian_stop_before_spawn_refuses_without_child(self):
        probe.stop(self.directory, 'fault already latched')
        args = SimpleNamespace(receipt_dir=self.directory)
        with patch.object(probe.signal, 'signal') as handler, patch.object(probe.subprocess, 'Popen') as spawn:
            with self.assertRaisesRegex(RuntimeError, 'STOP before spawn'):
                probe.guardian(args, {})
        self.assertEqual(handler.call_count, 2)
        spawn.assert_not_called()

    def test_no_signal_kill_or_abrupt_exit_in_first_forward(self):
        tree = ast.parse((HERE / 'single_rank_first_forward_probe.py').read_text())
        forbidden = {'kill', 'killpg', '_exit', 'alarm', 'terminate', 'send_signal'}
        calls = {node.func.attr for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
        self.assertFalse(calls & forbidden)


if __name__ == '__main__':
    unittest.main()
