"""CPU-only bounded-pipeline tests: no torch import, devices, launch or server."""
import ast
import os
from contextlib import nullcontext
from pathlib import Path
import sys
import threading
import time
import types
from unittest.mock import patch
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import stream_decode as sd


def job(name):
    return {'run_name': name, 'timing': {}, 'stage_names': ('anchor',)}


class SplitDisplay(unittest.TestCase):
    def make_worker(self, fn, **kwargs):
        errors = []
        w = sd.SplitWorker(fn, lambda j, e: errors.append((j['run_name'], str(e))), **kwargs)
        self.addCleanup(w.close)
        return w, errors

    def test_next_anchor_runs_while_previous_display_is_blocked(self):
        tail = threading.Event()
        self.addCleanup(tail.set)
        w, _ = self.make_worker(None)
        def front(j):
            w.publish(j, 'anchor', j['run_name'])
            return sd.DeferredDisplay(lambda: (tail.wait(2), {'name': j['run_name']})[1])
        w.process_fn = front
        a, b = job('a'), job('b')
        w.submit(a)
        w.submit(b)
        self.assertEqual(w.wait_stage(b, 'anchor', 1), 'b')
        self.assertFalse(a['done'].is_set())
        self.assertFalse(b['done'].is_set())
        tail.set()
        self.assertEqual(w.wait(b, 2), {'name': 'b'})
        self.assertTrue(w.drain(2))
        self.assertEqual(w.order, ['a', 'b'])
        self.assertEqual(w.completed, 2)

    def test_pending_and_drain_cover_transferred_display(self):
        tail, started = threading.Event(), threading.Event()
        self.addCleanup(tail.set)
        w, _ = self.make_worker(lambda j: sd.DeferredDisplay(
            lambda: (started.set(), tail.wait(2), {'ok': True})[-1]))
        a = job('a')
        w.submit(a)
        self.assertTrue(started.wait(1))
        self.assertGreaterEqual(w.pending(), 1)
        self.assertEqual(w.summary()['display_current'], 'a')
        self.assertFalse(w.drain(0.01))
        self.assertIsNone(w.record('a'))
        tail.set()
        self.assertEqual(w.wait(a, 1), {'ok': True})
        self.assertTrue(w.drain(1))
        self.assertEqual(w.pending(), 0)

    def test_wait_for_returns_final_record_not_anchor_result(self):
        w, _ = self.make_worker(lambda j: sd.DeferredDisplay(lambda: {'final': j['run_name']}))
        w.submit(job('a'))
        record, _ = w.wait_for('a', 1)
        self.assertEqual(record, {'final': 'a'})
        self.assertEqual(w.record('a'), record)

    def test_original_stage_events_and_timestamps_survive_transfer(self):
        w, _ = self.make_worker(None)
        events = []
        def front(j):
            events.append(j['stage_events']['anchor'])
            w.publish(j, 'anchor', {'bytes': 'unchanged'})
            return sd.DeferredDisplay(lambda: {'ok': True})
        w.process_fn = front
        a = job('a')
        w.submit(a)
        w.wait(a, 1)
        self.assertIs(a['stage_events']['anchor'], events[0])
        self.assertEqual(w.wait_stage(a, 'anchor', 1), {'bytes': 'unchanged'})
        stamps = [a['timing'][k] for k in ('queued', 'start', 'display_worker_queued', 'display_worker_start')]
        self.assertEqual(stamps, sorted(stamps))

    def test_display_failure_latches_once_releases_waiters_and_never_retries(self):
        ready, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        w, errors = self.make_worker(None)
        def front(j):
            w.publish(j, 'anchor', j['run_name'])
            if j['run_name'] == 'b':
                ready.set()
            def tail():
                release.wait(2)
                raise RuntimeError('cross-card byte mismatch')
            return sd.DeferredDisplay(tail)
        w.process_fn = front
        a, b = job('a'), job('b')
        w.submit(a)
        w.submit(b)
        self.assertTrue(ready.wait(1))
        release.set()
        for j in (a, b):
            with self.assertRaises(sd.DecodeFailure):
                w.wait(j, 1)
        self.assertEqual(errors, [('a', 'cross-card byte mismatch')])
        self.assertEqual(w.completed, 0)
        self.assertFalse(w.drain(1))
        with self.assertRaises(sd.DecodeFailure):
            w.submit(job('c'))

    def test_anchor_failure_releases_unpublished_stage(self):
        def fail(j):
            raise RuntimeError('cone failed')
        w, errors = self.make_worker(fail)
        a = job('a')
        w.submit(a)
        with self.assertRaises(sd.DecodeFailure):
            w.wait_stage(a, 'anchor', 1)
        with self.assertRaises(sd.DecodeFailure):
            w.wait(a, 1)
        self.assertEqual(errors, [('a', 'cone failed')])

    def test_qualification_inline_path_has_one_completion_and_no_transfer(self):
        w, _ = self.make_worker(lambda j: {'inline': True})
        a = job('a')
        w.submit(a)
        self.assertEqual(w.wait(a, 1), {'inline': True})
        self.assertNotIn('display_worker_queued', a['timing'])
        self.assertTrue(w.drain(1))
        self.assertEqual(w.completed, 1)
        self.assertEqual(w.order, ['a'])

    def test_display_cannot_defer_again(self):
        w, errors = self.make_worker(lambda j: sd.DeferredDisplay(lambda: sd.DeferredDisplay(lambda: {})))
        a = job('a')
        w.submit(a)
        with self.assertRaises(sd.DecodeFailure):
            w.wait(a, 1)
        self.assertEqual(len(errors), 1)
        self.assertIn('cannot defer twice', errors[0][1])

    def test_both_queues_are_bounded(self):
        w, _ = self.make_worker(lambda j: {}, maxsize=1)
        self.assertEqual(w.queue.maxsize, 1)
        self.assertEqual(w.display_queue.maxsize, 1)
        self.assertEqual(w.summary()['display_maxsize'], 1)

    def test_display_transfer_backpressure_fault_is_bounded(self):
        hold, display_started = threading.Event(), threading.Event()
        self.addCleanup(hold.set)
        def finish():
            display_started.set()
            hold.wait(2)
            return {}
        w, errors = self.make_worker(lambda j: sd.DeferredDisplay(finish), maxsize=1, submit_bound_s=0.03)
        a, b, c = job('a'), job('b'), job('c')
        w.submit(a)
        self.assertTrue(display_started.wait(1))
        w.submit(b)
        # Wait for the first waiting display to be transferred before submitting
        # the third front job: this is an event barrier, not a scheduling guess.
        entered = threading.Event()
        old = w.process_fn
        w.process_fn = lambda j: (entered.set(), old(j))[1]
        w.submit(c)
        self.assertTrue(entered.wait(1))
        with self.assertRaises(sd.DecodeFailure):
            w.wait(c, 1)
        self.assertIn('bounded submit', errors[0][1])
        hold.set()


class EarlyAudio(unittest.TestCase):
    def build(self, mode='parallel', failed=None, aux='legacy'):
        tree = ast.parse((HERE / 'integration.py').read_text())
        runtime = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Runtime')
        method = next(n for n in runtime.body if isinstance(n, ast.FunctionDef) and n.name == '_decode_audio_early')
        calls = []
        ns = {'time': time, 'residency123': types.SimpleNamespace(
            guard_aux=lambda t, phase, before, residency: calls.append(('guard', before)))}
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<sealed-early-audio-method>', 'exec'), ns)
        def require(ok, message):
            if not ok:
                raise RuntimeError(message)
        ctx = types.SimpleNamespace(display_worker=mode, aux_residency=aux,
            encoder_lock=threading.RLock(), decoder=types.SimpleNamespace(failed=failed),
            session=types.SimpleNamespace(require=require))
        audio = {'waveform': object(), 'sample_rate': 48000}
        def execute(**kwargs):
            calls.append(('native', kwargs))
            return types.SimpleNamespace(result=[audio])
        modules = {'torch': types.SimpleNamespace(inference_mode=nullcontext),
                   'nodes': types.SimpleNamespace(NODE_CLASS_MAPPINGS={
                       'LTXVAudioVAEDecode': types.SimpleNamespace(execute=execute)})}
        return ns['_decode_audio_early'], ctx, calls, audio, modules

    def test_early_audio_calls_native_once_on_same_private_latent(self):
        fn, ctx, calls, audio, modules = self.build()
        latent, vae = object(), object()
        with patch.dict(sys.modules, modules):
            row = fn(ctx, {'audio_latent': latent}, vae)
        self.assertIs(row['audio'], audio)
        self.assertEqual(calls, [('guard', True), ('native', {'samples': {'samples': latent}, 'audio_vae': vae}),
                                 ('guard', False)])
        self.assertLessEqual(row['start_ns'], row['done_ns'])

    def test_early_audio_refuses_outside_parallel_legacy_scope(self):
        for mode, aux in [('serial', 'legacy'), ('parallel', 'xpu2')]:
            fn, ctx, calls, _, modules = self.build(mode=mode, aux=aux)
            with patch.dict(sys.modules, modules), self.assertRaises(RuntimeError):
                fn(ctx, {'audio_latent': object()}, object())
            self.assertEqual(calls, [])

    def test_early_audio_failure_guard_precedes_any_native_work(self):
        fn, ctx, calls, _, modules = self.build(failed='earlier decode failed')
        with patch.dict(sys.modules, modules), self.assertRaisesRegex(RuntimeError, 'companion worker'):
            fn(ctx, {'audio_latent': object()}, object())
        self.assertEqual(calls, [])


class ParallelRuntimeFlow(unittest.TestCase):
    def run_parallel(self, frames, inject='none'):
        from test_runtime_flow import harness
        with patch.dict(os.environ, {'LTX_DISPLAY_WORKER': 'parallel', 'OMP_NUM_THREADS': '1'}):
            return harness('--frames', str(frames), '--anchor', 'frame', '--decoder-graph', '0',
                '--display-schedule', 'eager-display', '--display-device', 'xpu:2', '--stream-chunks', '2',
                '--decode-delay', '0.01', '--audio-delay', '0.01', '--inject', inject)

    def check_parallel(self, frames):
        d = self.run_parallel(frames)
        self.assertIsNone(d.get('error'), d.get('error'))
        self.assertIsNone(d.get('halted'), d.get('halted'))
        self.assertTrue(d['verdict']['passed'], d['verdict'])
        self.assertFalse(d['xpu_initialized'])
        self.assertTrue(d['decoder_drained'] and d['preview_drained'])
        self.assertEqual(len(d['chunks']), 11)
        self.assertEqual([r['completion_worker'] for r in d['chunks']], ['serial'] * 6 + ['parallel'] * 5)
        self.assertTrue(all(r['display_worker'] == 'parallel' for r in d['chunks']))
        self.assertTrue(all(r['anchor_decode']['equal'] is True for r in d['chunks'][3:]))
        self.assertTrue(all(r['display_replica']['equal'] is True for r in d['chunks'][:9]))
        for i in range(3):
            for tensor in ('images', 'waveform'):
                hashes = [d['chunks'][i + offset]['decoded_tensors'][tensor]['sha256'] for offset in (0, 3, 6)]
                self.assertEqual(len(set(hashes)), 1, (frames, tensor, i, hashes))
        for row in d['chunks'][6:]:
            t, w = row['decode_timing_ns'], row['display_worker_timing']
            self.assertLessEqual(w['audio_start_ns'], w['audio_done_ns'])
            self.assertEqual(t['audio_done'], w['audio_done_ns'])
            self.assertLessEqual(w['audio_done_ns'], w['queued_ns'])
            self.assertLessEqual(w['queued_ns'], w['start_ns'])
            self.assertLessEqual(w['start_ns'], t['display_start'])
            self.assertEqual(t['decode_done'], t['display_done'])
            self.assertAlmostEqual(row['decode_timing_s']['audio_decode'],
                                   (w['audio_done_ns'] - w['audio_start_ns']) / 1e9)
            self.assertEqual(row['preview_timing_ns']['audio_done'], t['audio_done'])
        return d

    def test_parallel145_three_chains_early_audio_and_live_bytes(self):
        self.check_parallel(145)

    def test_parallel169_three_chains_early_audio_and_live_bytes(self):
        self.check_parallel(169)

    def test_parallel_live_byte_difference_latches_without_fallback(self):
        d = self.run_parallel(145, inject='replica-live-diff')
        self.assertTrue(d.get('error') or d.get('halted'), d)
        self.assertIn('display-replica-120-refused.json', d['lever_latches'], d)


class IntegrationWiring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse((HERE / 'integration.py').read_text())
        runtime = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Runtime')
        cls.methods = {n.name: ast.unparse(n) for n in runtime.body if isinstance(n, ast.FunctionDef)}

    def test_parallel_is_opt_in_and_closed_scope(self):
        s = self.methods['__init__']
        self.assertIn("os.environ.get('LTX_DISPLAY_WORKER', 'serial')", s)
        for marker in ("self.frames in (145, 169)", "self.anchor == 'frame'", "self.anchor_decode == 'cone'",
                       'self.decoder_graph_flag == 0', "self.display_device == 'xpu:2'",
                       "self.display_schedule == 'eager-display'", "self.aux_residency == 'legacy'"):
            self.assertIn(marker, s)
        self.assertIn("stream_decode.SplitWorker if self.display_worker == 'parallel' else stream_decode.OrderedWorker", s)

    def test_qualification_completes_inline_and_tail_follows_precompute(self):
        s = self.methods['_decode_job']
        self.assertLess(s.index("self._precompute(reserved['B']"), s.index('self._decode_audio_early('))
        self.assertLess(s.index('self._decode_audio_early('), s.index('def finish_display():'))
        self.assertIn("if self.display_worker == 'parallel' and (not gated):", s)
        self.assertIn('return stream_decode.DeferredDisplay(finish_display)', s)
        self.assertTrue(s.endswith('return finish_display()'))

    def test_xpu3_cone_audio_and_reference_share_encoder_lock(self):
        s = self.methods['_decode_job']
        self.assertIn("with self.encoder_lock if self.display_worker == 'parallel' else nullcontext(), torch.inference_mode():", s)
        self.assertIn("with self.encoder_lock if self.display_worker == 'parallel' else nullcontext():", s)
        self.assertIn("with self.encoder_lock if self.display_worker == 'parallel' else nullcontext():", self.methods['_reference_decode'])
        self.assertIn('with self.encoder_lock:', self.methods['_precompute'])

    def test_existing_byte_gate_and_full_qualification_reference_are_retained(self):
        s = self.methods['_decode_job']
        for marker in ('display_raw == frame_raw', 'self.cone.note_check(equal)',
                       "kind in ('qualify-eager', 'qualify-graph', 'qualify-repeat')",
                       'display_replica.compare(torch, images, ref_images)',
                       "require(replica_check['equal']", 'Cross-card display differs'):
            self.assertIn(marker, s)

    def test_companion_failure_blocks_new_display_and_audio_work(self):
        s = self.methods['_decode_job']
        self.assertIn("require(self.decoder.failed is None, 'Display refused after companion worker failure')", s)
        self.assertIn("require(self.decoder.failed is None, 'Audio refused after companion worker failure')", s)

    def test_pipeline_timing_and_status_are_observable(self):
        source = (HERE / 'integration.py').read_text()
        for marker in ("'display_worker': self.display_worker", "'display_worker_timing':", "'completion_worker':", "'queued_ns'", "'start_ns'", "'gated_inline'",
                       'display_worker=ctx.display_worker', "'audio_start_ns'", "'audio_done_ns'"):
            self.assertIn(marker, source)


if __name__ == '__main__':
    unittest.main()
