"""CPU-only negative controls. All process/journal/device interaction is mocked."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import signal
import tempfile
import unittest
from unittest.mock import patch
from contextlib import ExitStack

import preparation
import summarize
import window_support as support
import window


class AdmissionTests(unittest.TestCase):
    def test_specific_fault_signatures(self):
        for text in ('Fault response', 'Engine memory CAT error', 'engine reset',
                     'timed-out job', 'job 17 timed out', 'devcoredump', 'xe GPU coredump'):
            self.assertIsNotNone(support.SUPERVISION.FAULT.search(text))
        for text in ('hang detection enabled', 'cache restored', 'job completed'):
            self.assertIsNone(support.SUPERVISION.FAULT.search(text))

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
                row = dict(schema='own-runtime.packet48b.window.v1', **identity,
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
                    launches = count
                    duration = 10000 if arm == 'current' else 7000
                    # Current 350/410 us; specialized250/310 us: paired100us.
                    events = [dict(id=i+1, start_ns=1+i*10000, end_ns=1+i*10000+duration,
                                   **{'class': 'mock'}) for i in range(launches)]
                    rows.append(dict(layer=layer, iteration=iteration, mode=arm,
                        warmup=iteration < 10, position=4095, occupied_context=4096,
                        submissions=launches, gpu_ns=launches*duration,
                        classes_ns={'mock': launches*duration}, events=events))
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
            self.assertEqual(result['layers']['qsa']['paired_saved_gpu_us']['median'], 123)
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

    def test_missing_capture_rejected_even_when_cases_remain(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = []
            for layer in (3, 4):
                for iteration in range(6):
                    for scope, buffer in (('producer', 'first'), ('producer', 'second'),
                                          ('all-mutable-allocation', 'state')):
                        rows.append(dict(layer=layer, iteration=iteration, scope=scope,
                                         buffer=buffer, bytes=8, equal=True, sha256='a'*64))
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps(summarize.capture_manifest(rows)))
            def write(data):
                (root / 'comparisons.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in data))
                (root / 'receipt.json').write_text(json.dumps(dict(passed=True, mode='exact',
                    cpu_mock=False, safe_to_exit=True, checks=len(data), route_set_counts={'3': 2, '4': 2})))
            write(rows)
            self.assertTrue(summarize.exact(root, manifest_path=manifest)['passed'])
            write(rows[1:])
            with self.assertRaisesRegex(ValueError, 'capture manifest'):
                summarize.exact(root, manifest_path=manifest)


class CoordinatorRehearsalTests(unittest.TestCase):
    def test_full_mock_exact_window(self):
        # Exercise the coordinator's real command assembly and durable receipt,
        # with every external observation/process mocked; no device or journal.
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory)
            (root / 'build').mkdir()
            output = root / 'evidence' / 'exact'
            class Child:
                pid = 321
                returncode = 0
                def poll(self): return 0
            def launch(command, **kwargs):
                run = output / 'run'
                run.mkdir()
                for name in ('receipt.json', 'comparisons.jsonl', 'iterations.jsonl', 'exact-capture-manifest.json'):
                    (run / name).write_text('{}\n')
                return Child()
            original_read = Path.read_text
            def read(path, *args, **kwargs):
                if path == Path('/proc/self/cgroup'):
                    return '0::/user.slice/packet48b-test.service\n'
                if path == Path('/proc/sys/kernel/random/boot_id'):
                    return 'mock-boot\n'
                return original_read(path, *args, **kwargs)
            stack.enter_context(patch.object(Path, 'read_text', read))
            stack.enter_context(patch.object(window, 'HERE', root))
            stack.enter_context(patch.object(window.os, 'getpriority', return_value=19))
            stack.enter_context(patch.object(window.os, 'sched_getaffinity', return_value={4}))
            stack.enter_context(patch.object(window, 'environment', return_value={'PATH': '/mock'}))
            stack.enter_context(patch.object(window, 'sealed_gate', return_value={}))
            stack.enter_context(patch.object(window, 'identity', return_value=dict(
                card=0, boot_id='mock-boot', environment={'PATH': '/mock'},
                seal_sha256='seal', binary_sha256='binary')))
            stack.enter_context(patch.object(window, 'host_memory', return_value={}))
            stack.enter_context(patch.object(window, 'storage', return_value={}))
            stack.enter_context(patch.object(window, 'gpu_clients', return_value={}))
            stack.enter_context(patch.object(window, 'process_start', return_value=1000))
            stack.enter_context(patch.object(window.SUPERVISION, 'journal', return_value=('', 'cursor')))
            stack.enter_context(patch.object(window.SUPERVISION, 'ldd_preflight', return_value={}))
            stack.enter_context(patch.object(window.SUPERVISION, 'supervise', return_value=dict(
                returncode=0, child_still_running=False)))
            stack.enter_context(patch.object(window.summarize, 'exact', return_value=dict(
                passed=True, exact_output_identity='mock-output')))
            mocked_launch = stack.enter_context(patch.object(window.subprocess, 'Popen', side_effect=launch))
            result = window.main(['--authorized-device-window', '--mode', 'exact', '--card', '0',
                                  '--output', str(output)])
            self.assertEqual(result, 0)
            row = json.loads((output / 'window.json').read_text())
            self.assertTrue(row['passed'])
            self.assertEqual(len(row['native_files']), 4)
            self.assertEqual(row['exact_output_identity'], 'mock-output')
            self.assertEqual(mocked_launch.call_args.args[0], [str(root / 'build/device/layer-bench'),
                '--mode', 'exact', '--card', '0', '--output', str(output / 'run'), '--authorized-device-window'])


if __name__ == '__main__':
    unittest.main()
