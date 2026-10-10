"""CPU boundary and real receipt-route scheduling tests; no sockets or devices."""
import asyncio
import ctypes
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest import mock

import integration
import maintenance128 as m
import session


class Scheduling(unittest.TestCase):
    def test_default_is_parent(self):
        self.assertEqual(m.launch_mode({}), 'parent')

    def test_strict_options(self):
        for v in ('', '0', '1', 'IDLE', None, 0, True):
            with self.assertRaises(ValueError):
                m.launch_mode({m.ENV: v})

    def test_parent_decisions_exact(self):
        for interval in (10, 60):
            for age in (0, 9.99, 10, 10.01, 59.9, 60, 60.01, 100):
                self.assertEqual(m.should_run('parent', 100+age, 100, 100+age, interval), age > interval)
                self.assertEqual(m.wait_timeout('parent', 100+age, 100, interval), max(interval-((100+age)-100), 0))

    def test_due_handoff_deferred(self):
        self.assertFalse(m.should_run('idle', 111, 100, 111, 10))
        self.assertFalse(m.should_run('idle', 111.09, 100, 111, 10))

    def test_quiet_gap_runs_full_pair(self):
        self.assertTrue(m.should_run('idle', 111.26, 100, 111, 10))

    def test_debt_stays_due(self):
        for n in range(11, 60):
            self.assertFalse(m.should_run('idle', 100+n, 100, 100+n, 10))
        self.assertTrue(m.should_run('idle', 160, 100, 160, 10))

    def test_inflight_boundary_forces(self):
        self.assertTrue(m.should_run('idle', 167, 100, 167, 10))

    def test_explicit_free_forces(self):
        self.assertTrue(m.should_run('idle', 111, 100, 111, 10, forced=True))

    def test_not_due_unchanged(self):
        self.assertFalse(m.should_run('idle', 110, 100, 1, 10))

    def test_no_due_spin(self):
        self.assertEqual(m.wait_timeout('idle', 111, 100, 10), .25)
        self.assertEqual(m.wait_timeout('idle', 160, 100, 10), 0)
        self.assertAlmostEqual(m.wait_timeout('idle', 159.95, 100, 10), .05)

    def test_gc60_no_extra_deferral(self):
        self.assertTrue(m.should_run('idle', 160.01, 100, 160.01, 60))

    def test_invalid_mode(self):
        for fn, args in ((m.wait_timeout, (1, 0, 10)), (m.should_run, (1, 0, 0, 10))):
            with self.assertRaises(ValueError):
                fn('other', *args)

    def test_transform_preserves_calls_and_explicit_flags(self):
        parent = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-127/source/main.py').read_bytes()
        child = m.transform_main(parent)
        calls = b'maintenance125.run_maintenance(\n                        gc.collect, comfy.model_management.soft_empty_cache,\n                        gc_collect_interval, getattr(server_instance, "last_prompt_id", None))'
        self.assertEqual(child.count(calls), 1)
        self.assertIn(b'forced=bool(free_memory or flags.get("unload_models", free_memory))', child)
        self.assertEqual(child.count(b'last_gc_collect = current_time'), parent.count(b'last_gc_collect = current_time'))
        self.assertNotIn(b'gc.disable', child)
        self.assertNotIn(b'gc.freeze', child)

    def test_transform_rejects_drift(self):
        for raw in (b'', b'    gc_collect_interval = maintenance125.launch_interval()\n' * 2):
            with self.assertRaises(ValueError):
                m.transform_main(raw)
        with self.assertRaises(TypeError):
            m.transform_main('source')

    def test_native_pair_failure_flow_unchanged(self):
        import maintenance125
        calls = []
        def fail():
            calls.append('gc')
            raise RuntimeError('test')
        with self.assertRaises(RuntimeError):
            maintenance125.run_maintenance(fail, lambda: calls.append('cache'), 10)
        self.assertEqual(calls, ['gc'])


class ReceiptTiming(unittest.TestCase):
    def exercise(self, mode):
        from aiohttp import web
        with tempfile.TemporaryDirectory(prefix='receipt128-') as directory:
            run = Path(directory)
            (run/'receipts').mkdir()
            name = 'stream138-s00000012'
            raw = b'{"preserved":"receipt bytes","hash":"unchanged"}\n'
            (run/'receipts'/('receipt-'+name+'.json')).write_bytes(raw)
            ctx = SimpleNamespace(run=run, session=session, receipt_polls={}, receipt_served={},
                                  decoder=SimpleNamespace(failed=None), preview=SimpleNamespace(failed=None))
            server = SimpleNamespace(routes=web.RouteTableDef(), app=web.Application(), send_sync=lambda *a: None)
            fake = SimpleNamespace(PromptServer=SimpleNamespace(instance=server))
            with mock.patch.dict('sys.modules', {'server': fake}), mock.patch.object(integration, '_CTX', ctx), mock.patch.object(integration, '_ROUTES_INSTALLED', False):
                integration.install_routes()
            handler = next(r.handler for r in server.routes if r.path == '/ltx-stream/receipt/{run_name}')
            # Synthetic decode occupancy and a C operation holding the GIL, modelling
            # the measured full-collection pause without allocating a large heap.
            libc = ctypes.PyDLL(None)
            libc.usleep.argtypes = [ctypes.c_uint]
            libc.usleep.restype = ctypes.c_int
            started = threading.Event()
            def decode():
                started.set()
                end = time.monotonic() + .4
                payload = b'x' * 65536
                while time.monotonic() < end:
                    hashlib.sha256(payload).digest()
            def prompt_boundary():
                time.sleep(.005)
                if m.should_run(mode, 111, 100, 111, 10):
                    libc.usleep(300000)
            async def request():
                decode_thread = threading.Thread(target=decode)
                prompt_thread = threading.Thread(target=prompt_boundary)
                decode_thread.start()
                started.wait()
                begin = time.perf_counter()
                prompt_thread.start()
                try:
                    await asyncio.sleep(.02)
                    response = await handler(SimpleNamespace(match_info={'run_name': name}))
                    elapsed = time.perf_counter()-begin
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.body, raw)
                    self.assertIn(name, ctx.receipt_served)
                    return elapsed
                finally:
                    prompt_thread.join()
                    decode_thread.join()
            return asyncio.run(request())

    def test_parent_reproduces_gil_stall(self):
        elapsed = self.exercise('parent')
        print('packet128 parent synthetic receipt seconds:', elapsed, flush=True)
        self.assertGreater(elapsed, .25)

    def test_receipt_under_50ms_during_decode_work(self):
        samples = [self.exercise('idle') for _ in range(3)]
        print('packet128 idle synthetic receipt seconds:', json.dumps(samples), flush=True)
        self.assertLess(max(samples), .05)


if __name__ == '__main__':
    unittest.main()
