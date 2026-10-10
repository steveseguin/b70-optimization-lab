"""CPU-only tests for the exact periodic-maintenance source transformation."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import maintenance125 as m


# The parent's branch structure, with only external operations replaced by fakes.
MAIN = b'''def prompt_worker(server_instance, durations):
    last_gc_collect = 0
    need_gc = False
    gc_collect_interval = 10.0
    events = []
    for duration in durations:
        clock.advance(duration)
        server_instance.last_prompt_id = str(len(events))
        need_gc = True
        if need_gc:
            current_time = time.perf_counter()
            if (current_time - last_gc_collect) > gc_collect_interval:
                    gc.collect()
                    comfy.model_management.soft_empty_cache()
                    last_gc_collect = current_time
                    need_gc = False
                    hook_breaker_ac10a0.restore_functions()
                    asset_manager.queue_output_scan()
                    asset_manager.resume_background_scan()
        events.append(list(calls))
        calls.clear()
    return events
'''


class Maintenance125Tests(unittest.TestCase):
    def setUp(self):
        with m._lock:
            m._events.clear()
            m._count = 0

    def test_default_is_parent(self):
        self.assertEqual(m.launch_interval({}), 10)

    def test_two_checked_choices(self):
        self.assertEqual([m.launch_interval({m.ENV: str(v)}) for v in (10, 60)], [10, 60])

    def test_invalid_values_fail_closed(self):
        for value in ('0', '10.0', ' 10', '60 ', '600', '', 'off', 10, None, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                m.launch_interval({m.ENV: value})

    def test_transform_exactly_once(self):
        transformed = m.transform_main(MAIN)
        ast.parse(transformed)
        self.assertEqual(transformed.count(b'maintenance125.run_maintenance('), 1)
        with self.assertRaises(ValueError):
            m.transform_main(transformed)

    def test_anchor_drift_and_duplicate_refused(self):
        for source in (MAIN.replace(b'10.0', b'11.0'), MAIN + MAIN,
                       MAIN.replace(b'                    gc.collect()', b'                    gc.collect(2)')):
            with self.subTest(source=source[:30]), self.assertRaises(ValueError):
                m.transform_main(source)

    def test_source_type_refused(self):
        with self.assertRaises(TypeError):
            m.transform_main(MAIN.decode())

    def simulate(self, interval, transformed=True):
        clock = SimpleNamespace(value=0.)
        clock.advance = lambda duration: setattr(clock, 'value', clock.value + duration)
        calls = []
        record = lambda name: lambda: calls.append(name)
        scope = {'clock': clock, 'calls': calls,
                 'gc': SimpleNamespace(collect=record('gc')),
                 'time': SimpleNamespace(perf_counter=lambda: clock.value),
                 'comfy': SimpleNamespace(model_management=SimpleNamespace(soft_empty_cache=record('cache'))),
                 'hook_breaker_ac10a0': SimpleNamespace(restore_functions=record('restore')),
                 'asset_manager': SimpleNamespace(queue_output_scan=record('scan'),
                                                  resume_background_scan=record('resume'))}
        exec(m.transform_main(MAIN) if transformed else MAIN, scope)
        with patch.dict(m.os.environ, {m.ENV: str(interval)}):
            return scope['prompt_worker'](SimpleNamespace(), [5.5] * 24)

    def test_parent_off_identical_call_cadence_order(self):
        self.assertEqual(self.simulate(10), self.simulate(10, transformed=False))

    def test_parent_two_cycle_and_candidate_bounded_eleven_cycle(self):
        old, new = self.simulate(10), self.simulate(60)
        self.assertEqual([i for i, row in enumerate(old) if row], list(range(1, 24, 2)))
        self.assertEqual([i for i, row in enumerate(new) if row], [10, 21])
        self.assertTrue(all(row == ['gc', 'cache', 'restore', 'scan', 'resume']
                            for row in old + new if row))

    def test_timestamps_record_real_call_order(self):
        calls = []
        with patch.object(m.time, 'time_ns', side_effect=[100, 200, 300, 400]):
            self.assertIsNone(m.run_maintenance(lambda: calls.append('gc'), lambda: calls.append('cache'), 60, 'p'))
        self.assertEqual(calls, ['gc', 'cache'])
        event = m.snapshot()['events'][0]
        self.assertEqual(event['timing_ns'], {'gc_start': 100, 'gc_done': 200, 'cache_done': 300})
        self.assertEqual((event['end_ns'], event['prompt_id'], event['interval_s']), (400, 'p', 60))

    def test_gc_failure_prevents_cache_and_propagates_identity(self):
        error = RuntimeError('gc failure')
        def fail():
            raise error
        calls = []
        with self.assertRaises(RuntimeError) as caught:
            m.run_maintenance(fail, lambda: calls.append('cache'), 10)
        self.assertIs(caught.exception, error)
        self.assertEqual(calls, [])
        event = m.snapshot()['events'][0]
        self.assertEqual(event['failed_stage'], 'gc')
        self.assertIsNone(event['timing_ns']['gc_done'])

    def test_cache_failure_propagates_and_preserves_gc_evidence(self):
        def fail():
            raise KeyboardInterrupt('cache interrupted')
        with self.assertRaises(KeyboardInterrupt):
            m.run_maintenance(lambda: None, fail, 60)
        event = m.snapshot()['events'][0]
        self.assertEqual(event['failed_stage'], 'cache')
        self.assertIsNotNone(event['timing_ns']['gc_done'])
        self.assertIsNone(event['timing_ns']['cache_done'])

    def test_evidence_bound_and_copy(self):
        for i in range(40):
            m.run_maintenance(lambda: None, lambda: None, 60, str(i))
        result = m.snapshot()
        self.assertEqual((result['count'], result['retained']), (40, 32))
        self.assertEqual(result['events'][0]['sequence'], 9)
        result['events'][0]['timing_ns']['gc_start'] = -1
        self.assertGreater(m.snapshot()['events'][0]['timing_ns']['gc_start'], 0)

    def test_callbacks_run_outside_evidence_lock(self):
        counts = []
        m.run_maintenance(lambda: counts.append(m.snapshot()['count']),
                          lambda: counts.append(m.snapshot()['count']), 10)
        self.assertEqual(counts, [0, 0])

    def test_bad_runtime_arguments_have_no_side_effect(self):
        for interval in (True, 10., 0, 11, '10'):
            with self.subTest(interval=interval), self.assertRaises(ValueError):
                m.run_maintenance(lambda: None, lambda: None, interval)
        with self.assertRaises(TypeError):
            m.run_maintenance(None, lambda: None, 10)
        self.assertEqual(m.snapshot()['count'], 0)

    def test_real_parent_source_transforms_without_importing_runtime(self):
        root = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-124')
        raw = (root / 'source/main.py').read_bytes()
        transformed = m.transform_main(raw)
        self.assertIn(b'gc_collect_interval = maintenance125.launch_interval()', transformed)
        self.assertEqual(transformed.count(b'last_gc_collect = 0'), raw.count(b'last_gc_collect = 0'))
        self.assertIn(b'if free_memory:\n                e.reset()', transformed)


if __name__ == '__main__':
    unittest.main()
