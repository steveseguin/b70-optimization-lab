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

import summarize
import preparation
import window_support as support
import window


class AdmissionTests(unittest.TestCase):
    def test_cpu_priority_affinity_and_build_reserve(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(preparation, 'HERE', Path(directory)), \
                patch.object(preparation.os, 'getpriority', return_value=19), \
                patch.object(preparation.os, 'sched_getaffinity', return_value={4, 20}), \
                patch.object(preparation.shutil, 'disk_usage', return_value=SimpleNamespace(free=20_000_000_000)):
            self.assertEqual(preparation.limits()['affinity'], [4, 20])
            with patch.object(preparation.os, 'getpriority', return_value=0):
                with self.assertRaisesRegex(AssertionError, 'nice19'):
                    preparation.limits()
            with patch.object(preparation.os, 'sched_getaffinity', return_value={0, 4}):
                with self.assertRaisesRegex(AssertionError, 'affinity'):
                    preparation.limits()
            with patch.object(preparation.shutil, 'disk_usage', return_value=SimpleNamespace(free=18_000_000_000)):
                with self.assertRaisesRegex(AssertionError, 'reserve'):
                    preparation.limits(planned_write_bytes=1)
            build = Path(directory) / 'build'
            build.mkdir()
            with (build / 'own-sparse-scratch').open('wb') as stream:
                stream.truncate(999_999_999)
            with self.assertRaisesRegex(AssertionError, '1 GB build cap'):
                preparation.limits(planned_write_bytes=1)

    def test_early_window_refusals_never_launch(self):
        args = ['--mode', 'exact', '--card', '0', '--output', '/unused']
        with patch.object(window.subprocess, 'Popen') as launch:
            with self.assertRaisesRegex(ValueError, 'authorization'):
                window.main(args)
            for seconds in ('0', 'nan', 'inf', '1200', '1140', '7200'):
                with self.subTest(seconds=seconds), self.assertRaisesRegex(ValueError, '2880'):
                    window.main(args + ['--authorized-device-window', '--seconds', seconds])
            with patch.object(window.os, 'getpriority', return_value=0):
                with self.assertRaisesRegex(ValueError, 'nice 19'):
                    window.main(args + ['--authorized-device-window'])
            with patch.object(window.os, 'getpriority', return_value=19), \
                    patch.object(window.os, 'sched_getaffinity', return_value={0, 4}):
                with self.assertRaisesRegex(ValueError, 'affinity'):
                    window.main(args + ['--authorized-device-window'])
            launch.assert_not_called()

    def test_storage_reserve_and_visible_gpu_owner_refuse(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(support.shutil, 'disk_usage', return_value=SimpleNamespace(free=8_064_000_000)):
                with self.assertRaisesRegex(ValueError, 'free-storage floor'):
                    support.storage(root)
            fdinfo = root / '123' / 'fdinfo'
            fdinfo.mkdir(parents=True)
            self.assertEqual(support.gpu_clients(root)['visible_xe_clients'], [])
            (fdinfo / '4').write_text('drm-driver: xe\ndrm-pdev: 0000:23:00.0\n')
            with self.assertRaisesRegex(ValueError, 'foreign Xe clients'):
                support.gpu_clients(root)

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

    def test_exiting_task_without_mm_is_tolerated_only_with_pf_exiting(self):
        # p52-a-e1: the native child lost RssAnon in exit_mm() while still R.
        with tempfile.TemporaryDirectory() as directory:
            proc = Path(directory)
            root = proc / '123'
            root.mkdir()
            for state in ('R', 'D'):
                (root / 'status').write_text(f'State:\t{state} (exiting)\n')
                # Include parentheses/spaces in comm to check field parsing.
                (root / 'stat').write_text(f'123 (expert (order) bench) {state} 1 123 123 0 -1 4194560 0 0\n')
                with self.subTest(state=state), self.assertRaisesRegex(ValueError, 'missing/malformed RssAnon'):
                    support.process_tree_anon(123, proc)
                (root / 'stat').write_text(f'123 (expert (order) bench) {state} 1 123 123 0 -1 4194564 0 0\n')
                result = support.process_tree_anon(123, proc)
                self.assertEqual(result['anonymous_bytes'], 0)
                self.assertFalse(result['root_seen'])

    def test_fault_review_requires_past_utc(self):
        started = int(datetime(2026, 10, 17, tzinfo=timezone.utc).timestamp() * 1_000_000)
        review, stamp = support.SUPERVISION.fault_review('2026-10-16T23:59:59Z', started)
        self.assertEqual(review, '2026-10-16T23:59:59Z')
        self.assertLess(stamp, started)
        for value in ('2026-10-17T00:00:01Z', '2026-10-17T00:00:00-01:00',
                      '2026-10-16T23:59:59', '2026-10-16'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                support.SUPERVISION.fault_review(value, started)

    def test_seal_requires_each_passing_cpu_gate_and_bound_binary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'source.cpp').write_text('source')
            (root / 'build/device').mkdir(parents=True)
            (root / 'build/device/virtual-bench').write_text('binary')
            gates = {}
            for name in ('python-gates.json', 'cpu-gates.json', 'build-receipt.json'):
                (root / name).write_text(json.dumps(dict(passed=True, device_executed=False)))
                gates[name] = support.sha(root / name)
            seal = dict(schema='own-runtime.packet53b.seal.v1', passed=True, device_executed=False,
                        sources={'source.cpp': support.sha(root / 'source.cpp')},
                        artifacts={'build/device/virtual-bench': support.sha(root / 'build/device/virtual-bench')},
                        gates=gates)
            def check(row):
                (root / 'seal.json').write_text(json.dumps(row))
                return support.sealed_gate(root=root, repo=root)
            self.assertTrue(check(seal)['passed'])
            row = copy.deepcopy(seal)
            row['gates'].pop('cpu-gates.json')
            with self.assertRaisesRegex(ValueError, 'complete named CPU gates'):
                check(row)
            for change in (dict(passed=False, device_executed=False),
                           dict(passed=True, device_executed=True)):
                row = copy.deepcopy(seal)
                (root / 'cpu-gates.json').write_text(json.dumps(change))
                row['gates']['cpu-gates.json'] = support.sha(root / 'cpu-gates.json')
                with self.assertRaisesRegex(ValueError, 'failed or non-CPU gate'):
                    check(row)
            (root / 'cpu-gates.json').write_text(json.dumps(dict(passed=True, device_executed=False)))
            (root / 'build/device/virtual-bench').write_text('changed binary')
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
                for name in ('receipt.json', 'comparisons.jsonl', 'iterations.jsonl', 'manifest.json'):
                    (out / 'run' / name).write_text('{}')
                    native_files['run/' + name] = support.sha(out / 'run' / name)
                row = dict(schema='own-runtime.packet53b.window.v1', **identity,
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
    def manifest(root):
        spec = dict(classes=list(summarize.CLASSES), variants=list(summarize.VARIANTS),
                    warmup=10, iterations=210, exact_fixtures=2,
                    class_variants={c:list(v) for c,v in summarize.CLASS_VARIANTS.items()},
                    m_values=[1,2], routes=10,
                    expected_buffers=summarize.EXPECTED_BUFFERS,
                    expected_bytes=summarize.EXPECTED_BYTES,
                    expected_events=summarize.EXPECTED_EVENTS)
        (root / 'manifest.json').write_text(json.dumps(spec))
        return spec

    @staticmethod
    def receipt(root, mode, checks=0):
        (root / 'receipt.json').write_text(json.dumps(dict(schema='ownrt.packet53b.bench.v1',
            mode=mode, passed=True, safe_to_exit=True, device_executed=True, checks=checks)))

    @staticmethod
    def write(root, name, rows):
        (root / name).write_text(''.join(json.dumps(r)+'\n' for r in rows))

    def test_exact_complete_inventory_and_production_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.manifest(root)
            rows = [dict(**{'class': c}, variant=v, m=m, token_row=t, iteration=i,
                         equal=True, sha256='a'*64, cpu_sha256='a'*64,
                         production_equal=True, production_sha256='a'*64,
                         buffers=summarize.EXPECTED_BUFFERS[c], bytes=summarize.EXPECTED_BYTES[c])
                    for c in summarize.CLASSES for v in ('control', *summarize.CLASS_VARIANTS[c])
                    for m in (1,2) for t in range(m) for i in range(2)]
            self.receipt(root, 'exact', len(rows))
            with patch.object(summarize, 'HERE', root):
                self.write(root, 'comparisons.jsonl', rows)
                result = summarize.exact(root)
                self.assertEqual(result['comparisons'], len(rows))
                self.write(root, 'comparisons.jsonl', list(reversed(rows)))
                self.assertEqual(summarize.exact(root)['exact_output_identity'], result['exact_output_identity'])
                mutations = [lambda d: d.pop(), lambda d: d.append(d[0]),
                    lambda d: d[0].update(cpu_sha256='b'*64),
                    lambda d: d[0].update(equal=False), lambda d: d[0].update(buffers=1),
                    lambda d: d[0].update(bytes=30),
                    lambda d: d[0].update(sha256='x'*64, cpu_sha256='x'*64),
                    lambda d: d[0].update(production_equal=False),
                    lambda d: d[0].update(production_sha256='b'*64),
                    # A self-consistent own-mirror claim must still match the real control.
                    lambda d: d[6].update(sha256='b'*64, cpu_sha256='b'*64, production_sha256='b'*64),
                    lambda d: d.__setitem__(slice(None), [r for r in d if r['variant'] != 'control']),
                    lambda d: d.__setitem__(slice(None), [r for r in d if not(r['m']==2 and r['token_row']==1)])]
                for mutate in mutations:
                    changed = copy.deepcopy(rows)
                    mutate(changed)
                    self.write(root, 'comparisons.jsonl', changed)
                    with self.assertRaises(ValueError):
                        summarize.exact(root)

    def test_timing_event_pair_and_m2_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.manifest(root)
            self.receipt(root, 'timing')
            rows=[]
            for c in summarize.CLASSES:
              for v in summarize.CLASS_VARIANTS[c]:
               for m in (1,2):
                for t in range(m):
                 for i in range(210):
                  for arm in ('control',v):
                    duration = 20000 if arm == 'control' else 10000
                    rows.append(dict(**{'class':c}, variant=arm, pair_variant=v, m=m,
                        token_row=t, iteration=i, warmup=i<10, gpu_ns=duration*summarize.EXPECTED_EVENTS[c][arm],
                        events=[dict(start_ns=1+j*100000,end_ns=1+j*100000+duration) for j in range(summarize.EXPECTED_EVENTS[c][arm])]))
            with patch.object(summarize, 'HERE', root):
                self.write(root, 'iterations.jsonl', rows)
                result=summarize.timing(root)
                for c in summarize.CLASSES:
                    for v in summarize.CLASS_VARIANTS[c]:
                        self.assertEqual(result['classes'][c][v]['1']['median_paired_saved_us'],10*summarize.EXPECTED_EVENTS[c]['control'])
                        self.assertEqual(result['classes'][c][v]['2']['median_paired_saved_us'],20*summarize.EXPECTED_EVENTS[c]['control'])
                mutations = [lambda d:d.pop(),lambda d:d.append(d[0]),
                    lambda d:d[0].update(gpu_ns=1),lambda d:d[0].update(warmup=False),
                    lambda d:d[0].update(pair_variant='unknown'),
                    lambda d:d[0]['events'][0].update(end_ns=0),
                    lambda d:d[0]['events'].append(copy.deepcopy(d[0]['events'][0])),
                    lambda d:d[0]['events'].pop(),
                    lambda d:d.__setitem__(slice(None),[r for r in d if not(r['m']==2 and r['token_row']==1)])]
                for mutate in mutations:
                    changed=copy.deepcopy(rows)
                    mutate(changed)
                    self.write(root,'iterations.jsonl',changed)
                    with self.assertRaises(ValueError):
                        summarize.timing(root)

    def test_common_selection_both_owners_and_exact_threshold(self):
        def summaries(savings):
            return [dict(classes={c:{v:{'1':dict(median_paired_saved_us=savings(owner,c,v)),
                                      '2':dict(median_paired_saved_us=10000)}
                                    for v in summarize.CLASS_VARIANTS[c]} for c in summarize.CLASSES})
                    for owner in range(2)]
        good=summaries(lambda owner,c,v:20)
        result=summarize.choose(good)
        self.assertTrue(result['virtualization_proceeds'])
        self.assertEqual(result['owner_saved_us'],[80,80])
        self.assertTrue(all(r['variant']==min(summarize.CLASS_VARIANTS[c]) for c,r in result['selected_classes'].items()))
        disagree=summaries(lambda owner,c,v:30 if v==summarize.CLASS_VARIANTS[c][owner] else -1)
        result=summarize.choose(disagree)
        self.assertFalse(result['virtualization_proceeds'])
        self.assertTrue(all(r['variant']=='control' for r in result['selected_classes'].values()))
        below=summaries(lambda owner,c,v:20 if owner==0 else 8.5)
        self.assertEqual(summarize.choose(below)['owner_saved_us'],[80,34])
        self.assertFalse(summarize.choose(below)['virtualization_proceeds'])
        threshold=summaries(lambda owner,c,v:35 if c==summarize.CLASSES[0] else 0)
        self.assertTrue(summarize.choose(threshold)['virtualization_proceeds'])
        # M2 savings are huge in every fixture; they cannot rescue zero M1.
        zero=summaries(lambda owner,c,v:0)
        self.assertFalse(summarize.choose(zero)['virtualization_proceeds'])
        self.assertTrue(all(r['variant']=='control' for r in summarize.choose(zero)['selected_classes'].values()))
        invalid=summaries(lambda owner,c,v:float('nan'))
        with self.assertRaisesRegex(ValueError,'nonfinite'):
            summarize.choose(invalid)

    def test_timing_pair_revalidates_native_and_exact_companions(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'seal.json').write_text('sealed')
            (root/'build/device').mkdir(parents=True)
            (root/'build/device/virtual-bench').write_text('binary')
            identity=dict(seal_sha256=support.sha(root/'seal.json'),
                          binary_sha256=support.sha(root/'build/device/virtual-bench'),
                          card=0,boot_id='boot',environment={'PATH':'mock'},coordinator_fault_review=None)
            exact_paths=[]
            timing_paths=[]
            for index,mode in enumerate(('exact','exact','timing','timing')):
                out=root/str(index)
                (out/'run').mkdir(parents=True)
                native={}
                for name in ('receipt.json','comparisons.jsonl','iterations.jsonl','manifest.json'):
                    (out/'run'/name).write_text('{}')
                    native['run/'+name]=support.sha(out/'run'/name)
                row=dict(schema='own-runtime.packet53b.window.v1',**identity,
                    mode=mode,passed=True,device_executed=True,child_still_running=False,
                    pid=100+index,process_start_ticks=1000+index,native_files=native)
                if mode=='exact':
                    row['exact_output_identity']='identical'
                    exact_paths.append(out/'window.json')
                else:
                    row['exactness_companions']=[dict(path=str(p),sha256=support.sha(p)) for p in exact_paths]
                    timing_paths.append(out/'window.json')
                (out/'window.json').write_text(json.dumps(row))
            fake=dict(classes={c:{v:{'1':dict(median_paired_saved_us=20)} for v in summarize.CLASS_VARIANTS[c]}
                               for c in summarize.CLASSES})
            with patch.object(summarize,'HERE',root),patch.object(support,'sealed_gate',return_value={}), \
                    patch.object(summarize,'exact',return_value=dict(exact_output_identity='identical')) as exact, \
                    patch.object(summarize,'timing',return_value=fake) as timing:
                self.assertTrue(summarize.fresh_pair(timing_paths)['virtualization_proceeds'])
                self.assertEqual(exact.call_count,4)
                self.assertEqual(timing.call_count,2)
                with self.assertRaisesRegex(ValueError,'different timing'):
                    summarize.fresh_pair([timing_paths[0],timing_paths[0]])
                original=json.loads(timing_paths[1].read_text())
                for key,value in (('pid',102),('binary_sha256','other'),('card',1),('boot_id','other'),
                                  ('passed',False),('child_still_running',True)):
                    changed=copy.deepcopy(original)
                    changed[key]=value
                    if key=='pid':
                        changed['process_start_ticks']=1002
                    timing_paths[1].write_text(json.dumps(changed))
                    with self.subTest(key=key),self.assertRaises(ValueError):
                        summarize.fresh_pair(timing_paths)
                timing_paths[1].write_text(json.dumps(original))
                (timing_paths[0].parent/'run/iterations.jsonl').write_text('changed')
                with self.assertRaisesRegex(ValueError,'sealed input changed'):
                    summarize.fresh_pair(timing_paths)
                (timing_paths[0].parent/'run/iterations.jsonl').write_text('{}')
                exact_paths[0].write_text(exact_paths[0].read_text()+'\n')
                with self.assertRaisesRegex(ValueError,'exactness companion changed'):
                    summarize.fresh_pair(timing_paths)


class CoordinatorRehearsalTests(unittest.TestCase):
    def test_full_mock_exact_window(self):
        # Exercise the coordinator's real command assembly and durable receipt,
        # with every external observation/process mocked; no device or journal.
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory)
            (root / 'build').mkdir()
            (root / 'manifest.json').write_text('{"mock":true}\n')
            output = root / 'evidence' / 'exact'
            class Child:
                pid = 321
                returncode = 0
                def poll(self): return 0
            def launch(command, **kwargs):
                run = output / 'run'
                run.mkdir(exist_ok=True)
                self.assertEqual((run / 'manifest.json').read_bytes(), (root / 'manifest.json').read_bytes())
                for name in ('receipt.json', 'comparisons.jsonl', 'iterations.jsonl'):
                    (run / name).write_text('{}\n')
                return Child()
            original_read = Path.read_text
            def read(path, *args, **kwargs):
                if path == Path('/proc/self/cgroup'):
                    return '0::/user.slice/packet53b-test.service\n'
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
            with self.assertRaisesRegex(ValueError, 'boundary required'):
                window.main(['--authorized-device-window', '--mode', 'exact', '--card', '0',
                             '--output', str(output)])
            with self.assertRaisesRegex(ValueError, 'future'):
                window.main(['--authorized-device-window', '--mode', 'exact', '--card', '0',
                             '--faults-reviewed-through', '2100-01-01T00:00:00Z',
                             '--output', str(output)])
            mocked_launch.assert_not_called()
            self.assertFalse(output.exists())
            result = window.main(['--authorized-device-window', '--mode', 'exact', '--card', '0',
                                  '--faults-reviewed-through', '2026-01-01T00:00:00Z',
                                  '--output', str(output)])
            self.assertEqual(result, 0)
            row = json.loads((output / 'window.json').read_text())
            self.assertTrue(row['passed'])
            self.assertEqual(len(row['native_files']), 4)
            self.assertEqual(row['exact_output_identity'], 'mock-output')
            self.assertIs(mocked_supervision.call_args.kwargs.get('memory_sensor'),
                          support.process_tree_anon)
            self.assertEqual(mocked_launch.call_args.args[0], [str(root / 'build/device/virtual-bench'),
                '--mode', 'exact', '--card', '0', '--output', str(output / 'run'), '--authorized-device-window'])


if __name__ == '__main__':
    unittest.main()
