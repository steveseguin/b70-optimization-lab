#!/usr/bin/env python3
"""CPU-only tests for packet 93. No XPU, no ComfyUI server, no GPU call.

1. Window selection: smallest admitted bucket >= the real token count, else 1024.
2. Layout: for every real length 1..1024 and every bucket that holds it, the window
   is the tail of the padded row, its position ids are the real tokens' positions
   in the 1024 layout, and its attention mask equals the tail of the 1024 mask;
   the mask rule mirrors comfy/sd1_clip.py (tripwire). The stack wrapper injects
   1024-W..1023 only on a windowed thread and passes everything through otherwise.
3. Qualification logic: one determinism mismatch, a capture-proof failure, a
   wrong capture count or a relative difference above 1e-3 rejects; differing
   oracle passes reject.
4. The probe orchestration end to end with fakes on the real ltx_pipeline
   workers: two distinct workers run one after the other, sliding layers are at W
   only while capturing, a pass captures nothing, a pass result admits; a
   non-deterministic worker rejects, releases the window graphs and leaves the
   window refused.
5. Lean reuse guard: computed once per clip and reused only for bitwise-equal
   input (-0.0 vs 0.0 recomputes), never across clips or threads, passthrough with
   lean off or no context; the context sentry hashes the first forward per stage.
6. Fail-closed before the probe: a 'pipeline-window' request is refused with a
   receipt, submits nothing and does not latch; window.encode refuses too.
7. Control path unchanged with every switch off: the 'pipeline' tag is the text's
   sha256, the encode is the native CLIPTextEncode call, the pre-93 queue lookup
   is unchanged, the memo is installed only by a lean request.
"""
import hashlib
import json
import os
import sys
import tempfile
import threading
import time
import types
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import torch  # noqa: E402  (CPU only; nothing here touches torch.xpu)

import ltx_text_window as window  # noqa: E402
import ltx_lean_conditioning as lean  # noqa: E402

PACKET_SRC = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-decode-91b/source')
results = []


def case(name, fn):
    try:
        fn()
        results.append((name, True, ''))
    except Exception as error:  # noqa: BLE001
        import traceback
        results.append((name, False, repr(error) + ' ' + ' | '.join(traceback.format_exc().splitlines()[-4:])))


def raises(fn, text=None):
    try:
        fn()
    except Exception as error:  # noqa: BLE001
        assert text is None or text in str(error), (text, str(error))
        return
    raise AssertionError('expected a refusal')


# --- 1. selection -------------------------------------------------------------
def selection_case():
    allb = window.BUCKETS
    expect = {1: 64, 30: 64, 56: 64, 64: 64, 65: 128, 128: 128, 129: 256, 256: 256, 257: 512, 512: 512,
              513: 1024, 1000: 1024, 1024: 1024, 5000: 1024}
    for n, w in expect.items():
        assert window.select_window(n, allb) == w, (n, window.select_window(n, allb))
    assert window.select_window(30, (128, 256)) == 128
    assert window.select_window(300, (64, 128)) == 1024          # nothing admitted holds it: certified path
    assert window.select_window(30, ()) == 1024
    raises(lambda: window.select_window(0, allb))
    raises(lambda: window.select_window(10, (100,)))


case('selection: smallest admitted bucket >= length, fallback 1024', selection_case)


# --- 2. layout ------------------------------------------------------------------
def layout_case():
    import random
    rng = random.Random(93)
    for n in range(1, 1025):
        real = [2] + [rng.randrange(3, 262000) for _ in range(n - 1)]
        full = [(0, 1.0)] * (1024 - n) + [(t, 1.0) for t in real]
        assert len(full) == 1024 and window.real_token_count(full) == n
        full_tokens = [t for t, _ in full]
        full_mask = window.attention_mask_rule(full_tokens)
        assert sum(full_mask) == n and full_mask[-n:] == [1] * n
        real_positions = list(range(1024 - n, 1024))
        for w in window.BUCKETS:
            if w == 1024:
                continue
            if w < n:
                raises(lambda: window.window_row(full, w), 'drop real tokens')
                continue
            row = window.window_row(full, w)
            assert row == full[-w:]
            pos = window.window_positions(w)
            assert pos == list(range(1024 - w, 1024)) and len(pos) == w
            assert pos[-n:] == real_positions, (n, w)
            wmask = window.attention_mask_rule([t for t, _ in row])
            assert wmask == full_mask[-w:], (n, w)
            assert window.real_token_count(row) == n
    # an embedded pad token after the prompt starts (eos rule) is kept identical too
    full = [0] * 1000 + [2, 7, 9, 0, 5] + [8] * 19
    assert window.attention_mask_rule(full[-64:]) == window.attention_mask_rule(full)[-64:]
    src = (PACKET_SRC / 'comfy/sd1_clip.py').read_text()
    for line in ('if index == 0 and token == pad_token:', 'if eos or (left_pad and token == pad_token):',
                 'if not eos and token == cmp_token and not left_pad:', 'cmp_token = pad_token'):
        assert line in src, 'sd1_clip mask rule moved: ' + line
    lt = (PACKET_SRC / 'comfy/text_encoders/lt.py').read_text()
    assert 'min_length=1024, pad_left=True' in lt and "out = out[:, :, -torch.sum(extra[\"attention_mask\"]).item():]" in lt


case('layout: tail window, positions 1024-W..1023 and mask equal the padded layout (1..1024)', layout_case)


def wrapper_case():
    class Stack(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.seen = []

        def compute_freqs_cis(self):
            pass

        def forward(self, x, attention_mask=None, embeds=None, position_ids=None, **kw):
            self.seen.append(position_ids)
            return x

    s = Stack()
    window.install_stack_wrapper(s)
    window.install_stack_wrapper(s)          # idempotent
    x = torch.zeros(1, 1024, 4)
    assert s(x) is x and s.seen[-1] is None   # no window on this thread: untouched
    window._tls.window = 64
    try:
        s(torch.zeros(1, 64, 4))
        assert torch.equal(s.seen[-1], torch.arange(960, 1024).unsqueeze(0))
        raises(lambda: s(torch.zeros(1, 128, 4)), 'length differs')
        out = []
        t = threading.Thread(target=lambda: out.append(s(torch.zeros(1, 1024, 4)) is not None))
        t.start(); t.join()
        assert s.seen[-1] is None, 'another thread saw the window'
    finally:
        window._tls.window = None


case('stack wrapper: positions only on the windowed thread, passthrough otherwise', wrapper_case)


# --- 3. qualification logic -------------------------------------------------------
def judge_case():
    det = {'p%d' % i: ['a%d' % i] * 4 for i in range(5)}
    cap = {('w0', 64): {'captured': 48, 'error': None}, ('w1', 64): {'captured': 48, 'error': None}}
    close = {'p%d' % i: {'rel': 1e-5} for i in range(5)}
    assert window.judge_probe(det, cap, close) == (True, 'window-qualified', [])
    bad = dict(det); bad['p3'] = ['a3', 'a3', 'a3', 'zz']
    assert window.judge_probe(bad, cap, close)[1] == 'window-not-deterministic'
    bad = dict(det); bad['p1'] = ['a1', 'a1', None, 'a1']
    assert window.judge_probe(bad, cap, close)[1] == 'window-not-deterministic'
    c2 = dict(cap); c2[('w1', 64)] = {'captured': None, 'error': 'graph replay differs from eager execution'}
    assert window.judge_probe(det, c2, close)[1] == 'window-capture-proof-failed'
    c3 = dict(cap); c3[('w0', 64)] = {'captured': 47, 'error': None}
    assert window.judge_probe(det, c3, close)[1] == 'window-capture-proof-failed'
    cl = dict(close); cl['p2'] = {'rel': 1.0001e-3}
    assert window.judge_probe(det, cap, cl)[1] == 'window-not-close'
    cl['p2'] = {'rel': 1e-3}
    assert window.judge_probe(det, cap, cl)[0] is True          # bound inclusive
    cl['p2'] = {'rel': float('nan')}
    assert window.judge_probe(det, cap, cl)[1] == 'window-not-close'
    assert window.judge_probe(det, cap, close, memory_ok=False)[1] == 'insufficient-memory'
    names = ('images', 'video_latent', 'audio_latent', 'waveform')
    p1 = {'f%d' % i: {k: '%s%d' % (k, i) for k in names} for i in range(10)}
    p2 = json.loads(json.dumps(p1))
    assert window.judge_oracle_passes(p1, p2) == (True, [])
    p2['f4']['waveform'] = 'other'
    assert window.judge_oracle_passes(p1, p2) == (False, ['f4/waveform'])
    p3 = {k: v for k, v in p1.items() if k != 'f9'}
    assert window.judge_oracle_passes(p1, p3)[0] is False
    a = torch.tensor([[1.0, -2.0, 4.0]]); b = a.clone(); b[0, 2] = 4.002
    r = window.relative_difference(a, b)
    assert abs(r['rel'] - 0.002 / 4.002) < 1e-7 and r['bitwise_equal'] is False
    assert window.relative_difference(a, a.clone())['bitwise_equal'] is True


case('qualification: determinism / capture proof / closeness / oracle-pass verdicts', judge_case)


# --- 4. probe orchestration with fakes --------------------------------------------
class FakeEntry:
    def __init__(self, rows):
        self.output = torch.zeros(1, rows, 1)


class FakeShadow:
    def __init__(self):
        self.entries_by_thread = {}


class FakeLayer:
    def __init__(self, sliding):
        self.sliding_attention = sliding


class FakeClip:
    """tokenize -> left-padded 1024 row; encode -> deterministic per (tokens, window)."""

    def __init__(self, layers, shadows, noisy_thread=None):
        self.layers, self.shadows, self.noisy_thread = layers, shadows, noisy_thread
        self.capture_sliding, self.pass_sliding = [], []
        self.noise = iter(range(1, 10 ** 6))

    def tokenize(self, text):
        n = min(1 + len(text.split()), 1500)
        real = [2] + [5 + (len(w) % 7) for w in text.split()][:n - 1]
        row = [(0, 1.0)] * max(0, 1024 - len(real)) + [(t, 1.0) for t in real]
        return {'gemma3_12b': [row]}

    def encode_from_tokens_scheduled(self, tokens):
        row = tokens['gemma3_12b'][0]
        rows = len(row)
        tid = threading.get_ident()
        n = window.real_token_count(row)
        if rows != 1024:
            new = 0
            for s in self.shadows:
                e = s.entries_by_thread.setdefault(tid, {})
                if rows not in e:
                    e[rows] = FakeEntry(rows)
                    new += 1
            sliding = {l.sliding_attention for l in self.layers if l.sliding_attention}
            (self.capture_sliding if new else self.pass_sliding).append((rows, sliding))
        base = torch.arange(n * 6, dtype=torch.float32).reshape(1, n, 6) + float(sum(t for t, _ in row))
        if rows != 1024:
            base = base + 1e-6 * rows          # 'rounding' differs from the 1024 encode
        if self.noisy_thread is not None and threading.current_thread().name == self.noisy_thread:
            base = base + 0.01 * next(self.noise)
        return [[base, {}]]


def fake_native_encode(clip, text, consume_observations=False, encode_fn=None):
    if encode_fn is None:
        encode_fn = lambda: (clip.encode_from_tokens_scheduled(clip.tokenize(text)),)
    out = encode_fn()
    assert isinstance(out, tuple) and len(out) == 1
    return out[0]


def setup_probe(noisy_thread=None):
    import ltx_pipeline as p
    p.clear()
    p.STAGE_WORKERS['encode'] = 2
    layers = [FakeLayer(1024 if (i % 6) != 5 else False) for i in range(48)]
    shadows = [FakeShadow() for _ in range(48)]
    clip = FakeClip(layers, shadows, noisy_thread)
    stack = types.SimpleNamespace()
    window._STATE.update(qualified=False, admitted=(), outcome='not-run', probe_run=None)
    window._graph_layers = lambda c: (stack, layers, shadows)
    window.install_stack_wrapper = lambda s: None
    window._memory = lambda: {d: {'free_gib': 9.0, 'reserved_gib': 20.0, 'allocated_gib': 18.0}
                              for d in window.ENCODER_CARDS}
    freed = []
    window._free_cached = lambda: freed.append(True)
    prompts = [('fixture-a', 'a small boat on calm water ' * 3), ('fixture-b', 'a bird turns its head'),
               ('synthetic-80w', ' '.join(['word'] * 80)), ('synthetic-600w', ' '.join(['word'] * 600))]
    return p, clip, layers, shadows, prompts, freed


def probe_pass_case():
    p, clip, layers, shadows, prompts, freed = setup_probe()
    report = window.run_probe(clip, prompts, fake_native_encode, p)
    assert report['passed'] is True and report['outcome'] == 'window-qualified', report.get('error') or report
    assert report['admitted'] == [64, 128] and window.qualified() and window.admitted() == (64, 128)
    assert len(set(report['workers'])) == 2 and all(w.startswith('ltx-encode') for w in report['workers'])
    assert all(row == {'captured': 48, 'error': None} for row in report['capture'].values()), report['capture']
    assert sorted(report['capture']) == ['w0/128', 'w0/64', 'w1/128', 'w1/64']
    # sliding layers at W only while capturing; at 1024 for the timed passes
    assert {(r, tuple(s)) for r, s in clip.capture_sliding} == {(64, (64,)), (128, (128,))}
    assert clip.pass_sliding and all(s == {1024} for _r, s in clip.pass_sliding)
    assert all(l.sliding_attention in (1024, False) for l in layers)
    rows = {r['prompt']: r for r in report['rows']}
    assert rows['synthetic-600w']['window'] == 1024 and rows['synthetic-600w']['bitwise_equal'] is True
    assert rows['fixture-a']['window'] == 64 and rows['fixture-a']['bitwise_equal'] is False
    assert all(r['rel'] <= 1e-3 for r in report['rows'])
    assert report['label'] == window.LABEL and not freed
    assert p.pending('encode') == []
    # 93b: a timed encode whose graphs are missing is refused BEFORE anything runs
    calls = []
    real = clip.encode_from_tokens_scheduled
    clip.encode_from_tokens_scheduled = lambda t: calls.append(1) or real(t)
    for s in shadows:
        s.entries_by_thread.clear()
    raises(lambda: window.encode(clip, 'a bird turns its head'), 'refused before execution')
    raises(lambda: window.encode(clip, ' '.join(['word'] * 600)), 'refused before execution')  # 1024 fallback
    assert calls == [], 'an uncaptured timed encode executed'
    raises(lambda: window.run_probe(clip, prompts, fake_native_encode, p), 'once per server')


case('probe: two workers in turn, W only while capturing, passes replay, qualifies', probe_pass_case)


def probe_fail_case():
    p, clip, layers, shadows, prompts, freed = setup_probe(noisy_thread='ltx-encode-1')
    report = window.run_probe(clip, prompts, fake_native_encode, p)
    assert report['passed'] is False and report['outcome'] == 'window-not-deterministic', report
    assert not window.qualified() and window.admitted() == ()
    assert report['released_graphs'] > 0 and freed
    assert all(int(e.output.shape[1]) == 1024 for s in shadows for d in s.entries_by_thread.values()
               for e in d.values())
    assert all(l.sliding_attention in (1024, False) for l in layers)
    raises(lambda: window.encode(clip, 'a bird'), 'refused')


case('probe: a non-deterministic worker rejects, releases graphs, window stays refused', probe_fail_case)


def probe_capture_error_case():
    p, clip, layers, shadows, prompts, freed = setup_probe()
    real = clip.encode_from_tokens_scheduled

    def broken(tokens):
        if len(tokens['gemma3_12b'][0]) == 128:
            raise RuntimeError('Gemma layer 7 graph replay differs from eager execution; refuse graph mode')
        return real(tokens)

    clip.encode_from_tokens_scheduled = broken
    report = window.run_probe(clip, prompts, fake_native_encode, p)
    assert report['passed'] is False and report['outcome'] == 'window-capture-proof-failed', report
    assert not window.qualified() and freed and p.pending('encode') == []
    assert all(l.sliding_attention in (1024, False) for l in layers)


case('probe: a capture-proof failure rejects and releases (no latch)', probe_capture_error_case)


def timed_capture_case():
    p, clip, layers, shadows, prompts, freed = setup_probe()
    window._STATE.update(qualified=True, admitted=(64, 128), probe_run='done')
    me = threading.get_ident()
    other = me + 1
    # precheck on the prompt thread: every encode worker must hold the row count
    for s in shadows:
        s.entries_by_thread[me] = {1024: FakeEntry(1024), 64: FakeEntry(64)}
        s.entries_by_thread[other] = {1024: FakeEntry(1024)}
    raises(lambda: window.precheck(clip, 'a bird turns its head', [me, other]), 'refused before execution')
    assert window.precheck(clip, 'a bird turns its head', [me])['rows'] == 64
    assert window.precheck(clip, ' '.join(['w'] * 600), [me, other])['rows'] == 1024
    raises(lambda: window.precheck(clip, ' '.join(['w'] * 90), [me]), 'refused before execution')   # 128 missing
    raises(lambda: window.precheck(clip, 'a bird', []), 'No encode worker')
    del shadows[7].entries_by_thread[me][64]                     # one layer lacks the graph
    raises(lambda: window.precheck(clip, 'a bird turns its head', [me]), 'refused before execution')
    shadows[7].entries_by_thread[me][64] = FakeEntry(64)
    # the timed encode runs with the capture guard armed on this thread only
    seen = []
    real = clip.encode_from_tokens_scheduled
    clip.encode_from_tokens_scheduled = lambda t: seen.append(getattr(window._tls, 'no_capture', None)) or real(t)
    window.install_capture_guard = lambda cls=None: None
    out = window.encode(clip, 'a bird turns its head', tag='t1', index=5)
    assert seen == [True] and getattr(window._tls, 'no_capture', False) is False
    info = window.info_for(('t1', 5))
    assert info['window'] == 64 and info['captured_graphs'] == 0 and info['clip_index'] == 5
    assert isinstance(out, tuple) and len(out) == 1


case('93b: timed encodes are checked before execution (prompt thread and worker), guard armed', timed_capture_case)


def capture_guard_case():
    import importlib
    importlib.reload(window)            # undo the stubs of earlier cases for this module object
    calls = []

    class Layer:
        index = 3

        def _capture(self, kwargs, key):
            calls.append(key)
            return 'captured'

    assert window.install_capture_guard(Layer) is True and window.install_capture_guard(Layer) is False
    assert Layer()._capture({}, 'k1') == 'captured'
    window._tls.no_capture = True
    try:
        raises(lambda: Layer()._capture({}, 'k2'), 'never captures')
    finally:
        window._tls.no_capture = False
    assert calls == ['k1']


case('93b: capture guard refuses any capture while a timed encode runs', capture_guard_case)


def probe_timeout_case():
    p, clip, layers, shadows, prompts, freed = setup_probe()
    release = threading.Event()

    def hanging(clip_, text, consume_observations=False, encode_fn=None):
        release.wait(30)
        return fake_native_encode(clip_, text, consume_observations, encode_fn)

    saved = window.PROBE_TIMEOUT_S
    window.PROBE_TIMEOUT_S = 0.5
    try:
        report = window.run_probe(clip, prompts, hanging, p)
    finally:
        window.PROBE_TIMEOUT_S = saved
        release.set()
    assert report['passed'] is False and report['outcome'] == 'error' and report.get('timed_out'), report
    assert 'did not finish' in report['error'] and not window.qualified()
    assert 'released_graphs' not in report and not freed, 'released while a worker may still run'
    deadline = time.time() + 20
    while p.busy() and time.time() < deadline:
        time.sleep(0.1)
    assert p.busy() == 0, 'stopped workers did not wind down'
    p.clear()


case('93b: a hung probe worker times out cleanly; window refused, graphs not released under it', probe_timeout_case)


# --- 5. lean reuse guard and sentry ----------------------------------------------
class FakeDiffusion:
    def __init__(self):
        self.calls = 0
        self.forwards = 0

    def preprocess_text_embeds(self, context, unprocessed=False):
        self.calls += 1
        return torch.cat([context * 2.0, context + 1.0], dim=-1)

    def forward(self, x, timestep, context=None, **kw):
        self.forwards += 1
        return x


def lean_case():
    m = FakeDiffusion()
    assert lean.install_memo(m) is True and lean.install_memo(m) is False
    c = torch.randn(1, 5, 4, dtype=torch.bfloat16)
    m.preprocess_text_embeds(c, unprocessed=True); m.preprocess_text_embeds(c, unprocessed=True)
    assert m.calls == 2, 'no context: passthrough'
    lean.begin_clip(1, lean=False)
    m.preprocess_text_embeds(c, unprocessed=True); m.preprocess_text_embeds(c, unprocessed=True)
    s = lean.end_clip()
    assert m.calls == 4 and s['connector_passthrough'] == 2 and s['connector_computed'] == 0
    lean.begin_clip(2, lean=True)
    o1 = m.preprocess_text_embeds(c, unprocessed=True)
    o2 = m.preprocess_text_embeds(c.clone(), unprocessed=True)          # same bytes, other storage
    o3 = m.preprocess_text_embeds(c, unprocessed=True)
    assert m.calls == 5, m.calls
    assert lean.bitwise_equal(o1, o2) and lean.bitwise_equal(o1, o3) and o2.data_ptr() != o1.data_ptr()
    o2.add_(1)                                                        # a consumer mutating its copy
    assert lean.bitwise_equal(o1, m.preprocess_text_embeds(c, unprocessed=True)), 'stored output was aliased'
    flipped = c.clone(); flipped.view(torch.int16)[0, 0, 0] ^= 1
    m.preprocess_text_embeds(flipped, unprocessed=True)
    assert m.calls == 6, 'one changed bit must recompute'
    m.preprocess_text_embeds(c, unprocessed=False)
    assert m.calls == 7, 'a different unprocessed flag must recompute'
    z = torch.zeros(1, 2, 4); nz = -torch.zeros(1, 2, 4)
    m.preprocess_text_embeds(z, unprocessed=True); m.preprocess_text_embeds(nz, unprocessed=True)
    assert m.calls == 9, '-0.0 and 0.0 are different bytes'
    s = lean.end_clip()
    assert s['connector_computed'] == 5 and s['connector_reused'] == 3, s
    lean.begin_clip(3, lean=True)
    m.preprocess_text_embeds(c, unprocessed=True)
    assert m.calls == 10, 'never across clips'
    other = []

    def worker():
        lean.begin_clip(4, lean=True)
        m.preprocess_text_embeds(c, unprocessed=True)
        other.append(lean.end_clip())

    t = threading.Thread(target=worker); t.start(); t.join()
    assert m.calls == 11 and other[0]['connector_computed'] == 1, 'never across threads'
    lean.end_clip()
    raises(lambda: (lean.begin_clip(5, True), lean.begin_clip(6, True)), 'already open')
    lean.end_clip()


case('lean: once per clip, bitwise-equal reuse only, never across clips or threads', lean_case)


def sentry_case():
    m = FakeDiffusion()
    assert lean.install_sentry(m) is True
    x = torch.zeros(2)
    c1, c2, c3 = torch.ones(1, 3, 2), torch.full((1, 3, 2), 2.0), torch.full((1, 3, 2), 3.0)
    m.forward(x, 0, context=c1)                 # no context open: nothing recorded
    lean.begin_clip(7, lean=False)
    m.forward(x, 0, context=c1)                 # before a stage is set: nothing recorded
    lean.set_stage('a')
    m.forward(x, 0, context=c2); m.forward(x, 1, context=c3)
    lean.set_stage('b')
    m.forward(x, 0, context=c3)
    s = lean.end_clip()
    assert s['stage_a_context_sha256'] == lean.tensor_sha256(c2) != lean.tensor_sha256(c3)
    assert s['stage_b_context_sha256'] == lean.tensor_sha256(c3)
    assert s['forwards_per_stage'] == {'a': 2, 'b': 1} and m.forwards == 5
    assert lean.tensor_sha256(c2) != lean.tensor_sha256(c2.to(torch.bfloat16))


case('sentry: sha256 of the first forward context per stage, read-only passthrough', sentry_case)


# --- 6/7. text node: fail-closed and control path unchanged -------------------------
def import_text_node():
    if 'encoder_diagnostics' not in sys.modules:
        stub = types.ModuleType('encoder_diagnostics')
        stub._context = lambda: (_ for _ in ()).throw(RuntimeError('stub context'))
        sys.modules['encoder_diagnostics'] = stub
    import pipeline_node as node
    return node


def text_node_case():
    node = import_text_node()
    import ltx_pipeline as p
    p.clear()
    window._STATE.update(qualified=False, admitted=(), outcome='not-run', probe_run=None)
    with tempfile.TemporaryDirectory() as tmp:
        run = Path(tmp)
        identity = {'model_verification_sha256': node.MODEL_SHA256, 'server_identity_sha256': 'x' * 64}
        os.environ['LTX_ENCODER_IDENTITY_SHA256'] = 'x' * 64
        shas = {n: hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()
                for n, m in (('ltx_pipeline.py', p), ('ltx_text_window.py', window), ('pipeline_node.py', node))}
        (run / 'server-identity.json').write_text(json.dumps({'extension_sha256s': shas}))
        node._context = lambda: (run, identity)
        torch.use_deterministic_algorithms(True)
        try:
            try:
                node.LTXPipelineTextEncode().apply(object(), 'a bird', 'pipeline-window', 931200, 2, 'refuse-w')
                raise AssertionError('window ran without a probe')
            except node.WindowNotQualified as error:
                assert 'text-window probe' in str(error)
            r = json.loads((run / 'pipeline-refuse-w.json').read_text())
            assert r['passed'] is False and 'probe' in r['refused'] and r['window']['label'] == window.LABEL
            assert node._failed is False and p.pending('encode') == [], 'a refusal must not latch or submit'
            # 93b: qualified, but the workers lack this prompt's graphs -> refused, not latched
            layers = [FakeLayer(1024 if (i % 6) != 5 else False) for i in range(48)]
            shadows = [FakeShadow() for _ in range(48)]
            fake = FakeClip(layers, shadows)
            window._graph_layers = lambda c: (types.SimpleNamespace(), layers, shadows)
            window._STATE.update(qualified=True, admitted=(64,), probe_run='done')
            try:
                node.LTXPipelineTextEncode().apply(fake, 'a bird', 'pipeline-window', 931250, 2, 'refuse-g')
                raise AssertionError('window ran without captured graphs')
            except node.WindowNotQualified as error:
                assert 'encode worker' in str(error) or 'refused before execution' in str(error), str(error)
            r = json.loads((run / 'pipeline-refuse-g.json').read_text())
            assert r['passed'] is False and r['refused'] and node._failed is False and p.pending('encode') == []
            window._STATE.update(qualified=False, admitted=(), probe_run=None)
            # an unknown mode still latches, as before
            try:
                node.LTXPipelineTextEncode().apply(object(), 'a bird', 'bogus', 931300, 2, 'latch-x')
            except RuntimeError:
                pass
            assert node._failed is True
        finally:
            node._failed = False
            os.environ.pop('LTX_ENCODER_IDENTITY_SHA256', None)
            p.clear()


case('fail-closed: pipeline-window refused before the probe (receipt, no submit, no latch)', text_node_case)


def control_path_case():
    node = import_text_node()
    text = 'A clear blue glass marble rolls slowly across a light wooden tabletop.'
    assert node._job_tag('pipeline', text) == hashlib.sha256(text.encode()).hexdigest() == node._text_sha256(text)
    assert node._job_tag('pipeline-window', text) != node._job_tag('pipeline', text)
    assert node._encode_fn(object(), text, 'pipeline', 't') is None
    assert node.TEXT_MODES == ('original', 'pipeline', 'pipeline-window')
    calls = []
    fake_nodes = types.ModuleType('nodes')

    class CLIPTextEncode:
        def encode(self, clip, t):
            calls.append((clip, t))
            return ([['cond', {}]],)

    fake_nodes.CLIPTextEncode = CLIPTextEncode
    stubs = {'nodes': fake_nodes, 'ltx_graph_capture': types.ModuleType('ltx_graph_capture'),
             'ltx_graph_text_encoder': types.ModuleType('ltx_graph_text_encoder')}
    saved = {k: sys.modules.get(k) for k in stubs}
    sys.modules.update(stubs)
    try:
        clip = object()
        out = node.native_encode(clip, text)          # prompt thread: no worker stream setup
        assert out == [['cond', {}]] and calls == [(clip, text)], 'native call changed'
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    # queue lookups: the pre-93 interface returns only 'pipeline' texts
    queued = []
    fake_server = types.ModuleType('server')
    fake_server.PromptServer = types.SimpleNamespace(instance=types.SimpleNamespace(
        prompt_queue=types.SimpleNamespace(get_current_queue_volatile=lambda: ([], queued))))
    sys.modules['server'] = fake_server
    try:
        queued[:] = [(0, 'id', {'364': {'class_type': 'LTXPipelineTextEncode',
                                        'inputs': {'mode': 'pipeline', 'clip_index': 5, 'text': 'x'}}})]
        assert node._queued_text(5) == 'x' and node._queued_request(5) == ('x', 'pipeline')
        queued[:] = [(0, 'id', {'364': {'class_type': 'LTXPipelineTextEncode',
                                        'inputs': {'mode': 'pipeline-window', 'clip_index': 5, 'text': 'x'}}})]
        assert node._queued_text(5) is None and node._queued_request(5) == ('x', 'pipeline-window')
        assert node._queued_request(6) is None
    finally:
        sys.modules.pop('server', None)
    sampler = (HERE / 'pipeline_sampler_node.py').read_text()
    i_lean = sampler.index("if mode == 'pipeline-lean':\n                    report['lean'] = {'memo_installed_now': lean.install_memo(")
    assert sampler.count('lean.install_memo(') == 1 and i_lean > 0, 'memo installed outside a lean request'
    assert "SAMPLER_MODES = pipeline.MODES + ('pipeline-lean',)" in sampler
    assert "lean_mode = mode == 'pipeline-lean'" in sampler
    tnode = (HERE / 'pipeline_node.py').read_text()
    assert tnode.count('window.encode(') == 1 and "if mode == 'pipeline-window':\n        return lambda: window.encode(" in tnode
    import ltx_pipeline as p
    assert p.MODES == ('original', 'pipeline'), 'ltx_pipeline modes changed'


case('control path unchanged with every switch off', control_path_case)

for name, ok, err in results:
    print(f'{"ok " if ok else "BAD"} {name}{"" if ok else "  " + err}')
print('ALL CASES AS EXPECTED:', all(ok for _, ok, _ in results))
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
