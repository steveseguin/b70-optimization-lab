"""Execute the transformed prompt-worker loop with deterministic CPU-only fakes."""
import ast
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock
import maintenance128

PARENT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-127/source/main.py')

class Finished(BaseException):
    pass

class MainLoop(unittest.TestCase):
    def exercise(self, rows, mode='idle', original=False, gc_failure=False):
        # Compile only the actual prompt_worker function. Never execute main's imports,
        # launch code, device discovery, endpoints or server initialization.
        raw = PARENT.read_bytes()
        if not original:
            raw = maintenance128.transform_main(raw)
        node = next(n for n in ast.parse(raw).body if isinstance(n, ast.FunctionDef) and n.name == 'prompt_worker')
        trace, clock, active = [], [100.0], [None]
        rows = iter(rows)
        def record(name, *args):
            trace.append((name, round(clock[0], 6), *args))
        class Queue:
            def get(self, timeout):
                record('get', round(timeout, 6))
                try:
                    row = next(rows)
                except StopIteration:
                    raise Finished()
                active[0] = row
                if row.get('idle'):
                    clock[0] += timeout + .000001  # queue wakeup after the timeout boundary
                    return None
                clock[0] += row.get('gap', .02)
                item = (0, row['id'], {'unchanged': row['id']}, {}, [], {})
                return item, row['id']
            def get_flags(self):
                return active[0].get('flags', {})
            def get_tasks_remaining(self):
                return 0
            def task_done(self, item_id, result, **kwargs):
                record('done', item_id, result)
        class Executor:
            success = True
            status_messages = []
            history_result = {'original': 'bytes'}
            def execute(self, graph, prompt_id, extra, outputs):
                record('execute', prompt_id, graph)
                clock[0] += active[0].get('duration', 1.0)
            def reset(self):
                record('reset')
        def collect():
            record('gc')
            if gc_failure:
                raise RuntimeError('synthetic native collection failure')
        def pair(gc, cache, interval, prompt_id):
            record('pair', interval, prompt_id)
            gc()
            cache()
        manager = SimpleNamespace(total_ram=0, unload_all_models=lambda: record('unload'),
                                  soft_empty_cache=lambda: record('cache'))
        assets = SimpleNamespace(pause_background_scan=lambda: record('pause'),
                                 resume_background_scan=lambda: record('resume'),
                                 queue_output_scan=lambda: record('scan'))
        server = SimpleNamespace(client_id=None, last_prompt_id=None)
        execution = SimpleNamespace(CacheType=SimpleNamespace(RAM_PRESSURE=0, CLASSIC=1, LRU=2, NONE=3),
            PromptExecutor=lambda *a, **k: Executor(),
            PromptQueue=SimpleNamespace(ExecutionStatus=lambda **k: k))
        scope = dict(args=SimpleNamespace(cache_classic=True, cache_none=False, cache_lru=0, cache_ram=[]),
            comfy=SimpleNamespace(model_management=manager), execution=execution,
            time=SimpleNamespace(perf_counter=lambda: clock[0]),
            logging=SimpleNamespace(info=lambda *a, **k: None, exception=lambda *a, **k: None),
            gc=SimpleNamespace(collect=collect),
            hook_breaker_ac10a0=SimpleNamespace(restore_functions=lambda: record('restore')))
        exec(compile(ast.Module(body=[node], type_ignores=[]), '<actual-prompt-worker>', 'exec'), scope)
        fake125 = SimpleNamespace(launch_interval=lambda: 10, run_maintenance=pair)
        with mock.patch.dict(os.environ, {'LTX_MAINTENANCE_MODE': mode}), mock.patch.dict('sys.modules', {'maintenance125': fake125}):
            try:
                scope['prompt_worker'](Queue(), server, assets)
            except Finished:
                pass
            except RuntimeError:
                if not gc_failure:
                    raise
        return trace

    def test_parent_mode_matches_original_loop(self):
        rows = [dict(id='first'), dict(id='second', duration=11), dict(id='third'), dict(idle=True)]
        self.assertEqual(self.exercise(rows, mode='parent'), self.exercise(rows, original=True))

    def test_idle_debt_survives_successor_until_idle_gap(self):
        trace = self.exercise([dict(id='first'), dict(id='second', duration=11), dict(id='third'), dict(idle=True)])
        pairs = [r for r in trace if r[0] == 'pair']
        self.assertEqual([r[-1] for r in pairs], ['first', 'third'])
        self.assertGreaterEqual(pairs[-1][1] - next(r[1] for r in trace if r[0] == 'done' and r[2] == 'third'), .249999)
        self.assertEqual([r[2] for r in trace if r[0] == 'get'][-3:-1], [.25, .25])

    def test_continuous_prompts_force_age_bound(self):
        rows = [dict(id='first', duration=1)] + [dict(id=str(n), duration=9) for n in range(7)]
        trace = self.exercise(rows)
        pairs = [r for r in trace if r[0] == 'pair']
        self.assertEqual([r[-1] for r in pairs], ['first', '6'])
        self.assertGreaterEqual(pairs[1][1] - pairs[0][1], 60)
        self.assertLess(pairs[1][1] - pairs[0][1], 69.1)
        due_waits = [r[2] for r in trace if r[0] == 'get' and r[1] > 120 and r[1] < pairs[1][1]]
        self.assertTrue(due_waits)
        self.assertTrue(all(wait == .25 for wait in due_waits))

    def test_explicit_free_keeps_reset_unload_and_collection(self):
        trace = self.exercise([dict(id='first'), dict(id='free', flags={'free_memory': True})])
        names = [r[0] for r in trace]
        i = names.index('unload')
        self.assertEqual(names[i:i+5], ['unload', 'reset', 'pair', 'gc', 'cache'])
        self.assertEqual([r[-1] for r in trace if r[0] == 'pair'], ['first', 'free'])

    def test_unload_without_free_preserves_native_calls(self):
        trace = self.exercise([dict(id='first'), dict(id='unload', flags={'unload_models': True})])
        names = [r[0] for r in trace]
        i = names.index('unload')
        self.assertEqual(names[i:i+4], ['unload', 'pair', 'gc', 'cache'])
        self.assertNotIn('reset', names)

    def test_native_failure_stops_before_cache_and_restores_background_scan(self):
        trace = self.exercise([dict(id='first')], gc_failure=True)
        names = [r[0] for r in trace]
        self.assertEqual(names[-3:], ['pair', 'gc', 'resume'])
        self.assertNotIn('cache', names)
        self.assertNotIn('restore', names)

    def test_same_execute_inputs_and_completion_results(self):
        rows = [dict(id='first'), dict(id='second', duration=11), dict(id='third'), dict(idle=True)]
        only_model = lambda trace: [(r[0], *r[2:]) for r in trace if r[0] in ('execute', 'done')]
        self.assertEqual(only_model(self.exercise(rows)), only_model(self.exercise(rows, original=True)))
