"""Packet 93/93b: suffix-window text encoding. Changes output at rounding level; owner approved
2026-10-04 on two conditions (negligible finished-clip difference; new references, byte-identical
thereafter).

Every prompt is left-padded to 1024 tokens (comfy/text_encoders/lt.py:84-90)
and only the last N real rows are kept (lt.py:188); real prompts are 30-56
tokens. A window encode runs the Gemma stack on the last W positions of the
same padded sequence, with explicit absolute position ids 1024-W..1023 and the
sliding layers' window set to W during capture, so attention takes the same
expanded-KV path it takes at 1024. Padded keys get exactly zero attention
weight, so it is the same mathematics. It is NOT byte-identical to the
1024-token encode: this stack's GEMM kernels round differently for different
row counts (notes/2026-10-04-encoder-suffix-window-probe.md). The window
therefore has its own oracle, and every receipt carries LABEL.

Policy, fixed and recorded in every receipt: W is the smallest admitted bucket
in BUCKETS that holds the prompt's real token count (BOS included). 1024 is
the certified full-length encode, called exactly as the native node calls it.

Implementation (packet 93): the window runs through the SAME per-layer graph
stand-ins as the 1024 encode (ltx_graph_text_encoder.GraphedLayer, unchanged).
A window has a different argument signature, so each layer captures one more
graph per bucket per encode worker, with the lane's capture proof (replay
bit-equal to a fresh eager call of the layer, non-inert) and the lane's
per-(device, thread) pool. Those captures happen only inside the qualification
probe, with the pipeline idle and the two workers run one after the other;
the sliding layers' window attribute is set to W only for those captures and
is back at 1024 before the probe's timed passes. A replay does not read the
attribute.

Packet 93b: a timed encode never captures. Before any execution, the request
is checked (on the prompt thread, for every encode worker) and again on the
worker that runs it: every one of the 48 layers must already hold a graph for
the row count it will use (W, or 1024 on the fallback). Otherwise it is refused
before anything runs. As a backstop, a capture guard on GraphedLayer._capture
raises before capturing whenever a timed encode is running on that thread.

Nothing here runs unless a 'pipeline-window' request is admitted, and that
needs a passed probe on this server (`qualified()`).
"""
import gc
import hashlib
import threading
import time

FULL = 1024
BUCKETS = (64, 128, 256, 512, 1024)
LABEL = ('changes output at rounding level; owner approved 2026-10-04 on two conditions '
         '(negligible finished-clip difference; new references, byte-identical thereafter)')
POLICY = ('W = the smallest admitted bucket in (64, 128, 256, 512, 1024) holding the real token count '
          '(BOS included); W = 1024 is the certified full-length encode, called unchanged; position ids '
          '1024-W..1023; sliding layers captured with window W')
REL_BOUND = 1e-3
REL_DEFINITION = ('max |window - full| / max |full| over the conditioning tensor [1, N, 6144] '
                  '(normwise; an elementwise ratio is undefined where the full value is ~0)')
SLIDING_LAYERS = 40          # gemma4 12B: sliding_attention = [1024]*5 + [False], 48 layers
MIN_FREE_GIB = 3.0           # per encoder card before capturing a bucket
MIN_FREE_AFTER_GIB = 2.0     # per encoder card after the probe
ENCODER_CARDS = ('xpu:2', 'xpu:3')
PROBE_JOB_INDICES = (-930001, -930002)   # never a clip index (clip indices are >= 0)
BARRIER_TIMEOUT_S = 180.0

# Synthetic probe prompts, identical to scripts/probe-encoder-suffix-window.py.
WORDS = ('a slow pan across a quiet harbour at dawn while gulls circle above the masts and a fisherman coils wet rope '
         'beside stacked wooden crates as soft light spreads over rippling water and distant bells ring twice').split()
SYNTHETIC_WORDS = (1, 3, 6, 12, 20, 28, 40, 52, 58, 61, 63, 66, 80, 100, 118, 122, 126, 130, 160, 200, 240, 250,
                   256, 262, 300, 380, 440, 500, 508, 514)

PROBE_TIMEOUT_S = 1200.0     # server-side bound on the whole probe (both workers)
_STATE = {'qualified': False, 'admitted': (), 'outcome': 'not-run', 'probe_run': None}


class WindowNotCaptured(RuntimeError):
    """A timed encode whose signature has no captured graph: refused before execution."""


class CaptureRefused(RuntimeError):
    """Backstop: a capture attempted during a timed encode."""
_LOCK = threading.Lock()
_tls = threading.local()
_INFO = {}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def synthetic_prompts():
    return [('synthetic-%dw' % n, ' '.join(WORDS[i % len(WORDS)] for i in range(n)) + '.')
            for n in SYNTHETIC_WORDS]


# --- pure policy (CPU-tested) -------------------------------------------------
def select_window(n_real, admitted):
    """Smallest admitted bucket below FULL that holds n_real tokens, else FULL."""
    require(isinstance(n_real, int) and n_real >= 1, 'Real token count must be a positive int')
    for w in sorted(admitted):
        require(w in BUCKETS, 'Unknown bucket %r' % (w,))
        if w < FULL and w >= n_real:
            return w
    return FULL


def real_token_count(row, pad_token=0):
    """Positions after the leading pad run (the window must hold all of them)."""
    tokens = [t[0] if isinstance(t, (tuple, list)) else t for t in row]
    lead = 0
    while lead < len(tokens) and tokens[lead] == pad_token:
        lead += 1
    return len(tokens) - lead


def attention_mask_rule(tokens, pad_token=0):
    """Mirror of comfy/sd1_clip.py process_tokens' mask for a model with no end
    token (cmp_token == pad_token), as the Gemma encoder uses it."""
    mask, eos, left_pad = [], False, False
    for index, token in enumerate(tokens):
        if index == 0 and token == pad_token:
            left_pad = True
        if eos or (left_pad and token == pad_token):
            mask.append(0)
        else:
            mask.append(1)
            left_pad = False
        if not eos and token == pad_token and not left_pad:
            mask[-1] = 0
            eos = True
    return mask


def window_positions(w):
    require(w in BUCKETS, 'Unknown bucket %r' % (w,))
    return list(range(FULL - w, FULL))


def window_row(row, w):
    require(len(row) == FULL, 'A window is cut from the 1024-token padded layout only')
    require(w in BUCKETS and w < FULL, 'Window must be a bucket below 1024')
    require(real_token_count(row) <= w, 'Window would drop real tokens')
    return list(row[-w:])


def judge_probe(determinism, capture, closeness, memory_ok=True, bound=REL_BOUND):
    """Verdict of the qualification probe.

    determinism: {prompt: [sha w0 pass1, w0 pass2, w1 pass1, w1 pass2]}
    capture: {(worker, bucket): {'captured': int, 'error': str|None}}
    closeness: {prompt: {'rel': float, 'max_abs': float}}
    """
    reasons = []
    if not memory_ok:
        return False, 'insufficient-memory', ['an encoder card fell below the free-memory floor']
    for key, row in sorted(capture.items(), key=repr):
        if row.get('error'):
            reasons.append('capture proof failed %r: %s' % (key, row['error'][:200]))
        elif row.get('captured') != 48:
            reasons.append('expected 48 layer captures for %r, got %r' % (key, row.get('captured')))
    if reasons:
        return False, 'window-capture-proof-failed', reasons
    for prompt, shas in sorted(determinism.items()):
        if len(shas) != 4 or len(set(shas)) != 1 or None in shas:
            reasons.append('not deterministic across workers/repeats: %s' % prompt)
    if reasons:
        return False, 'window-not-deterministic', reasons
    for prompt, row in sorted(closeness.items()):
        rel = row.get('rel')
        if rel is None or not (rel <= bound):
            reasons.append('relative difference %r > %g for %s' % (rel, bound, prompt))
    if reasons:
        return False, 'window-not-close', reasons
    if not determinism:
        return False, 'error', ['no prompts were compared']
    return True, 'window-qualified', []


def judge_oracle_passes(pass1, pass2):
    """B2: {fixture: {tensor: sha256}} for two passes; every fixture and all four tensors equal."""
    names = ('images', 'video_latent', 'audio_latent', 'waveform')
    bad = []
    if set(pass1) != set(pass2) or len(pass1) != 10:
        return False, ['fixture sets differ or are not ten: %s / %s' % (sorted(pass1), sorted(pass2))]
    for fixture in sorted(pass1):
        for name in names:
            a, b = pass1[fixture].get(name), pass2[fixture].get(name)
            if a is None or a != b:
                bad.append('%s/%s' % (fixture, name))
    return not bad, bad


def relative_difference(window, full):
    import torch
    require(window.shape == full.shape and window.dtype == full.dtype, 'Window and full shapes differ')
    diff = (window.double() - full.double()).abs()
    peak = float(full.double().abs().max())
    max_abs = float(diff.max())
    return {'max_abs': max_abs, 'mean_abs': float(diff.mean()), 'max_abs_full': peak,
            'rel': (max_abs / peak) if peak > 0 else (0.0 if max_abs == 0 else float('inf')),
            'bitwise_equal': bool(torch.equal(window.view(torch.int32), full.view(torch.int32)))
            if window.dtype == torch.float32 else bool(torch.equal(window, full))}


# --- state --------------------------------------------------------------------
def qualified():
    with _LOCK:
        return bool(_STATE['qualified'])


def admitted():
    with _LOCK:
        return tuple(_STATE['admitted'])


def state():
    with _LOCK:
        return {k: v for k, v in _STATE.items() if k != 'probe_run'}


def info_for(tag):
    with _LOCK:
        return _INFO.get(tag)


def _record_info(tag, info):
    with _LOCK:
        _INFO[tag] = info
        while len(_INFO) > 256:
            _INFO.pop(next(iter(_INFO)))


# --- runtime (XPU) ------------------------------------------------------------
def _graph_layers(clip):
    import ltx_graph_text_encoder as tenc
    stack, layers = tenc.stack_of(clip)
    shadows = [vars(layer).get('forward') for layer in layers]
    require(all(isinstance(s, tenc.GraphedLayer) for s in shadows),
            'The window encode needs the graph-captured encoder (text gate graph-shard)')
    require(getattr(stack, '_ltx_text_shard_applied', False), 'The window encode needs the sharded encoder')
    return stack, list(layers), shadows


def _sliding(layers):
    found = [layer for layer in layers if getattr(layer, 'sliding_attention', False)]
    require(len(found) == SLIDING_LAYERS, 'Expected %d sliding layers, found %d' % (SLIDING_LAYERS, len(found)))
    return found


def _set_sliding(layers, value):
    for layer in _sliding(layers):
        layer.sliding_attention = value


def install_stack_wrapper(stack):
    """Inject position ids 1024-W..1023 for a windowed encode on this thread only."""
    if vars(stack).get('_ltx_window_wrapped'):
        return
    import torch
    require('forward' not in vars(stack), 'Gemma stack forward is already shadowed')
    require(hasattr(stack, 'compute_freqs_cis'), 'Not the Gemma stack')
    original = stack.forward

    def forward(*args, **kwargs):
        w = getattr(_tls, 'window', None)
        if w is None:
            return original(*args, **kwargs)
        require(kwargs.get('position_ids') is None, 'A windowed encode was given explicit position ids')
        ref = kwargs.get('embeds') if kwargs.get('embeds') is not None else (args[0] if args else kwargs.get('x'))
        require(ref is not None and ref.shape[1] == w, 'Windowed encode length differs from its bucket')
        kwargs['position_ids'] = torch.arange(FULL - w, FULL, device=ref.device).unsqueeze(0)
        return original(*args, **kwargs)

    stack.forward = forward
    stack._ltx_window_wrapped = True


def _thread_entries(shadows):
    tid = threading.get_ident()
    return sum(len(s.entries_by_thread.get(tid, {})) for s in shadows)


def _plan(clip, text, allowed):
    tokens = clip.tokenize(text)
    require(isinstance(tokens, dict) and len(tokens) == 1, 'Unexpected tokenizer output')
    key = next(iter(tokens))
    rows = tokens[key]
    require(len(rows) == 1, 'Expected one token batch')
    n_total, n_real = len(rows[0]), real_token_count(rows[0])
    w = select_window(n_real, allowed) if n_total == FULL else FULL
    exec_rows = w if w < FULL else n_total     # a prompt longer than 1024 tokens runs at its own length
    return tokens, key, rows, n_total, n_real, w, exec_rows


def rows_captured(shadows, tid, rows):
    """True only if every layer holds a captured graph for `rows` on thread `tid`."""
    return bool(shadows) and all(
        any(int(e.output.shape[1]) == rows for e in s.entries_by_thread.get(tid, {}).values())
        for s in shadows)


def install_capture_guard(cls=None):
    """Make GraphedLayer refuse to capture on a thread that is running a timed encode."""
    if cls is None:
        import ltx_graph_text_encoder as tenc
        cls = tenc.GraphedLayer
    if vars(cls).get('_ltx_window_capture_guard'):
        return False
    original = cls._capture

    def _capture(self, kwargs, key):
        if getattr(_tls, 'no_capture', False):
            raise CaptureRefused('Gemma layer %s: a timed encode never captures (no graph for this '
                                 'signature on this worker)' % getattr(self, 'index', '?'))
        return original(self, kwargs, key)

    cls._capture = _capture
    cls._ltx_window_capture_guard = True
    return True


def precheck(clip, text, worker_idents):
    """Prompt-thread check before a windowed request is admitted: every encode worker
    must hold graphs for the row count this prompt will use. Raises WindowNotCaptured."""
    require(qualified(), 'Window encode refused: no passed text-window probe on this server')
    _tokens, _key, _rows, n_total, n_real, w, exec_rows = _plan(clip, text, admitted())
    stack, layers, shadows = _graph_layers(clip)
    idents = [t for t in worker_idents if t is not None]
    if not idents:
        raise WindowNotCaptured('No encode worker exists yet to check')
    missing = [t for t in idents if not rows_captured(shadows, t, exec_rows)]
    if missing:
        raise WindowNotCaptured('No captured graphs for %d rows (real tokens %d, window %d) on encode '
                                'worker(s) %s; refused before execution' % (exec_rows, n_real, w, missing))
    return {'window': w, 'rows': exec_rows, 'real_tokens': n_real, 'workers_checked': len(idents)}


def encode(clip, text, *, tag=None, index=None):
    """Windowed CLIPTextEncode equivalent. Returns the same 1-tuple the native node returns."""
    probing = getattr(_tls, 'probing', None)
    require(probing is not None or qualified(),
            'Window encode refused: no passed text-window probe on this server')
    allowed = probing['admitted'] if probing is not None else admitted()
    tokens, key, rows, n_total, n_real, w, exec_rows = _plan(clip, text, allowed)
    info = {'label': LABEL, 'policy': POLICY, 'admitted': list(allowed), 'real_tokens': n_real,
            'padded_tokens': n_total, 'window': w, 'rows': exec_rows, 'full_path': w == FULL,
            'clip_index': index}
    stack, layers, shadows = _graph_layers(clip)
    timed = probing is None
    if timed:
        # Before ANY execution: this worker must already hold every layer's graph.
        if not rows_captured(shadows, threading.get_ident(), exec_rows):
            raise WindowNotCaptured('Encode worker %s has no captured graphs for %d rows; refused before '
                                    'execution' % (threading.current_thread().name, exec_rows))
        install_capture_guard()
    started = time.monotonic()
    before = _thread_entries(shadows)
    _tls.no_capture = timed
    try:
        if w == FULL:
            out = clip.encode_from_tokens_scheduled(tokens)
        else:
            install_stack_wrapper(stack)
            windowed = {key: [window_row(rows[0], w)]}
            _tls.window = w
            try:
                out = clip.encode_from_tokens_scheduled(windowed)
            finally:
                _tls.window = None
    finally:
        _tls.no_capture = False
    captured = _thread_entries(shadows) - before
    info['captured_graphs'] = captured
    if timed:
        require(captured == 0, 'A timed encode captured %d graphs; refused' % captured)
    info['seconds'] = round(time.monotonic() - started, 4)
    if tag is not None:
        _record_info((tag, index), info)
    if probing is not None:
        probing['last'] = info
    return (out,)


def _free_gib(device):
    import torch
    try:
        free, _total = torch.xpu.mem_get_info(device)
        return round(free / 2**30, 3)
    except Exception:  # noqa: BLE001
        props = torch.xpu.get_device_properties(device)
        return round((props.total_memory - torch.xpu.memory_reserved(device)) / 2**30, 3)


def _memory():
    import torch
    return {d: {'free_gib': _free_gib(d), 'reserved_gib': round(torch.xpu.memory_reserved(d) / 2**30, 3),
                'allocated_gib': round(torch.xpu.memory_allocated(d) / 2**30, 3)} for d in ENCODER_CARDS}


def _cond_tensor(conditioning):
    import torch
    require(isinstance(conditioning, list) and len(conditioning) == 1, 'Unexpected conditioning structure')
    t = conditioning[0][0]
    require(isinstance(t, torch.Tensor), 'Unexpected conditioning tensor')
    return t.detach().to('cpu', copy=True).contiguous()


def _sha(t):
    import torch
    return hashlib.sha256(t.view(torch.uint8).numpy().tobytes()).hexdigest()


def drop_window_entries(shadows, layers):
    """Drop every captured window graph (any signature whose hidden state is not
    1024 rows) on every thread and put the sliding window back at 1024."""
    dropped = 0
    for shadow in shadows:
        for entries in shadow.entries_by_thread.values():
            for key in [k for k, e in entries.items() if int(e.output.shape[1]) != FULL]:
                del entries[key]
                dropped += 1
    _set_sliding(layers, FULL)
    return dropped


def _free_cached():
    import torch
    gc.collect()
    for d in ENCODER_CARDS:
        torch.xpu.synchronize(d)
        with torch.xpu.device(d):
            torch.xpu.empty_cache()


def release_windows(clip):
    """After a failed probe: drop the window graphs, free cached blocks. The
    shared per-thread pools keep their blocks for the 1024 graphs (recorded)."""
    stack, layers, shadows = _graph_layers(clip)
    dropped = drop_window_entries(shadows, layers)
    _free_cached()
    return dropped


def run_probe(clip, prompts, native_encode, pipeline):
    """B: qualify the windowed identity on this server. Never latches anything.

    prompts: [(name, text)]. native_encode(clip, text, consume_observations, encode_fn)
    is pipeline_node.native_encode (thread-stream discipline of a worker encode).
    """
    with _LOCK:
        require(_STATE['probe_run'] is None, 'The text-window probe runs once per server')
        _STATE['probe_run'] = 'running'
        _STATE['qualified'] = False
        _STATE['admitted'] = ()
    report = {'schema': 'ltx.text-window-probe.v1', 'label': LABEL, 'policy': POLICY,
              'rel_bound': REL_BOUND, 'rel_definition': REL_DEFINITION, 'buckets': list(BUCKETS),
              'passed': False, 'outcome': 'error'}
    started = time.monotonic()
    try:
        stack, layers, shadows = _graph_layers(clip)
        report['memory_before'] = _memory()
        # Idle = no job queued or running in any stage. A finished, uncollected
        # tail job cannot run again and the probe's own jobs use negative indices.
        report['pending_encode_at_start'] = pipeline.pending('encode')
        require(pipeline.busy() == 0, 'The pipeline must be idle for the text-window probe')
        require(pipeline.STAGE_WORKERS.get('encode', 1) >= 2, 'The probe needs the two encode workers')
        require(len(_sliding(layers)) == SLIDING_LAYERS and
                all(layer.sliding_attention == FULL for layer in _sliding(layers)),
                'Sliding layers are not at their 1024 window')
        install_stack_wrapper(stack)
        lengths = {}
        for name, text in prompts:
            row = next(iter(clip.tokenize(text).values()))[0]
            lengths[name] = (len(row), real_token_count(row))
        report['prompt_tokens'] = {n: {'padded': a, 'real': b} for n, (a, b) in lengths.items()}
        wanted = sorted({select_window(b, BUCKETS) for a, b in lengths.values() if a == FULL} - {FULL})
        report['buckets_wanted'] = wanted
        barrier = threading.Barrier(2, timeout=BARRIER_TIMEOUT_S)
        go = [threading.Event(), threading.Event()]
        go[0].set()
        results = [None, None]
        aborted = []
        stop = threading.Event()             # set when the server-side bound expires
        done = [threading.Event(), threading.Event()]

        def check_stop():
            require(not stop.is_set(), 'Probe stopped: the server-side time bound expired')

        def worker_probe(k):
            try:
                return worker_body(k)
            finally:
                done[k].set()

        def worker_body(k):
            name = threading.current_thread().name
            barrier.wait()
            require(go[k].wait(BARRIER_TIMEOUT_S * 10), 'Worker %d was never released' % k)
            require(not aborted, 'Worker %d skipped: the first worker failed' % k)
            out = {'thread': name, 'thread_ident': threading.get_ident(), 'full': {}, 'passes': [{}, {}],
                   'seconds': {}, 'capture': {}, 'admitted': [], 'memory': {}}
            try:
                for pname, text in prompts:
                    check_stop()
                    t0 = time.monotonic()
                    cond = native_encode(clip, text, consume_observations=True)
                    out['seconds'].setdefault('1024', []).append(round(time.monotonic() - t0, 4))
                    out['full'][pname] = _cond_tensor(cond)
                probing = {'admitted': (), 'last': None}
                _tls.probing = probing
                try:
                    for w in wanted:
                        check_stop()
                        mem = _memory()
                        out['memory']['before-%d' % w] = mem
                        if min(m['free_gib'] for m in mem.values()) < MIN_FREE_GIB:
                            out['memory_stop'] = w
                            break
                        first = next(t for n, t in prompts if lengths[n][0] == FULL
                                     and select_window(lengths[n][1], BUCKETS) == w)
                        probing['admitted'] = tuple(out['admitted']) + (w,)
                        _set_sliding(layers, w)
                        try:
                            native_encode(clip, first, consume_observations=True,
                                          encode_fn=lambda t=first: encode(clip, t))
                            out['capture'][w] = {'captured': probing['last'].get('captured_graphs'),
                                                 'error': None}
                        except Exception as error:  # noqa: BLE001
                            out['capture'][w] = {'captured': None, 'error': repr(error)[:2000]}
                            raise
                        finally:
                            _set_sliding(layers, FULL)
                        out['admitted'].append(w)
                    probing['admitted'] = tuple(out['admitted'])
                    for p in range(2):
                        for pname, text in prompts:
                            check_stop()
                            t0 = time.monotonic()
                            cond = native_encode(clip, text, consume_observations=True,
                                                 encode_fn=lambda t=text: encode(clip, t))
                            info = dict(probing['last'])
                            require(info.get('captured_graphs', 0) == 0,
                                    'A probe pass captured graphs; replay path not proven')
                            t = _cond_tensor(cond)
                            out['passes'][p][pname] = {'tensor': t, 'window': info['window']}
                            out['seconds'].setdefault(str(info['window']), []).append(
                                round(time.monotonic() - t0, 4))
                finally:
                    _tls.probing = None
            except BaseException:
                aborted.append(k)
                raise
            finally:
                _set_sliding(layers, FULL)
                if k == 0:
                    go[1].set()
            return out

        for k, index in enumerate(PROBE_JOB_INDICES):
            require(pipeline.submit('encode', index, (lambda kk=k: worker_probe(kk))),
                    'Probe job index already in use')
        # Bounded: a hung worker must not block the prompt thread forever. On
        # expiry the probe fails, the window stays refused, the workers are told
        # to stop at their next prompt, and the window graphs are NOT released
        # while a worker may still be using them (recorded).
        deadline = time.monotonic() + PROBE_TIMEOUT_S
        for k in range(2):
            if not done[k].wait(max(0.0, deadline - time.monotonic())):
                stop.set()
                report['outcome'] = 'error'
                report['error'] = ('probe worker %d did not finish within %.0f s; window refused, '
                                   'graphs not released while a worker may still hold them' % (k, PROBE_TIMEOUT_S))
                report['timed_out'] = True
                raise RuntimeError(report['error'])
        errors = []
        for k, index in enumerate(PROBE_JOB_INDICES):
            try:
                results[k], _detail = pipeline.collect('encode', index)
            except Exception as error:  # noqa: BLE001
                errors.append(str(error)[-3000:])
        report['worker_errors'] = errors
        capture = {}
        for k, res in enumerate(results):
            if res is None:
                continue
            for w, row in res['capture'].items():
                capture[('w%d' % k, w)] = row
        report['capture'] = {'%s/%d' % key: row for key, row in capture.items()}
        if errors:
            proof = any('graph replay differs from eager' in e or 'captured an inert graph' in e for e in errors)
            report['outcome'] = 'window-capture-proof-failed' if proof else 'error'
            report['error'] = errors[0]
            raise RuntimeError('probe worker failed')
        require(results[0]['thread_ident'] != results[1]['thread_ident'], 'Both probe jobs ran on one thread')
        # A bucket that did not fit is simply not admitted (its prompts take the
        # certified 1024 path); only the floor after the probe is a failure.
        report['memory_stops'] = {res['thread']: res.get('memory_stop') for res in results}
        both = sorted(set(results[0]['admitted']) & set(results[1]['admitted']))
        determinism, closeness, rows = {}, {}, []
        for pname, _text in prompts:
            shas = [_sha(res['passes'][p][pname]['tensor']) if pname in res['passes'][p] else None
                    for res in results for p in range(2)]
            determinism[pname] = shas
            win = results[0]['passes'][0][pname]
            full0, full1 = results[0]['full'][pname], results[1]['full'][pname]
            close = relative_difference(win['tensor'], full0)
            closeness[pname] = close
            rows.append({'prompt': pname, 'real_tokens': lengths[pname][1], 'window': win['window'],
                         'window_sha256': shas, 'full_sha256': [_sha(full0), _sha(full1)],
                         'full_identical_across_workers': _sha(full0) == _sha(full1), **close})
        report['rows'] = rows
        report['seconds_by_bucket'] = {
            res['thread']: {b: {'n': len(v), 'median': sorted(v)[len(v) // 2]} for b, v in res['seconds'].items()}
            for res in results}
        report['memory_by_worker'] = {res['thread']: res['memory'] for res in results}
        mem_after = _memory()
        report['memory_after_probe'] = mem_after
        memory_ok = bool(both) and min(m['free_gib'] for m in mem_after.values()) >= MIN_FREE_AFTER_GIB
        passed, outcome, reasons = judge_probe(determinism, capture, closeness, memory_ok)
        report.update({'passed': passed, 'outcome': outcome, 'reasons': reasons, 'admitted': both,
                       'workers': [res['thread'] for res in results]})
    except Exception as error:  # noqa: BLE001  (a recorded verdict, never a latch)
        report.setdefault('error', repr(error)[:3000])
        report['passed'] = False
    finally:
        if not report['passed'] and not report.get('timed_out'):
            try:
                report['released_graphs'] = release_windows(clip)
                report['memory_after_release'] = _memory()
            except Exception as error:  # noqa: BLE001
                report['release_error'] = repr(error)[:1000]
        with _LOCK:
            _STATE['qualified'] = bool(report['passed'])
            _STATE['admitted'] = tuple(report.get('admitted', ())) if report['passed'] else ()
            _STATE['outcome'] = report['outcome']
            _STATE['probe_run'] = 'done'
        report['seconds'] = round(time.monotonic() - started, 3)
        report['torch_threads_note'] = 'probe jobs ran on the two ltx-encode workers, one after the other'
    return report
