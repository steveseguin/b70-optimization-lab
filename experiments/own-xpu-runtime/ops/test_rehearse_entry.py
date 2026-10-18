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


if __name__ == '__main__':
    unittest.main()
