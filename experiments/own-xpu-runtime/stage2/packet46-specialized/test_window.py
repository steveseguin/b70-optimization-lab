"""CPU-only negative controls. All process/journal/device interaction is mocked."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import signal
import tempfile
import unittest
from unittest.mock import patch

import preparation
import summarize
import window_support as support


class AdmissionTests(unittest.TestCase):
    def test_cutoff_before_any_build(self):
        with self.assertRaisesRegex(ValueError, 'prohibited before'):
            preparation.limits(now=datetime(2026, 10, 17, 2, 54, 59, tzinfo=timezone.utc))
        with patch.object(preparation.os, 'getpriority', return_value=19), \
             patch.object(preparation.os, 'sched_getaffinity', return_value={4, 5}), \
             patch.object(preparation.shutil, 'disk_usage') as disk:
            disk.return_value.free = 10_000_000_000
            self.assertEqual(preparation.limits(now=preparation.NOT_BEFORE)['nice'], 19)
            with self.assertRaisesRegex(ValueError, 'storage floor'):
                preparation.limits(now=preparation.NOT_BEFORE, planned_write_bytes=2_000_000_001)

    def test_closed_environment(self):
        self.assertEqual(support.environment({'LD_LIBRARY_PATH': '/runtime'})['OMP_NUM_THREADS'], '2')
        for env in ({}, {'LD_LIBRARY_PATH': '/runtime', 'ZE_AFFINITY_MASK': '1'},
                    {'LD_LIBRARY_PATH': '/runtime', 'OMP_NUM_THREADS': '32'}):
            with self.assertRaises(ValueError):
                support.environment(env)

    def test_sealed_paths_and_changed_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'source.cpp').write_text('pinned')
            files = {'source.cpp': support.sha(root / 'source.cpp')}
            support.verify_files(files, root)
            (root / 'source.cpp').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'changed'):
                support.verify_files(files, root)
            for path in ('../escape', '/absolute'):
                with self.assertRaisesRegex(ValueError, 'unsafe'):
                    support.inside(root, path)

    def test_fresh_exact_companions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            identity = dict(seal_sha256='seal', binary_sha256='binary', card=0,
                            boot_id='boot', environment={'test': 'only'})
            paths = []
            for index in range(2):
                out = root / str(index)
                out.mkdir()
                (out / 'native.json').write_text('{}')
                row = dict(schema='own-runtime.packet46.window.v1', **identity,
                           mode='exact', passed=True, device_executed=True, child_still_running=False,
                           pid=100 + index, process_start_ticks=index + 1, exact_output_identity='identical',
                           native_files={'native.json': support.sha(out / 'native.json')})
                path = out / 'window.json'
                path.write_text(json.dumps(row))
                paths.append(path)
            self.assertEqual(len(support.prerequisite(paths, identity)), 2)
            with self.assertRaisesRegex(ValueError, 'distinct'):
                support.prerequisite([paths[0], paths[0]], identity)
            row = json.loads(paths[1].read_text())
            row['exact_output_identity'] = 'changed'
            paths[1].write_text(json.dumps(row))
            with self.assertRaisesRegex(ValueError, 'identity differs'):
                support.prerequisite(paths, identity)

    def test_supervisor_never_hard_kills(self):
        import io
        class Clock:
            value = 0
            def now(self): return self.value
            def sleep(self, seconds): self.value += seconds
        class Child:
            pid = 123
            returncode = None
            signals = []
            def poll(self): return None
            def send_signal(self, sig): self.signals.append(sig)
        clock, child, reasons, latched = Clock(), Child(), [], []
        row = support.SUPERVISION.supervise(child, 1, 'cursor', io.StringIO(), reasons,
            latched.append, lambda: None, read_journal=lambda cursor: ('', cursor),
            now=clock.now, sleep=clock.sleep, drain_seconds=2,
            memory_sensor=lambda pid: dict(root_seen=True, anonymous_bytes=1, processes=[]))
        self.assertTrue(row['child_still_running'])
        self.assertEqual(child.signals, [signal.SIGTERM])
        self.assertTrue(latched)


class SummaryTests(unittest.TestCase):
    @staticmethod
    def fixture(root):
        (root / 'receipt.json').write_text(json.dumps(dict(passed=True, mode='timing',
            cpu_mock=False, safe_to_exit=True, timing_pair_checks=420)))
        rows = []
        for layer, count in summarize.BASELINE_LAUNCHES.items():
            for iteration in range(210):
                for arm in ('current', 'specialized'):
                    launches = count if arm == 'current' else count - 10
                    # Current 350/410 us; specialized250/310 us: paired100us.
                    events = [dict(id=i+1, start_ns=1+i*10000, end_ns=1+(i+1)*10000,
                                   **{'class': 'mock'}) for i in range(launches)]
                    rows.append(dict(layer=layer, iteration=iteration, mode=arm,
                        warmup=iteration < 10, position=4095, occupied_context=4096,
                        submissions=launches, gpu_ns=launches*10000,
                        classes_ns={'mock': launches*10000}, events=events))
        return rows

    def test_complete_event_accounting_and_bar(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = self.fixture(root)
            def write(data):
                (root / 'iterations.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in data))
            write(rows)
            result = summarize.timing(root)
            self.assertTrue(all(row['bar_passed'] for row in result['layers'].values()))
            self.assertEqual(result['layers']['qsa']['paired_saved_gpu_us']['median'], 100)
            mutations = [lambda data: data.pop(),
                         lambda data: data.append(data[0]),
                         lambda data: data[0].update(gpu_ns=1),
                         lambda data: data[0].update(occupied_context=1),
                         lambda data: data[0]['events'][0].update(end_ns=0),
                         lambda data: data[0]['events'][0].update(id=2)]
            for mutate in mutations:
                data = copy.deepcopy(rows)
                mutate(data)
                write(data)
                with self.assertRaises(ValueError):
                    summarize.timing(root)


if __name__ == '__main__':
    unittest.main()
