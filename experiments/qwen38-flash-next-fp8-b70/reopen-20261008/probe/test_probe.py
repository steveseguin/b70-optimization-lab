"""CPU-only refusal/address tests; no runtime imports or device emulation."""
import ast
import argparse
import datetime as dt
import importlib.util
import hashlib
import io
import json
import os
import re
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import single_rank_slab_probe as probe
import container_command


def health(now):
    stamp = now.strftime('%Y-%m-%d %H:%M:%S UTC')
    return dict(schema='ltx.four-card-health.v1', passed=True, kernel='test', torch='test',
                boot_id='test-boot', start_utc=stamp, end_utc=stamp,
                journal_fault_lines_during_probe=[], device_count=4,
                cards=[dict(device=f'xpu:{i}', name='fixture', **{'pass': True},
                            copy_roundtrip_exact=True, gemm_repeat_exact=True,
                            gemm_fp32_max_abs_err=0., gemm_bf16_max_abs_err=0.,
                            staged_from_previous_exact=True) for i in range(4)])


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = dt.datetime(2026, 10, 9, tzinfo=dt.timezone.utc)
        self.path = self.root / 'health.json'
        self.path.write_text(json.dumps(health(self.now)))
        self.env = dict(FLASHNEXT_PROBE_ADMIT='1', NEOReadDebugKeys='1', EnableDeferBacking='0',
                        **{key: probe.CONF for key in probe.ALIASES})

    def admit(self):
        return probe.admission(self.path, env=self.env, boot_id='test-boot', now=self.now)

    def test_complete_receipt(self):
        self.assertEqual(self.admit()['boot_id'], 'test-boot')

    def test_missing_admission_and_conflicting_aliases(self):
        for key in ('FLASHNEXT_PROBE_ADMIT', *probe.ALIASES, 'NEOReadDebugKeys', 'EnableDeferBacking'):
            with self.subTest(key=key), patch.dict(self.env, {key: 'wrong'}):
                with self.assertRaises(RuntimeError): self.admit()

    def test_health_wrong_boot_missing_evidence_age_and_future(self):
        mutations = [dict(boot_id='wrong'), dict(passed=False), dict(cards=[]),
                     dict(journal_fault_lines_during_probe=['fault']),
                     dict(end_utc='2026-10-09 00:00:01 UTC'),
                     dict(start_utc='2026-10-08 18:00:00 UTC', end_utc='2026-10-08 18:00:00 UTC')]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.path.write_text(json.dumps(health(self.now) | mutation))
                with self.assertRaises(RuntimeError): self.admit()

    def test_failed_boot_refused(self):
        with self.assertRaisesRegex(RuntimeError, 'fault boot'):
            probe.admission(self.path, env=self.env, boot_id='10192010-fixture', now=self.now)

    def test_signed_offsets_positive_negative_and_wrap(self):
        for resident, host in [(0x100000, 0x200000), (0x200000, 0x100000),
                               (2**64-65536, 4096), (4096, 2**64-65536)]:
            with self.subTest(resident=resident, host=host):
                values, rebuilt = probe.table_values(resident, host)
                self.assertEqual(rebuilt, [(host + row * 4096) % 2**64 for row in probe.ROWS])
                self.assertTrue(all(-2**63 <= v < 2**63 and v % 256 == 0 for v in values))

    def test_misaligned_pointer_refused(self):
        with self.assertRaises(ValueError): probe.table_values(4096, 8193)

    def test_refusal_subprocess_never_imports_torch(self):
        env = dict(os.environ, FLASHNEXT_PROBE_ADMIT='0')
        guard = self.root / 'torch.py'
        guard.write_text("raise AssertionError('Torch import forbidden')\n")
        env['PYTHONPATH'] = str(self.root)
        p = subprocess.run([sys.executable, '-B', str(HERE / 'single_rank_slab_probe.py'),
                            '--health-receipt', str(self.path), '--receipt-dir', str(self.root / 'refusal')],
                           env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, 2, p.stderr)
        receipt = json.loads((self.root / 'refusal/receipt.json').read_text())
        self.assertEqual(receipt['exception']['message'], 'FLASHNEXT_PROBE_ADMIT=1 required')
        self.assertFalse(receipt['passed'])
        self.assertEqual(receipt['gather_launches'], 0)

    def test_wrapper_one_device_no_network_exact_image_env(self):
        command = container_command.command('/dev/dri/by-path/pci-0000:23:00.0-render',
                                              '/tmp/health file.json', '/tmp/receipt dir')
        self.assertEqual(shlex.split(shlex.join(command)), command)
        self.assertEqual(len([x for x in command if x.startswith('--device=')]), 1)
        self.assertIn('--network=none', command)
        self.assertIn('--rm', command)
        self.assertIn(json.loads((HERE.parent / 'image-plan.json').read_text())['image'], command)
        for key in probe.ALIASES: self.assertIn(key + '=' + probe.CONF, command)
        self.assertFalse(any('/model' in x for x in command))
        with self.assertRaises(ValueError): container_command.command('/dev/dri', '/tmp/h', '/tmp/r')

    def test_wrapper_only_prints(self):
        p = subprocess.run(['bash', str(HERE / 'run-probe-in-container.sh'),
                            '--render-node', '/dev/dri/by-path/pci-0000:23:00.0-render',
                            '--health-receipt', '/PATH/health.json', '--receipt-dir', '/PATH/receipts',
                            '--direct-host-pointer'], capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(p.stdout.startswith('docker run --rm '))
        self.assertIn('--direct-host-pointer', shlex.split(p.stdout))
        self.assertFalse(Path('/PATH/receipts').exists())

    def test_default_command_byte_for_byte(self):
        expected = (HERE / 'default-command.txt').read_text().format(probe=HERE, package=HERE.parent)
        with patch.object(container_command.os.path, 'realpath', return_value='/dev/dri/renderD128'), \
             patch.object(container_command, 'host_umd_mounts', side_effect=AssertionError('opt-in only')):
            command = container_command.command('/dev/dri/by-path/pci-0000:23:00.0-render',
                                                '/tmp/health file.json', '/tmp/receipt dir')
        self.assertEqual(shlex.join(command) + '\n', expected)

    def test_exit_flag_plumbing_both_parsers(self):
        for flag in (['--clean-exit'], ['--exit-after-sleep', '10']):
            with self.subTest(flag=flag):
                p = subprocess.run(['bash', str(HERE / 'run-probe-in-container.sh'),
                    '--render-node', '/dev/dri/by-path/pci-0000:23:00.0-render',
                    '--health-receipt', str(self.path), '--receipt-dir', str(self.root),
                    *flag], capture_output=True, text=True, timeout=10)
                self.assertEqual(p.returncode, 0, p.stderr)
                command = shlex.split(p.stdout)
                parser = argparse.ArgumentParser()
                probe.add_exit_arguments(parser)
                index = command.index(flag[0])
                args = parser.parse_args(command[index:])
                self.assertEqual(args.clean_exit, flag[0] == '--clean-exit')
                self.assertEqual(args.exit_after_sleep, 10 if len(flag) == 2 else None)

    def test_invalid_exit_modes_refused_before_receipt_or_import(self):
        for flags in (['--clean-exit', '--exit-after-sleep', '1'],
                      *[['--exit-after-sleep', n] for n in ('-1', '31', 'nan', 'inf')]):
            with self.subTest(flags=flags), patch('sys.stderr', new_callable=io.StringIO):
                with self.assertRaises(SystemExit):
                    probe.main(['--health-receipt', str(self.path),
                                '--receipt-dir', str(self.root / 'invalid'), *flags])
                self.assertFalse((self.root / 'invalid').exists())
        with self.assertRaises(ValueError):
            container_command.command('/dev/dri/by-path/pci-0000:23:00.0-render',
                                      self.path, self.root, clean_exit=True, exit_after_sleep=0)

    def test_exit_modes_recorded_on_refusal(self):
        for i, flags in enumerate((['--clean-exit'], ['--exit-after-sleep', '10'])):
            directory = self.root / str(i)
            with patch.dict(os.environ, {'FLASHNEXT_PROBE_ADMIT': '0'}):
                self.assertEqual(probe.main(['--health-receipt', str(self.path),
                                 '--receipt-dir', str(directory), *flags]), 2)
            receipt = json.loads((directory / 'receipt.json').read_text())
            self.assertEqual(receipt['exit_mode'], 'clean' if i == 0 else 'abrupt')
            self.assertEqual(receipt['exit_after_sleep_seconds'], None if i == 0 else 10)

    def test_idle_watcher_stop_prevents_exit_marker(self):
        args = types.SimpleNamespace(exit_after_sleep=10, receipt_dir=self.root)
        receipt = dict(boot_id='test-boot', health_sha256='hash')
        with patch.object(probe, 'check_receipt_watcher', side_effect=RuntimeError('STOP')):
            with self.assertRaisesRegex(RuntimeError, 'STOP'):
                probe.idle_before_exit(args, receipt, lambda: None)
        self.assertIn('idle_begin', receipt['lifecycle'])
        self.assertNotIn('idle_end', receipt['lifecycle'])

    def test_guardian_clean_exit_runs_atexit_abrupt_does_not(self):
        # Real OS fork/finalization, but run_device replaced before execution;
        # no Torch import, device call, or emulated device operation.
        for i, flags in enumerate((['--clean-exit'], ['--exit-after-sleep', '0'])):
            directory = self.root / ('exit' + str(i))
            marker = self.root / ('atexit' + str(i))
            code = f'''
import atexit, sys
from pathlib import Path
sys.path.insert(0, {str(HERE)!r})
import single_rank_slab_probe as p
p.admission = lambda *a: dict(boot_id='cpu', health_sha256='hash')
p.check_receipt_watcher = lambda *a: dict(passed=True)
p.wait_postflight = lambda *a: dict(passed=True)
p.production_placement = lambda: None
def fake_device(args, receipt, save):
    atexit.register(lambda: Path({str(marker)!r}).write_text('finalized'))
    receipt['bytes_equal'] = True
    p.mark(receipt, save, 'before_return')
p.run_device = fake_device
raise SystemExit(p.main({['--health-receipt', str(self.path), '--receipt-dir', str(directory), *flags]!r}))
'''
            p = subprocess.run([sys.executable, '-B', '-c', code],
                               capture_output=True, text=True, timeout=10)
            self.assertEqual(p.returncode, 0, p.stderr)
            receipt = json.loads((directory / 'receipt.json').read_text())
            self.assertEqual(marker.exists(), i == 0)
            self.assertTrue(receipt['passed'])
            self.assertIn('before_exit', receipt['lifecycle'])
            if i == 1:
                self.assertIn('watcher_after_idle', receipt)
                self.assertLessEqual(receipt['lifecycle']['idle_end']['monotonic_ns'],
                                     receipt['lifecycle']['before_exit']['monotonic_ns'])

    def test_overlay_closure_matches_remedy_a(self):
        note = (HERE.parents[1] / 'notes/2026-10-09-runtime-comparison.md').read_text()
        mounts = [line.split('|') for line in note.split("done <<'MOUNTS'\n")[1].split('\nMOUNTS')[0].splitlines()]
        hashes = dict(re.findall(r'\| `([^`]+)` \| `([0-9a-f]{64})` \|', note))
        self.assertEqual(len(mounts), 12)
        self.assertEqual(container_command.HOST_UMD_OVERLAY,
                         tuple((source, target, hashes[source]) for source, target in mounts))

    def overlay_fixture(self):
        closure = []
        for i, (_, target, _) in enumerate(container_command.HOST_UMD_OVERLAY):
            source = self.root / ('library' + str(i))
            data = ('library bytes ' + str(i)).encode()
            source.write_bytes(data)
            closure.append((str(source), target, hashlib.sha256(data).hexdigest()))
        return tuple(closure)

    def test_overlay_command_order_env_and_cli(self):
        closure = self.overlay_fixture()
        argv = ['container_command.py', '--render-node', '/dev/dri/by-path/pci-0000:23:00.0-render',
                '--health-receipt', str(self.path), '--receipt-dir', str(self.root), '--host-umd-overlay']
        with patch.object(container_command, 'HOST_UMD_OVERLAY', closure), \
             patch.object(container_command.os.path, 'realpath', return_value='/dev/dri/renderD128'), \
             patch.object(sys, 'argv', argv), patch('sys.stdout', new_callable=io.StringIO) as output:
            container_command.main()
        command = shlex.split(output.getvalue())
        mounts = [command[i+1] for i, value in enumerate(command) if value == '--mount']
        self.assertEqual(len(mounts), 16)
        self.assertEqual(mounts[4:], [f'type=bind,src={src},dst={dst},readonly' for src, dst, _ in closure])
        self.assertIn('LD_LIBRARY_PATH=/usr/local/lib:/opt/ucx/lib:/opt/venv/lib', command)
        self.assertIn('FLASHNEXT_PROBE_UMD=host-26.18.38308', command)
        self.assertIn('--device=/dev/dri/renderD128:/dev/dri/renderD128:rw', command)
        self.assertIn(f'type=bind,src={HERE.parent},dst=/repo/experiments/qwen38-flash-next-fp8-b70/reopen-20261008,readonly', command)

    def test_overlay_missing_file_refuses(self):
        for index in range(12):
            closure = self.overlay_fixture()
            Path(closure[index][0]).unlink()
            with self.subTest(index=index), patch.object(container_command, 'HOST_UMD_OVERLAY', closure), \
                 self.assertRaisesRegex(ValueError, 'source missing or unreadable'):
                container_command.host_umd_mounts()

    def test_overlay_changed_hash_refuses(self):
        for index in range(12):
            closure = self.overlay_fixture()
            Path(closure[index][0]).write_bytes(b'changed host package')
            with self.subTest(index=index), patch.object(container_command, 'HOST_UMD_OVERLAY', closure), \
                 self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
                container_command.host_umd_mounts()

    def test_receipt_records_runtime_and_render_environment_on_refusal(self):
        for identity in (None, 'host-26.18.38308'):
            directory = self.root / ('image' if identity is None else 'host')
            env = dict(FLASHNEXT_PROBE_ADMIT='0', FLASHNEXT_PROBE_RENDER_NODE='/dev/dri/renderD128',
                       FLASHNEXT_PROBE_RENDER_BYPATH='/dev/dri/by-path/pci-0000:23:00.0-render',
                       FLASHNEXT_PROBE_RENDER_EXTRA='future-field', UNRELATED_SECRET='excluded')
            if identity is not None:
                env['FLASHNEXT_PROBE_UMD'] = identity
            with self.subTest(identity=identity), patch.dict(os.environ, env, clear=True):
                self.assertEqual(probe.main(['--health-receipt', str(self.path),
                                            '--receipt-dir', str(directory)]), 2)
            receipt = json.loads((directory / 'receipt.json').read_text())
            self.assertEqual(receipt['environment'], {
                'FLASHNEXT_PROBE_UMD': identity or 'image-26.27.39122',
                **{k: v for k, v in env.items() if k.startswith('FLASHNEXT_PROBE_RENDER_')}})

    def test_watcher_stale_failed_or_stopped_refuses(self):
        now = dt.datetime.now(dt.timezone.utc).timestamp()
        path = self.root / 'watcher.json'
        for data in [dict(passed=False, boot_id='test-boot', updated_unix=now),
                     dict(passed=True, boot_id='test-boot', updated_unix=now-6),
                     dict(passed=True, boot_id='wrong', updated_unix=now)]:
            path.write_text(json.dumps(data))
            with self.assertRaises(RuntimeError): probe.check_watcher(self.root, 'test-boot')
        path.write_text(json.dumps(dict(passed=True, boot_id='test-boot', updated_unix=now)))
        self.assertTrue(probe.check_watcher(self.root, 'test-boot')['passed'])
        (self.root / 'STOP').write_text('fault')
        with self.assertRaises(RuntimeError): probe.check_watcher(self.root, 'test-boot')

    def test_queue_query_uses_launch_context_and_both_pointers(self):
        seen = []
        context = types.SimpleNamespace(get_pointer_type=lambda p: seen.append(p) or 'host')
        stream = types.SimpleNamespace(sycl_queue=123, get_context=lambda: context)
        result = probe.query_usm_kind(None, stream, 4096, 8192)
        self.assertEqual(result['kinds'], ['host', 'host'])
        self.assertEqual(seen, [4096, 8192])
        self.assertEqual(probe.query_usm_kind(None, types.SimpleNamespace(sycl_queue=123), 1, 2)['status'], 'unavailable')

    def test_postflight_requires_a_new_sample(self):
        receipt = dict(boot_id='test-boot', health_sha256='hash')
        old = dict(passed=True, read_started_unix=9)
        new = dict(passed=True, read_started_unix=11)
        with patch.object(probe, 'check_receipt_watcher', side_effect=[old, new]):
            self.assertEqual(probe.wait_postflight(self.root, receipt, 10), new)
        with patch.object(probe, 'check_receipt_watcher', return_value=old):
            with self.assertRaisesRegex(RuntimeError, 'after worker exit'):
                probe.wait_postflight(self.root, receipt, 10, timeout=.01)

    def test_watcher_health_hash_mismatch(self):
        now = dt.datetime.now(dt.timezone.utc).timestamp()
        (self.root / 'watcher.json').write_text(json.dumps(dict(
            passed=True, boot_id='test-boot', updated_unix=now, health_sha256='wrong')))
        with self.assertRaisesRegex(RuntimeError, 'different health'):
            probe.check_watcher(self.root, 'test-boot', 'right')

    @unittest.skipUnless(hasattr(os, 'fork'), 'Linux signal guardian test')
    def test_guardian_records_native_signal_without_runtime_imports(self):
        import signal
        args = ['--health-receipt', str(self.path), '--receipt-dir', str(self.root / 'signal')]
        with patch.object(probe, 'admission', return_value=dict(boot_id='test-boot', health_sha256='hash')), \
             patch.object(probe, 'check_watcher', return_value=dict(passed=True)), \
             patch.object(probe, 'wait_postflight', return_value=dict(passed=True)), \
             patch.object(probe, 'run_device', side_effect=lambda *a: os.kill(os.getpid(), signal.SIGALRM)):
            previous = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)}
            try:
                self.assertEqual(probe.main(args), 2)
            finally:
                for sig, handler in previous.items(): signal.signal(sig, handler)
        outcome = json.loads((self.root / 'signal/receipt.json').read_text())
        self.assertFalse(outcome['passed'])
        self.assertEqual(outcome['exception']['name'], 'SIGALRM')
        self.assertEqual(outcome['gather_launches'], 0)

    def test_kernel_contract_and_single_launch_sync(self):
        tree = ast.parse((HERE / 'slab_kernels.py').read_text())
        indirect, direct = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
        self.assertEqual([a.arg for a in indirect.args.args], ['resident_base', 'offset_table', 'output'])
        self.assertIn('host_uva_base', [a.arg for a in direct.args.args])
        source = (HERE / 'single_rank_slab_probe.py').read_text()
        self.assertEqual(source.count('get_accelerator_view_from_cpu_tensor(view)'), 1)
        self.assertEqual(source.count('kernel[(4,)]'), 1)
        self.assertEqual(source.count('torch.xpu.synchronize(0)'), 1)


if __name__ == '__main__': unittest.main()
