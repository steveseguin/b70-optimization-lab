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
        fixture = json.loads((S.LANE / 'operating/first-model-prompt.json').read_text())
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
        bad = [{}, {'messages': []}, {'messages': [{'role': 'user', 'content': 'x', 'tool_calls': [{'function': {'name': 'f'}}]}]},
               {'messages': [{'role': 'user', 'content': 'x'}], 'tools': [{'type': 'function', 'function': {}}]},
               {'messages': [{'role': 'user', 'content': 'x'}], 'tool_choice': 'required'},
               {'messages': [{'role': 'user', 'content': [{'type': 'image_url', 'image_url': {}}]}]},
               {'messages': [{'role': 'user', 'content': 'x'}], 'n': 2},
               {'messages': [{'role': 'user', 'content': 'x'}], 'max_tokens': 0},
               {'messages': [{'role': 'user', 'content': 'x'}], 'tools': [{'type': 'function'}]},
               {'messages': [{'role': 'user', 'content': 'word ' * (C.CONTEXT + 1000)}]}]
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
                       'max_tokens': float(C.CONTEXT + 1000), 'n': None}, CHAT)
        self.assertEqual(req['max_new'], C.CONTEXT - len(req['prompt_ids']))
        self.assertTrue(CHAT.tok.decode(req['prompt_ids'], skip_special_tokens=False).startswith('<|im_start|>system\nBe brief.'))

    def test_sampling_parameters_reported_as_ignored(self):
        req = C.parse({'messages': [{'role': 'user', 'content': 'x'}], 'temperature': 0.7, 'top_p': 1}, CHAT)
        self.assertEqual(req['ignored_sampling'], ['temperature'])



TOOLS = [{'type': 'function', 'function': {'name': 'recall', 'description': 'Search the archive for <old> text.',
          'parameters': {'type': 'object', 'properties': {'query': {'type': 'string'}, 'limit': {'type': 'integer'}},
                         'required': ['query']}}}]


class ToolTests(unittest.TestCase):
    def test_tools_render_like_hugging_face_tojson(self):
        req = C.parse({'messages': [{'role': 'user', 'content': 'Find it'}], 'tools': TOOLS}, CHAT)
        text = CHAT.tok.decode(req['prompt_ids'], skip_special_tokens=False)
        self.assertIn('<tools>\n' + json.dumps(TOOLS[0], ensure_ascii=False) + '\n</tools>', text)
        self.assertNotIn('\\u003c', text)
        self.assertTrue(req['parse_tool_calls'])
        plain = C.parse({'messages': [{'role': 'user', 'content': 'Find it'}]}, CHAT)
        self.assertFalse(plain['parse_tool_calls'])
        self.assertNotIn('<tools>', CHAT.tok.decode(plain['prompt_ids'], skip_special_tokens=False))

    def test_history_with_calls_and_results(self):
        msgs = [{'role': 'user', 'content': 'Find it'},
                {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'call_1', 'type': 'function',
                 'function': {'name': 'recall', 'arguments': '{"query": "blue sky", "limit": 3}'}}]},
                {'role': 'tool', 'tool_call_id': 'call_1', 'content': 'Rayleigh scattering.'}]
        req = C.parse({'messages': msgs, 'tools': TOOLS}, CHAT)
        text = CHAT.tok.decode(req['prompt_ids'], skip_special_tokens=False)
        self.assertIn('<tool_call>\n<function=recall>\n<parameter=query>\nblue sky\n</parameter>\n'
                      '<parameter=limit>\n3\n</parameter>\n</function>\n</tool_call><|im_end|>', text)
        self.assertIn('<|im_start|>user\n<tool_response>\nRayleigh scattering.\n</tool_response><|im_end|>', text)
        with self.assertRaises(C.RequestError):
            bad = [dict(msgs[1], tool_calls=[{'function': {'name': 'recall', 'arguments': '{not json'}}])]
            C.parse({'messages': [msgs[0]] + bad, 'tools': TOOLS}, CHAT)

    def test_call_parsed_with_schema_types(self):
        req = C.parse({'messages': [{'role': 'user', 'content': 'Find it'}], 'tools': TOOLS}, CHAT)
        out = 'Let me look.\n\n<tool_call>\n<function=recall>\n<parameter=query>\n42\n</parameter>\n' \
              '<parameter=limit>\n3\n</parameter>\n</function>\n</tool_call>'
        tokens = CHAT.encode(out) + [C.EOS[1]]
        full = C.completion(req, tokens, {}, CHAT)
        choice = full['choices'][0]
        self.assertEqual(choice['finish_reason'], 'tool_calls')
        self.assertEqual(choice['message']['content'], 'Let me look.')
        call = choice['message']['tool_calls'][0]
        self.assertEqual(call['function']['name'], 'recall')
        self.assertEqual(json.loads(call['function']['arguments']), {'query': '42', 'limit': 3})
        chunks = list(C.chunks(full))
        self.assertEqual(chunks[0]['choices'][0]['delta']['tool_calls'][0]['index'], 0)
        self.assertEqual(chunks[-1]['choices'][0]['finish_reason'], 'tool_calls')

    def test_tool_choice_none_keeps_text_and_prompt(self):
        auto = C.parse({'messages': [{'role': 'user', 'content': 'Find it'}], 'tools': TOOLS}, CHAT)
        none = C.parse({'messages': [{'role': 'user', 'content': 'Find it'}], 'tools': TOOLS, 'tool_choice': 'none'}, CHAT)
        self.assertEqual(auto['prompt_ids'], none['prompt_ids'])  # same prefix either way (prefix reuse)
        out = '<tool_call>\n<function=recall>\n<parameter=query>\nx\n</parameter>\n</function>\n</tool_call>'
        full = C.completion(none, CHAT.encode(out) + [C.EOS[1]], {}, CHAT)
        self.assertEqual(full['choices'][0]['message']['content'], out)
        self.assertNotIn('tool_calls', full['choices'][0]['message'])

    def test_thinking_history_and_effort(self):
        hist = [{'role': 'user', 'content': 'Q'}, {'role': 'assistant', 'content': 'A', 'reasoning_content': 'think it over'},
                {'role': 'user', 'content': 'Q2'}]
        on = C.parse({'messages': hist, 'tools': TOOLS, 'chat_template_kwargs': {'enable_thinking': True}}, CHAT)
        text = CHAT.tok.decode(on['prompt_ids'], skip_special_tokens=False)
        self.assertIn('<|im_start|>assistant\n<think>\nthink it over\n</think>\n\nA<|im_end|>', text)
        self.assertIn('Reasoning effort is set to xhigh', text)  # template default with thinking on
        med = C.parse({'messages': hist, 'tools': TOOLS, 'reasoning_effort': 'medium',
                       'chat_template_kwargs': {'enable_thinking': True}}, CHAT)
        off = C.parse({'messages': hist, 'tools': TOOLS, 'reasoning_effort': 'medium'}, CHAT)
        tm = CHAT.tok.decode(med['prompt_ids'], skip_special_tokens=False)
        to = CHAT.tok.decode(off['prompt_ids'], skip_special_tokens=False)
        self.assertNotIn('Reasoning effort', tm)
        cut = '<|im_start|>assistant\n<think>\n'
        self.assertEqual(tm[:tm.rindex(cut)], to[:to.rindex(cut)])  # same opening and history; only the generation prompt differs
        with self.assertRaises(C.RequestError):
            C.parse({'messages': hist, 'reasoning_effort': 'max'}, CHAT)

    def test_streamer_holds_call_markup(self):
        req = C.parse({'messages': [{'role': 'user', 'content': 'Find it'}], 'tools': TOOLS, 'stream': True}, CHAT)
        out = 'Checking.<tool_call>\n<function=recall>\n<parameter=query>\nsky\n</parameter>\n</function>\n</tool_call>'
        ids = CHAT.encode(out) + [C.EOS[1]]
        st = C.Streamer(req, CHAT)
        streamed = [d for t in ids for d in st.feed(t)]
        self.assertEqual(streamed, [])
        tail, finish = st.finish(ids)
        self.assertEqual(finish, 'tool_calls')
        self.assertEqual(dict(tail)['content'], 'Checking.')
        self.assertEqual(json.loads(dict(tail)['tool_calls'][0]['function']['arguments']), {'query': 'sky'})
        self.assertFalse(st.mismatch)

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

    t = None
    prefill_rows = 0

    def activations(self):
        return 'bf16'

    reply = 'Blue light scatters more.'

    def generate(self, prompt, max_new, label, on_token=None, **service_options):  # continue_ok etc.
        time.sleep(self.delay)
        if self.fail:
            raise RuntimeError('rank failed')
        self.count += 1
        self.calls.append((prompt, max_new))
        out = CHAT.encode(self.reply) + [248046]
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

    def test_tool_call_over_http_and_stream(self):
        engine = FakeEngine()
        engine.reply = 'One moment.<tool_call>\n<function=recall>\n<parameter=query>\nsky\n</parameter>\n</function>\n</tool_call>'
        _, port = self.serve(engine)
        body = {'messages': [{'role': 'user', 'content': 'Find it'}], 'tools': TOOLS, 'max_tokens': 64}
        code, raw = self.post(port, body)
        self.assertEqual(code, 200, raw)
        msg = json.loads(raw)['choices'][0]
        self.assertEqual(msg['finish_reason'], 'tool_calls')
        self.assertEqual(msg['message']['content'], 'One moment.')
        self.assertEqual(json.loads(msg['message']['tool_calls'][0]['function']['arguments']), {'query': 'sky'})
        code, raw = self.post(port, dict(body, stream=True))
        self.assertEqual(code, 200)
        events = [json.loads(l[6:]) for l in raw.splitlines() if l.startswith('data: {')]
        deltas = [e['choices'][0]['delta'] for e in events if e['choices']]
        self.assertEqual(''.join(d.get('content') or '' for d in deltas), 'One moment.')
        calls = [c for d in deltas for c in d.get('tool_calls', [])]
        self.assertEqual([c['function']['name'] for c in calls], ['recall'])
        self.assertEqual(events[-1]['choices'][0]['finish_reason'], 'tool_calls')

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



# ---------------------------------------------------------------- session parking (SC117_SESSIONS=1), CPU only
import hashlib, shutil, struct
A6 = load(P / 'adapter6.py', 'sc117_lan_adapter6_test')


class FakeRanks:
    """Two ranks behind the adapter's transport API (start/io/call). Ops 11, 17, 18, 19 follow the engine's rules
    (session_checkpoint.hpp): STAGE writes a sealed directory, VERIFY only directly after RESET, APPLY only directly after
    VERIFY; refusals reply status 2 / error = op with a checkpoint-refused receipt. State = (position, payload)."""

    def __init__(self, root):
        self.out = root / 'evidence'
        for r in (0, 1):
            (self.out / f'rank{r}').mkdir(parents=True)
        self.request_output = self.out
        self.seq, self.pending, self.cmd = [0, 0], [False, False], [None, None]
        self.mapping = bytearray(A6.BASE.SHARED)
        self.plan = dict(binary_sha256='b' * 64, build_receipt_sha256='r' * 64, context=4096, service_flags=['--activations', 'f32'],
                         environment=[dict(PATH='/usr/bin', SYCL_CACHE_DIR='/x0'), dict(PATH='/usr/bin', SYCL_CACHE_DIR='/x1')])
        self.state = [dict(position=0, payload=b''), dict(position=0, payload=b'')]
        self.outdir = [self.out / 'rank0', self.out / 'rank1']
        self.last = [None, None]
        self.held = [None, None]
        self.refuse = set()   # (rank, op)
        self.log = []

    def check_alive(self):
        pass

    def live(self, tokens, pending):
        """The end-of-request state the native loop leaves: both ranks at N, reverse slot of N-1, reverse_ready = N."""
        n = len(tokens)
        for r in (0, 1):
            self.state[r] = dict(position=n, payload=f'rank{r}:{tokens}:{pending}'.encode())
        row = hashlib.sha256(str(tokens).encode()).digest() * 2048
        self.mapping[A6.SESSION_REVERSE:A6.SESSION_REVERSE + A6.SESSION_SLOT] = row
        struct.pack_into('<I', self.mapping, A6.SESSION_READY, n)
        self.pending_token = pending
        return row

    def start(self, rank, op, token=0, position=0, fixture=0, speculative=0):
        assert not self.pending[rank]
        self.seq[rank] += 1
        self.pending[rank] = True
        self.cmd[rank] = (op, token, position, fixture)

    def call(self, rank, op, token=0, position=0, fixture=0, speculative=0):
        self.start(rank, op, token, position, fixture)
        values = A6.BASE.REPLY.unpack(self.io(rank))
        self.pending[rank] = False
        assert values[0] == 0
        return dict(token=values[1])

    def reply(self, rank, status=0, error=0, token=0, nbytes=0):
        return A6.BASE.REPLY.pack(status, token, error, nbytes, self.seq[rank], rank, 0, 0, 1.0, 0, 0, 0)

    def io(self, rank, payload=None, timeout=None):
        op, token, position, fixture = self.cmd[rank]
        seq, st, prev = self.seq[rank], self.state[rank], self.last[rank]
        self.last[rank] = op
        self.log.append((rank, op))
        meta = self.out / f'rank{rank}' / f'checkpoint-{seq}.txt'
        def refuse(reason):
            (self.outdir[rank] / f'checkpoint-refused-{seq}.json').write_text(json.dumps(dict(reason=reason)))
            return self.reply(rank, 2, op)
        if op == 11:
            dest = Path((self.out / f'rank{rank}' / f'reset-{seq}.txt').read_text().split('\n')[0])
            dest.mkdir(parents=True)
            self.outdir[rank] = dest
            self.state[rank] = dict(position=0, payload=b'')
            self.held[rank] = None
            return self.reply(rank)
        if op == 16:  # redirect: only the request output directory moves; the state stays
            dest = Path((self.out / f'rank{rank}' / f'redirect-{seq}.txt').read_text().split('\n')[0])
            dest.mkdir(parents=True)
            self.outdir[rank] = dest
            return self.reply(rank)
        if (rank, op) in self.refuse:
            return refuse('injected')
        if op == 17:
            d, tag = meta.read_text().split('\n')[:2]
            if st['position'] != position:
                return refuse('position')
            d = Path(d)
            d.mkdir()
            (d / 'state.bundle').write_bytes(st['payload'])
            (d / 'state-seal.txt').write_text(hashlib.sha256(st['payload'] + tag.encode()).hexdigest() + f'\n{position}\n{tag}\n')
            (self.outdir[rank] / f'checkpoint-stage-{seq}.json').write_text(json.dumps(dict(draft_position=position - 1 if rank == 0 else -1)))
            return self.reply(rank, token=token, nbytes=len(st['payload']))
        if op == 18:
            if prev != 11:
                return refuse('must directly follow the request reset')
            d, tag = meta.read_text().split('\n')[:2]
            seal = (Path(d) / 'state-seal.txt').read_text().split('\n')
            data = (Path(d) / 'state.bundle').read_bytes()
            if seal[0] != hashlib.sha256(data + tag.encode()).hexdigest() or seal[2] != tag or int(seal[1]) != position:
                return refuse('seal/tag/position')
            self.held[rank] = dict(position=position, payload=data)
            return self.reply(rank, nbytes=len(data))
        if op == 19:
            if prev != 18 or self.held[rank] is None or self.held[rank]['position'] != position:
                return refuse('needs the directly preceding verify')
            self.state[rank], self.held[rank] = self.held[rank], None
            return self.reply(rank, nbytes=len(self.state[rank]['payload']))
        raise AssertionError(op)


class SessionAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root = self.tmp / 'sessions'
        self.root.mkdir(mode=0o700)
        self.t = FakeRanks(self.tmp)
        self.tokens = list(range(300))

    def park(self, tokens=None, pending=77):
        tokens = self.tokens if tokens is None else tokens
        row = self.t.live(tokens, pending)
        return A6.session_save(self.t, self.root, tokens, pending), row

    def test_save_publishes_manifest_last_and_binds_both_ranks(self):
        m, row = self.park()
        path = self.root / m['id']
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), sorted([m['id'], m['id'] + '.lock']))  # no staging left
        self.assertEqual(A6.session_inspect(path), m)
        self.assertEqual((m['position'], m['pending_token'], m['tokens']), (300, 77, self.tokens))
        self.assertEqual(m['reverse']['sha256'], hashlib.sha256(row).hexdigest())
        self.assertEqual(m['reverse']['ready'], 300)
        self.assertEqual(m['draft_position'], 299)
        for r in ('0', '1'):
            self.assertEqual(m['ranks'][r]['seal_sha256'], hashlib.sha256((path / f'rank{r}' / 'state-seal.txt').read_bytes()).hexdigest())
        self.assertEqual(m['identity'], A6.session_identity(self.t))
        self.assertEqual(self.t.cmd[1][3], 1)  # rank 1 STAGE checks its next_token against the pending token
        seq = list(self.t.seq)
        self.assertEqual(A6.session_save(self.t, self.root, self.tokens, 77), m)  # same state: no second STAGE
        self.assertEqual(self.t.seq, seq)

    def test_restore_is_reset_verify_apply_then_redirect_shared_map(self):
        m, row = self.park()
        self.t.live(list(range(10)), 5)  # another conversation is live now
        self.t.mapping[0:16] = b'x' * 16       # stale verification/mailbox bytes must not survive
        dest = self.t.out / 'req-000009'
        r = A6.session_restore(self.t, self.root / m['id'], dest)
        self.assertEqual((r['position'], r['pending_token'], r['tokens']), (300, 77, self.tokens))
        self.assertEqual(self.t.request_output, dest)
        for rank in (0, 1):
            self.assertEqual(self.t.state[rank], dict(position=300, payload=f'rank{rank}:{self.tokens}:77'.encode()))
        self.assertEqual(bytes(self.t.mapping[A6.SESSION_REVERSE:A6.SESSION_REVERSE + A6.SESSION_SLOT]), row)
        self.assertEqual(struct.unpack_from('<I', self.t.mapping, A6.SESSION_READY)[0], 300)
        rest = bytearray(self.t.mapping)
        rest[A6.SESSION_REVERSE:A6.SESSION_REVERSE + A6.SESSION_SLOT] = bytes(A6.SESSION_SLOT)
        rest[A6.SESSION_READY:A6.SESSION_READY + 4] = bytes(4)
        self.assertFalse(any(rest))
        ops = [op for _, op in self.t.log[-6:]]
        self.assertEqual(ops, [11, 11, 18, 18, 19, 19])

    def test_stage_refusal_leaves_nothing_and_live_state(self):
        self.t.refuse.add((1, 17))
        with self.assertRaises(A6.SessionRefused) as c:
            self.park()
        self.assertEqual(c.exception.engine, 'unchanged')
        self.assertEqual([p.name for p in self.root.iterdir() if not p.name.endswith('.lock')], [])
        self.assertEqual(self.t.state[0]['position'], 300)

    def test_verify_refusal_is_fresh_and_applies_nothing(self):
        m, _ = self.park()
        self.t.refuse.add((1, 18))
        with self.assertRaises(A6.SessionRefused) as c:
            A6.session_restore(self.t, self.root / m['id'], self.t.out / 'req-000002')
        self.assertEqual(c.exception.engine, 'fresh')
        self.assertNotIn(19, [op for _, op in self.t.log])
        self.assertEqual([s['position'] for s in self.t.state], [0, 0])

    def test_partial_apply_is_reported(self):
        m, _ = self.park()
        self.t.refuse.add((1, 19))
        with self.assertRaises(A6.SessionRefused) as c:
            A6.session_restore(self.t, self.root / m['id'], self.t.out / 'req-000002')
        self.assertEqual(c.exception.engine, 'partial')
        self.assertEqual([s['position'] for s in self.t.state], [300, 0])

    def test_identity_corruption_and_lock_refuse_before_any_command(self):
        m, _ = self.park()
        path = self.root / m['id']
        seq = list(self.t.seq)
        self.t.plan = dict(self.t.plan, binary_sha256='c' * 64)
        with self.assertRaises(A6.SessionRefused) as c:
            A6.session_restore(self.t, path, self.t.out / 'req-000002')
        self.assertEqual((c.exception.engine, self.t.seq), ('untouched', seq))
        self.t.plan = dict(self.t.plan, binary_sha256='b' * 64)
        with A6.SessionLock(self.root, m['id'], True):  # a save/delete holds it: restore and delete refuse, no wait
            with self.assertRaises(A6.SessionRefused):
                A6.session_restore(self.t, path, self.t.out / 'req-000002')
            self.assertFalse(A6.session_delete(path))
        with A6.SessionLock(self.root, m['id'], False):  # a restore holds it: save refuses
            with self.assertRaises(A6.SessionRefused) as c:
                A6.session_save(self.t, self.root, self.tokens, 78)
            self.assertEqual(c.exception.engine, 'unchanged')
            self.assertEqual(A6.session_inspect(path, lock=True)['id'], m['id'])  # shared + shared is fine
        self.assertEqual(self.t.seq, seq)
        raw = bytearray((path / 'reverse.bin').read_bytes())
        raw[5] ^= 1
        os.chmod(path / 'reverse.bin', 0o600)
        (path / 'reverse.bin').write_bytes(bytes(raw))
        with self.assertRaises(A6.SessionRefused):
            A6.session_inspect(path)
        self.assertEqual([x[2] is not None for x in A6.session_list(self.root)], [True])
        self.assertTrue(A6.session_delete(path))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_save_refuses_off_boundary(self):
        self.t.live(self.tokens, 77)
        struct.pack_into('<I', self.t.mapping, A6.SESSION_READY, 299)
        with self.assertRaises(A6.SessionRefused):
            A6.session_save(self.t, self.root, self.tokens, 77)


class SessionOps:
    """In-memory session store with the adapter's interface (policy tests)."""
    SessionRefused = A6.SessionRefused

    def __init__(self, size=lambda n: 1000 + n):
        self.saved, self.calls, self.size, self.refuse = {}, [], size, None

    @staticmethod
    def session_id(tokens):
        return A6.session_id(tokens)

    def session_identity(self, t):
        return {'engine': 1}

    def session_list(self, root):
        return [(root / sid, m, None) for sid, m in self.saved.items()]

    def session_save(self, t, root, tokens, pending):
        self.calls.append(('save', len(tokens)))
        getattr(self, 'events', []).append(('save', len(tokens)))
        sid = self.session_id(tokens)
        (root / sid).mkdir(exist_ok=True)
        m = dict(id=sid, tokens=list(tokens), pending_token=pending, identity={'engine': 1}, bytes=self.size(len(tokens)), position=len(tokens))
        self.saved[sid] = m
        return m

    def session_restore(self, t, path, destination, readback=False):
        self.calls.append(('restore', len(self.saved[path.name]['tokens'])))
        if self.refuse == 'untouched':
            raise A6.SessionRefused('session identity differs', 'untouched')
        destination.mkdir()
        t.request_output = destination
        if self.refuse:
            raise A6.SessionRefused('verify refused', self.refuse)
        m = self.saved[path.name]
        return dict(id=m['id'], position=m['position'], pending_token=m['pending_token'], tokens=m['tokens'], verify_ms=1.0, apply_ms=1.0)

    def session_delete(self, path):
        self.calls.append(('delete', len(self.saved.get(path.name, {}).get('tokens', []))))
        shutil.rmtree(path, ignore_errors=True)
        self.saved.pop(path.name, None)
        return True


class SessionPolicyTests(unittest.TestCase):
    """Engine.generate with sessions on: park on eviction, longest-prefix restore, budget, refusal fallbacks."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        out = self.tmp / 'evidence'
        out.mkdir()
        self.events = []
        events = self.events

        class T:
            pass
        t = T()
        t.out = out
        t.check_alive = lambda: None
        t.request_output = out
        t.seq = [0, 0]
        self.t = t

        def fake_reset(tr, dest):
            dest.mkdir()
            tr.request_output = dest
            events.append(('reset', dest.name))

        def fake_redirect(tr, dest):
            dest.mkdir()
            tr.request_output = dest
            events.append(('redirect', dest.name))
        reply = self.reply = [7, 8, 9]

        class NC:
            def __init__(self, tr, draft, overlap, dumps, prefill=None, start=0):
                self.start = start

            def run(self, prompt, count, eos):
                events.append(('run', len(prompt), self.start))
                return dict(tokens=list(reply), stats=dict(guesses=0, hits=0, misses=0))
        had = hasattr(S.A, 'NativeController')
        old = (S.A.reset, S.A.redirect if hasattr(S.A, 'redirect') else None, getattr(S.A, 'NativeController', None))
        S.A.reset, S.A.redirect, S.A.NativeController = fake_reset, fake_redirect, NC

        def restore():
            S.A.reset = old[0]
            if old[1] is None:
                del S.A.redirect
            else:
                S.A.redirect = old[1]
            if had:
                S.A.NativeController = old[2]
            else:
                del S.A.NativeController
        self.addCleanup(restore)
        self.ops = SessionOps()
        self.ops.events = events
        e = S.Engine(out, out, type('M', (), {'check': lambda self: None})())
        e.t = t
        e.continuation = True
        e.session_identity = {'engine': 1}
        root = self.tmp / 'sessions'
        e.sessions = S.Sessions(root, 10**9, self.ops, meminfo=lambda: 10**15, ram=False)
        e.sessions.prepare({'engine': 1})
        self.e = e
        self.A = list(range(1000, 1300))   # 300-token conversation
        self.B = list(range(2000, 2010))   # short other conversation

    def client(self, prompt):
        tokens, summary = self.e.generate(prompt, 3, 'client', continue_ok=True)
        return summary

    def test_park_on_eviction_then_restore_longest_prefix(self):
        self.client(self.A)                                   # request 1: fresh (first request, no reset)
        s2 = self.client(self.B)                              # request 2: evicts A -> parked before the RESET
        self.assertEqual(self.ops.calls, [('save', 302)])
        self.assertEqual(self.events[1:4], [('save', 302), ('reset', 'req-000002'), ('run', 10, 0)])  # parked before the RESET
        self.assertEqual(s2['session']['parked'], A6.session_id(self.A + [7, 8]))
        a2 = self.A + [7, 8, 9] + [1, 2]                      # A's next turn: does not continue the live state (B)
        s3 = self.client(a2)
        self.assertEqual(self.ops.calls[-1], ('restore', 302))  # B is short: not parked
        self.assertEqual(self.events[-1], ('run', 305, 302))
        self.assertEqual(s3['continued_from'], 302)
        req = dict(prompt_ids=a2, thinking=False, stop=[], parse_tool_calls=False, max_new=3)
        usage = C.completion(req, [7, 8, 9], s3, CHAT)['usage']
        self.assertEqual(usage['prompt_tokens_details']['cached_tokens'], 302)
        self.assertEqual(s3['session']['restored']['position'], 302)
        a3 = a2 + [7, 8, 9] + [3, 4]                          # live continuation: unchanged redirect path, no session ops
        calls = len(self.ops.calls)
        s4 = self.client(a3)
        self.assertEqual(self.events[-2][0], 'redirect')
        self.assertEqual((len(self.ops.calls), s4['continued_from'], 'session' in s4), (calls, 307, False))
        self.client(self.B)                                   # evicts the longer A state (a3 + 2 = 312 tokens) -> parked
        self.assertEqual(self.ops.calls[-1], ('save', 312))
        s6 = self.client(a3 + [7, 8, 9] + [5, 6])             # both parked prefixes (302, 312) match: the longest wins
        self.assertEqual(self.ops.calls[-1], ('restore', 312))
        self.assertEqual(s6['continued_from'], 312)

    def test_prefix_rule_short_and_gate_requests(self):
        self.client(self.A)
        self.client(self.B)
        self.client(self.A + [7, 8, 9])                       # only one token after the prefix: fresh read
        self.assertEqual(self.ops.calls[-1], ('save', 302))   # (the B state was too short to park)
        self.assertEqual(self.events[-1], ('run', 303, 0))
        self.client(self.A + [7, 8, 5, 1])                    # prompt[N] != pending token: fresh read
        self.assertEqual(self.events[-1][2], 0)
        calls = len(self.ops.calls)
        self.e.generate(self.A + [7, 8, 9, 1, 2], 3, 'gate', force_reset=True)  # gate requests never park/restore
        self.assertEqual(len(self.ops.calls), calls)

    def test_budget_evicts_least_recently_used(self):
        self.e.sessions.budget = 2 * S.SESSION_FIXED_BYTES + 2 * 400 * S.SESSION_TOKEN_BYTES
        self.ops.size = lambda n: S.SESSION_FIXED_BYTES + n * S.SESSION_TOKEN_BYTES
        convs = [list(range(k * 10000, k * 10000 + 300)) for k in (1, 2, 3)]
        for c in convs:
            self.client(c)
        self.client(self.B)                                   # parks conv 3; conv 1 (least recent) is evicted
        self.assertEqual([c for c in self.ops.calls if c[0] == 'save'], [('save', 302)] * 3)
        self.assertIn(('delete', 302), self.ops.calls)
        self.assertNotIn(A6.session_id(convs[0] + [7, 8]), self.e.sessions.index)
        self.assertEqual(len(self.e.sessions.index), 2)
        self.assertLessEqual(self.e.sessions.used_bytes(), self.e.sessions.budget)
        self.e.sessions.meminfo = lambda: S.MEM_ONGOING   # RAM store below the margin: parking is skipped, never fatal
        self.e.sessions.ram = True
        self.client(list(range(50000, 50300)))
        self.client(self.B)
        self.assertEqual(self.e.sessions.stats['park_skipped'], 1)

    def test_refusals_fall_back_to_a_fresh_read(self):
        a2 = self.A + [7, 8, 9] + [1, 2]
        for engine, resets in (('fresh', []), ('untouched', ['req-000003']), ('partial', ['req-000003-retry'])):
            with self.subTest(engine=engine):
                self.setUp()
                self.client(self.A)
                self.client(self.B)
                self.ops.refuse = engine
                before = len(self.events)
                s = self.client(a2)
                self.assertEqual(s['continued_from'], 0)
                self.assertEqual(s['session']['refused']['engine'], engine)
                self.assertEqual([x[1] for x in self.events[before:] if x[0] == 'reset'], resets)
                self.assertEqual(self.events[-1], ('run', 305, 0))
                self.assertEqual(self.e.sessions.index, {})  # a refused session is dropped
                self.assertFalse((self.t.out / 'req-000003').exists() and engine == 'partial')

    def test_reuse_false_reads_fresh_without_parking(self):
        self.client(self.A)
        self.e.generate(self.B, 3, 'client', continue_ok=False)  # sc117_reuse=false: no park, no restore
        self.assertEqual(self.ops.calls, [])
        req = C.parse({'messages': [{'role': 'user', 'content': 'x'}], 'sc117_reuse': False}, CHAT)
        self.assertFalse(req['reuse'])
        self.assertTrue(C.parse({'messages': [{'role': 'user', 'content': 'x'}]}, CHAT)['reuse'])
        with self.assertRaises(C.RequestError):
            C.parse({'messages': [{'role': 'user', 'content': 'x'}], 'sc117_reuse': 'no'}, CHAT)

    def test_sessions_are_off_by_default(self):
        self.assertFalse(S.SESSIONS)
        self.assertIsNone(S.Engine(self.tmp, self.tmp, None).sessions)

    def test_cached_tokens_over_http(self):
        engine = FakeEngine()
        engine.generate = lambda prompt, max_new, label, on_token=None, **kw: (CHAT.encode('ok') + [248046], dict(request=1, continued_from=300))
        state = S.State()
        state.phase = 'ready'
        state.fault = lambda e: None
        server = S.Server(('127.0.0.1', 0), S.make_handler(state, engine, CHAT, None))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        c = http.client.HTTPConnection('127.0.0.1', server.server_address[1], timeout=30)
        c.request('POST', '/v1/chat/completions', json.dumps({'messages': [{'role': 'user', 'content': 'x'}]}), {'Content-Type': 'application/json'})
        body = json.loads(c.getresponse().read())
        self.assertEqual(body['usage']['prompt_tokens_details']['cached_tokens'], 300)



class SessionIntegrationTests(unittest.TestCase):
    """Service policy + the real adapter6 session protocol over FakeRanks (files, manifest, locks, RESET metadata)."""

    def test_park_restore_continue_through_the_adapter(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        t = FakeRanks(tmp)
        seen = []

        class NC:
            def __init__(self, tr, draft, overlap, dumps, prefill=None, start=0):
                self.start = start

            def run(self, prompt, count, eos):
                if self.start:  # what the native continuation needs on entry
                    h = prompt[:self.start]
                    seen.append(([s['position'] for s in t.state], struct.unpack_from('<I', t.mapping, A6.SESSION_READY)[0],
                                 [s['payload'] for s in t.state] == [f'rank{r}:{h}:{prompt[self.start]}'.encode() for r in (0, 1)],
                                 bytes(t.mapping[A6.SESSION_REVERSE:A6.SESSION_REVERSE + 32]) == hashlib.sha256(str(h).encode()).digest()))
                tokens = [7, 8, 9]
                t.live(list(prompt) + tokens[:-1], tokens[-1])  # the end-of-request state of the native loop
                return dict(tokens=tokens, stats=dict(guesses=0, hits=0, misses=0))
        old = (S.A.reset, getattr(S.A, 'redirect', None), getattr(S.A, 'NativeController', None))
        S.A.reset, S.A.redirect, S.A.NativeController = A6.reset, A6.redirect, NC

        def restore():
            S.A.reset = old[0]
            for name, value in (('redirect', old[1]), ('NativeController', old[2])):
                if value is None:
                    delattr(S.A, name)
                else:
                    setattr(S.A, name, value)
        self.addCleanup(restore)
        e = S.Engine(tmp, tmp, type('M', (), {'check': lambda self: None})())
        e.t = t
        e.continuation = True
        e.session_identity = A6.session_identity(t)
        root = tmp / 'sessions'
        e.sessions = S.Sessions(root, 10**10, A6, meminfo=lambda: 10**15, ram=False)
        e.sessions.prepare(e.session_identity)
        conv_a, conv_b = list(range(1000, 1300)), list(range(2000, 2010))
        e.generate(conv_a, 3, 'client', continue_ok=True)
        _, s2 = e.generate(conv_b, 3, 'client', continue_ok=True)
        h = conv_a + [7, 8]
        self.assertEqual(s2['session']['parked'], A6.session_id(h))
        self.assertEqual(A6.session_inspect(root / A6.session_id(h))['tokens'], h)
        _, s3 = e.generate(h + [9, 1, 2], 3, 'client', continue_ok=True)
        self.assertEqual(s3['continued_from'], 302)
        self.assertEqual(seen, [([302, 302], 302, True, True)])
        _, s4 = e.generate(h + [9, 1, 2] + [7, 8, 9, 3, 4], 3, 'client', continue_ok=True)  # live continuation (redirect)
        self.assertEqual(s4['continued_from'], 307)
        self.assertNotIn('session', s4)
        # A second engine process (same identity) finds the parked session on disk.
        e2 = S.Sessions(root, 10**10, A6, meminfo=lambda: 10**15, ram=False)
        e2.prepare(e.session_identity)
        self.assertEqual(list(e2.index), [A6.session_id(h)])
        e2.prepare(dict(e.session_identity, binary_sha256='0' * 64))  # another engine: its sessions are purged
        self.assertEqual(e2.index, {})
        self.assertEqual(sorted(p.name for p in root.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
