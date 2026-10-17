#!/usr/bin/env python3
"""CPU-only tests: no torch import, real tracer invocation or device operation."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import analyze_feasibility as analysis
import run_driver as driver
from common import write_json


def synthetic(replay=True):
    events = []
    for phase, base in [('eager', 1000), ('replay', 100000)]:
        for index in range(50):
            timestamp = base + index * 100
            events.append(dict(ph='X', name=f'PyTorch::A367Feas|{phase}|i={index}',
                               ts=timestamp, dur=90, pid=1, tid=1))
            # Host submit names alone must never count as device visibility.
            events.append(dict(ph='X', name='zeCommandListImmediateAppendCommandListsExp',
                               ts=timestamp + 1, dur=1, pid=1, tid=1, cat='api'))
            if phase == 'replay' and not replay:
                continue
            for kernel, name in enumerate(('add', 'scalar_add', 'mul', 'sin', 'clamp', 'matmul', 'softmax', 'copy_kernel')):
                events.append(dict(ph='X', name=name, cat='gpu_op', ts=timestamp + 10 + kernel * 5,
                                   dur=2, pid=99, tid=5))
    return events


class AnalysisTests(unittest.TestCase):
    def test_full_graph_visibility(self):
        result = analysis.graph_events(synthetic())
        self.assertEqual(result['visibility'], 'yes')
        self.assertTrue(result['names_match'])
        self.assertEqual([i['kernel_count'] for i in result['replay']['iterations']], [8] * 50)

    def test_submit_only_replay_is_no(self):
        self.assertEqual(analysis.graph_events(synthetic(False))['visibility'], 'no')

    def test_missing_timestamp_is_partial(self):
        events = synthetic()
        del events[-1]['ts']
        self.assertEqual(analysis.graph_events(events)['visibility'], 'partial')

    def test_name_mismatch_is_partial(self):
        events = synthetic()
        events[-1]['name'] = 'different_kernel'
        self.assertEqual(analysis.graph_events(events)['visibility'], 'partial')

    def test_unnamed_device_events_cannot_pass(self):
        events = synthetic()
        for event in events:
            if event.get('cat') == 'gpu_op':
                del event['name']
        self.assertEqual(analysis.graph_events(events)['visibility'], 'partial')

    def test_ambiguous_marker_is_partial(self):
        events = synthetic()
        events.append(events[0].copy())
        self.assertEqual(analysis.graph_events(events)['visibility'], 'partial')

    def test_begin_end_markers(self):
        events = []
        for row in synthetic():
            if 'A367Feas' in row['name']:
                events += [dict(row, ph='B'), dict(row, ph='E', ts=row['ts'] + row['dur'])]
            else:
                events.append(row)
        self.assertEqual(analysis.graph_events(events)['visibility'], 'yes')

    def test_no_trace_or_run_is_incomplete(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = analysis.analyze(Path(temporary))
        self.assertEqual(result['verdict']['graph_replay_kernel_visibility'], 'partial')
        self.assertIsNone(result['verdict']['paused_tracer_ccl_init_stall'])

    def test_trace_files_and_stage_comparison(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rows = driver.plan(root)
            summary = driver.new_summary(root, rows, {})
            summary['status'] = 'passed'
            for row in summary['steps']:
                row.update(status='passed', rc=0, duration_s=5.)
                directory = Path(row['directory'])
                directory.mkdir()
                if row['test'] == 'graph' and row['traced']:
                    (directory / 'unitrace').mkdir()
                    write_json(directory / 'unitrace/chrome_trace.json', dict(traceEvents=synthetic()))
                if row['test'] == 'ccl':
                    for rank in range(4):
                        offset = 1 if row['name'] == 'ccl-control' else 2
                        stages = ['starting', 'init_process_group', 'init_complete', 'all_reduce_4k',
                                  'all_reduce_4k_complete', 'all_reduce_64m', 'all_reduce_64m_complete',
                                  'destroy_process_group', 'destroy_complete', 'exit']
                        records = [dict(event='stage', stage=stage, monotonic_s=i * offset,
                                        unix_s=1000 + i * offset, rank=rank) for i, stage in enumerate(stages)]
                        (directory / f'rank-{rank}.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in records))
            driver.validate_summary(summary)
            write_json(root / 'summary.json', summary)
            result = analysis.analyze(root)
            self.assertEqual(result['verdict']['graph_replay_kernel_visibility'], 'yes')
            self.assertEqual(result['verdict']['paused_tracer_ccl_init_stall'], 'no')
            self.assertEqual(result['ccl']['per_rank_comparison'][0]['stages']['init_process_group']['delta_s'], 1)
            path = root / 'ccl-paused/rank-0.jsonl'
            with path.open('a') as handle:
                handle.write(json.dumps(dict(event='stall', stage='all_reduce_4k', seconds=120.5, rank=0)) + '\n')
            result = analysis.analyze(root)
            self.assertEqual(result['verdict']['paused_tracer_ccl_init_stall'], 'yes')
            self.assertEqual(result['verdict']['paused_ccl_max_init_stage_s'], 120.5)


class DriverTests(unittest.TestCase):
    def test_argument_order_and_exact_environment(self):
        root = Path('/mnt/raid-models/bench-results/a367-tracefeas-cpu-test')
        rows = driver.plan(root)
        self.assertEqual([r['name'] for r in rows], ['graph-control', 'graph-traced', 'graph-paused', 'ccl-control', 'ccl-paused'])
        for row in rows:
            command = row['command']
            self.assertEqual('--start-paused' in command, row['paused'])
            self.assertEqual('--handshake' in command, row['paused'])
            self.assertIn(driver.PYTHON, command)
            if row['traced']:
                self.assertEqual(command[1:7], driver.FLAGS)
        env = driver.selected_environment(root)
        self.assertEqual(env['CCL_ATL_TRANSPORT'], 'ofi')
        self.assertEqual(env['FI_PROVIDER'], 'tcp')
        self.assertEqual(env['FI_TCP_IFACE'], 'lo')
        self.assertEqual(env['ZE_AFFINITY_MASK'], '0,1,2,3')
        self.assertEqual(env['CCL_SYCL_ALLREDUCE_LL'], 'twoshots')
        self.assertEqual(env['CCL_SYCL_ALLREDUCE_LL_THRESHOLD'], '4096')
        self.assertEqual(env['LD_PRELOAD'], '/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public/lib/libccl.so.1.0')
        self.assertNotIn('PYTHONPATH', env)

    def test_summary_rejects_false_success(self):
        summary = driver.new_summary(Path('/tmp/not-created'), driver.plan(Path('/tmp/not-created')), {})
        driver.validate_summary(summary)
        summary['steps'][0]['status'] = 'passed'
        with self.assertRaises(AssertionError):
            driver.validate_summary(summary)

    def test_cpu_child_overrun_waits_and_records_rc(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            summary = driver.new_summary(root, driver.plan(root), {})
            row = summary['steps'][0]
            row.update(command=[sys.executable, '-B', '-c', 'import time; time.sleep(.7)'], budget_s=.01)
            self.assertFalse(driver.run_step(row, summary, root, {}))
            self.assertEqual(row['rc'], 0)
            self.assertGreaterEqual(row['duration_s'], .7)
            self.assertTrue(row['overrun'])
            driver.validate_summary(json.loads((root / 'summary.json').read_text()))

    def test_launch_failure_recorded(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            summary = driver.new_summary(root, driver.plan(root), {})
            row = summary['steps'][0]
            row['command'] = ['/no/such/executable']
            self.assertFalse(driver.run_step(row, summary, root, {}))
            self.assertEqual(row['rc'], 127)

    def test_paused_handshake_and_ack_with_cpu_fakes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fake_control = root / 'fake_control.py'
            fake_control.write_text('#!/usr/bin/python3\nimport sys\n'
                                    'print("[INFO] extra harmless output")\n'
                                    'print("Session " + sys.argv[2] + " is " + {"--resume":"resumed", "--pause":"paused"}[sys.argv[1]])\n')
            fake_control.chmod(0o755)
            fake_child = root / 'fake_child.py'
            fake_child.write_text('from pathlib import Path\nimport sys,time\n'
                                  'root=Path(sys.argv[1])\n(root/"ready-0").touch()\n'
                                  'while not (root/"go").exists(): time.sleep(.01)\n'
                                  '(root/"done-0").touch()\n'
                                  'while not (root/"release").exists(): time.sleep(.01)\n')
            summary = driver.new_summary(root, driver.plan(root), {})
            row = summary['steps'][2]
            row['command'] = [sys.executable, '-B', str(fake_child), row['directory']]
            env = dict(HOME=temporary, USER='test', LOGNAME='test', LANG='C.UTF-8', PATH='/usr/bin:/bin')
            with patch.object(driver, 'UNITRACE', str(fake_control)):
                self.assertTrue(driver.run_step(row, summary, root, env))
            self.assertEqual([r['action'] for r in row['controls']], ['resume', 'pause'])
            self.assertTrue(all(r['rc'] == 0 and r['acknowledged'] for r in row['controls']))

    def test_failed_resume_releases_waiter_cooperatively(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fake_child = root / 'fake_child.py'
            fake_child.write_text('from pathlib import Path\nimport sys,time\n'
                                  'root=Path(sys.argv[1])\n(root/"ready-0").touch()\n'
                                  'while not (root/"abort").exists(): time.sleep(.01)\n'
                                  'sys.exit(2)\n')
            summary = driver.new_summary(root, driver.plan(root), {})
            row = summary['steps'][2]
            row['command'] = [sys.executable, '-B', str(fake_child), row['directory']]
            env = dict(HOME=temporary, USER='test', LOGNAME='test', LANG='C.UTF-8', PATH='/usr/bin:/bin')
            with patch.object(driver, 'UNITRACE', '/no/such/control'):
                self.assertFalse(driver.run_step(row, summary, root, env))
            self.assertEqual(row['rc'], 2)
            self.assertEqual([r['action'] for r in row['controls']], ['resume', 'pause'])
            self.assertTrue(all(r['rc'] == 127 for r in row['controls']))
            self.assertFalse((Path(row['directory']) / 'go').exists())


if __name__ == '__main__':
    unittest.main()
