"""CPU tests (packet115): the ordered decode worker, the registry lock, and structural rules of the
runtime's decode path (native calls, no authority lock on the decode thread, drains before gated requests)."""
import ast
import threading
import time
import types
import unittest
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import stream_decode as sd  # noqa: E402

INTEGRATION = (HERE / 'integration.py').read_text()
TREE = ast.parse(INTEGRATION)
RUNTIME = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == 'Runtime')
METHODS = {n.name: n for n in RUNTIME.body if isinstance(n, ast.FunctionDef)}


def job(name, **extra):
    return dict({'run_name': name, 'timing': {}}, **extra)


class Worker(unittest.TestCase):
    def test_fifo_records_and_results(self):
        seen = []
        w = sd.OrderedWorker(lambda j: (seen.append(j['run_name']), {'run_name': j['run_name']})[1],
                             lambda j, e: None)
        jobs = [job('c%d' % i) for i in range(6)]
        for j in jobs:
            w.submit(j)
        self.assertTrue(w.drain(5))
        self.assertEqual(seen, ['c%d' % i for i in range(6)])
        self.assertEqual(w.record('c3'), {'run_name': 'c3'})
        self.assertEqual(w.wait(jobs[5]), {'run_name': 'c5'})
        self.assertTrue(all('queued' in j['timing'] and 'start' in j['timing'] for j in jobs))
        self.assertTrue(all(j['timing']['queued'] <= j['timing']['start'] for j in jobs))
        s = w.summary()
        self.assertEqual((s['submitted'], s['completed'], s['pending'], s['failed'], s['maxsize']), (6, 6, 0, None, 2))
        w.close()

    def test_back_pressure_blocks_the_submitter_and_drops_nothing(self):
        gate = threading.Event()
        done = []

        def slow(j):
            gate.wait(5)
            done.append(j['run_name'])
            return {}
        w = sd.OrderedWorker(slow, lambda j, e: None, maxsize=2)
        for i in range(3):            # one running, two waiting
            w.submit(job('c%d' % i))
        t0 = time.monotonic()
        threading.Timer(0.4, gate.set).start()
        _, depth, blocked = w.submit(job('c3'))
        self.assertGreaterEqual(time.monotonic() - t0, 0.3)
        self.assertGreaterEqual(blocked, 0.3)
        self.assertEqual(depth, 3)
        self.assertTrue(w.drain(5))
        self.assertEqual(done, ['c0', 'c1', 'c2', 'c3'])
        w.close()

    def test_failure_latches_once_and_skips_later_jobs(self):
        failures = []

        def work(j):
            if j['run_name'] == 'c1':
                raise RuntimeError('decode exploded')
            return {}
        w = sd.OrderedWorker(work, lambda j, e: failures.append((j['run_name'], str(e))))
        jobs = [job('c0'), job('c1'), job('c2')]
        for j in jobs:
            w.submit(j)
        w.drain(5)
        deadline = time.monotonic() + 5
        while w.pending() and time.monotonic() < deadline:   # drain returns early once failed
            time.sleep(0.01)
        self.assertEqual(failures, [('c1', 'decode exploded')])
        self.assertIn('c1', w.failed)
        self.assertEqual(w.summary()['skipped_after_failure'], ['c2'])
        with self.assertRaises(sd.DecodeFailure):
            w.wait(jobs[1])
        with self.assertRaises(sd.DecodeFailure):
            w.wait(jobs[2])
        with self.assertRaises(sd.DecodeFailure):
            w.submit(job('c3'))
        self.assertFalse(w.drain(1))
        w.close()

    def test_submit_bound_turns_a_stuck_queue_into_a_fault(self):
        gate = threading.Event()
        w = sd.OrderedWorker(lambda j: gate.wait(5) or {}, lambda j, e: None, maxsize=1, submit_bound_s=0.6)
        w.submit(job('c0'))
        w.submit(job('c1'))
        with self.assertRaises(sd.DecodeFailure):
            w.submit(job('c2'))
        gate.set()
        w.drain(5)
        w.close()

    def test_frame_mode_wait_is_bounded(self):
        gate = threading.Event()
        w = sd.OrderedWorker(lambda j: (gate.wait(5), {'ok': 1})[1], lambda j, e: None)
        j = job('c0')
        w.submit(j)
        with self.assertRaises(sd.DecodeFailure):
            w.wait(j, timeout_s=0.2)
        gate.set()
        self.assertEqual(w.wait(j, timeout_s=5), {'ok': 1})
        w.close()


class WaitFor(unittest.TestCase):
    """Packet115 mixed anchor: the stage-B node waits for the predecessor's record by run name."""
    def test_returns_the_record_once_committed(self):
        gate = threading.Event()
        w = sd.OrderedWorker(lambda j: (gate.wait(5), {'run_name': j['run_name']})[1], lambda j, e: None)
        w.submit(job('n0'))
        threading.Timer(0.3, gate.set).start()
        record, waited = w.wait_for('n0', 5)
        self.assertEqual(record, {'run_name': 'n0'})
        self.assertGreaterEqual(waited, 0.2)
        record, waited = w.wait_for('n0', 5)          # already committed: no wait
        self.assertLess(waited, 0.1)
        w.close()

    def test_bounded_and_latched(self):
        gate = threading.Event()
        w = sd.OrderedWorker(lambda j: (gate.wait(5), {'run_name': j['run_name']})[1], lambda j, e: None)
        w.submit(job('n0'))
        with self.assertRaises(sd.DecodeFailure):
            w.wait_for('n0', 0.2)
        gate.set()
        w.wait_for('n0', 5)

        def boom(j):
            raise RuntimeError('decode failed')
        bad = sd.OrderedWorker(boom, lambda j, e: None)
        bad.submit(job('n1'))
        start = time.monotonic()
        with self.assertRaises(sd.DecodeFailure):
            bad.wait_for('n1', 30)
        self.assertLess(time.monotonic() - start, 5)   # the latch ends the wait, not the bound
        w.close()
        bad.close()


class Registry(unittest.TestCase):
    def test_lock_serializes_loads_and_inspection(self):
        mm = types.SimpleNamespace()
        inside = []
        order = []

        def load_models_gpu(models, **kw):
            inside.append(threading.get_ident())
            self.assertEqual(len(inside), 1)
            time.sleep(0.05)
            order.append(('load', models))
            inside.pop()
        mm.load_models_gpu = load_models_gpu
        lock = sd.RegistryLock()
        self.assertEqual(lock.install(mm)['reentrant'], True)
        inspect = lock.wrap(lambda: (inside.append(1), time.sleep(0.05), order.append('inspect'), inside.pop()))
        threads = [threading.Thread(target=mm.load_models_gpu, args=(['vae'],)) for _ in range(3)]
        threads += [threading.Thread(target=inspect) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(order), 6)
        lock.check()
        with self.assertRaises(RuntimeError):
            lock.install(mm)
        mm.load_models_gpu = load_models_gpu
        with self.assertRaises(RuntimeError):
            lock.check()

    def test_reentrant(self):
        lock = sd.RegistryLock()
        mm = types.SimpleNamespace(load_models_gpu=lambda: 'loaded')
        lock.install(mm)
        outer = lock.wrap(lambda: mm.load_models_gpu())
        self.assertEqual(outer(), 'loaded')


def calls(node):
    return [ast.unparse(n.func) for n in ast.walk(node) if isinstance(n, ast.Call)]


def attributes(node):
    return {ast.unparse(n) for n in ast.walk(node) if isinstance(n, ast.Attribute)}


class RuntimeStructure(unittest.TestCase):
    def test_decode_thread_uses_the_native_nodes_under_inference_mode(self):
        body = METHODS['_decode_job']
        text = ast.unparse(body)
        self.assertIn("nodes.VAEDecode().decode(vae, {'samples': job['video_latent']})[0]", text)
        self.assertIn("nodes.NODE_CLASS_MAPPINGS['LTXVAudioVAEDecode'].execute(samples={'samples': "
                      "job['audio_latent']}, audio_vae=audio_vae).result[0]", text)
        withs = [n for n in ast.walk(body) if isinstance(n, ast.With)]
        self.assertTrue(any('torch.inference_mode()' in ast.unparse(w.items[0].context_expr) for w in withs))
        self.assertIn("nodes.NODE_CLASS_MAPPINGS['LTXBaselineCapture']().capture", text)
        self.assertIn('XPU3_DECODE_FLOOR', text)

    def test_decode_thread_never_takes_the_authority_lock(self):
        reached = {'_decode_job', 'active_capture_request', '_geometry_mismatch', 'write', '_decode_failed',
                   '_preview_failed', '_save_preview', '_commit_preview', '_halt_async'}
        for name in reached:
            node = METHODS[name]
            text = ast.unparse(node)
            self.assertNotIn('authority.lock', text, name)
            self.assertNotIn('active_row', text, name)
        # Failures reach the authority only through a separate thread.
        self.assertIn('threading.Thread(target=self.authority.halt', ast.unparse(METHODS['_halt_async']))

    def test_output_node_submits_outside_the_lock_and_frame_mode_waits(self):
        node = METHODS['output']
        top = node.body
        withs = [i for i, s in enumerate(top) if isinstance(s, ast.With)]
        submit = next(i for i, s in enumerate(top) if 'self.decoder.submit(job)' in ast.unparse(s))
        self.assertTrue(withs[0] < submit < withs[1])
        self.assertIn("self.decoder.wait(job) if self.anchor == 'frame' else None", ast.unparse(top[submit + 1]))
        first = ast.unparse(top[withs[0]])
        # Off-chain modes: the anchor is written and anchor_ready stamped before the decode is queued.
        self.assertLess(first.index('latent_anchor.write_anchor'), first.index("cur['timing']['anchor_ready']"))
        self.assertIn('if self.anchor in contract.OFF_CHAIN_DECODE:', first)
        self.assertIn("'video_latent': latents['video_latent'].detach().to('cpu', copy=True).clone()", first)

    def test_gated_requests_drain_the_decode_thread_first(self):
        text = ast.unparse(METHODS['before_request'])
        self.assertLess(text.index('self.decoder.drain(DECODE_DRAIN_BOUND_S)'),
                        text.index('self.adapter.before_request'))
        self.assertIn('contract.GATED_KINDS', text)
        verdict = ast.unparse(METHODS['action'])
        self.assertLess(verdict.index('self.decoder.drain'), verdict.index('self.preview.drain'))

    def test_registry_lock_is_installed_before_preparation(self):
        text = ast.unparse(METHODS['prepare'])
        self.assertLess(text.index('self.registry.install(mm)'), text.index('self.adapter.prepare()'))
        self.assertLess(text.index('self.adapter._inspect = self.registry.wrap(self.adapter._inspect)'),
                        text.index('self.adapter.prepare()'))

    def test_capture_callback_is_bound_to_the_decode_thread(self):
        text = ast.unparse(METHODS['active_capture_request'])
        self.assertIn("cap['thread'] == threading.get_ident()", text)

    def test_event_nodes_cover_the_sampler_a_split(self):
        import stream_receipts
        self.assertEqual(set(stream_receipts.EVENT_NODES), {'364', '344', '367', '348', 'stream_condition_b',
                                                            '340', '368', '369', 'stream_output',
                                                            'stream_crop_a', 'stream_crop_b'})
        self.assertIn('stream_receipts.EVENT_NODES', ast.unparse(METHODS['record_event']))


class MixedStructure(unittest.TestCase):
    """Packet115: where the mixed anchor's stage B waits, and what the decode thread writes first."""
    def test_stage_b_waits_outside_the_authority_lock_then_encodes(self):
        node = METHODS['mixed_condition_b']
        top = node.body
        withs = [i for i, s in enumerate(top) if isinstance(s, ast.With)]
        wait = next(i for i, s in enumerate(top) if 'self.decoder.wait_for(' in ast.unparse(s))
        self.assertEqual(len(withs), 2)
        self.assertTrue(withs[0] < wait < withs[1])
        for i in withs:
            self.assertIn('self.authority.lock', ast.unparse(top[i].items[0].context_expr))
        second = ast.unparse(top[withs[1]])
        order = [second.index(s) for s in ("stream_receipts.read_anchor(frame['path'], frame['sha256'])",
                                           "first_stage='B'", "self.conditioning.run_stage('B'")]
        self.assertEqual(order, sorted(order))
        self.assertIn('FRAME_WAIT_BOUND_S', ast.unparse(top[wait]))
        self.assertIn("cur['timing']['frame_wait_start']", ast.unparse(top[withs[0]]))
        self.assertIn("cur['timing']['frame_ready']", second)

    def test_decode_thread_writes_frame_then_record_and_measures_sharpness(self):
        text = ast.unparse(METHODS['_decode_job'])
        self.assertLess(text.index("stream_receipts.write_anchor(self.run / 'anchors'"),
                        text.index("self.write('receipts/decode-'"))
        self.assertIn('stream_preview.sharpness_profile(torch, images, self.frames)', text)
        self.assertLess(text.index('sharpness_profile'), text.index("self.write('receipts/decode-'"))

    def test_guide_native_calls_are_rechecked(self):
        text = ast.unparse(METHODS['_guide_native'])
        self.assertIn('nodes.NODE_CLASS_MAPPINGS.get(cls.__name__) is cls', text)
        self.assertIn('self.bindings.check_native()', text)
        prep = ast.unparse(METHODS['prepare'])
        self.assertIn("('guide', 'LTXVAddLatentGuide'), ('crop', 'LTXVCropGuides')", prep)
        self.assertIn("native.get('get_keyframe_idxs')", prep)


if __name__ == '__main__':
    unittest.main()
