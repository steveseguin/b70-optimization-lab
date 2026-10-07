import asyncio
import importlib.util
from pathlib import Path
import types
import unittest

spec = importlib.util.spec_from_file_location('guard_under_test', Path(__file__).with_name('executor_guard.py'))
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)


class GuardControls(unittest.TestCase):
    def fixture(self, stage=None):
        seen = []
        class Authority:
            failed = None
            def begin(self, name, graph, pid):
                seen.append('begin')
                if self.failed or stage == 'begin':
                    raise RuntimeError('admission refused')
                return {'name': name}
            def finish(self, messages):
                seen.append('finish')
                if stage == 'finish':
                    raise RuntimeError('finish refused')
                assert [m[0] for m in messages] == ['execution_start', 'execution_success']
            def halt(self, error):
                seen.append('halt')
                self.failed = str(error)
                if stage == 'halt-write':
                    raise OSError('disk full while preserving halt receipt')
        class Executor:
            def __init__(self):
                self.server = types.SimpleNamespace(client_id=None)
            def add_message(self, event, data, broadcast):
                seen.append(event)
                self.status_messages.append((event, data))
            async def execute_async(self, prompt, pid, extra_data, execute_outputs):
                seen.append('model execution')
                self.add_message('execution_start', {'prompt_id': pid}, False)
                if stage == 'execute':
                    raise RuntimeError('numerical failure')
                if stage == 'returned-error':
                    self.add_message('execution_error', {'prompt_id': pid}, False)
                    return
                self.history_result = {'outputs': {'414': 'preserved'}, 'meta': {}}
                self.add_message('execution_success', {'prompt_id': pid}, False)
        def before(row, pid):
            seen.append('before')
        def after(row, pid):
            seen.append('after')
            if stage in ('after', 'halt-write'):
                raise RuntimeError('post-request memory floor')
        a = Authority()
        G.install(Executor, a, before, after)
        return Executor(), a, seen

    def run_one(self, executor):
        asyncio.run(executor.execute_async({'414': {'inputs': {'run_name': 'clip-1'}}}, 'p1'))

    def test_postchecks_precede_success_event(self):
        e, a, seen = self.fixture()
        self.run_one(e)
        self.assertEqual(seen, ['begin', 'before', 'model execution', 'execution_start',
                                'after', 'finish', 'execution_success'])
        self.assertTrue(e.success)
        self.assertNotIn('add_message', e.__dict__)

    def test_failures_never_broadcast_success_or_restart(self):
        for stage in ('begin', 'execute', 'returned-error', 'after', 'finish'):
            with self.subTest(stage=stage):
                e, a, seen = self.fixture(stage)
                self.run_one(e)
                self.assertFalse(e.success)
                self.assertNotIn('execution_success', seen)
                self.assertEqual(seen[-1], 'execution_error')
                self.assertIsNotNone(a.failed)
                previous = seen.count('model execution')
                self.run_one(e)
                self.assertEqual(seen.count('model execution'), previous)

    def test_failed_postcheck_preserves_outputs(self):
        e, _, _ = self.fixture('after')
        self.run_one(e)
        self.assertEqual(e.history_result['outputs'], {'414': 'preserved'})

    def test_halt_receipt_write_failure_does_not_kill_prompt_worker(self):
        e, a, seen = self.fixture('halt-write')
        self.run_one(e)
        self.assertFalse(e.success)
        self.assertIsNotNone(a.failed)
        self.assertNotIn('execution_success', seen)
        error = e.status_messages[-1][1]
        self.assertIn('disk full', error['halt_receipt_error'])
        self.assertEqual(error['exception_message'], 'post-request memory floor')

    def test_distinct_node_names_refused(self):
        with self.assertRaisesRegex(RuntimeError, 'one resolution request'):
            G.request_name({'1': {'inputs': {'run_name': 'a'}}, '2': {'inputs': {'run_name': 'b'}}})

    def test_double_install_refused(self):
        e, a, _ = self.fixture()
        with self.assertRaisesRegex(RuntimeError, 'twice'):
            G.install(type(e), a, None, None)

    def test_failure_restores_adapter_scope_without_clearing_latch(self):
        calls = []
        class Authority:
            def begin(self, *args): return {'name': 'clip-1'}
            def halt(self, error): calls.append('latched')
        class Executor:
            def __init__(self): self.server = types.SimpleNamespace(client_id=None)
            def add_message(self, *args): self.status_messages.append(args[:2])
            async def execute_async(self, *args): raise RuntimeError('native failed')
        def cleanup(*args):
            calls.append('restore scoped loader')
            raise RuntimeError('native adapter latched after restore')
        G.install(Executor, Authority(), lambda *a: None, lambda *a: None, cleanup)
        e = Executor()
        self.run_one(e)
        self.assertEqual(calls, ['restore scoped loader', 'latched'])
        self.assertFalse(e.success)
        self.assertIn('latched after restore', e.status_messages[-1][1]['failure_cleanup_error'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
