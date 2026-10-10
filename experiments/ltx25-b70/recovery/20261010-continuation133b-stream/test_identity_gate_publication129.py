"""CPU routes for immutable identity and external atomic model-gate updates."""
import ast
import asyncio
import json
import os
import stat
from pathlib import Path
import tempfile
import threading
import types
import unittest
from unittest import mock

from aiohttp import web

PARENT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-128')


class IdentityGatePublication129(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ltx129-identity-gate-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def extract(self, filename, function, namespace):
        tree = ast.parse((PARENT / 'source/scripts' / filename).read_bytes())
        node = next(row for row in tree.body if isinstance(row, ast.AsyncFunctionDef)
                    and row.name == function)
        node.decorator_list = []
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                     '<actual-route129>', 'exec'), namespace)
        return namespace[function]

    def paused_atomic_update(self, path, raw, observe):
        midwrite, release = threading.Event(), threading.Event()
        errors = []
        def writer():
            try:
                tmp = path.with_suffix('.tmp')
                with tmp.open('wb') as stream:
                    stream.write(raw[:len(raw)//2])
                    stream.flush()
                    midwrite.set()
                    if not release.wait(3):
                        raise TimeoutError('reader did not finish')
                    stream.write(raw[len(raw)//2:])
                    stream.flush()
                    os.fsync(stream.fileno())
                tmp.replace(path)
                fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
            except BaseException as error:
                errors.append(error)
        thread = threading.Thread(target=writer)
        thread.start()
        try:
            self.assertTrue(midwrite.wait(3))
            observe()
        finally:
            release.set()
            thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])

    def test_identity_route_serves_loaded_complete_identity_during_writer(self):
        old = {'pid': 123, 'source_packet_manifest_sha256': 'a' * 64}
        path = self.root / 'server-identity.json'
        path.write_text(json.dumps(old))
        # This exactly represents encoder_identity_node's import-time JSON snapshot.
        identity = json.loads(path.read_bytes())
        route = self.extract('encoder_identity_node.py', 'encoder_identity',
                             {'web': web, 'identity': identity})
        def observe():
            response = asyncio.run(route(None))
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.body), old)
        self.paused_atomic_update(path, json.dumps({'pid': 456}).encode(), observe)
        observe()

    def gate_route(self):
        route = self.extract('capture_node.py', 'fault_gate',
                             {'web': web, 'json': json, 'Path': lambda _: self.root})
        async def admitted(request):
            return web.json_response({'admitted': True})
        request = types.SimpleNamespace(method='POST', path='/prompt')
        return lambda: asyncio.run(route(request, admitted))

    def test_prompt_model_gate_serves_previous_complete_during_atomic_update(self):
        path = self.root / 'model-verification.json'
        path.write_text(json.dumps({'status': 'passed', 'generation': 1}))
        route = self.gate_route()
        self.paused_atomic_update(path, json.dumps({'status': 'verifying', 'generation': 2}).encode(),
                                  lambda: self.assertEqual(route().status, 200))
        self.assertEqual(route().status, 503)

    def test_prompt_pending_model_gate_remains_closed_until_commit(self):
        path = self.root / 'model-verification.json'
        path.write_text(json.dumps({'status': 'verifying', 'generation': 1}))
        route = self.gate_route()
        self.paused_atomic_update(path, json.dumps({'status': 'passed', 'generation': 2}).encode(),
                                  lambda: self.assertEqual(route().status, 503))
        self.assertEqual(route().status, 200)

    def test_actual_staging_gate_save_is_durable_and_never_exposes_partial(self):
        path = self.root / 'model-verification.json'
        path.write_text(json.dumps({'status': 'passed', 'generation': 1}))
        script = Path(__file__).resolve().parents[2] / 'scripts/stage-model.py'
        tree = ast.parse(script.read_bytes())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                        and node.name == 'save')
        report = {'status': 'running', 'revision': 'r', 'files': []}
        namespace = dict(receipt=path, report=report, json=json, os=os)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
                     '<stage-save-only>', 'exec'), namespace)
        route = self.gate_route()
        opened, release = threading.Event(), threading.Event()
        errors, sync_modes = [], []
        original_open, original_fsync = Path.open, os.fsync
        class PausedWriter:
            def __init__(self, stream): self.stream = stream
            def __enter__(self): return self
            def __exit__(self, *args): return self.stream.__exit__(*args)
            def write(self, raw):
                halfway = len(raw) // 2
                self.stream.write(raw[:halfway])
                self.stream.flush()
                opened.set()
                if not release.wait(3):
                    raise TimeoutError('route did not finish')
                self.stream.write(raw[halfway:])
            def flush(self): return self.stream.flush()
            def fileno(self): return self.stream.fileno()
        def open_file(target, *args, **kwargs):
            stream = original_open(target, *args, **kwargs)
            return PausedWriter(stream) if target == path.with_suffix('.tmp') and args == ('w',) else stream
        def fsync(fd):
            sync_modes.append(os.fstat(fd).st_mode)
            return original_fsync(fd)
        def writer():
            try:
                namespace['save']()
            except BaseException as error:
                errors.append(error)
        with mock.patch.object(Path, 'open', open_file), mock.patch.object(os, 'fsync', fsync):
            thread = threading.Thread(target=writer)
            thread.start()
            try:
                self.assertTrue(opened.wait(3))
                self.assertEqual(route().status, 200)
            finally:
                release.set()
                thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(path.read_bytes(), (json.dumps(report, indent=2) + '\n').encode())
        self.assertEqual(route().status, 503)
        self.assertEqual(len(sync_modes), 2)
        self.assertTrue(stat.S_ISREG(sync_modes[0]))
        self.assertTrue(stat.S_ISDIR(sync_modes[1]))


if __name__ == '__main__':
    unittest.main()
