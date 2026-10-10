"""Every bundled helper executes from sealed bytes, with per-file fault injection.

These are import-only child processes. Never execute startup, runtime APIs or
launcher CLIs; never mutate a sealed packet to simulate a missing file.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

import runtime_packet as packet_inventory

HERE = Path(__file__).resolve().parent
PACKET = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-134')


class SealedImport134(unittest.TestCase):
    def invoke(self, *options):
        env = dict(os.environ, OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', PYTHONDONTWRITEBYTECODE='1')
        env.pop('PYTHONPATH', None)
        result = subprocess.run([sys.executable, '-B', str(HERE / 'sealed_import_cpu.py'),
            '--packet', str(PACKET), *options], env=env, cwd='/home/steve/llm-optimizations',
            text=True, capture_output=True)
        self.assertTrue(result.stdout.strip(), result.stderr)
        return result, json.loads(result.stdout)

    def check_complete(self, mode):
        result, value = self.invoke('--mode', mode)
        self.assertEqual(result.returncode, 0, value)
        expected_components = {name: str(PACKET / 'resolution/components' / name)
                               for name in packet_inventory.COMPONENTS}
        expected_runtime = {name: str(PACKET / 'source/scripts' / filename)
                            for name, filename in packet_inventory.MODULES.items()}
        self.assertEqual(value['component_helper_origins'], expected_components)
        self.assertEqual(value['runtime_helper_origins'], expected_runtime)
        self.assertEqual(value['completed_helper_imports'], sorted(
            set(expected_components.values()) | set(expected_runtime.values())))
        self.assertEqual(value['components_imported'], len(packet_inventory.COMPONENTS))
        self.assertEqual(value['runtime_helpers_imported'], len(packet_inventory.MODULES))
        environment = value['control_environment']
        self.assertEqual(environment['LTX_CHUNK_ARM'], mode)
        self.assertEqual(environment['LTX_STREAM_FRAMES'], '169' if mode == 'split36-169' else '145')
        self.assertEqual(environment['LTX_DECODER_GRAPH'], '0' if mode == 'split36-169' else '1')
        self.assertEqual(environment['LTX_CONE_GRAPH_MEMORY'], 'off' if mode == 'split36-169' else 'text-shift')
        self.assertEqual(environment['LTX_TEXT_RESIDENCY'], 'split36')
        self.assertEqual(value['sys_path'][0], str(PACKET / 'launch'))
        self.assertNotIn(str(PACKET / 'source/scripts'), value['sys_path'])
        self.assertEqual(value['runtime_sys_path'][0], str(PACKET / 'source/scripts'))
        self.assertFalse(value['prepare_start_called'])
        self.assertFalse(value['launch_called'])
        self.assertFalse(value['health_receipt_read'])

    def test_parent_off_145_every_bundled_helper(self):
        self.check_complete('off')

    def test_new_169_every_bundled_helper(self):
        self.check_complete('split36-169')


def missing_helper_test(relative):
    def test(self):
        result, value = self.invoke('--block-path', relative)
        self.assertEqual(result.returncode, 1, value)
        self.assertEqual(value['error_type'], 'ModuleNotFoundError', value)
        self.assertIn('fault injection', value['error'])
        self.assertIn(str(PACKET / relative), value['error'])
    return test


# Discovery uses the builder inventory: adding a new helper automatically adds
# a missing-helper test, while each positive run verifies actual import origins.
paths = ['resolution/components/' + name for name in packet_inventory.COMPONENTS]
paths += ['source/scripts/' + name for name in packet_inventory.MODULES.values()]
paths += ['launch/text_residency133.py']
for relative in paths:
    name = 'test_missing_' + relative.replace('/', '_').replace('.', '_')
    setattr(SealedImport134, name, missing_helper_test(relative))


if __name__ == '__main__':
    unittest.main()
