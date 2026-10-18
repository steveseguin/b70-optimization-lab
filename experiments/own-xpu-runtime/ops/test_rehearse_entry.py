"""Real proposal parsing and mocked/native CPU entry, never a service launch."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import launch_env
import rehearse_entry as entry


class RehearsalTest(unittest.TestCase):
    def setUp(self):
        self.queue = entry.lanequeue()
        self.path = Path('/usr/bin/true').resolve()
        self.spec = dict(path=str(self.path), sha256=entry.digest(self.path),
                         args=['--version'], returncode=0, contains='coreutils')
        self.job = dict(name='loader-test-B', lane='B', argv=['/usr/bin/true'],
                        plan=dict(entry_rehearsal=dict(binaries=[self.spec])))

    def test_exact_lanequeue_environment_and_unit_without_service(self):
        calls = []
        def run(argv, **kwargs):
            calls.append(argv)
            self.assertEqual(argv[:2], ['/usr/bin/env', '-i'])
            self.assertNotIn('/usr/bin/systemd-run', argv)
            self.assertIn('LD_LIBRARY_PATH=' + launch_env.library_path(), argv)
            return subprocess.CompletedProcess(argv, 0, 'GNU coreutils', '')
        with patch.object(self.queue, 'command', wraps=self.queue.command) as command:
            result = entry.rehearse(self.job, self.queue, launch_env.library_path(), runner=run)
        self.assertTrue(result['passed'])
        self.assertEqual(result['unit'], 'screen-loader-test-B')
        self.assertFalse(result['service_started'])
        self.assertFalse(result['arm_sequence_tested'])
        command.assert_called_once()
        self.assertEqual(len(calls), 2)

    def test_real_safe_native_version_and_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            proposal = Path(directory) / 'proposal.txt'
            proposal.write_text(json.dumps(self.job)+'\n')
            output = io.StringIO()
            with patch.object(entry, 'lanequeue', return_value=self.queue), \
                 patch.object(self.queue, 'library_path', return_value=launch_env.library_path()), \
                 patch('sys.argv', ['rehearse_entry.py', str(proposal)]), \
                 contextlib.redirect_stdout(output):
                self.assertEqual(entry.main(), 0)
            self.assertIn('PASS screen-loader-test-B: 1/1', output.getvalue())

    def test_own_parser_refusal_counts_but_generic_error_does_not(self):
        self.spec.pop('args')
        def runner(output, code):
            return lambda argv, **kw: subprocess.CompletedProcess(argv,
                0 if '/usr/bin/ldd' in argv else code,
                '' if '/usr/bin/ldd' in argv else output, '')
        for output, code, expected in [('unknown option --help', 1, True),
                                       ('usage: native OPTIONS', 0, True),
                                       ('failed to open model', 1, False),
                                       ('', 0, False), ('missing libumf.so.1', 127, False)]:
            with self.subTest(output=output):
                result = entry.rehearse(self.job, self.queue, launch_env.library_path(), runner(output, code))
                self.assertEqual(result['passed'], expected)

    def test_packet_override_is_tested_and_missing_lib_blocks_entry(self):
        self.job['argv'] += ['--library-path', '/compiler-only']
        calls = []
        def runner(argv, **kwargs):
            calls.append(argv)
            self.assertIn('/usr/bin/ldd', argv)
            missing = 'LD_LIBRARY_PATH=/compiler-only' in argv
            return subprocess.CompletedProcess(argv, 0, 'libumf.so.1 => not found' if missing else '', '')
        result = entry.rehearse(self.job, self.queue, launch_env.library_path(), runner)
        self.assertFalse(result['passed'])
        self.assertTrue(result['packet_library_override'])
        self.assertEqual(len(calls), 2)

    def test_stale_binary_and_empty_inventory_fail_before_exec(self):
        for specs in ([{**self.spec, 'sha256': '0'*64}], []):
            self.job['plan']['entry_rehearsal']['binaries'] = specs
            with patch.object(entry.entry_sandbox, 'run', side_effect=AssertionError('must not run')) as runner:
                self.assertFalse(entry.rehearse(self.job, self.queue, launch_env.library_path(), runner)['passed'])
                runner.assert_not_called()

    def test_script_coordinator_fails_instead_of_guessing_environment(self):
        self.job.pop('argv')
        self.job['script'] = __file__
        result = entry.rehearse(self.job, self.queue, launch_env.library_path())
        self.assertFalse(result['passed'])

    def test_proposal_error_does_not_leak_secret(self):
        self.job['env_extra'] = {'PASSWORD': 'secret-value'}
        result = entry.rehearse(self.job, self.queue, launch_env.library_path())
        self.assertFalse(result['passed'])
        self.assertNotIn('secret-value', json.dumps(result))

    def test_malformed_declaration_is_a_job_failure(self):
        self.job['plan']['entry_rehearsal'] = []
        result = entry.rehearse(self.job, self.queue, launch_env.library_path())
        self.assertFalse(result['passed'])


class ReportRehearsalTest(unittest.TestCase):
    PACKET = 'experiments/own-xpu-runtime/stage2/packet142-class-layout'
    FIX = '3d08f0a2289b32e5bb892df60690287c12e4110b'

    def job(self, script):
        return dict(name='report-test-B', lane='B', argv=[
            '/usr/bin/python3', '-B', str(script), '--variant', 'attention-order600',
            '--kind', 'smoke', '--lane', 'B', '--output', '/must-not-write',
            '--authorized-device-window'])

    def historical_copy(self, root, revision):
        # No checkout/worktree and no packet writes. Only source and its small
        # import-time registry, never retained model/device/oracle evidence.
        names = subprocess.check_output(['git', '-c', 'core.packedGitWindowSize=16m', '-c', 'core.packedGitLimit=64m', 'ls-tree', '-r', '--name-only',
            revision, '--', self.PACKET,
            'experiments/own-xpu-runtime/stage1/packet4-prep/driver/window_driver.py'], cwd=entry.ROOT, text=True).splitlines()
        for name in names:
            if not (name.endswith('.py') or name.endswith(('/kernel-registry.json', '/launch-environment.json'))):
                continue
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(subprocess.check_output(['git', '-c', 'core.packedGitWindowSize=16m', '-c', 'core.packedGitLimit=64m', 'show', revision + ':' + name],
                                                       cwd=entry.ROOT))
        return root / self.PACKET / 'v5/bracket_job.py'

    def test_history_before_fix_fails_and_after_fix_passes_both_reports(self):
        for revision, passed in [(self.FIX + '^', False), (self.FIX, True)]:
            with self.subTest(revision=revision), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                script = self.historical_copy(root, revision)
                result = entry.rehearse_report(self.job(script), launch_env.environment(), root)
                self.assertEqual(result['passed'], passed, result)
                self.assertEqual([r['kind'] for r in result['kinds']], ['smoke', 'bracket'])
                if passed:
                    self.assertTrue(all(r['real_entry_main'] for r in result['kinds']), result)
                if not passed:
                    self.assertEqual(result['kinds'][0]['error_type'], 'ImportError', result)
                    self.assertTrue(all(r['collisions'] for r in result['kinds']), result)

    def test_collision_even_when_unused_schema_errors_and_no_model_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = self.historical_copy(root, self.FIX)
            job = self.job(script)
            top = script.parent.parent / 'unused_collision.py'
            shadow = script.parent / top.name
            top.write_text('VALUE = 1\n')
            shadow.write_text('VALUE = 2\n')
            result = entry.rehearse_report(job, launch_env.environment(), root)
            self.assertFalse(result['passed'])
            self.assertTrue(all(r['report_completed'] for r in result['kinds']), result)
            self.assertEqual(result['kinds'][0]['collisions'][0]['module'], 'unused_collision')
            top.unlink()
            shadow.unlink()
            screen = script.with_name('screen.py')
            source = screen.read_text()
            for statement, error in [
                    ("raise AttributeError('secret-error-text')", 'AttributeError'),
                    ("raise KeyError('secret-error-text')", 'KeyError'),
                    ("open('/mnt/model.safetensors', 'rb')", 'PermissionError'),
                    ("__import__('subprocess').run(['/usr/bin/true'])", 'PermissionError'),
                    ("open('/tmp/opsreview5-forbidden-write', 'w')", 'PermissionError')]:
                with self.subTest(statement=statement):
                    screen.write_text(source.replace('def report_completed(output, record, identity, coordination):',
                        'def report_completed(output, record, identity, coordination):\n    ' + statement))
                    result = entry.rehearse_report(job, launch_env.environment(), root)
                    self.assertFalse(result['passed'], result)
                    self.assertTrue(all(r['error_type'] == error for r in result['kinds']), result)
                    self.assertNotIn('secret-error-text', json.dumps(result))

    def test_report_gate_is_required_in_combined_result(self):
        base = RehearsalTest()
        base.setUp()
        runner = lambda argv, **kw: subprocess.CompletedProcess(argv, 0, 'GNU coreutils', '')
        with patch.object(entry, 'rehearse_report', return_value=dict(passed=False)) as report:
            result = entry.rehearse(base.job, base.queue, launch_env.library_path(), runner, report=True)
        self.assertFalse(result['passed'])
        self.assertTrue(all(b['passed'] for b in result['binaries']))
        report.assert_called_once()

    def test_static_packages_and_off_path_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in ('shared.py', 'v5/shared/__init__.py', 'unused/shared.py'):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('')
            rows = entry.duplicate_modules(root, [str(root), str(root / 'v5')])
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['module'], 'shared')
            self.assertEqual(rows[0]['shadow'], str(root / 'v5/shared/__init__.py'))

    def test_unsupported_entry_fails(self):
        result = entry.rehearse_report(dict(argv=['/usr/bin/true']), launch_env.environment())
        self.assertFalse(result['passed'])


if __name__ == '__main__':
    unittest.main()
