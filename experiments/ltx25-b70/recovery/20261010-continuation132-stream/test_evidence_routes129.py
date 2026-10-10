"""Deterministic mid-write races through actual registered CPU HTTP handlers.
No listener or device. Pause a real writer after half its bytes have flushed.
"""
import ast
import asyncio
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace as NS
import unittest
from unittest import mock

import evidence_publication as ep
import integration
import session
import stream_preview

HERE = Path(__file__).resolve().parent

class EvidenceRoutes(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='evidence129-')
        self.addCleanup(self.temp.cleanup)
        self.run = Path(self.temp.name)
        (self.run / 'receipts').mkdir()
        self.name = 'stream132-s00000012'
        worker = NS(failed=None, record=lambda name: None, summary=lambda: {})
        authority = NS(failed=None, qid='qid', status=lambda: {'phase': 'stream'})
        authority.halt = lambda error: setattr(authority, 'failed', str(error))
        self.ctx = NS(run=self.run, root=self.run, session=session, receipt_polls={}, receipt_served={},
            decoder=worker, preview=worker, action_busy=False, authority=authority,
            identity_sha='identity', manifest_sha='manifest', frames=145, anchor='frame',
            decoder_graph_flag=0, anchor_decode='cone', bencode_overlap=1, prep_ahead=1,
            snapshot_mode='fingerprint', pool_cap=None, display_device='xpu:3', display_schedule='sampler-a',
            anchor_read_ahead=0, snapshot_schedule='full', qualified_windows=None,
            decoder_graph=None, cone=None, precompute=worker, inspector=worker, display_worker='serial',
            server_options={}, storage_check=lambda **kw: {}, note_status_route=lambda elapsed: None)
        self.ctx.fault = lambda: (self.run/'stream-halt.json').exists()
        from aiohttp import web
        server = NS(routes=web.RouteTableDef(), app=web.Application(), send_sync=lambda *a: None)
        fake = NS(PromptServer=NS(instance=server))
        with mock.patch.dict('sys.modules', {'server': fake}), mock.patch.object(integration, '_CTX', self.ctx), mock.patch.object(integration, '_ROUTES_INSTALLED', False):
            integration.install_routes()
        self.routes = {route.path: route.handler for route in server.routes}

    def call(self, path):
        request = NS(match_info={'run_name': self.name})
        async def body():
            return {'action': 'qualify-verdict'}
        request.json = body
        return asyncio.run(self.routes[path](request))

    def midwrite(self, final, writer, check, *, duplicate=False):
        ready, release = threading.Event(), threading.Event()
        errors = []
        opened = Path.open
        temporary = ep.temporary_name(final)
        class SlowFile:
            def __init__(self, stream): self.stream = stream
            def __enter__(self): return self
            def __exit__(self, *args): return self.stream.__exit__(*args)
            def write(self, raw):
                cut = len(raw)//2
                self.stream.write(raw[:cut]); self.stream.flush()
                ready.set()
                if not release.wait(5): raise TimeoutError('reader did not release writer')
                self.stream.write(raw[cut:])
                return len(raw)
            def __getattr__(self, key): return getattr(self.stream, key)
        def slow(path, *args, **kwargs):
            stream = opened(path, *args, **kwargs)
            return SlowFile(stream) if path == temporary and args and args[0] == 'xb' else stream
        def run():
            try: writer()
            except BaseException as error: errors.append(error)
        with mock.patch.object(Path, 'open', slow):
            thread = threading.Thread(target=run)
            thread.start()
            try:
                self.assertTrue(ready.wait(5))
                self.assertTrue(temporary.exists())
                for _ in range(8): check()
            finally:
                release.set(); thread.join(5)
        self.assertFalse(thread.is_alive())
        if duplicate:
            self.assertEqual(len(errors), 1)
            self.assertIsInstance(errors[0], FileExistsError)
        else:
            self.assertEqual(errors, [])
            self.assertFalse(temporary.exists())
            self.assertEqual(final.stat().st_nlink, 1)

    def record_race(self, prefix, *, previous=False):
        path = self.run/'receipts'/(prefix+'-'+self.name+'.json')
        route = '/ltx-stream/'+prefix+'/{run_name}'
        value = {'record': prefix, 'unchanged': 'é'*1024}
        raw = session.canonical(value)+b'\n'
        if previous: path.write_bytes(b'{"previous":"complete"}\n')
        writer = (lambda: stream_preview.write_record_atomic(session,path,value)) if prefix=='preview' else (lambda: session.write_exclusive(path,value))
        def check():
            response = self.call(route)
            self.assertEqual(response.status, 200 if previous else 404)
            if previous: self.assertEqual(response.body,b'{"previous":"complete"}\n')
            else: self.assertIn(b'No committed', response.body)
        self.midwrite(path,writer,check,duplicate=previous)
        response = self.call(route)
        self.assertEqual(response.status,200)
        self.assertEqual(response.body,b'{"previous":"complete"}\n' if previous else raw)

    def test_receipt_midwrite_404_then_exact_bytes(self): self.record_race('receipt')
    def test_decode_midwrite_404_then_exact_bytes(self): self.record_race('decode')
    def test_preview_midwrite_404_then_exact_bytes(self): self.record_race('preview')
    def test_receipt_previous_complete_never_replaced(self): self.record_race('receipt',previous=True)
    def test_decode_previous_complete_never_replaced(self): self.record_race('decode',previous=True)
    def test_preview_previous_complete_never_replaced(self): self.record_race('preview',previous=True)

    def test_status_midwrite_halt_evidence(self):
        path=self.run/'stream-halt.json'
        def check():
            response=self.call('/ltx-stream/status')
            self.assertEqual(response.status,200)
            value=json.loads(response.body)
            self.assertFalse(value['fault'])
            self.assertTrue(value['features']['atomic_evidence_publication'])
        self.midwrite(path,lambda:session.write_exclusive(path,{'reason':'halt'*100}),check)
        self.assertTrue(json.loads(self.call('/ltx-stream/status').body)['fault'])

    def test_action_midwrite_evidence_refuses_cleanly(self):
        path=self.run/'stream-qualification-verdict.json'
        def action(name):
            try: return session.strict_json(session.read_regular(path))
            except FileNotFoundError: raise session.Refusal('not-yet-published','Evidence not yet published')
        self.ctx.action=action
        def check():
            # Exercise actual route and owned action worker, including halt on action failure.
            self.ctx.authority.failed=None
            self.ctx.action_busy=False
            response=self.call('/ltx-stream/action')
            self.assertEqual(response.status,409)
            self.assertIn(b'not yet published', response.body)
        self.midwrite(path,lambda:session.write_exclusive(path,{'passed':True,'hash':'a'*64}),check)
        self.ctx.authority.failed=None; self.ctx.action_busy=False
        self.assertEqual(self.call('/ltx-stream/action').status,200)

    def test_guard_source_identical_to_sealed128(self):
        parent=Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-128/source/scripts/ltx_resolution_session.py')
        def source(path):
            text=path.read_text(); tree=ast.parse(text)
            return ast.get_source_segment(text,next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='read_regular'))
        self.assertEqual(source(parent),source(HERE/'session.py'))

    def test_fsync_before_publication_and_directory_after(self):
        final=self.run/'proof.json'; value={'payload':'é'}; raw=session.canonical(value)+b'\n'
        calls=[]; fsync=os.fsync; publish=ep.publish_file
        def sync(fd):
            calls.append(('fsync',final.exists())); return fsync(fd)
        def rename(tmp,path):
            self.assertFalse(final.exists()); self.assertEqual(tmp.read_bytes(),raw)
            self.assertTrue(calls); return publish(tmp,path)
        with mock.patch.object(ep.os,'fsync',sync),mock.patch.object(ep,'publish_file',rename):
            result=session.write_exclusive(final,value)
        self.assertEqual(result,hashlib.sha256(raw).hexdigest())
        self.assertEqual(calls[-1],('fsync',True))
        self.assertEqual(session.read_regular(final),raw)

    def test_failed_file_sync_never_exposes_final(self):
        final=self.run/'failed.json'
        with mock.patch.object(ep.os,'fsync',side_effect=OSError('injected fsync failure')):
            with self.assertRaises(OSError): session.write_exclusive(final,{'a':1})
        self.assertFalse(final.exists())

    def test_no_replace_keeps_open_reader_identity(self):
        final=self.run/'old.json'; session.write_exclusive(final,{'old':True})
        old=final.stat()
        with self.assertRaises(FileExistsError): session.write_exclusive(final,{'new':True})
        self.assertEqual(old,final.stat())
        self.assertEqual(session.strict_json(session.read_regular(final)),{'old':True})
