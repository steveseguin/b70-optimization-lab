"""CPU tests: chat rendering/parsing, HTTP behavior with a fake engine, retention, monitor rules. No GPU, no model I/O."""
import http.client, importlib.util, json, os, tempfile, threading, time, unittest
from pathlib import Path

P = Path(__file__).resolve().parent


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


S = load(P / 'service.py', 'sc117_lan_service_test')
C = S.CHAT
CHAT = C.Chat()


class ChatTests(unittest.TestCase):
    def test_selftest_prompt_is_what_the_template_renders(self):
        fixture = json.loads((P.parents[1] / 'operating/first-model-prompt.json').read_text())
        req = C.parse({'messages': fixture['messages']}, CHAT)
        self.assertEqual(req['prompt_ids'], fixture['token_ids'])
        self.assertEqual(req['max_new'], 512)
        self.assertFalse(req['thinking'])

    def test_multi_turn_and_system(self):
        req = C.parse({'messages': [{'role': 'system', 'content': 'Be brief.'}, {'role': 'user', 'content': 'Hi'},
                                    {'role': 'assistant', 'content': 'Hello.'}, {'role': 'user', 'content': [{'type': 'text', 'text': 'Again'}]}],
                       'max_tokens': 7}, CHAT)
        text = CHAT.tok.decode(req['prompt_ids'], skip_special_tokens=False)
        self.assertTrue(text.startswith('<|im_start|>system\nBe brief.<|im_end|>'))
        self.assertTrue(text.endswith('<|im_start|>assistant\n<think>\n\n</think>\n\n'))
        self.assertEqual(req['max_new'], 7)

    def test_rejections(self):
        bad = [{}, {'messages': []}, {'messages': [{'role': 'tool', 'content': 'x'}]},
               {'messages': [{'role': 'user', 'content': [{'type': 'image_url', 'image_url': {}}]}]},
               {'messages': [{'role': 'user', 'content': 'x'}], 'n': 2},
               {'messages': [{'role': 'user', 'content': 'x'}], 'max_tokens': 0},
               {'messages': [{'role': 'user', 'content': 'x'}], 'tools': [{'type': 'function'}]},
               {'messages': [{'role': 'user', 'content': 'word ' * 5000}]}]
        for body in bad:
            with self.assertRaises(C.RequestError, msg=str(body)[:80]):
                C.parse(body, CHAT)

    def test_shape_eos_length_thinking_stop(self):
        ids = CHAT.encode('Hello there.')
        req = dict(thinking=False, stop=[], prompt_ids=[1])
        self.assertEqual(C.shape(req, ids + [248046], CHAT), ('Hello there.', None, 'stop'))
        self.assertEqual(C.shape(req, ids, CHAT)[2], 'length')
        req = dict(thinking=True, stop=[], prompt_ids=[1])
        out = CHAT.encode('plan it') + [248069] + CHAT.encode('\n\nDone.') + [248046]
        self.assertEqual(C.shape(req, out, CHAT), ('Done.', 'plan it', 'stop'))
        req = dict(thinking=False, stop=['there'], prompt_ids=[1])
        self.assertEqual(C.shape(req, ids, CHAT), ('Hello ', None, 'stop'))

    def test_clamp_and_lenient_fields(self):
        req = C.parse({'messages': [{'role': 'developer', 'content': 'Be brief.'}, {'role': 'user', 'content': 'x'}],
                       'max_tokens': 5000.0, 'n': None}, CHAT)
        self.assertEqual(req['max_new'], C.CONTEXT - len(req['prompt_ids']))
        self.assertTrue(CHAT.tok.decode(req['prompt_ids'], skip_special_tokens=False).startswith('<|im_start|>system\nBe brief.'))

    def test_sampling_parameters_reported_as_ignored(self):
        req = C.parse({'messages': [{'role': 'user', 'content': 'x'}], 'temperature': 0.7, 'top_p': 1}, CHAT)
        self.assertEqual(req['ignored_sampling'], ['temperature'])


class StreamerTests(unittest.TestCase):
    def run_stream(self, req, ids):
        st = C.Streamer(req, CHAT)
        sent = {'content': '', 'reasoning_content': ''}
        for t in ids:
            for f, d in st.feed(t):
                sent[f] += d
        tail, finish = st.finish(ids)
        for f, d in tail:
            sent[f] += d
        content, reasoning, fin = C.shape(req, ids, CHAT)
        self.assertFalse(st.mismatch)
        self.assertEqual(sent['content'], content)
        self.assertEqual(sent['reasoning_content'], reasoning or '')
        self.assertEqual(finish, fin)

    def test_plain_unicode_and_stop(self):
        ids = CHAT.encode('Héllo wörld — 你好世界 🙂 done. END tail') + [248046]
        self.run_stream(dict(thinking=False, stop=[], prompt_ids=[1]), ids)
        self.run_stream(dict(thinking=False, stop=['END', 'xyz'], prompt_ids=[1]), ids)
        self.run_stream(dict(thinking=False, stop=['🙂'], prompt_ids=[1]), ids[:-1])

    def test_thinking(self):
        ids = CHAT.encode('  plan it carefully  ') + [248069] + CHAT.encode('\n\nAnswer: 391') + [248046]
        self.run_stream(dict(thinking=True, stop=[], prompt_ids=[1]), ids)
        self.run_stream(dict(thinking=True, stop=[], prompt_ids=[1]), CHAT.encode('still thinking'))


class FakeEngine:
    def __init__(self, fail=False, delay=0.0):
        self.lock = threading.Lock()
        self.count = 0
        self.calls = []
        self.fail = fail
        self.delay = delay

    def storage_ok(self):
        return None

    def generate(self, prompt, max_new, label, on_token=None):
        time.sleep(self.delay)
        if self.fail:
            raise RuntimeError('rank failed')
        self.count += 1
        self.calls.append((prompt, max_new))
        out = CHAT.encode('Blue light scatters more.') + [248046]
        for t in out:
            if on_token:
                on_token(t)
        return out, dict(request=self.count)


class HttpTests(unittest.TestCase):
    def serve(self, engine, phase='ready', key=None):
        state = S.State()
        state.phase = phase
        state.faults = []
        state.fault = lambda e: (state.faults.append(e), setattr(state, 'phase', 'halted'))
        server = S.Server(('127.0.0.1', 0), S.make_handler(state, engine, CHAT, key))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        return state, server.server_address[1]

    def post(self, port, body, headers=None):
        c = http.client.HTTPConnection('127.0.0.1', port, timeout=30)
        c.request('POST', '/v1/chat/completions', json.dumps(body), {'Content-Type': 'application/json', **(headers or {})})
        r = c.getresponse()
        return r.status, r.read().decode()

    def test_completion_and_stream(self):
        engine = FakeEngine()
        _, port = self.serve(engine)
        code, raw = self.post(port, {'messages': [{'role': 'user', 'content': 'Why is the sky blue?'}], 'max_tokens': 16})
        self.assertEqual(code, 200)
        body = json.loads(raw)
        self.assertEqual(body['choices'][0]['message']['content'], 'Blue light scatters more.')
        self.assertEqual(body['choices'][0]['finish_reason'], 'stop')
        self.assertEqual(engine.calls[0][1], 16)
        code, raw = self.post(port, {'messages': [{'role': 'user', 'content': 'x'}], 'stream': True,
                                     'stream_options': {'include_usage': True}})
        self.assertEqual(code, 200)
        events = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith('data: {')]
        self.assertTrue(raw.rstrip().endswith('data: [DONE]'))
        deltas = [e['choices'][0]['delta'].get('content', '') for e in events if e['choices']]
        self.assertGreater(len([d for d in deltas if d]), 2)  # really incremental
        self.assertEqual(''.join(deltas), 'Blue light scatters more.')
        self.assertEqual(events[0]['choices'][0]['delta']['role'], 'assistant')
        self.assertEqual(events[-2]['choices'][0]['finish_reason'], 'stop')
        self.assertIn('usage', events[-1])

    def test_not_ready_and_bad_requests_do_not_touch_engine(self):
        engine = FakeEngine()
        _, port = self.serve(engine, phase='starting')
        self.assertEqual(self.post(port, {'messages': [{'role': 'user', 'content': 'x'}]})[0], 503)
        self.assertEqual(self.post(port, {'messages': 'x'})[0], 400)
        self.assertEqual(engine.calls, [])
        c = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
        c.request('GET', '/health')
        self.assertEqual(c.getresponse().status, 503)

    def test_engine_failure_halts(self):
        engine = FakeEngine(fail=True)
        state, port = self.serve(engine)
        code, raw = self.post(port, {'messages': [{'role': 'user', 'content': 'x'}]})
        self.assertEqual(code, 503)
        self.assertEqual(state.phase, 'halted')
        self.assertEqual(len(state.faults), 1)
        self.assertEqual(self.post(port, {'messages': [{'role': 'user', 'content': 'x'}]})[0], 503)
        self.assertFalse(engine.lock.locked())

    def test_serial_execution_and_queue_counter(self):
        engine = FakeEngine(delay=0.3)
        state, port = self.serve(engine)
        out = []
        threads = [threading.Thread(target=lambda: out.append(self.post(port, {'messages': [{'role': 'user', 'content': 'x'}]})[0])) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(out, [200, 200, 200])
        self.assertEqual(state.waiting, 0)

    def test_api_key(self):
        _, port = self.serve(FakeEngine(), key='secret')
        self.assertEqual(self.post(port, {'messages': [{'role': 'user', 'content': 'x'}]})[0], 401)
        self.assertEqual(self.post(port, {'messages': [{'role': 'user', 'content': 'x'}]}, {'Authorization': 'Bearer secret'})[0], 200)


class RetentionTests(unittest.TestCase):
    def test_release_removes_only_dumps(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            for rel in ('rank0/state-2147483647/a.bin', 'rank1/state-2147483647/b.bin', 'rank0/draft-final-state/c.bin',
                        'rank0/census.json', 'req-000002/rank0/state-2147483647/x.bin', 'req-000002/rank0/timings.jsonl'):
                (out / rel).parent.mkdir(parents=True, exist_ok=True)
                (out / rel).write_bytes(b'12345')
            e = S.Engine.__new__(S.Engine)
            e.t = type('T', (), {'out': out})()
            self.assertEqual(e.release(out), 15)
            self.assertTrue((out / 'rank0/census.json').exists())
            self.assertFalse((out / 'rank0/state-2147483647').exists())
            self.assertEqual(e.release(out / 'req-000002'), 10)
            self.assertFalse((out / 'req-000002').exists())
            with self.assertRaises(RuntimeError):
                e.release(Path(d).parent)


class MonitorTests(unittest.TestCase):
    def snapshot(self, holders, faults=()):
        drm = {'card3': {'bdf': '0000:23:00.0'}, 'renderD130': {'bdf': '0000:23:00.0'},
               'card2': {'bdf': '0000:47:00.0'}, 'renderD129': {'bdf': '0000:47:00.0'},
               'renderD131': {'bdf': '0000:27:00.0'}}
        return {'boot': 'b', 'kernel': {'faults': list(faults)}, 'drm': drm, 'memory': {'MemAvailable': 50 * 1024**3},
                'inventory': {'holders': [{'pid': p, 'node': n} for p, n in holders], 'errors': []},
                'holders': {str(p): {'start_ticks': 7} for p, _ in holders}, 'identity_races': [],
                'units': {'qwen38-27b-vision': {'MainPID': '9'}}}

    def monitor(self):
        m = S.Monitor(Path('/nonexistent'))
        m.baseline = self.snapshot([(9, 'renderD131')])
        m.target = {'0000:23:00.0': {'card3': 0, 'renderD130': 0}, '0000:47:00.0': {'card2': 0, 'renderD129': 0}}
        m.identities = [(100, 7), (101, 7)]
        return m

    def test_rules(self):
        m = self.monitor()
        m.validate(self.snapshot([(9, 'renderD131'), (100, 'renderD130'), (101, 'renderD129')]))
        self.assertEqual(m.contacts, [True, True])
        for bad in ([(55, 'renderD130')], [(100, 'renderD129')], [(100, 'renderD131')]):
            with self.assertRaises(RuntimeError, msg=str(bad)):
                self.monitor().validate(self.snapshot(bad))
        with self.assertRaises(RuntimeError):
            self.monitor().validate(self.snapshot([], faults=[{'message': 'xe GT0: Fault response', 'timestamp': '5'}]), holders=False)
        m = self.monitor()
        m.baseline = self.snapshot([], faults=[{'message': 'old', 'timestamp': '1'}])
        m.validate(self.snapshot([]))  # a vacuumed baseline fault is not a new fault
        m = self.monitor()
        m.validate(self.snapshot([(10, 'renderD131')]))  # vision change recorded only
        self.assertEqual(m.notes, [])  # MainPID unchanged in units view


class GenerateOrderTests(unittest.TestCase):
    def test_reset_then_generate_then_release_previous(self):
        events = []
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)

            class T:
                pass
            t = T()
            t.out = out
            t.check_alive = lambda: None

            def fake_reset(tr, dest):
                # native RESET dumps into the previous output directory, then switches
                prev = tr.request_output
                for r in ('rank0', 'rank1'):
                    (prev / r / 'state-2147483647').mkdir(parents=True, exist_ok=True)
                    (prev / r / 'state-2147483647' / 'x.bin').write_bytes(b'0' * 10)
                dest.mkdir()
                tr.request_output = dest
                events.append(('reset', dest.name))

            class NC:
                def __init__(self, *a):
                    pass

                def run(self, prompt, count, eos):
                    events.append(('run', len(prompt)))
                    return dict(tokens=[5, 248046], stats=dict(guesses=1, hits=1, misses=0))
            old = (S.A.reset, S.A.BASE.NativeController)
            S.A.reset, S.A.BASE.NativeController = fake_reset, NC
            try:
                e = S.Engine(out, out, type('M', (), {'check': lambda self: None})())
                e.t = t
                e.generate([1, 2], 4, 'a')
                e.generate([1, 2, 3], 4, 'b')
                self.assertTrue((out / 'req-000002').exists())
                self.assertFalse((out / 'rank0/state-2147483647').exists())  # released after request 2 ran
                e.generate([1], 4, 'c')
                self.assertFalse((out / 'req-000002').exists())
                self.assertTrue((out / 'req-000003').exists())
            finally:
                S.A.reset, S.A.BASE.NativeController = old
        self.assertEqual(events, [('run', 2), ('reset', 'req-000002'), ('run', 3), ('reset', 'req-000003'), ('run', 1)])


class StreamTailTests(unittest.TestCase):
    def test_tail_confirmed_tokens_through_check(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            (out / 'rank0').mkdir()

            class T:
                pass
            t = T()
            t.out = out
            t.seq = [4, 4]
            t.plan = {'service_flags': ['--reset-dump', 'none', '--finish-dump', 'none', '--token-stream', 'jsonl']}
            t.check_alive = lambda: None
            t.check = lambda: None
            ids = [11, 22, 248046]

            class NC:
                def __init__(self, tr, *a):
                    self.t = tr

                def run(self, prompt, count, eos):
                    f = open(out / 'rank0/confirmed-tokens.jsonl', 'w')
                    f.write(json.dumps(dict(type='begin', schema='sc117.confirmed-tokens.v1', request_sequence=5, limit=count, vocab=248320)) + '\n')
                    f.flush()
                    rows = []
                    for i, tok in enumerate(ids, 1):
                        f.write(json.dumps(dict(type='token', index=i, token_id=tok, target_completed_monotonic=float(i))) + '\n')
                        f.write('{"type":"tok') if i == 1 else None  # torn line must be held back
                        f.flush()
                        self.t.check()
                        if i == 1:
                            f.write('en_partial_ignored"}') if False else None
                        rows.append(dict(generated_index=i, token_id=tok, completed_monotonic=float(i)))
                    return dict(tokens=ids, timing_rows=rows, stats=dict(guesses=0, hits=0, misses=0))
            old = S.A.BASE.NativeController
            S.A.BASE.NativeController = NC
            got = []
            try:
                e = S.Engine(out, out, type('M', (), {'check': lambda self: None})())
                e.t = t
                with self.assertRaises(S.SP.StreamError):  # the torn line is malformed once completed
                    e.generate([1], 8, 'x', on_token=got.append)
            finally:
                S.A.BASE.NativeController = old
            self.assertEqual(got[:1], [11])

    def test_tail_clean(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            (out / 'rank0').mkdir()

            class T:
                pass
            t = T()
            t.out = out
            t.seq = [0, 0]
            t.plan = {'service_flags': ['--token-stream', 'jsonl']}
            t.check_alive = lambda: None
            t.check = lambda: None
            ids = [11, 22, 248046]

            class NC:
                def __init__(self, tr, *a):
                    self.t = tr

                def run(self, prompt, count, eos):
                    f = open(out / 'rank0/confirmed-tokens.jsonl', 'w')
                    f.write(json.dumps(dict(type='begin', schema='sc117.confirmed-tokens.v1', request_sequence=1, limit=count, vocab=248320)) + '\n')
                    rows = []
                    for i, tok in enumerate(ids, 1):
                        line = json.dumps(dict(type='token', index=i, token_id=tok, target_completed_monotonic=float(i))) + '\n'
                        f.write(line[:10]); f.flush(); self.t.check()  # partial line held back
                        f.write(line[10:]); f.flush(); self.t.check()
                        seen_now.append(len(got))
                        rows.append(dict(generated_index=i, token_id=tok, completed_monotonic=float(i)))
                    f.write(json.dumps(dict(type='end', count=3)) + '\n'); f.close()
                    return dict(tokens=ids, timing_rows=rows, stats=dict(guesses=2, hits=2, misses=0))
            old = S.A.BASE.NativeController
            S.A.BASE.NativeController = NC
            got, seen_now = [], []
            try:
                e = S.Engine(out, out, type('M', (), {'check': lambda self: None})())
                e.t = t
                tokens, summary = e.generate([1], 8, 'x', on_token=got.append)
            finally:
                S.A.BASE.NativeController = old
            self.assertEqual(got, ids)
            self.assertEqual(seen_now, [1, 2, 3])  # delivered during generation, token by token
            self.assertTrue(summary['streamed'])


if __name__ == '__main__':
    unittest.main()
