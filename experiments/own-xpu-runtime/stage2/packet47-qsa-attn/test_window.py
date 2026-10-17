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
        self.assertEqual(support.environment({'LD_LIBRARY_PATH': '/runtime'})['ONEAPI_DEVICE_SELECTOR'], 'level_zero:0')
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
                run=out/'run';run.mkdir()
                records=[]
                for c,m,seed,v,control,buffer in sorted(summarize.exact_keys()):
                    n={'attention.output':m*6144*2,'selection.ids':m*2051*4,'qgate.output':m*12288*2,'error':4,'readonly.input':m*32780+c*2048+8}[buffer]
                    records.append(dict(context=c,rows=m,seed=seed,variant=v,control=control,buffer=buffer,
                        bytes=n,equal=True,sha256='a'*64,expected_sha256='a'*64))
                (run/'comparisons.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
                (run/'receipt.json').write_text(json.dumps(dict(passed=True,mode='exact',cpu_mock=False,safe_to_exit=True,checks=len(records))))
                raw_identity=summarize.exact(run)['exact_output_identity']
                row = dict(schema='own-runtime.packet47.window.v1', **identity,
                           mode='exact', passed=True, device_executed=True, child_still_running=False,
                           pid=100 + index, process_start_ticks=index + 1, exact_output_identity=raw_identity,
                           native_files={str(p.relative_to(out)):support.sha(p) for p in run.iterdir()})
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


class CoordinatorRehearsalTests(unittest.TestCase):
    def test_full_mock_exact_window(self):
        # Exercise the coordinator's real command assembly and durable receipt,
        # with every external observation/process mocked; no device or journal.
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory)
            (root / 'build/device').mkdir(parents=True)
            (root / 'build/device/qsa-bench').write_text('mock executable; never invoked')
            (root / 'source').write_text('mock pinned source')
            gates={}
            for name in ('python-gates.json','cpu-gates.json','build-host.json','build-device.json'):
                (root/name).write_text(json.dumps(dict(passed=True,device_executed=False)))
                gates[name]=support.sha(root/name)
            (root/'seal.json').write_text(json.dumps(dict(schema='own-runtime.packet47.seal.v1',
                passed=True,device_executed=False,sources={'source':support.sha(root/'source')},
                artifacts={'build/device/qsa-bench':support.sha(root/'build/device/qsa-bench')},gates=gates)))
            output = root / 'evidence' / 'exact'
            class Child:
                pid = 321
                returncode = 0
                def poll(self): return 0
            def launch(command, **kwargs):
                run = output / 'run'
                run.mkdir()
                records=[]
                for c,m,seed,v,control,buffer in sorted(summarize.exact_keys()):
                    n={'attention.output':m*6144*2,'selection.ids':m*2051*4,'qgate.output':m*12288*2,'error':4,'readonly.input':m*32780+c*2048+8}[buffer]
                    records.append(dict(context=c,rows=m,seed=seed,variant=v,control=control,buffer=buffer,
                        bytes=n,equal=True,sha256='a'*64,expected_sha256='a'*64))
                (run/'comparisons.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
                (run/'receipt.json').write_text(json.dumps(dict(passed=True,mode='exact',cpu_mock=False,safe_to_exit=True,checks=len(records))))
                for name in ('iterations.jsonl','differences.jsonl'):(run/name).write_text('')
                return Child()
            original_read = Path.read_text
            def read(path, *args, **kwargs):
                if path == Path('/proc/self/cgroup'):
                    return '0::/user.slice/packet47-test.service\n'
                if path == Path('/proc/sys/kernel/random/boot_id'):
                    return 'mock-boot\n'
                return original_read(path, *args, **kwargs)
            stack.enter_context(patch.object(Path, 'read_text', read))
            stack.enter_context(patch.object(window, 'HERE', root))
            stack.enter_context(patch.object(window.os, 'getpriority', return_value=19))
            stack.enter_context(patch.object(window.os, 'sched_getaffinity', return_value={4}))
            stack.enter_context(patch.object(support, 'HERE', root))
            stack.enter_context(patch.object(support, 'REPO', root))
            stack.enter_context(patch.dict(window.os.environ, {'LD_LIBRARY_PATH':'/mock/runtime'}, clear=True))
            stack.enter_context(patch.object(window, 'host_memory', return_value={}))
            stack.enter_context(patch.object(window, 'storage', return_value={}))
            stack.enter_context(patch.object(window, 'gpu_clients', return_value={}))
            stack.enter_context(patch.object(window, 'process_start', return_value=1000))
            stack.enter_context(patch.object(window.SUPERVISION, 'journal', return_value=('', 'cursor')))
            stack.enter_context(patch.object(window.SUPERVISION, 'ldd_preflight', return_value={}))
            stack.enter_context(patch.object(window.SUPERVISION, 'supervise', return_value=dict(
                returncode=0, child_still_running=False)))
            mocked_launch = stack.enter_context(patch.object(window.subprocess, 'Popen', side_effect=launch))
            result = window.main(['--authorized-device-window', '--mode', 'exact', '--card', '0',
                                  '--output', str(output)])
            self.assertEqual(result, 0)
            row = json.loads((output / 'window.json').read_text())
            self.assertTrue(row['passed'])
            self.assertEqual(len(row['native_files']), 4)
            self.assertEqual(row['exact_output_identity'], summarize.exact(output/'run')['exact_output_identity'])
            self.assertEqual(row['environment']['ONEAPI_DEVICE_SELECTOR'], 'level_zero:0')
            self.assertEqual(row['seal_sha256'], support.sha(root/'seal.json'))
            self.assertEqual(mocked_launch.call_args.args[0], [str(root / 'build/device/qsa-bench'),
                '--mode', 'exact', '--card', '0', '--output', str(output / 'run'), '--authorized-device-window'])


if __name__ == '__main__':
    unittest.main()
