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
    def test_cpu_priority_affinity_and_storage_admission(self):
        from types import SimpleNamespace
        with patch.object(preparation.os, 'getpriority', return_value=19), \
                patch.object(preparation.os, 'sched_getaffinity', return_value={4, 20}), \
                patch.object(preparation.shutil, 'disk_usage', return_value=SimpleNamespace(free=20_000_000_000)):
            self.assertEqual(preparation.limits()['affinity'], [4, 20])
            with patch.object(preparation.os, 'getpriority', return_value=0):
                with self.assertRaises(AssertionError):
                    preparation.limits()
            with patch.object(preparation.os, 'sched_getaffinity', return_value={0, 4}):
                with self.assertRaises(AssertionError):
                    preparation.limits()
            with patch.object(preparation.shutil, 'disk_usage', return_value=SimpleNamespace(free=18_000_000_000)):
                with self.assertRaises(AssertionError):
                    preparation.limits(planned_write_bytes=256_000_000)
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / 'build').mkdir()
                with (root / 'build/sparse-scratch').open('wb') as scratch:
                    scratch.truncate(1_300_000_000)
                with patch.object(preparation, 'HERE', root):
                    with self.assertRaisesRegex(AssertionError, '1.5 GB build cap'):
                        preparation.limits(planned_write_bytes=256_000_000)

    def test_zombie_memory_sensor_rejects_live_missing_rss(self):
        with tempfile.TemporaryDirectory() as directory:
            proc = Path(directory)
            root = proc / '123'
            task = root / 'task' / '123'
            task.mkdir(parents=True)
            (task / 'children').write_text('124')
            (root / 'status').write_text('State:\tS (sleeping)\nRssAnon:\t12 kB\n')
            child = proc / '124'
            child.mkdir()
            (child / 'status').write_text('State:\tZ (zombie)\n')
            result = support.process_tree_anon(123, proc)
            self.assertEqual(result['anonymous_bytes'], 12 * 1024)
            self.assertEqual(result['processes'], [{'pid': 123, 'rss_anon_bytes': 12 * 1024}])
            self.assertTrue(result['root_seen'])
            (child / 'status').write_text('State:\tS (sleeping)\n')
            with self.assertRaisesRegex(ValueError, 'missing/malformed RssAnon'):
                support.process_tree_anon(123, proc)
            (root / 'status').write_text('State:\tZ (zombie)\n')
            result = support.process_tree_anon(123, proc)
            self.assertEqual(result['anonymous_bytes'], 0)
            self.assertFalse(result['root_seen'])

    def test_seal_requires_each_passing_cpu_gate_and_bound_binary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'source.cpp').write_text('source')
            (root / 'build/device').mkdir(parents=True)
            (root / 'build/device/layer-bench').write_text('binary')
            gates = {}
            for name in ('python-gates.json', 'cpu-layer-gates.json', 'cpu-candidate-gates.json',
                         'build-layer-host.json', 'build-layer-device.json'):
                (root / name).write_text(json.dumps(dict(passed=True, device_executed=False)))
                gates[name] = support.sha(root / name)
            seal = dict(schema='own-runtime.packet51.seal.v1', passed=True, device_executed=False,
                        sources={'source.cpp': support.sha(root / 'source.cpp')},
                        artifacts={'build/device/layer-bench': support.sha(root / 'build/device/layer-bench')},
                        gates=gates)
            def check(row):
                (root / 'seal.json').write_text(json.dumps(row))
                return support.sealed_gate(root=root, repo=root)
            self.assertTrue(check(seal)['passed'])
            row = copy.deepcopy(seal)
            row['gates'].pop('cpu-layer-gates.json')
            with self.assertRaisesRegex(ValueError, 'complete named CPU gates'):
                check(row)
            for change in (dict(passed=False, device_executed=False),
                           dict(passed=True, device_executed=True)):
                row = copy.deepcopy(seal)
                (root / 'cpu-layer-gates.json').write_text(json.dumps(change))
                row['gates']['cpu-layer-gates.json'] = support.sha(root / 'cpu-layer-gates.json')
                with self.assertRaisesRegex(ValueError, 'failed or non-CPU gate'):
                    check(row)
            (root / 'cpu-layer-gates.json').write_text(json.dumps(dict(passed=True, device_executed=False)))
            (root / 'build/device/layer-bench').write_text('changed binary')
            with self.assertRaisesRegex(ValueError, 'changed'):
                check(seal)

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

    @patch.object(summarize, 'exact', return_value=dict(passed=True, exact_output_identity='identical'))
    def test_fresh_exact_companions(self, native_exact):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            identity = dict(seal_sha256='seal', binary_sha256='binary', card=0,
                            boot_id='boot', environment={'test': 'only'})
            paths = []
            for index in range(2):
                out = root / str(index)
                (out / 'run').mkdir(parents=True)
                native_files = {}
                for name in ('receipt.json', 'comparisons.jsonl', 'iterations.jsonl', 'exact-capture-manifest.json'):
                    (out / 'run' / name).write_text('{}')
                    native_files['run/' + name] = support.sha(out / 'run' / name)
                row = dict(schema='own-runtime.packet51.window.v1', **identity,
                           mode='exact', passed=True, device_executed=True, child_still_running=False,
                           pid=100 + index, process_start_ticks=index + 1, exact_output_identity='identical',
                           native_files=native_files)
                path = out / 'window.json'
                path.write_text(json.dumps(row))
                paths.append(path)
            self.assertEqual(len(support.prerequisite(paths, identity)), 2)
            self.assertEqual(native_exact.call_count, 2)
            with patch.object(summarize, 'exact', side_effect=ValueError('native captures incomplete')):
                with self.assertRaisesRegex(ValueError, 'native captures incomplete'):
                    support.prerequisite(paths, identity)
            with self.assertRaisesRegex(ValueError, 'distinct'):
                support.prerequisite([paths[0], paths[0]], identity)
            original = json.loads(paths[1].read_text())
            for key, changed in [('seal_sha256', 'other-seal'), ('binary_sha256', 'other-binary'),
                                 ('boot_id', 'other-boot'), ('card', 1),
                                 ('environment', {'test': 'changed'}),
                                 ('coordinator_fault_review', {'changed': True}),
                                 ('child_still_running', True), ('passed', False)]:
                row = copy.deepcopy(original)
                row[key] = changed
                paths[1].write_text(json.dumps(row))
                with self.subTest(key=key), self.assertRaises(ValueError):
                    support.prerequisite(paths, identity)
            row = copy.deepcopy(original)
            row['pid'], row['process_start_ticks'] = 100, 1
            paths[1].write_text(json.dumps(row))
            with self.assertRaisesRegex(ValueError, 'not fresh'):
                support.prerequisite(paths, identity)
            row = copy.deepcopy(original)
            row['exact_output_identity'] = 'changed'
            paths[1].write_text(json.dumps(row))
            with self.assertRaisesRegex(ValueError, 'identity changed|identity differs'):
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
            cpu_mock=False, safe_to_exit=True, timing_pair_checks=1260)))
        rows = []
        for layer, count in summarize.BASELINE_LAUNCHES.items():
          for m in (1, 2):
           for token_row in range(m):
            for iteration in range(210):
                for arm in ('current', 'specialized'):
                    launches = count
                    duration = 10000 if arm == 'current' else 7000
                    classes = summarize.CLASS_CENSUS[layer]
                    events = [dict(id=i+1, start_ns=1+i*10000, end_ns=1+i*10000+duration,
                                   **{'class': classes[i % len(classes)]}) for i in range(launches)]
                    totals = {}
                    for event in events:
                        totals[event['class']] = totals.get(event['class'], 0) + duration
                    rows.append(dict(layer=layer, m=m, token_row=token_row, iteration=iteration, mode=arm,
                        warmup=iteration < 10, position=4095, occupied_context=4096,
                        submissions=launches, gpu_ns=launches*duration,
                        classes_ns=totals, events=events))
        return rows

    def test_complete_event_accounting_and_bar(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = self.fixture(root)
            def write(data):
                (root / 'iterations.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in data))
            write(rows)
            result = summarize.timing(root)
            self.assertTrue(all(result['layers'][name]['bar_passed'] for name in ('ordinary_gdn', 'qsa')))
            self.assertEqual(result['layers']['qsa']['paired_saved_gpu_us']['median'], 123)
            self.assertEqual(result['layers']['qsa_m2']['paired_saved_gpu_us']['median'], 246)
            mutations = [lambda data: data.pop(),
                         lambda data: data.append(data[0]),
                         lambda data: data[0].update(gpu_ns=1),
                         lambda data: data[0].update(occupied_context=1),
                         lambda data: data[0]['events'][0].update(end_ns=0),
                         lambda data: data[0]['events'][0].update(id=2),
                         lambda data: data.__setitem__(slice(None), [row for row in data if not (row['m'] == 2 and row['token_row'] == 1)]),
                         lambda data: data[0].update(token_row=1)]
            for mutate in mutations:
                data = copy.deepcopy(rows)
                mutate(data)
                write(data)
                with self.assertRaises(ValueError):
                    summarize.timing(root)

    def test_gate_speedup_alternative_and_m2_cannot_pass_primary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = self.fixture(root)
            for scenario in ('gate_only', 'm2_only'):
                for row in rows:
                    totals = {}
                    for event in row['events']:
                        duration = 10000
                        if row['mode'] == 'specialized':
                            if scenario == 'gate_only' and event['class'] == 'expsgate':
                                duration = 6000
                            elif scenario == 'm2_only' and row['m'] == 2:
                                duration = 5000
                        event['end_ns'] = event['start_ns'] + duration
                        totals[event['class']] = totals.get(event['class'], 0) + duration
                    row['classes_ns'], row['gpu_ns'] = totals, sum(totals.values())
                (root / 'iterations.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
                result = summarize.timing(root)
                for name in ('ordinary_gdn', 'qsa'):
                    self.assertEqual(result['layers'][name]['bar_passed'], scenario == 'gate_only')
                    self.assertFalse(result['layers'][name + '_m2']['bar_passed'])
                    if scenario == 'gate_only':
                        self.assertLess(result['layers'][name]['paired_saved_gpu_us']['median'], 40)

    def test_missing_capture_rejected_even_when_cases_remain(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = []
            for layer in (3, 4):
              for m in (1, 2):
               for token_row in range(m):
                for iteration in range(6):
                    for scope, buffer in (('producer', 'first'), ('producer', 'second'),
                                          ('all-mutable-allocation', 'state')):
                        rows.append(dict(layer=layer, m=m, token_row=token_row, iteration=iteration, scope=scope,
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
                    return '0::/user.slice/packet51-test.service\n'
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
            mocked_supervision = stack.enter_context(patch.object(window.SUPERVISION, 'supervise', return_value=dict(
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
            self.assertIs(mocked_supervision.call_args.kwargs.get('memory_sensor'),
                          support.process_tree_anon)
            self.assertEqual(mocked_launch.call_args.args[0], [str(root / 'build/device/layer-bench'),
                '--mode', 'exact', '--card', '0', '--output', str(output / 'run'), '--authorized-device-window'])


if __name__ == '__main__':
    unittest.main()
