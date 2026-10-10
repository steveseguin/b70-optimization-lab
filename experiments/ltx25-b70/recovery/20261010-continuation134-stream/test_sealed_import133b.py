"""Fresh-process sealed startup import regressions; no launcher execution."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

HERE = Path(__file__).resolve().parent
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
PACKET = ROOT / 'prepared-continuation-stream-134'
PARENT = ROOT / 'prepared-continuation-stream-133'


class SealedImport133b(unittest.TestCase):
    def invoke(self, packet=PACKET, *options):
        env = dict(os.environ, OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', PYTHONDONTWRITEBYTECODE='1')
        env.pop('PYTHONPATH', None)
        result = subprocess.run([sys.executable, '-B', str(HERE / 'sealed_import_cpu.py'),
            '--packet', str(packet), *options], env=env, cwd='/home/steve/llm-optimizations',
            text=True, capture_output=True)
        self.assertTrue(result.stdout.strip(), result.stderr)
        return result, json.loads(result.stdout)

    def test_split36_sealed_launcher_lazy_imports(self):
        result, value = self.invoke()
        self.assertEqual(result.returncode, 0, value)
        self.assertTrue(value['passed'])
        self.assertIn(str(PACKET / 'launch/text_residency133.py'), value['module_origins'])
        self.assertEqual(value['sys_path'][0], str(PACKET / 'launch'))
        self.assertNotIn(str(PACKET / 'source/scripts'), value['sys_path'])
        self.assertEqual(value['cwd'], '/home/steve/llm-optimizations')
        self.assertEqual(value['dont_write_bytecode'], 1)
        self.assertFalse(value['prepare_start_called'])
        self.assertFalse(value['launch_called'])
        self.assertFalse(value['health_receipt_read'])

    def test_legacy_sealed_launcher_imports(self):
        result, value = self.invoke(PACKET, '--mode', 'legacy')
        self.assertEqual(result.returncode, 0, value)
        self.assertEqual(value['mode'], 'legacy')

    def test_cached_launch_helper_finds_exact_oracle(self):
        result, value = self.invoke()
        self.assertEqual(result.returncode, 0, value)
        self.assertEqual(value['oracle_prompts'], 12)
        self.assertEqual(value['oracle_window_rows'], 40)
        self.assertEqual(value['oracle_sha256'], '125750aa533d91d08aab7c47b416bc15e25a1371078425a4802e3cac762442c2')

    def test_unchanged_parent_reproduces_missing_module(self):
        result, value = self.invoke(PARENT)
        self.assertEqual(result.returncode, 1, value)
        self.assertEqual(value['error_type'], 'ModuleNotFoundError')
        self.assertIn('text_residency133', value['error'])

    def test_missing_helper_fails_without_author_fallback(self):
        result, value = self.invoke(PACKET, '--block-helper')
        self.assertEqual(result.returncode, 1, value)
        self.assertEqual(value['error_type'], 'ModuleNotFoundError')
        self.assertIn('fault injection', value['error'])

    def test_missing_oracle_fails_without_packet_mutation(self):
        result, value = self.invoke(PACKET, '--block-oracle')
        self.assertEqual(result.returncode, 1, value)
        self.assertEqual(value['error_type'], 'FileNotFoundError')
        self.assertIn('fault injection', value['error'])


if __name__ == '__main__':
    unittest.main()
