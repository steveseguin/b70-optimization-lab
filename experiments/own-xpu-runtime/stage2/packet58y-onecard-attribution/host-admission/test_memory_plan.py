#!/usr/bin/env python3
"""CPU regression/replay tests; no native launch, model read or device access."""
import ast
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import sys
import tempfile
import time
import types
import unittest

import derive
import memory_plan as M

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
DATA = json.loads((HERE/'measured-peaks.json').read_text())
BASE = json.loads((HERE/'base-plan.json').read_text())


def source_function(path, name, namespace):
    """Execute the exact original function without importing launch modules."""
    module = ast.parse(path.read_text())
    function = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == name)
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace[name]


class MemoryTests(unittest.TestCase):
    def test_receipts_reproduce_exactly(self):
        base, report = derive.derive()
        self.assertEqual(base, BASE)
        self.assertEqual(report, DATA)
        self.assertEqual(len(report['windows']), 29)

    def test_old_refusal_and_all_new_views_admit_saved_1458_reading(self):
        old = source_function(HERE.parent/'lineage-inputs/original/experiments/own-xpu-runtime/stage2/packet58r-onecard-v5/memory_plan.py', 'admit', {'require': M.require})
        snapshot = DATA['historical_refusal']['snapshot']
        with self.assertRaisesRegex(ValueError, 'shortage 2827844624'):
            old(snapshot, BASE)
        for view in M.VIEWS:
            result = M.admit(snapshot, M.plan(view))
            self.assertGreater(result['margin_bytes'], 20_000_000_000)

    def test_admission_exact_boundary(self):
        for view in M.VIEWS:
            budget = M.plan(view)
            needed = budget['host_required_available_bytes']
            self.assertEqual(M.admit({'MemAvailable': needed}, budget)['margin_bytes'], 0)
            with self.assertRaisesRegex(ValueError, 'host admission refused'):
                M.admit({'MemAvailable': needed-1}, budget)

    def test_every_measured_peak_has_at_least_four_gib_margin(self):
        for row in DATA['windows']:
            if not row['full_model']:
                continue
            view = 'production' if row['view'] == 'production' else 'tile16'
            budget = M.plan(view)
            self.assertGreaterEqual(budget['host_bound_bytes']-row['normalized_full_file_peak_bytes'], 4*M.GIB)
            self.assertLess(row['peak_shadow_bytes'], 4*M.GIB)
            self.assertIsNotNone(row['native_after_load_shadow_bytes'])

    def test_replay_every_sample_and_resident_design_increment(self):
        for row in DATA['windows']:
            view = 'production' if row['view'] == 'production' else 'tile16'
            path = REPO/row['source']
            receipt = json.loads(derive.archive_text(path.parent/'window.json'))
            baseline = receipt['memory_admission']['baseline_gpuactive_bytes']
            budget = M.window_plan(row['window'], view=view)
            for line in derive.archive_text(path).splitlines():
                sample = json.loads(line)
                result = M.account_memory(copy.deepcopy(sample), sample['host'], baseline,
                                          sample['pinned_expert_bytes'], budget, row['full_model'])
                if row['full_model']:
                    resident = M.window_plan(row['window'], view='tile16-resident')
                    simulated = copy.deepcopy(sample)
                    simulated['anonymous_bytes'] += resident['derivation']['resident_lookup_bytes']
                    simulated = M.account_memory(simulated, sample['host'], baseline,
                                                 sample['pinned_expert_bytes'], resident)
                    self.assertEqual(simulated['host_accounted_bytes'], result['host_accounted_bytes'])

    def test_resident_allowance_is_explicit_not_a_measurement(self):
        resident = M.plan('tile16-resident')
        normal = M.plan('tile16')
        delta = 29_321_610_240
        self.assertEqual(resident['host_categories']['resident_lookup_bytes'], delta)
        self.assertEqual(normal['host_categories']['file_backed_nonexpert_and_lookup_bound'] -
                         resident['host_categories']['file_backed_nonexpert_and_lookup_bound'], delta)
        self.assertEqual(resident['host_required_available_bytes'], normal['host_required_available_bytes'])
        self.assertFalse(resident['derivation']['resident_device_measured'])
        self.assertEqual(resident['derivation']['full_model_windows'], 0)

    def test_device_cache_kv_and_reserve_unchanged(self):
        for view in M.VIEWS:
            budget = M.plan(view)
            for key in ('census', 'allocation_inventory', 'device_categories', 'device_owned_bound_bytes',
                        'device_reserve_bytes', 'arena_limit_bytes', 'device_margin_bytes',
                        'context', 'gpu_count', 'decode_mode', 'kv_dtype', 'host_reserve_bytes'):
                self.assertEqual(budget[key], BASE[key])
            self.assertTrue(budget['whole_host_required'])

    def test_k1_requirement_unchanged(self):
        for view in M.VIEWS:
            for name in ('K1', 'K1a', 'K1b'):
                budget = M.window_plan(name, view=view)
                self.assertEqual(budget['host_required_available_bytes'], 12*M.GIB)
                self.assertEqual(budget['host_reserve_bytes'], 8*M.GIB)

    def test_live_floor_including_resident(self):
        for view in M.VIEWS:
            budget = M.plan(view)
            M.account_memory({'anonymous_bytes': 0}, {'MemAvailable': M.HOST_RESERVE, 'GPUActive': 0}, 0, 0, budget)
            with self.assertRaisesRegex(ValueError, '8 GiB stop floor'):
                M.account_memory({'anonymous_bytes': 0}, {'MemAvailable': M.HOST_RESERVE-1, 'GPUActive': 0}, 0, 0, budget)

    def test_live_shadow_boundary(self):
        budget = M.plan('tile16')
        snapshot = {'MemAvailable': M.HOST_RESERVE, 'GPUActive': 4*M.GIB}
        M.account_memory({'anonymous_bytes': 0}, snapshot, 0, 0, budget)
        snapshot['GPUActive'] += 1
        with self.assertRaisesRegex(ValueError, 'shadow exceeds'):
            M.account_memory({'anonymous_bytes': 0}, snapshot, 0, 0, budget)

    def test_live_combined_boundary(self):
        for view in M.VIEWS:
            budget = M.plan(view)
            anonymous = budget['host_bound_bytes']-budget['census']['pinned_expert_bytes']-budget['host_categories']['file_backed_nonexpert_and_lookup_bound']
            snapshot = {'MemAvailable': M.HOST_RESERVE, 'GPUActive': budget['census']['pinned_expert_bytes']}
            M.account_memory({'anonymous_bytes': anonymous}, snapshot, 0, snapshot['GPUActive'], budget)
            with self.assertRaisesRegex(ValueError, 'combined host memory exceeds'):
                M.account_memory({'anonymous_bytes': anonymous+1}, snapshot, 0, snapshot['GPUActive'], budget)

    def test_resident_anonymous_bytes_are_charged_once(self):
        budget = M.plan('tile16-resident')
        row = max((r for r in DATA['windows'] if r['view'] == 'tile16' and r['full_model']),
                  key=lambda r: r['normalized_full_file_peak_bytes'])
        sample = copy.deepcopy(row['peak_witness']['sample'])
        snapshot = sample['host']
        baseline = snapshot['GPUActive']-sample['gpuactive_growth_bytes']
        sample['anonymous_bytes'] += 29_321_610_240
        got = M.account_memory(sample, snapshot, baseline, sample['pinned_expert_bytes'], budget)
        self.assertEqual(got['host_accounted_bytes'], row['normalized_full_file_peak_bytes'])

    def test_bad_sensors_and_pin_credit_fail_closed(self):
        budget = M.plan('production')
        for snapshot in ({'MemAvailable': M.HOST_RESERVE},
                         {'MemAvailable': -1, 'GPUActive': 0},
                         {'MemAvailable': M.HOST_RESERVE, 'GPUActive': -1},
                         {'MemAvailable': float('nan'), 'GPUActive': 0}):
            with self.assertRaises(ValueError):
                M.account_memory({'anonymous_bytes': 0}, snapshot, 0, 0, budget)
        with self.assertRaisesRegex(ValueError, 'pinned expert total'):
            M.account_memory({'anonymous_bytes': 0}, {'MemAvailable': M.HOST_RESERVE, 'GPUActive': 0},
                             0, budget['census']['pinned_expert_bytes']+1, budget)

    def test_modified_budget_cannot_lower_guards(self):
        for key, value in [('host_required_available_bytes', 0), ('host_reserve_bytes', 0),
                           ('gpu_count', 2), ('kv_dtype', 'FP8'), ('context', 8192)]:
            budget = M.plan('production')
            budget[key] = value
            with self.assertRaisesRegex(ValueError, 'differs from sealed'):
                M.admit({'MemAvailable': 200*M.GIB}, budget)

    def test_unknown_view_window_and_observation_refused(self):
        for view, window in [('guess', 'KD'), ('tile16', 'unknown')]:
            with self.assertRaises(ValueError):
                M.window_plan(window, view=view)
        with self.assertRaises(ValueError):
            M.window_plan('KD', {'peak_shadow_bytes': 0}, view='tile16')
        with self.assertRaises(TypeError):
            M.plan()

    def test_sensor_failure_is_saved_and_supervisor_requests_graceful_stop(self):
        for failure in ('reserve', 'shadow', 'combined'):
            with self.subTest(failure=failure):
                log, kernel, events, reasons = io.StringIO(), io.StringIO(), [], []
                budget = M.plan('tile16-resident')
                snapshot = {'MemAvailable': M.HOST_RESERVE, 'GPUActive': 0}
                anonymous = 0
                if failure == 'reserve':
                    snapshot['MemAvailable'] -= 1
                elif failure == 'shadow':
                    snapshot['GPUActive'] = 4*M.GIB+1
                else:
                    anonymous = budget['host_bound_bytes']+1
                class Child:
                    pid, returncode = 123, None
                    def poll(self):
                        return self.returncode
                    def send_signal(self, sig):
                        events.append(('signal', sig))
                        self.returncode = 0
                child = Child()
                sensor = lambda pid: M.live_memory_sensor(pid, budget=budget,
                    process_sampler=lambda _: {'anonymous_bytes': anonymous, 'root_seen': True},
                    snapshot_reader=lambda: snapshot, sample_log=log)
                namespace = dict(time=time, signal=signal, journal=lambda *a: ('', 'cursor'),
                                 process_tree_anon=None, DRAIN_SECONDS=60,
                                 ANONYMOUS_LIMIT_BYTES=200*M.GIB, ANONYMOUS_STOP_BYTES=200*M.GIB,
                                 FAULT=re.compile('Fault response'))
                supervise = source_function(HERE.parent/'runtime_supervision.py', 'supervise', namespace)
                result = supervise(child, 60, 'cursor', kernel, reasons,
                                   lambda why: events.append(('latch', why)),
                                   lambda: events.append(('persist', bool(log.getvalue()))),
                                   memory_sensor=sensor, postflight_seconds=0)
                self.assertTrue(result['sigterm_sent'])
                self.assertFalse(result['child_still_running'])
                self.assertIn('sensor_error', json.loads(log.getvalue()))
                self.assertEqual([e for e in events if e[0] == 'signal'], [('signal', signal.SIGTERM)])
                self.assertLess(next(i for i,e in enumerate(events) if e[0]=='persist'),
                                next(i for i,e in enumerate(events) if e[0]=='signal'))

    def test_existing_window_stop_still_triggers_with_new_plan(self):
        # Unchanged frozen accounting also retains the live floor when fed the
        # new plan. This executes its real function, without a window launch.
        account = source_function(HERE.parent/'lineage-inputs/original/experiments/own-xpu-runtime/stage2/packet58r-onecard-v5/window.py', 'account_memory',
                                  {'require': M.require, 'M': M})
        with self.assertRaisesRegex(ValueError, '8 GiB stop floor'):
            account({'anonymous_bytes': 0}, {'MemAvailable': M.HOST_RESERVE-1, 'GPUActive': 0},
                    0, 0, M.plan('tile16'))

    def test_seal_and_copy_forward_without_parent_imports(self):
        with tempfile.TemporaryDirectory(prefix='packet58u-') as temp:
            root = Path(temp)
            seal = M.verify_seal()
            for name in [*seal['files'], 'seal.json']:
                shutil.copyfile(HERE/name, root/name)
            spec = importlib.util.spec_from_file_location('copied58u', root/'memory_plan.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.assertEqual(module.plan('tile16'), M.plan('tile16'))
            (root/'measured-peaks.json').write_text('{}\n')
            with self.assertRaisesRegex(ValueError, 'seal mismatch'):
                module.plan('tile16')

    def test_requested_cpu_placement_and_memory_limit(self):
        self.assertEqual(os.getpriority(os.PRIO_PROCESS, 0), 19)
        self.assertLessEqual(os.sched_getaffinity(0), set(range(8,16)) | set(range(24,32)))
        self.assertTrue(sys.dont_write_bytecode)
        self.assertLess(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024, 2_000_000_000)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(MemoryTests))
    report = dict(passed=result.wasSuccessful(), tests=result.testsRun,
                  failures=len(result.failures), errors=len(result.errors),
                  device_executed=False, model_payload_reads=False,
                  seal_sha256=M.sha(HERE/'seal.json'),
                  peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                  affinity=sorted(os.sched_getaffinity(0)), nice=os.getpriority(os.PRIO_PROCESS, 0),
                  replayed_windows=len(DATA['windows']),
                  replayed_samples=sum(r['samples'] for r in DATA['windows']))
    (HERE/'evidence').mkdir(exist_ok=True)
    (HERE/'evidence/cpu-tests.json').write_text(json.dumps(report, indent=2)+'\n')
    sys.exit(0 if result.wasSuccessful() else 1)
