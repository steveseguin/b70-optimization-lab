"""CPU-only loader, environment and confinement regression tests."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import entry_sandbox
import launch_env


class LaunchEnvironmentTest(unittest.TestCase):
    def test_recorded_environment_has_umf_tcm_and_no_inheritance(self):
        source = Path(__file__).parent.parent / 'stage2/packet139-record-bundle/v5/launch-environment.json'
        self.assertEqual(launch_env.environment(), json.loads(source.read_text()))
        self.assertIn('/umf/1.1/lib', launch_env.library_path())
        self.assertIn('/tcm/1.5/lib', launch_env.library_path())
        with patch.dict('os.environ', {'SECRET': 'never-copy', 'LD_PRELOAD': '/bad'}):
            command = launch_env.env_command(['/usr/bin/true'])
        self.assertEqual(command[:2], ['/usr/bin/env', '-i'])
        self.assertNotIn('never-copy', ' '.join(command))
        self.assertNotIn('LD_PRELOAD', ' '.join(command))

    def test_missing_library_fails_even_with_zero_ldd_status(self):
        def runner(argv, **kwargs):
            self.assertIn('LD_LIBRARY_PATH=' + launch_env.library_path(), argv)
            return subprocess.CompletedProcess(argv, 0, 'libumf.so.1 => not found\n', '')
        row = launch_env.check_binary('/usr/bin/true', runner=runner)
        self.assertFalse(row['passed'])
        self.assertEqual(row['missing'], ['libumf.so.1'])

    def test_ldd_nonzero_fails_and_non_elf_is_refused(self):
        row = launch_env.check_binary('/usr/bin/true', runner=lambda a, **kw:
                                     subprocess.CompletedProcess(a, 1, '', 'bad ELF'))
        self.assertFalse(row['passed'])
        with self.assertRaises(ValueError):
            launch_env.check_binary(__file__)

    def test_real_loader_under_closed_environment(self):
        self.assertTrue(launch_env.check_binary('/usr/bin/true')['passed'])

    def test_sandbox_denies_model_file_and_device_access(self):
        with tempfile.TemporaryDirectory() as directory:
            payload = Path(directory) / 'weights.gguf'
            payload.write_text('must-not-read-this')
            for path in (str(payload), '/dev/zero'):
                result = entry_sandbox.run(launch_env.env_command(['/usr/bin/cat', path]),
                                           binary='/usr/bin/cat')
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, '')
                self.assertIn('Permission denied', result.stderr)

    def test_own_mapping_metadata_is_available_to_intel_loader(self):
        result = entry_sandbox.run(launch_env.env_command(['/usr/bin/cat', '/proc/self/maps']),
                                   binary='/usr/bin/cat')
        self.assertEqual(result.returncode, 0)
        self.assertIn('/usr/', result.stdout)

    def test_real_missing_library_detected_without_running_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'lib.c').write_text('int rehearsal_symbol(void) { return 0; }\n')
            (root / 'main.c').write_text('extern int rehearsal_symbol(void);\nint main(void) { return rehearsal_symbol(); }\n')
            for command in (
                ['/usr/bin/gcc', '-shared', '-fPIC', str(root/'lib.c'), '-o', str(root/'librehearsal.so')],
                ['/usr/bin/gcc', str(root/'main.c'), '-L'+str(root), '-lrehearsal', '-o', str(root/'native')],
            ):
                subprocess.run(command, check=True, stdin=subprocess.DEVNULL,
                               capture_output=True, timeout=15)
            env = launch_env.environment()
            env['LD_LIBRARY_PATH'] = str(root)
            self.assertTrue(launch_env.check_binary(root/'native', env)['passed'])
            (root/'librehearsal.so').rename(root/'saved-library')
            row = launch_env.check_binary(root/'native', env)
            self.assertFalse(row['passed'])
            self.assertEqual(row['missing'], ['librehearsal.so'])


if __name__ == '__main__':
    unittest.main()
