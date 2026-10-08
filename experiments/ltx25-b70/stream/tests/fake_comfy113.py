#!/usr/bin/env python3
"""A fake of the packet 113 continuation stream server, for testing ltx_continuation_client.py --packet 113.

Derived from fake_comfy112.py. Packet 113 differences: the receipt is committed at "anchor ready"
with the preview queued; a writer thread writes the MP4 --preview-delay seconds later (in order)
and commits receipts/preview-<run>.json, served by GET /ltx-stream/preview/<run>; a stream chunk
with reset=1 is admitted as an unanchored chunk; status carries packet/features/preview_writer;
--no-preview-at N never writes chunk N's preview record; --preview-fail-at N records a preview
write failure (stream-preview-failure-<run>.json) and latches.

    python3 -B fake_comfy113.py --root ROOT --port 18189 [--delay 0.05] [--qualification pass|fail|lie] ...

Implements the CONTRACT.md routes: POST /prompt (with the admission layer: setup graphs by digest,
the nine qualification requests in order, then stream chunks via stream_contract.parse_chunk_graph,
order / stale-anchor / text-reuse-rule / window-not-qualified / busy refusals, 503 halted after a
latch), GET /ltx-stream/status, GET /ltx-stream/receipt/<run_name>, POST /ltx-stream/action
{"action": "qualify-verdict"} (decided by the sealed qualification_gate.decide). Executes one
request at a time; writes receipts (stream_receipts.validate_receipt-clean), anchors (the two newest
kept) and preview MP4s under ROOT/output/<run_name>/preview_NNNNN_.mp4 (counter increments when a
file exists, as ComfyUI does).

Window rule (fake): a prompt longer than --max-prompt-chars is 'window-not-qualified'.
Qualification: 'fail' makes the repeat chain's chunk 1 tensors differ (the gate fails, the server
latches); 'lie' makes them differ but reports a pass anyway (the client must catch it).
Injection by stream_seq: --halt-at (latch, no failure file), --fail-at (stream-failure-<run>.json +
latch), --fault-at (ROOT/FAULT.json), --no-preview-at (receipt names a missing MP4), --stall-at
(never completes), --corrupt-anchor-at (receipt AND status report a wrong anchor; the next request is stale-anchor),
--corrupt-receipt-at (only the receipt reports a wrong anchor), --refuse-at N --refuse-code C
[--refuse-status 409] (admission refuses stream_seq N with code C),
--advance-at (server skips a stream_seq after that chunk, as if another client had submitted),
--odd-dir-at (preview written into a directory that does not match the 112 prefix).
Test evidence in ROOT/fake113-stats.json.
"""
import argparse, hashlib, json, os, shutil, sys, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.dont_write_bytecode = True
ap = argparse.ArgumentParser()
ap.add_argument('--root', required=True, type=Path)
ap.add_argument('--port', type=int, default=18189)
ap.add_argument('--contract-dir', type=Path,
                default=Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation113-stream'))
ap.add_argument('--frames', type=int, default=49)
ap.add_argument('--placement', default='two-way20-28')
ap.add_argument('--text-reuse', type=int, default=0)
ap.add_argument('--manifest-sha256', default='a23dbc946d156df70c3e61134dc3231b147817c5cb110a015f84c8f020f7f28b')
ap.add_argument('--preview-delay', type=float, default=0.3, help='seconds the fake writer takes per MP4')
ap.add_argument('--delay', type=float, default=0.05)
ap.add_argument('--setup-delay', type=float, default=0.05)
ap.add_argument('--phase', choices=('setup', 'stream'), default='setup',
                help='stream: start already qualified (runs the 11 requests + verdict internally)')
ap.add_argument('--qualification', choices=('pass', 'fail', 'lie'), default='pass')
ap.add_argument('--max-prompt-chars', type=int, default=300)
ap.add_argument('--clip', type=Path, help='MP4 to copy as every preview (default: small dummy bytes)')
for opt in ('halt-at', 'fail-at', 'fault-at', 'no-preview-at', 'stall-at', 'corrupt-anchor-at', 'advance-at',
            'odd-dir-at', 'corrupt-receipt-at', 'refuse-at', 'preview-fail-at'):
    ap.add_argument('--' + opt, type=int, default=None)
ap.add_argument('--refuse-code', default='busy')
ap.add_argument('--refuse-status', type=int, default=409)
a = ap.parse_args()
sys.path.insert(0, str(a.contract_dir))
import stream_contract as c          # noqa: E402
import stream_receipts as sr         # noqa: E402
import qualification_gate as qg      # noqa: E402

ROOT = a.root
DIAG = sr.border_diagnostic_reference(b'\0\0\0?' * (c.ANCHOR_BYTES // 4))
RUN = ROOT / ('encoder-server-continuation-stream-113-%s-w1-b1-p1-dxpu2-s256x256-f%d' % (a.placement, a.frames))
OUT = ROOT / 'output'
if RUN.exists():                      # a new launch never reuses a run dir: archive the old one
    RUN.rename(RUN.with_name(RUN.name + '.old%d' % time.time_ns()))
for d in (RUN / 'receipts', RUN / 'anchors', OUT):
    d.mkdir(parents=True, exist_ok=True)
IDENT = hashlib.sha256(('fake-%s-%d' % (uuid.uuid4(), os.getpid())).encode()).hexdigest()
PLAN = hashlib.sha256(b'fake-plan').hexdigest()
QID = c.qualification_id(a.frames, a.placement)
(RUN / 'server-identity.json').write_text(json.dumps({'pid': os.getpid(), 'identity': IDENT}) + '\n')

LOCK = threading.RLock()
S = {'phase': 'stream_setup', 'halted': None, 'completed': [], 'active': None, 'queue': [],
     'next': 0, 'stream_completed': 0, 'chains': {}, 'receipts': {}, 'stream_receipts': {}, 'verdict': None,
     'verdict_done': False, 'prompt_ids': set(), 'action_busy': False}
STATS = {'posts': 0, 'refusals': {}, 'max_in_server': 0, 'status_gets': 0, 'receipt_gets': 0,
         'resets': [], 'submitted_before_prev_preview': 0, 'preview_order': [],
         'stream_order': [], 'submit_after_commit_s': [], 'last_commit_mono': None, 'qual_posts': 0}
SETUP = c.setup_graphs()
QPARAMS = c.qualification_params(a.frames, a.text_reuse, a.placement)
COND = threading.Condition(LOCK)
import queue  # noqa: E402
PREVIEWS = queue.Queue(maxsize=2)
PREVIEW_STATE = {'pending': 0, 'failed': None, 'written': set()}


def preview_writer():
    while True:
        job = PREVIEWS.get()
        try:
            time.sleep(a.preview_delay)
            name, seq, final, timing = job
            if PREVIEW_STATE['failed'] is not None:
                continue
            if seq is not None and seq == a.preview_fail_at:
                PREVIEW_STATE['failed'] = name
                (RUN / ('stream-preview-failure-%s.json' % name)).write_text(json.dumps({'run_name': name}))
                with LOCK:
                    S['halted'] = 'RuntimeError: Preview write failed for %s' % name
                    (RUN / 'stream-halt.json').write_text(json.dumps({'reason': S['halted']}))
                continue
            start = time.time_ns()
            tmp = final.with_name('.' + final.name + '.partial')
            if a.clip:
                shutil.copyfile(a.clip, tmp)
            else:
                tmp.write_bytes(b'\0\0\0\x18ftypmp42' + name.encode() * 20)
            os.link(tmp, final)
            os.unlink(tmp)
            raw = final.read_bytes()
            written = time.time_ns()
            STATS['preview_order'].append(name)
            if seq is not None and seq == a.no_preview_at:
                continue
            t = dict(timing, write_start=start, preview_written=written)
            rec = {'schema': sr.PREVIEW_SCHEMA, 'run_name': name, 'prompt_id': job[3]['prompt_id'],
                   'path': str(final), 'relative_to_output_directory': str(final.relative_to(OUT)),
                   'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'container': 'mp4',
                   'written': True, 'order': 'fifo', 'frames': a.frames, 'fps': 24, 'lossy': True,
                   'timing_ns': {k: t[k] for k in sr.PREVIEW_TIMING_KEYS},
                   'timing_s': {'submit_to_preview_written': None if t['submit'] is None else
                                round((written - t['submit']) / 1e9, 6),
                                'anchor_ready_to_preview_written': round((written - t['anchor_ready']) / 1e9, 6),
                                'queue_wait': round((start - t['preview_queued']) / 1e9, 6),
                                'write': round((written - start) / 1e9, 6)}}
            sr.validate_preview_record(rec)
            write_exclusive(RUN / 'receipts' / ('preview-%s.json' % name), rec)
            PREVIEW_STATE['written'].add(name)
            save_stats()
        finally:
            PREVIEW_STATE['pending'] -= 1
            PREVIEWS.task_done()


def save_stats():
    s = dict(STATS)
    s.pop('last_commit_mono', None)
    tmp = ROOT / 'fake113-stats.json.tmp'
    tmp.write_text(json.dumps(s, indent=1) + '\n')
    os.replace(tmp, ROOT / 'fake113-stats.json')


def write_exclusive(path, value):
    raw = c.canonical(value) + b'\n'
    with open(path, 'xb') as f:
        f.write(raw)
    return hashlib.sha256(raw).hexdigest()


class Refusal(Exception):
    def __init__(self, code, msg, status=409):
        super().__init__(msg)
        self.code, self.status = code, status


def h(*parts):
    return hashlib.sha256('|'.join(str(p) for p in parts).encode()).hexdigest()


def classify(graph):
    if S['phase'] == 'stream_setup':
        row = SETUP[len(S['completed'])]
        if c.sha256(c.canonical(graph)) != c.sha256(c.canonical(row['graph'])):
            raise Refusal('order', 'Next request must be setup graph ' + row['name'])
        return {'name': row['name'], 'kind': row['kind'], 'params': None}
    try:
        params = c.parse_chunk_graph(graph, a.frames, a.placement)
    except ValueError as e:
        raise Refusal('contract', str(e))
    name = c.run_name(params)
    if S['phase'] == 'stream_qualification':
        i = len(S['completed']) - 2
        if i >= 9:
            raise Refusal('not-streaming', 'Qualification requests are done; the verdict action is next')
        if params != QPARAMS[i]:
            raise Refusal('order', 'Next qualification request is ' + c.run_name(QPARAMS[i]))
        chain = params['scene_id']
    else:
        if params['kind'] != 'stream':
            raise Refusal('order', 'Only stream chunks are admitted after qualification')
        if params['stream_seq'] != S['next']:
            raise Refusal('order', 'stream_seq must be %d' % S['next'])
        chain = 'stream'
        if a.refuse_at is not None and params['stream_seq'] == a.refuse_at:
            raise Refusal(a.refuse_code, 'injected refusal', a.refuse_status)
    state = S['chains'].get(chain)
    if params['chunk_index'] == 0:
        if state is not None:
            raise Refusal('order', 'Chain already started')
        if params['reuse_text']:
            raise Refusal('text-reuse-rule', 'An unanchored chunk always encodes its prompt')
    elif params['reset']:
        if state is None or state['last_chunk'] != params['chunk_index'] - 1:
            raise Refusal('order', 'Chain %s expects another chunk' % chain)
        pred = params['predecessor_anchor_sha256']
        if pred and pred != state['anchor_sha256']:
            raise Refusal('stale-anchor', 'A reset chunk may name only the current anchor')
    else:
        if state is None or state['last_chunk'] != params['chunk_index'] - 1:
            raise Refusal('order', 'Chain %s expects another chunk' % chain)
        if params['kind'] == 'stream' and params['predecessor_anchor_sha256'] != state['anchor_sha256']:
            raise Refusal('stale-anchor', 'predecessor_anchor_sha256 is not the anchor of %s' % state['run_name'])
        same = c.text_sha256(params['prompt']) == state['text_sha256']
        expected = int(bool(a.text_reuse) and same and params['kind'] != 'qualify-eager')
        if params['reuse_text'] != expected:
            raise Refusal('text-reuse-rule', 'reuse_text must be %d' % expected)
    if not params['reuse_text'] and len(params['prompt']) > a.max_prompt_chars:
        if S['phase'] == 'stream':
            raise Refusal('window-not-qualified', 'Prompt uses text window 128; this server qualified [64]')
    return {'name': name, 'kind': params['kind'], 'params': params, 'chain': chain}


def admit(body):
    if S['action_busy']:
        raise Refusal('busy', 'An action is running')
    if S['halted'] is not None or (ROOT / 'FAULT.json').exists():
        raise Refusal('halted', 'Stream server halted; inspect evidence', 503)
    if type(body) is not dict or type(body.get('prompt')) is not dict:
        raise Refusal('contract', 'Body needs a prompt graph', 400)
    if type(body.get('client_id')) is not str or not body['client_id']:
        raise Refusal('missing-client-id', 'client_id is required', 400)
    pid = body.get('prompt_id')
    try:
        ok = type(pid) is str and str(uuid.UUID(pid)) == pid
    except ValueError:
        ok = False
    if not ok:
        raise Refusal('missing-prompt-id', 'prompt_id must be a canonical lowercase UUID', 400)
    if set(body) - {'prompt', 'client_id', 'prompt_id'}:
        raise Refusal('contract', 'Only prompt, client_id and prompt_id are accepted', 400)
    if S['active'] is not None or S['queue']:
        raise Refusal('busy', 'A request is still executing or queued')
    if S['phase'] == 'stream_qualification' and len(S['completed']) == 11:
        raise Refusal('not-streaming', 'Qualification verdict pending')
    d = classify(body['prompt'])
    return d


def tensors_for(params, chain_variant):
    g = c.geometry(a.frames)
    return {t: {'shape': g['tensor_shapes'][t], 'dtype': 'torch.float32', 'finite': True,
                'sha256': h(params['chunk_index'], params['seed'], params['prompt'], params['stream_seq']
                            if params['kind'] == 'stream' else 'q', chain_variant, t)}
            for t in ('images', 'video_latent', 'audio_latent', 'waveform')}


def preview_for(name, seq):
    folder = OUT / (name + '-odd' if seq is not None and seq == a.odd_dir_at else name)
    folder.mkdir(parents=True, exist_ok=True)
    k = 1
    while (folder / ('preview_%05d_.mp4' % k)).exists():
        k += 1
    return folder / ('preview_%05d_.mp4' % k)        # written later by preview_writer


def execute(item):
    d, pid, submit_ns = item['d'], item['prompt_id'], item['submit_ns']
    name, params = d['name'], d['params']
    seq = params['stream_seq'] if params and params['kind'] == 'stream' else None
    t_exec = time.time_ns()
    if params is None:
        time.sleep(a.setup_delay)
        with LOCK:
            S['completed'].append(name)
            S['prompt_ids'].add(pid)
            if len(S['completed']) == 2:
                S['phase'] = 'stream_qualification'
            S['active'] = None
        return
    if seq is not None and seq == a.stall_at:
        while True:
            time.sleep(3600)
    time.sleep(a.delay)
    with LOCK:
        if seq is not None and seq == a.halt_at:
            S['halted'] = 'RuntimeError: injected halt at %s' % name
            (RUN / 'stream-halt.json').write_text(json.dumps({'reason': S['halted']}))
            S['active'] = None
            return
        if seq is not None and seq == a.fail_at:
            (RUN / ('stream-failure-%s.json' % name)).write_text(json.dumps({'run_name': name, 'error': 'injected'}))
            S['halted'] = 'RuntimeError: injected failure at %s' % name
            (RUN / 'stream-halt.json').write_text(json.dumps({'reason': S['halted']}))
            S['active'] = None
            return
        if seq is not None and seq == a.fault_at:
            (ROOT / 'FAULT.json').write_text(json.dumps({'fault': 'injected'}))
            S['active'] = None
            return
        chain = d['chain']
        prev = S['chains'].get(chain)
        variant = 'bad' if (a.qualification in ('fail', 'lie') and params['kind'] == 'qualify-repeat'
                            and params['chunk_index'] == 1) else ''
        tensors = tensors_for(params, variant)
        anchor_sha = h('anchor', tensors['images']['sha256'])
        anchor_path = RUN / 'anchors' / (name + '.f32')
        anchor_path.write_bytes(b'')       # placeholder; the client never reads anchors
        corrupt = seq is not None and seq in (a.corrupt_anchor_at, a.corrupt_receipt_at)
        reported_anchor = h('corrupt', anchor_sha) if corrupt else anchor_sha
        preview = preview_for(name, seq)
        t_prev = time.time_ns()
        anchored = c.anchored(params)
        kind = params['kind']
        gate_mode = 'original' if kind == 'qualify-eager' else 'graph'
        routes = 0 if kind == 'qualify-eager' else 48
        new = 96 if (kind == 'qualify-graph' and params['chunk_index'] < 2) else 0
        timing = {'submit': submit_ns, 'execution_start': t_exec, 'sampler_a_start': t_exec + 1_000_000,
                  'sampler_b_start': t_exec + 2_000_000, 'decode_start': t_exec + 3_000_000,
                  'decode_done': t_exec + 4_000_000, 'anchor_ready': t_prev, 'preview_queued': t_prev + 10,
                  'preview_written': None, 'receipt_staged': t_prev + 1000}
        receipt = {
            'schema': sr.SCHEMA, 'run_name': name, 'prompt_id': pid, 'kind': kind, 'stream_seq': params['stream_seq'],
            'chunk_index': params['chunk_index'], 'scene_id': params['scene_id'], 'seed': params['seed'],
            'frames': a.frames, 'placement': a.placement, 'prompt_sha256': c.text_sha256(params['prompt']),
            'prompt_changed': None if params['chunk_index'] == 0 else
            (c.text_sha256(params['prompt']) != prev['text_sha256']),
            'anchored': anchored, 'reset': bool(params['reset']),
            'reset_predecessor_anchor_sha256': params['predecessor_anchor_sha256'] if params['reset'] else None,
            'predecessor_preview': None,
            'anchor_diagnostics': DIAG,
            'reuse_text': params['reuse_text'], 'server_text_reuse': a.text_reuse,
            'text': {'reused': bool(params['reuse_text']), 'tensors': [{'sha256': h('text', params['prompt'])}]},
            'tensors': tensors,
            'anchor_in': None if not anchored else
            {'sha256': prev['anchor_sha256'], 'path': prev['anchor_path'], 'source_run_name': prev['run_name']},
            'anchor_out': {'sha256': reported_anchor, 'path': str(anchor_path), 'bytes': c.ANCHOR_BYTES,
                           'frame_index': a.frames - 1, 'shape': c.ANCHOR_SHAPE, 'dtype': 'F32'},
            'delivery': sr.delivery(params['chunk_index'], a.frames, anchored),
            'preview': {'path': str(preview), 'relative_to_output_directory': str(preview.relative_to(OUT)),
                        'bytes': None, 'state': 'queued', 'record': str(RUN / 'receipts' / ('preview-%s.json' % name)),
                        'container': 'mp4', 'lossy': True, 'fps': 24, 'frames': a.frames,
                        'includes_overlap_frame': anchored},
            'capture': {'path': str(RUN / name / 'tensors.safetensors')} if kind in c.CAPTURE_KINDS else None,
            'timing_ns': timing,
            'timing_s': {'submit_to_sampler_start': sr.seconds(timing, 'submit', 'sampler_a_start'),
                         'submit_to_decode_done': sr.seconds(timing, 'submit', 'decode_done'),
                         'submit_to_anchor_ready': sr.seconds(timing, 'submit', 'anchor_ready'),
                         'anchor_ready_to_receipt_staged': sr.seconds(timing, 'anchor_ready', 'receipt_staged'),
                         'submit_to_preview_written': None, 'execution_start_to_preview_written': None},
            'graph': {'gate_mode': gate_mode, 'routes': routes, 'signatures_per_route': 0 if routes == 0 else 4,
                      'new_captures': new, 'captures_frozen': kind == 'stream'},
            'memory': {}, 'storage': {'free_bytes': shutil.disk_usage(ROOT).free},
            'sanity': {'finite': True, 'shapes': True, 'anchor_chain': True},
            'plan_sha256': PLAN, 'qualification_id': QID, 'qualification_verdict_sha256': S['verdict'],
            'server_identity_sha256': IDENT, 'runtime_manifest_sha256': a.manifest_sha256}
        sr.validate_receipt(receipt)
        PREVIEW_STATE['pending'] += 1
        PREVIEWS.put((name, seq, preview, {'submit': submit_ns, 'anchor_ready': t_prev, 'preview_queued': t_prev + 10,
                                           'prompt_id': pid}))
        if params['reset']:
            STATS['resets'].append(params['stream_seq'])
        path = RUN / 'receipts' / ('receipt-%s.json' % name)
        sha = write_exclusive(path, dict(receipt, committed=True, commit_ns=time.time_ns()))
        S['chains'][chain] = {'last_chunk': params['chunk_index'], 'run_name': name, 'anchor_sha256': anchor_sha,
                              'anchor_path': str(anchor_path), 'text_sha256': c.text_sha256(params['prompt']),
                              'previous_anchor_path': prev['anchor_path'] if prev else None,
                              'reported_anchor': reported_anchor if (seq is not None and seq == a.corrupt_anchor_at) else anchor_sha}
        if kind == 'stream':
            S['stream_receipts'][name] = {'path': str(path), 'sha256': sha}
            while len(S['stream_receipts']) > 64:
                S['stream_receipts'].pop(next(iter(S['stream_receipts'])))
            S['next'] += 1
            S['stream_completed'] += 1
            if prev and prev['previous_anchor_path']:
                try:
                    os.unlink(prev['previous_anchor_path'])
                except FileNotFoundError:
                    pass
            if seq is not None and seq == a.advance_at:
                S['next'] += 1        # as if another client had used the next stream_seq
            STATS['last_commit_mono'] = time.monotonic()
        else:
            S['receipts'][name] = {'path': str(path), 'sha256': sha}
            S['completed'].append(name)
        S['prompt_ids'].add(pid)
        S['active'] = None
        save_stats()


def worker():
    while True:
        with COND:
            while not S['queue']:
                COND.wait()
            item = S['queue'].pop(0)
            S['active'] = {'name': item['d']['name'], 'prompt_id': item['prompt_id'], 'kind': item['d']['kind'],
                           'params': item['d']['params'], 'chain': item['d'].get('chain'), 'start_ns': time.time_ns()}
        execute(item)


def verdict():
    with LOCK:
        if S['verdict_done']:
            raise Refusal('action-failed', 'Only one qualify-verdict action exists')
        if S['phase'] != 'stream_qualification' or len(S['completed']) != 11:
            raise Refusal('action-failed', 'Nine qualification requests required')
        S['verdict_done'] = True
        PREVIEWS.join()
        receipts, captures = [], {}
        for p in QPARAMS:
            name = c.run_name(p)
            r = json.loads(Path(S['receipts'][name]['path']).read_text())
            receipts.append(r)
            captures[name] = {'path': r['capture']['path'], 'bytes': 1,
                              'tensors': {t: r['tensors'][t]['sha256'] for t in r['tensors']},
                              'last_frame_sha256': h('anchor', r['tensors']['images']['sha256'])}
        v = qg.decide(receipts, captures, PLAN, a.frames, a.text_reuse, a.placement)
        if a.qualification == 'lie':
            v = dict(v, passed=True, failures=[],
                     exact_replay=[dict(x, all_four_identical=True) for x in v['exact_replay']])
        v.update(receipts={n: S['receipts'][n] for n in S['receipts']}, captures=captures, time_ns=time.time_ns())
        sha = write_exclusive(RUN / 'stream-qualification-verdict.json', v)
        if not v['passed']:
            S['halted'] = 'RuntimeError: Qualification failed: ' + '; '.join(v['failures'])
            (RUN / 'stream-halt.json').write_text(json.dumps({'reason': S['halted']}))
            return {'passed': False, 'failures': v['failures'], 'verdict_sha256': sha}
        S['verdict'] = sha
        S['phase'] = 'stream'
        return {'passed': True, 'verdict_sha256': sha, 'phase': 'stream', 'qualified_text_windows': [64]}


def status():
    with LOCK:
        chain = S['chains'].get('stream')
        free = shutil.disk_usage(ROOT).free
        return {'phase': S['phase'], 'halted': S['halted'], 'active': S['active'],
                'completed_fixed_requests': list(S['completed']), 'stream_completed': S['stream_completed'],
                'next_stream_seq': S['next'], 'text_reuse': a.text_reuse,
                'qualification_verdict_sha256': S['verdict'],
                'last_stream_receipts': list(S['stream_receipts'].values())[-4:],
                'frames': a.frames, 'placement': a.placement, 'qualification_id': QID,
                'chain': None if chain is None else {'last_stream_seq': chain['last_chunk'],
                                                     'last_run_name': chain['run_name'],
                                                     'anchor_sha256': chain['reported_anchor'],
                                                     'prompt_sha256': chain['text_sha256']},
                'server_identity_sha256': IDENT, 'runtime_manifest_sha256': a.manifest_sha256, 'plan_sha256': PLAN,
                'fault': (ROOT / 'FAULT.json').exists() or (RUN / 'stream-halt.json').exists(),
                'receipt_dir': str(RUN / 'receipts'),
                'qualified_text_windows': [64] if S['phase'] == 'stream' else None,
                'output_directory': str(OUT), 'packet': 113,
                'features': {'async_preview': True, 'chain_reset': True, 'anchor_diagnostics': True},
                'preview_writer': {'pending': PREVIEW_STATE['pending'], 'failed': PREVIEW_STATE['failed']},
                'storage': {'free_bytes': free, 'consumed_bytes': 0, 'allowance_bytes': 3 * 2 ** 30,
                            'reserve_bytes': 50 * 2 ** 30}}


class H(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, obj=None, raw=None):
        body = raw if raw is not None else json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def refuse(self, e):
        STATS['refusals'][e.code] = STATS['refusals'].get(e.code, 0) + 1
        save_stats()
        self.send(e.status, {'error': {'code': e.code, 'message': str(e)}})

    def do_GET(self):
        if self.path == '/ltx-stream/status':
            STATS['status_gets'] += 1
            if S['action_busy']:
                return self.send(409, {'error': {'code': 'busy', 'message': 'action active'}})
            return self.send(200, status())
        if self.path.startswith('/ltx-stream/receipt/'):
            STATS['receipt_gets'] += 1
            name = self.path.rsplit('/', 1)[1]
            p = RUN / 'receipts' / ('receipt-%s.json' % name)
            if not p.is_file():
                return self.send(404, {'error': {'code': 'not-found', 'message': name}})
            return self.send(200, raw=p.read_bytes())
        if self.path.startswith('/ltx-stream/preview/'):
            name = self.path.rsplit('/', 1)[1]
            p = RUN / 'receipts' / ('preview-%s.json' % name)
            if not p.is_file():
                if PREVIEW_STATE['failed'] is not None:
                    return self.send(503, {'error': {'code': 'halted', 'message': 'preview writer failed'}})
                return self.send(404, {'error': {'code': 'not-found', 'message': name}})
            return self.send(200, raw=p.read_bytes())
        self.send(404, {'error': {'code': 'not-found', 'message': self.path}})

    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        try:
            body = json.loads(self.rfile.read(n) or b'null')
        except ValueError:
            return self.refuse(Refusal('contract', 'Body must be JSON', 400))
        if self.path == '/ltx-stream/action':
            if type(body) is not dict or body.get('action') != 'qualify-verdict':
                return self.send(400, {'error': {'code': 'contract', 'message': 'one named action required'}})
            S['action_busy'] = True
            try:
                time.sleep(0.2)
                return self.send(200, verdict())
            except Refusal as e:
                return self.send(409, {'error': {'code': e.code, 'message': str(e)}, 'halted': S['halted'] is not None})
            finally:
                S['action_busy'] = False
        if self.path != '/prompt':
            return self.send(404, {})
        submit_ns = time.time_ns()
        with COND:
            STATS['posts'] += 1
            try:
                d = admit(body)
            except Refusal as e:
                return self.refuse(e)
            if d['params'] is not None and d['kind'] == 'stream':
                STATS['stream_order'].append(d['params']['stream_seq'])
                prev_name = 'stream112-s%08d' % (d['params']['stream_seq'] - 1)
                if d['params']['stream_seq'] > 0 and prev_name not in PREVIEW_STATE['written']:
                    STATS['submitted_before_prev_preview'] += 1
                if STATS['last_commit_mono'] is not None:
                    STATS['submit_after_commit_s'].append(round(time.monotonic() - STATS['last_commit_mono'], 4))
            elif d['params'] is not None or d['kind'] in ('window-probe', 'prepare'):
                STATS['qual_posts'] += 1
            S['queue'].append({'d': d, 'prompt_id': body['prompt_id'], 'submit_ns': submit_ns})
            STATS['max_in_server'] = max(STATS['max_in_server'], len(S['queue']) + (S['active'] is not None))
            COND.notify_all()
            save_stats()
        NUM = STATS['posts']
        self.send(200, {'prompt_id': body['prompt_id'], 'number': NUM, 'node_errors': {}})


def prequalify():
    """--phase stream: run setup + qualification internally (as if a previous client had done it)."""
    for row in SETUP:
        execute({'d': {'name': row['name'], 'kind': row['kind'], 'params': None}, 'prompt_id': str(uuid.uuid4()),
                 'submit_ns': time.time_ns()})
    for p in QPARAMS:
        with LOCK:
            d = classify(c.build_chunk_graph(p))
        execute({'d': d, 'prompt_id': str(uuid.uuid4()), 'submit_ns': time.time_ns()})
    r = verdict()
    assert r['passed'], r


if a.phase == 'stream':
    threading.Thread(target=preview_writer, daemon=True).start()
    prequalify()
if a.phase != 'stream':
    threading.Thread(target=preview_writer, daemon=True).start()
threading.Thread(target=worker, daemon=True).start()
save_stats()
srv = ThreadingHTTPServer(('127.0.0.1', a.port), H)
srv.daemon_threads = True
(ROOT / 'fake113-ready').write_text(IDENT + '\n')
try:
    srv.serve_forever()
except KeyboardInterrupt:
    pass
