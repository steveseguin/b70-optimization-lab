#!/usr/bin/env python3
"""CPU synthetic tests for post-exit trace discovery and rank binding."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('build_manifest', Path(__file__).with_name('build_manifest.py'))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.output = self.root / 'map.json'
        identity = self.write('identity.json', {'schema': 'own-xpu-runtime.packet4.a367-census-identity.v1', 'arm': 'eager-census'})
        self.write('census-run.json', {'identity_sha256': MODULE.analysis.sha(identity), 'schema': 'own-xpu-runtime.packet4.a367-census.v1',
            'clean_exit': True, 'gap_complete': True, 'passed': False})

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
        return path

    def receipt(self, rank=0, pid=123):
        return self.write(f'markers/marker-rank-{rank}-pid-{pid}.json',
            {'schema': 'a367-census-marker-rank-v1', 'rank': rank, 'pid': pid,
             'source_pins': MODULE.marks.SOURCE_PINS})

    def trace(self, pid=123, gpu=True, name='unitrace/p0/chrome_trace.json'):
        events = [{'ph': 'M', 'name': 'process_name', 'pid': pid, 'args': {'name': 'python'}}]
        if gpu:
            events += [{'ph': 'X', 'cat': 'gpu_op', 'name': 'opaque', 'pid': 999000,
                        'tid': 1, 'ts': 100, 'dur': 10, 'args': {'id': '1'}}]
        return self.write(name, {'traceEvents': events})

    def build(self, arm='eager-census'):
        if arm != 'eager-census':
            identity = self.write('identity.json', {'schema': 'own-xpu-runtime.packet4.a367-census-identity.v1', 'arm': arm})
            life = json.loads((self.root / 'census-run.json').read_text())
            life['identity_sha256'] = MODULE.analysis.sha(identity)
            self.write('census-run.json', life)
        return MODULE.build(self.root, arm, self.output)

    def test_rank_bound_to_host_metadata_not_device_pid(self):
        self.receipt()
        self.trace()
        result = self.build()
        self.assertEqual(result['traces'][0]['rank'], 0)
        self.assertEqual(result['traces'][0]['worker_pid'], 123)

    def test_parent_api_trace_retained_excluded(self):
        self.trace(pid=55, gpu=False)
        result = self.build()
        self.assertEqual(len(result['excluded_traces']), 1)
        self.assertIn('parent/API-only', result['excluded_traces'][0]['reason'])

    def test_unbound_device_work_not_silently_attributed(self):
        self.trace()
        self.assertEqual(self.build()['excluded_traces'][0]['device_events'], 1)

    def test_missing_ranks_not_created(self):
        self.receipt()
        self.trace()
        self.assertEqual(len(self.build()['traces']), 1)

    def test_graph_reference_no_fake_trace(self):
        result = self.build('graph-reference')
        self.assertEqual(result['traces'], [])
        self.assertIn('no fabricated', result['notes'][0])

    def test_graph_missing_devices_reported_opaque(self):
        self.receipt()
        self.trace(gpu=False)
        self.assertTrue(self.build('graph-census')['graph_opaque'])

    def test_lifecycle_clean_exit_required(self):
        self.write('census-run.json', {'schema': 'own-xpu-runtime.packet4.a367-census.v1', 'clean_exit': False, 'gap_complete': True})
        with self.assertRaisesRegex(ValueError, 'clean exit'):
            self.build()

    def test_lifecycle_gap_required(self):
        self.write('census-run.json', {'schema': 'own-xpu-runtime.packet4.a367-census.v1', 'clean_exit': True, 'gap_complete': False})
        with self.assertRaisesRegex(ValueError, 'post-exit gap'):
            self.build()

    def test_false_overall_pass_does_not_hide_findings(self):
        self.assertEqual(self.build()['traces'], [])

    def test_arm_cannot_be_relabeled(self):
        with self.assertRaisesRegex(ValueError, 'arm or identity'):
            MODULE.build(self.root, 'graph-census', self.output)

    def test_identity_hash_drift_fails(self):
        identity = json.loads((self.root / 'identity.json').read_text())
        identity['changed'] = True
        self.write('identity.json', identity)
        with self.assertRaisesRegex(ValueError, 'arm or identity'):
            self.build()

    def test_source_pin_drift_fails(self):
        path = self.receipt()
        value = json.loads(path.read_text())
        value['source_pins'] = {}
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'source pins'):
            self.build()

    def test_duplicate_rank_fails(self):
        self.receipt()
        self.receipt(pid=456)
        with self.assertRaisesRegex(ValueError, 'duplicate worker'):
            self.build()

    def test_symlink_trace_fails(self):
        self.receipt()
        path = self.trace()
        path.with_name('link.json').symlink_to(path)
        with self.assertRaisesRegex(ValueError, 'regular file'):
            self.build()

    def test_truncated_chrome_trace_fails(self):
        path = self.trace()
        path.write_text('{"traceEvents":[')
        with self.assertRaises(json.JSONDecodeError):
            self.build()

    def test_non_chrome_config_ignored(self):
        self.write('unitrace/run_config.json', {'options': []})
        self.assertEqual(self.build()['traces'], [])

    def test_manifest_roundtrip_hash_binding(self):
        self.receipt()
        self.trace()
        self.output.write_text(json.dumps(self.build()))
        result = MODULE.analysis.analyze(self.output)
        self.assertEqual(result['rank_summaries'][0]['kernel_count'], 1)
        self.assertFalse(result['segmentation_complete'])


if __name__ == '__main__':
    unittest.main()
