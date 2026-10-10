#!/usr/bin/env python3
"""A fake of the packet 118 continuation stream server, for testing ltx_continuation_client.py --packet 118.

Derived from fake_comfy117.py (recovery/20261009-continuation118-stream sources as the contract): the server
options --snapshot-mode walk|fingerprint (default fingerprint) and --pool-cap GB (default none) are in the status
route ('snapshot_mode', 'decoder_graph_pool_cap_bytes', features timing_split / snapshot_fingerprint /
decoder_graph_pool_cap, snapshot_state) and in every receipt ('server_options'); receipts carry the 118 timing split
('snapshots' in the runtime's order and dual policy, 'node_starts_ns', 'timing_s.submit_split', 'authority_checks',
'turnaround' for anchored chunks); decode records carry 'decoder.pool'; the run dir name carries -sm<walk|fp>-; the
verdict is the 118 qualification_gate.decide(..., server_options=...). Test evidence in ROOT/fake118-stats.json.

The 117 description follows.

Derived from fake_comfy116.py (recovery/20261008-continuation117-stream sources as the contract): the three
frame-anchor levers (--anchor-decode full|cone, --bencode-overlap 0|1, --prep-ahead 0|1; defaults
stream_contract.default_levers(anchor)) are part of every request, the qualification id and the run dir name;
--frames 121 is accepted; receipts carry 'levers' and 'conditioning_sources' (precomputed stages in the graph
and repeat chains, dual-checked in the graph chain); decode records carry 'levers', 'anchor_decode',
'precompute', 'schedule' and the 117 timestamps (cone: anchor decode -> hand-off -> [A] -> go -> [B] ->
display decode -> audio); status adds the levers, the 117 features, anchor_decode_state and precompute_state;
the verdict is the 117 qualification_gate.decide(..., levers=...). --lever-fail precompute makes the repeat
chain's chunk 1 stage B 'native-inline' (the real gate then fails). Test evidence in ROOT/fake118-stats.json.
Never binds port 8188.

    python3 -B fake_comfy117.py --root ROOT --port 18192 [--frames 97] [--anchor-decode cone] ...
"""
import argparse, array, hashlib, json, os, queue, shutil, sys, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.dont_write_bytecode = True
ap = argparse.ArgumentParser()
ap.add_argument('--root', required=True, type=Path)
ap.add_argument('--port', type=int, default=18190)
ap.add_argument('--contract-dir', type=Path,
                default=Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261009-continuation118-stream'))
ap.add_argument('--snapshot-mode', default='fingerprint', choices=('walk', 'fingerprint'))
ap.add_argument('--pool-cap', default=None, help='LTX_DECODER_GRAPH_POOL_CAP_GB (decimal GB) or omitted')
ap.add_argument('--snapshot-fail', action='store_true',
                help='qualification snapshots report no dual walk in fingerprint mode (the real gate then fails)')
ap.add_argument('--frames', type=int, default=49, choices=(49, 97, 121))
ap.add_argument('--anchor-decode', default=None, choices=('full', 'cone'))
ap.add_argument('--bencode-overlap', type=int, default=None, choices=(0, 1))
ap.add_argument('--prep-ahead', type=int, default=None, choices=(0, 1))
ap.add_argument('--lever-fail', default='none', choices=('none', 'precompute'))
ap.add_argument('--placement', default='two-way20-28')
ap.add_argument('--anchor', default='frame', choices=('mixed', 'latent', 'frame', 'guide'))
ap.add_argument('--decoder-graph', type=int, default=1, choices=(0, 1))
ap.add_argument('--audio-delay', type=float, default=0.15, help='seconds the fake audio decode takes')
ap.add_argument('--text-reuse', type=int, default=1, choices=(0, 1))
ap.add_argument('--manifest-sha256', default=None, help='default sha256(fake-packet-<PACKET>-manifest)')
ap.add_argument('--decode-delay', type=float, default=0.2, help='seconds the fake decode thread takes per chunk')
ap.add_argument('--preview-delay', type=float, default=0.2, help='seconds the fake writer takes per MP4')
ap.add_argument('--delay', type=float, default=0.05)
ap.add_argument('--setup-delay', type=float, default=0.05)
ap.add_argument('--phase', choices=('setup', 'stream'), default='setup',
                help='stream: start already qualified (runs the 11 requests + verdict internally)')
ap.add_argument('--qualification', choices=('pass', 'fail', 'lie'), default='pass')
ap.add_argument('--max-prompt-chars', type=int, default=300)
for opt in ('halt-at', 'fail-at', 'fault-at', 'no-preview-at', 'stall-at', 'corrupt-anchor-at', 'advance-at',
            'odd-dir-at', 'corrupt-receipt-at', 'refuse-at', 'preview-fail-at', 'no-decode-at', 'decode-fail-at'):
    ap.add_argument('--' + opt, type=int, default=None)
ap.add_argument('--refuse-code', default='busy')
ap.add_argument('--refuse-status', type=int, default=409)
a = ap.parse_args()
assert a.port != 8188, 'never the live port'
sys.path.insert(0, str(a.contract_dir))
import stream_contract as c          # noqa: E402
import stream_receipts as sr         # noqa: E402
import qualification_gate as qg      # noqa: E402
assert c.PACKET in (118, '118b'), 'fake_comfy118 needs the packet 118 or 118b contract modules'
POOL_CAP = c.parse_pool_cap(a.pool_cap)
SERVER_OPTIONS = {'snapshot_mode': a.snapshot_mode, 'decoder_graph_pool_cap_bytes': POOL_CAP}
_d = c.default_levers(a.anchor)
LEVERS = c.check_levers(a.anchor, a.anchor_decode or _d[0], _d[1] if a.bencode_overlap is None else a.bencode_overlap,
                        _d[2] if a.prep_ahead is None else a.prep_ahead)
LEVER_DICT = dict(zip(c.LEVER_FIELDS, LEVERS))
if a.manifest_sha256 is None:
    a.manifest_sha256 = hashlib.sha256(('fake-packet-%s-manifest' % c.PACKET).encode()).hexdigest()

ROOT = a.root
G = c.geometry(a.frames)
DIAG = sr.border_diagnostic_reference(array.array('f', [0.25, 0.5, 0.75] * (c.ANCHOR_BYTES // 12)).tobytes())
RUN = ROOT / ('encoder-server-continuation-stream-%s-%s-dg%d-ad%s-bo%d-pa%d-sm%s-%s-w1-b1-p1-dxpu2-s256x256-f%d'
              % (c.PACKET, a.anchor, a.decoder_graph, LEVERS[0], LEVERS[1], LEVERS[2],
                 c.SNAPSHOT_MODE_TOKENS[a.snapshot_mode], a.placement, a.frames))
OFF_CHAIN = a.anchor in c.OFF_CHAIN_DECODE
OUT = ROOT / 'output'
if RUN.exists():                      # a new launch never reuses a run dir: archive the old one
    RUN.rename(RUN.with_name(RUN.name + '.old%d' % time.time_ns()))
for d in (RUN / 'receipts', RUN / 'anchors', OUT):
    d.mkdir(parents=True, exist_ok=True)
IDENT = hashlib.sha256(('fake118-%s-%d' % (uuid.uuid4(), os.getpid())).encode()).hexdigest()
PLAN = hashlib.sha256(b'fake-plan-117').hexdigest()
QID = c.qualification_id(a.frames, a.placement, a.anchor, a.decoder_graph, *LEVERS)
(RUN / 'server-identity.json').write_text(json.dumps({'pid': os.getpid(), 'identity': IDENT}) + '\n')

LOCK = threading.RLock()
S = {'phase': 'stream_setup', 'halted': None, 'completed': [], 'active': None, 'queue': [],
     'next': 0, 'stream_completed': 0, 'chains': {}, 'receipts': {}, 'stream_receipts': {}, 'verdict': None,
     'verdict_done': False, 'prompt_ids': set(), 'action_busy': False}
STATS = {'posts': 0, 'refusals': {}, 'max_in_server': 0, 'status_gets': 0, 'receipt_gets': 0, 'decode_gets': 0,
         'resets': [], 'submitted_before_prev_preview': 0, 'submitted_before_prev_decode': 0, 'preview_order': [],
         'decode_order': [], 'stream_order': [], 'reuse_text': {}, 'submit_after_commit_s': [],
         'last_commit_mono': None, 'qual_posts': 0, 'drained_before_gated': 0, 'frame_waits': [],
         'receipt_before_record': 0, 'gated_waited_full': 0}
SETUP = c.setup_graphs()
QPARAMS = c.qualification_params(a.frames, a.text_reuse, a.placement, a.anchor, a.decoder_graph, *LEVERS)
DG = {'captured': 0, 'replays': 0, 'frozen': False}
COND = threading.Condition(LOCK)
DECODES = queue.Queue(maxsize=2)
PREVIEWS = queue.Queue(maxsize=2)
DECODE_STATE = {'pending': 0, 'failed': None, 'written': set(), 'sequence': 0, 'submitted': 0, 'completed': 0,
                'current': None}
PREVIEW_STATE = {'pending': 0, 'failed': None, 'written': set(), 'submitted': 0, 'completed': 0}
FAST = [False]       # --phase stream: the internal prequalification runs without decode/preview delays


def h(*parts):
    return hashlib.sha256('|'.join(str(p) for p in parts).encode()).hexdigest()


def save_stats():
    with LOCK:
        s = dict(STATS)
        s.pop('last_commit_mono', None)
        tmp = ROOT / 'fake118-stats.json.tmp'
        tmp.write_text(json.dumps(s, indent=1) + '\n')
        os.replace(tmp, ROOT / 'fake118-stats.json')


def write_exclusive(path, value):
    # Written under a hidden name and hard-linked into place (exclusive), so a reader that sees the name
    # always sees the complete file (the 115 fake's open('xb') + write let a route read it half-written).
    raw = c.canonical(value) + b'\n'
    path = Path(path)
    tmp = path.with_name('.' + path.name + '.%d.partial' % threading.get_ident())
    with open(tmp, 'xb') as f:
        f.write(raw)
    try:
        os.link(tmp, path)
    finally:
        os.unlink(tmp)
    return hashlib.sha256(raw).hexdigest()


def halt(reason):
    with LOCK:
        if S['halted'] is None:
            S['halted'] = reason
            (RUN / 'stream-halt.json').write_text(json.dumps({'reason': reason}))


def anchor_bytes(kind, seed_hex):
    """Finite little-endian F32 anchor content derived from a hash (a real file of the real size)."""
    vals = [b / 255.0 for b in bytes.fromhex(seed_hex)]          # 32 floats in [0, 1]
    n = {'latent': c.LATENT_ANCHOR_BYTES, 'mixed': c.LATENT_ANCHOR_BYTES, 'guide': c.GUIDE_ANCHOR_BYTES,
         'frame': c.ANCHOR_BYTES}[kind] // 4
    arr = array.array('f', vals * (n // len(vals)))
    assert sys.byteorder == 'little' and len(arr) * 4 == n * 4
    return arr.tobytes()


def write_anchor_file(name, raw, kind):
    path = RUN / 'anchors' / (name + {'latent': '.latent.f32', 'mixed': '.latent.f32', 'guide': '.guide.f32'}
                              .get(kind, '.f32'))
    with open(path, 'xb') as f:
        f.write(raw)
    out = {'kind': kind, 'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
           'dtype': 'F32', 'byte_order': 'little'}
    if kind in ('latent', 'mixed', 'guide'):
        parts, sizes = ((c.GUIDE_ANCHOR_PARTS, c.GUIDE_ANCHOR_PART_BYTES) if kind == 'guide' else
                        (c.LATENT_ANCHOR_PARTS, c.LATENT_ANCHOR_PART_BYTES))
        layout, off = [], 0
        for part, shape in parts:
            size = sizes[part]
            layout.append({'part': part, 'shape': list(shape), 'offset': off, 'bytes': size,
                           'source': ('367' if part == 'A' else '369') + ' video_latent slot %d' % G['latent_anchor_slot']})
            off += size
        out.update(slot=G['latent_anchor_slot'], layout=layout)
        if kind == 'mixed':
            out['frame'] = {'writer': 'decode thread', 'path': str(RUN / 'anchors' / (name + '.f32')),
                            'record': str(RUN / 'receipts' / ('decode-%s.json' % name))}
        if kind == 'guide':
            out.update(slots=[G['latent_anchor_slot'] - 1, G['latent_anchor_slot']], latent_idx=c.GUIDE_LATENT_IDX)
    else:
        out.update(frame_index=G['anchor_frame_index'], shape=list(c.ANCHOR_SHAPE))
    return out


def tensor_rows(names, shapes, params, variant):
    key = params['stream_seq'] if params['kind'] == 'stream' else 'q'
    return {t: {'shape': list(shapes[t]), 'dtype': 'torch.float32', 'finite': True,
                'sha256': h(params['chunk_index'], params['seed'], params['prompt'], key, variant, t)}
            for t in names}


# ---- decode thread + preview writer ---------------------------------------------------------
def decoder_block(job, images_sha):
    p = job['params']
    graph = a.decoder_graph == 1 and p['kind'] != 'qualify-eager'
    first = graph and DG['captured'] == 0
    if first:
        DG['captured'] = 2 if POOL_CAP is None else 1
    elif graph:
        DG['replays'] += 1
    sigs = {'forward_pre_diffusion': 1 if DG['captured'] else 0, 'forward_diff_step': 1 if DG['captured'] else 0}
    return {'flag': a.decoder_graph, 'mode': 'graph' if graph else 'eager',
            'reference': ({'mode': 'eager-uncached', 'equal': True, 'images_sha256': images_sha, 'seconds': 0.01}
                          if graph and p['kind'] == 'qualify-graph' else None),
            'video_decode_s': 0.01, 'new_captures': DG['captured'] if first else 0,
            'captured_graphs_total': DG['captured'],
            'pool': None if not a.decoder_graph else {
                'cap_bytes': POOL_CAP, 'growth_bytes': 3 * 10 ** 9 if DG['captured'] else 0,
                'captured': ([] if not DG['captured'] else ['forward_diff_step', 'forward_pre_diffusion']
                             if POOL_CAP is None else ['forward_pre_diffusion']),
                'capped': [] if POOL_CAP is None or not DG['captured'] else ['forward_diff_step'],
                'capped_calls': {}, 'rule': 'fake'},
            'signatures': sigs if a.decoder_graph else {}, 'replays': {'forward_pre_diffusion': DG['replays'],
                                                                     'forward_diff_step': DG['replays']},
            'frozen': DG['frozen'] if a.decoder_graph else None}


def make_decode_record(job, t):
    p = job['params']
    images = tensor_rows(sr.DECODED, G['decoded_shapes'], p, job['variant'])
    with LOCK:
        DECODE_STATE['sequence'] += 1
        sequence = DECODE_STATE['sequence']
    timing = {k: None for k in sr.DECODE_TIMING_KEYS}
    timing.update({'submit': job['submit'], 'anchor_ready': job['anchor_ready'], 'decode_queued': job['queued'],
                   'decode_start': t['start'], 'video_done': t['video_done'], 'audio_done': t['audio_done'],
                   'decode_done': t['audio_done'], 'hashed': t['hashed']})
    for k in sr.OPTIONAL_DECODE_TIMING:
        timing[k] = t.get(k)
    timing['record_staged'] = time.time_ns()
    cone = live(p) and LEVERS[0] == 'cone'
    frame_anchor = None
    last = job['last_frame_sha256']
    if a.anchor == 'frame':
        frame_anchor = {'sha256': last, 'bytes': c.ANCHOR_BYTES, 'path': job['anchor_out']['path']}
    elif a.anchor == 'mixed':
        frame_anchor = {'sha256': last, 'bytes': c.ANCHOR_BYTES, 'path': str(RUN / 'anchors' / (job['name'] + '.f32'))}
    rec = {'schema': sr.DECODE_SCHEMA, 'run_name': job['name'], 'prompt_id': job['prompt_id'], 'kind': p['kind'],
           'stream_seq': p['stream_seq'], 'chunk_index': p['chunk_index'], 'frames': a.frames, 'anchor': a.anchor,
           'device': 'xpu:3', 'order': 'fifo', 'sequence': sequence, 'thread': 'ltx118-decode',
           'sample_rate': c.SAMPLE_RATE, 'tensors': images, 'last_frame_sha256': last,
           'anchor_diagnostics': DIAG,
           'sharpness': sr.sharpness_from_values({i: (0.97 if i < 6 else 1.0) for i in G['sharpness_frames']}, a.frames),
           'capture': None if p['kind'] == 'stream' else
           {'path': job['capture_path'], 'prewrite': {'name': job['name'], 'prompt_id': job['prompt_id']}},
           'frame_anchor': frame_anchor, 'decoder': decoder_block(job, images['images']['sha256']),
           'xpu3_free_before_decode': 12 * 2 ** 30,
           'levers': dict(LEVER_DICT),
           'anchor_decode': {'mode': 'cone' if cone else 'full', 'flag': LEVERS[0], 'seconds': 0.01,
                             'last_frame_sha256': last, 'display_last_frame_sha256': last,
                             'equal': True if cone else None, 'display_seconds': 0.02 if cone else None},
           'precompute': t.get('precompute') or None,
           'schedule': {'gated': p['kind'] in c.GATED_KINDS, 'levers_live': live(p), 'commit': None,
                        'commit_wait_s': None, 'go': t.get('go_kind'), 'go_wait_s': None},
           'preview': {'path': str(job['preview']), 'record': str(RUN / 'receipts' / ('preview-%s.json' % job['name']))},
           'timing_ns': timing,
           'timing_s': {'queue_wait': sr.seconds(timing, 'decode_queued', 'decode_start'),
                        'video_decode': sr.seconds(timing, 'decode_start', 'video_done'),
                        'precompute_a': sr.seconds(timing, 'precompute_a_start', 'precompute_a_done'),
                        'precompute_b': sr.seconds(timing, 'precompute_b_start', 'precompute_b_done'),
                        'anchor_ready_to_go': sr.seconds(timing, 'anchor_ready', 'go'),
                        'display_decode': sr.seconds(timing, 'display_start', 'display_done'),
                        'decode': sr.seconds(timing, 'decode_start', 'decode_done'),
                        'anchor_ready_to_decode_done': sr.seconds(timing, 'anchor_ready', 'decode_done'),
                        'submit_to_decode_done': sr.seconds(timing, 'submit', 'decode_done')}}
    sr.validate_decode_record(rec)
    return rec


def live(p):
    return a.anchor == 'frame' and p['kind'] != 'qualify-eager'


def commit_decode(job, rec):
    write_exclusive(RUN / 'receipts' / ('decode-%s.json' % job['name']), rec)
    with LOCK:
        DECODE_STATE['written'].add(job['name'])
        DECODE_STATE['completed'] += 1
        STATS['decode_order'].append(job['name'])
    save_stats()


def submit_preview(job, timing):
    with LOCK:
        PREVIEW_STATE['pending'] += 1
        PREVIEW_STATE['submitted'] += 1
    PREVIEWS.put(dict(job, decode_timing=timing, preview_queued=time.time_ns()))


def decode_failed(job):
    name = job['name']
    with LOCK:
        DECODE_STATE['failed'] = 'RuntimeError: injected decode failure at %s' % name
    (RUN / ('stream-decode-failure-%s.json' % name)).write_text(json.dumps({'run_name': name, 'error': 'injected'}))
    halt('RuntimeError: Decode failed for %s: injected' % name)


def decode_worker():
    """116a order: video -> (frame) anchor + hand-off -> audio -> hashes -> record -> preview."""
    while True:
        job = DECODES.get()
        try:
            if DECODE_STATE['failed'] is not None:
                continue
            tm = {'start': time.time_ns()}
            with LOCK:
                DECODE_STATE['current'] = job['name']
            time.sleep(0 if job.get('fast') else a.decode_delay)
            tm['video_done'] = time.time_ns()
            seq = job['seq']
            if seq is not None and seq == a.decode_fail_at:
                decode_failed(job)
                continue
            if a.anchor == 'frame':
                job['anchor_out'] = write_anchor_file(job['name'], job['frame_raw'], 'frame')
                job['anchor_ready'] = time.time_ns()
                job['video_done'] = tm['video_done']
                job['anchor_event'].set()          # the chain continues from here
                p = job['params']
                if live(p):
                    pre = {}
                    if LEVERS[2]:
                        tm['precompute_a_start'] = time.time_ns()
                        tm['precompute_a_done'] = time.time_ns()
                        pre['A'] = {'stage': 'A', 'state': 'done', 'anchor_sha256': job['last_frame_sha256']}
                    if LEVERS[0] == 'cone' or LEVERS[1]:
                        if p['kind'] not in c.GATED_KINDS:
                            time.sleep(0 if job.get('fast') else 0.02)    # the go wait (successor's sampler A)
                            tm['go_kind'] = 'sampler-a-start'
                        tm['go'] = time.time_ns()
                    if LEVERS[1]:
                        tm['precompute_b_start'] = time.time_ns()
                        tm['precompute_b_done'] = time.time_ns()
                        pre['B'] = {'stage': 'B', 'state': 'done', 'anchor_sha256': job['last_frame_sha256']}
                    if LEVERS[0] == 'cone':
                        tm['display_start'] = time.time_ns()
                        time.sleep(0 if job.get('fast') else a.decode_delay)
                        tm['display_done'] = time.time_ns()
                    tm['precompute'] = pre
            elif a.anchor == 'mixed':
                with open(RUN / 'anchors' / (job['name'] + '.f32'), 'xb') as f:
                    f.write(job['frame_raw'])
            time.sleep(0 if job.get('fast') else a.audio_delay)
            tm['audio_done'] = time.time_ns()
            tm['hashed'] = time.time_ns()
            rec = make_decode_record(job, tm)
            if seq is not None and seq == a.no_decode_at:
                continue                    # never committed; no preview behind it either
            commit_decode(job, rec)
            job['record'] = rec
            submit_preview(job, dict(rec['timing_ns'], record_written=time.time_ns()))
        finally:
            job['anchor_event'].set()
            job['done'].set()
            with LOCK:
                DECODE_STATE['pending'] -= 1
                DECODE_STATE['current'] = None
            DECODES.task_done()


def preview_writer():
    while True:
        job = PREVIEWS.get()
        try:
            time.sleep(0 if job.get('fast') else a.preview_delay)
            name, seq, final = job['name'], job['seq'], job['preview']
            if PREVIEW_STATE['failed'] is not None:
                continue
            if seq is not None and seq == a.preview_fail_at:
                PREVIEW_STATE['failed'] = name
                (RUN / ('stream-preview-failure-%s.json' % name)).write_text(json.dumps({'run_name': name}))
                halt('RuntimeError: Preview write failed for %s' % name)
                continue
            start = time.time_ns()
            tmp = final.with_name('.' + final.name + '.partial')
            tmp.write_bytes(b'\0\0\0\x18ftypmp42' + name.encode() * 20 + str(a.frames).encode())
            os.link(tmp, final)
            os.unlink(tmp)
            raw = final.read_bytes()
            written = time.time_ns()
            STATS['preview_order'].append(name)
            if seq is not None and seq == a.no_preview_at:
                continue
            dt = job['decode_timing']
            t = {'submit': job['submit'], 'video_done': dt['video_done'], 'anchor_ready': dt['anchor_ready'],
                 'audio_done': dt['audio_done'], 'decode_done': dt['decode_done'], 'hashed': dt['hashed'],
                 'record_written': dt['record_written'], 'preview_queued': job['preview_queued'],
                 'write_start': start, 'preview_written': written}
            rec = {'schema': sr.PREVIEW_SCHEMA, 'run_name': name, 'prompt_id': job['prompt_id'],
                   'path': str(final), 'relative_to_output_directory': str(final.relative_to(OUT)),
                   'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'container': 'mp4',
                   'written': True, 'order': 'fifo', 'frames': a.frames, 'fps': 24, 'lossy': True,
                   'includes_overlap_frame': job['anchored'] and a.anchor in c.SLOT0_ANCHORS,
                   'timing_ns': t,
                   'timing_s': {'submit_to_preview_written': None if t['submit'] is None else
                                round((written - t['submit']) / 1e9, 6),
                                'decode_done_to_preview_written': round((written - t['decode_done']) / 1e9, 6),
                                'queue_wait': round((start - t['preview_queued']) / 1e9, 6),
                                'write': round((written - start) / 1e9, 6)}}
            sr.validate_preview_record(rec)
            write_exclusive(RUN / 'receipts' / ('preview-%s.json' % name), rec)
            with LOCK:
                PREVIEW_STATE['written'].add(name)
                PREVIEW_STATE['completed'] += 1
            save_stats()
        finally:
            with LOCK:
                PREVIEW_STATE['pending'] -= 1
            PREVIEWS.task_done()


def decode_summary():
    with LOCK:
        return {'submitted': DECODE_STATE['submitted'], 'completed': DECODE_STATE['completed'],
                'pending': DECODE_STATE['pending'], 'current': DECODE_STATE['current'],
                'failed': DECODE_STATE['failed'], 'skipped_after_failure': [], 'maxsize': 2}


def preview_summary():
    with LOCK:
        return {'submitted': PREVIEW_STATE['submitted'], 'completed': PREVIEW_STATE['completed'],
                'pending': PREVIEW_STATE['pending'], 'failed': PREVIEW_STATE['failed'],
                'skipped_after_failure': [], 'maxsize': 2}


# ---- admission ------------------------------------------------------------------------------
class Refusal(Exception):
    def __init__(self, code, msg, status=409):
        super().__init__(msg)
        self.code, self.status = code, status


def classify(graph):
    if S['phase'] == 'stream_setup':
        row = SETUP[len(S['completed'])]
        if c.sha256(c.canonical(graph)) != c.sha256(c.canonical(row['graph'])):
            raise Refusal('order', 'Next request must be setup graph ' + row['name'])
        return {'name': row['name'], 'kind': row['kind'], 'params': None}
    try:
        params = c.parse_chunk_graph(graph, a.frames, a.placement, a.anchor, a.decoder_graph, LEVERS)
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
        if params['reuse_text']:
            raise Refusal('text-reuse-rule', 'A reset chunk always encodes its prompt')
    else:
        if state is None or state['last_chunk'] != params['chunk_index'] - 1:
            raise Refusal('order', 'Chain %s expects another chunk' % chain)
        if params['kind'] == 'stream' and params['predecessor_anchor_sha256'] != state['anchor_sha256']:
            raise Refusal('stale-anchor', 'predecessor_anchor_sha256 is not the anchor of %s' % state['run_name'])
        same = c.text_sha256(params['prompt']) == state['text_sha256']
        expected = int(bool(a.text_reuse) and same and params['kind'] != 'qualify-eager')
        if params['reuse_text'] != expected:
            raise Refusal('text-reuse-rule', 'reuse_text must be %d for this chunk (server text_reuse=%d)'
                          % (expected, a.text_reuse))
    if params['reuse_text']:
        if state is None or state['text_sha256'] != c.text_sha256(params['prompt']):
            raise Refusal('text-cache-missing', 'No cached conditioning for this prompt on this chain')
    elif len(params['prompt']) > a.max_prompt_chars and S['phase'] == 'stream':
        raise Refusal('window-not-qualified', 'Prompt uses text window 128; this server qualified [64]')
    return {'name': name, 'kind': params['kind'], 'params': params, 'chain': chain}


def fault():
    return ((ROOT / 'FAULT.json').exists() or (RUN / 'stream-halt.json').exists() or
            PREVIEW_STATE['failed'] is not None or DECODE_STATE['failed'] is not None)


def admit(body):
    if S['action_busy']:
        raise Refusal('busy', 'An action is running')
    if S['halted'] is not None or fault():
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
    return classify(body['prompt'])


# ---- execution ------------------------------------------------------------------------------
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
    kind = params['kind']
    drained = False
    if kind in c.GATED_KINDS:
        DECODES.join()                 # no decode beside a gated (capturing) request
        drained = True
        STATS['drained_before_gated'] += 1
    decode_at_start = {'drained': drained, 'pending': DECODE_STATE['pending'], 'current': DECODE_STATE['current']}
    if seq is not None and seq == a.stall_at:
        while True:
            time.sleep(3600)
    time.sleep(a.delay)
    with LOCK:
        if seq is not None and seq == a.halt_at:
            halt('RuntimeError: injected halt at %s' % name)
            S['active'] = None
            return
        if seq is not None and seq == a.fail_at:
            (RUN / ('stream-failure-%s.json' % name)).write_text(json.dumps({'run_name': name, 'error': 'injected'}))
            halt('RuntimeError: injected failure at %s' % name)
            S['active'] = None
            return
        if seq is not None and seq == a.fault_at:
            (ROOT / 'FAULT.json').write_text(json.dumps({'fault': 'injected'}))
            S['active'] = None
            return
        chain = d['chain']
        prev = S['chains'].get(chain)
    variant = 'bad' if (a.qualification in ('fail', 'lie') and kind == 'qualify-repeat'
                        and params['chunk_index'] == 1) else ''
    anchored = c.anchored(params)
    tensors = tensor_rows(sr.LATENTS, G['latent_shapes'], params, variant)
    preview = preview_for(name, seq)
    capture_path = str(OUT / 'validation' / name / 'tensors.safetensors')
    timing = {k: None for k in sr.TIMING_KEYS}
    timing.update(submit=submit_ns, execution_start=t_exec, text_start=t_exec + 100_000,
                  sampler_a_start=t_exec + 1_000_000, stage_a_done=t_exec + 1_500_000,
                  upsampler_start=t_exec + 1_600_000, condition_b_start=t_exec + 1_700_000 if anchored else None,
                  concat_b_start=t_exec + 1_800_000, sampler_b_start=t_exec + 2_000_000,
                  stage_b_done=t_exec + 3_000_000, output_start=t_exec + 3_100_000)
    job = {'name': name, 'prompt_id': pid, 'params': params, 'seq': seq, 'variant': variant, 'submit': submit_ns,
           'preview': preview, 'capture_path': capture_path, 'anchored': anchored, 'fast': FAST[0],
           'anchor_event': threading.Event(), 'done': threading.Event(), 'record': None}
    decode_state = 'queued'
    frame_in = None
    if a.anchor == 'mixed' and anchored:
        # Stage B waits (bounded) for the predecessor's decode record and reads its decoded frame.
        timing['frame_wait_start'] = time.time_ns()
        deadline = time.monotonic() + 60
        while prev['run_name'] not in DECODE_STATE['written']:
            if DECODE_STATE['failed'] is not None or time.monotonic() > deadline:
                (RUN / ('stream-failure-%s.json' % name)).write_text(json.dumps({'run_name': name,
                                                                                 'error': 'predecessor decode'}))
                halt('RuntimeError: predecessor decode failed or did not arrive for %s' % name)
                with LOCK:
                    S['active'] = None
                return
            time.sleep(0.01)
        raw_record = (RUN / 'receipts' / ('decode-%s.json' % prev['run_name'])).read_bytes()
        prev_record = json.loads(raw_record)
        timing['frame_ready'] = time.time_ns()
        frame_in = {'sha256': prev_record['frame_anchor']['sha256'], 'path': prev_record['frame_anchor']['path'],
                    'source_run_name': prev['run_name'], 'decode_record_sha256': hashlib.sha256(raw_record).hexdigest(),
                    'decode_sequence': prev_record['sequence'],
                    'waited_s': round((timing['frame_ready'] - timing['frame_wait_start']) / 1e9, 6)}
        STATS['frame_waits'].append(frame_in['waited_s'])
    job['frame_raw'] = anchor_bytes('frame', h('frame-anchor', tensors['video_latent']['sha256']))
    if OFF_CHAIN:
        raw = anchor_bytes(a.anchor, h('latent-anchor', tensors['video_latent']['sha256'],
                                       tensors['stage_a_latent']['sha256']))
        anchor_out = write_anchor_file(name, raw, a.anchor)
        timing['anchor_ready'] = time.time_ns()
        job['last_frame_sha256'] = (hashlib.sha256(job['frame_raw']).hexdigest() if a.anchor == 'mixed' else
                                    h('last-frame', tensors['video_latent']['sha256']))
        job['anchor_ready'] = timing['anchor_ready']
    else:
        job['last_frame_sha256'] = hashlib.sha256(job['frame_raw']).hexdigest()
        job['anchor_ready'] = None
    job['queued'] = timing['decode_queued'] = time.time_ns()
    with LOCK:
        DECODE_STATE['pending'] += 1
        DECODE_STATE['submitted'] += 1
    DECODES.put(job)
    gated = kind in c.GATED_KINDS
    if gated:
        job['done'].wait(120)
        STATS['gated_waited_full'] += 1
    elif a.anchor == 'frame':
        job['anchor_event'].wait(120)      # 116a: the video decode and the anchor file only
    if (a.anchor == 'frame' and 'anchor_out' not in job) or (gated and job['record'] is None and
                                                             not (seq is not None and seq == a.no_decode_at)):
        (RUN / ('stream-failure-%s.json' % name)).write_text(json.dumps({'run_name': name, 'error': 'decode'}))
        halt('RuntimeError: Decode failed for %s (chain)' % name)
        with LOCK:
            S['active'] = None
        return
    if a.anchor == 'frame':
        anchor_out = job['anchor_out']
        timing.update(video_done=job['video_done'], anchor_ready=job['anchor_ready'])
    if gated and job['record'] is not None:
        timing['decode_done'] = job['record']['timing_ns']['decode_done']
    decode_state = sr.decode_state(kind, a.anchor)
    if kind == 'stream' and a.anchor == 'frame' and name not in DECODE_STATE['written']:
        STATS['receipt_before_record'] += 1
    with LOCK:
        corrupt = seq is not None and seq in (a.corrupt_anchor_at, a.corrupt_receipt_at)
        real_anchor = anchor_out['sha256']
        reported = dict(anchor_out, sha256=h('corrupt', real_anchor)) if corrupt else anchor_out
        timing['receipt_staged'] = time.time_ns()
        prior = prior_decode = None
        if prev is not None:
            if prev['run_name'] in PREVIEW_STATE['written']:
                prior = {'run_name': prev['run_name']}
            if prev['run_name'] in DECODE_STATE['written']:
                prior_decode = {'run_name': prev['run_name']}
        pin = guide_pin = None
        row = lambda k: {'bytes_equal': True, 'elements': 128 * (16 if k == 'A' else 64), 'differing_elements': 0,
                         'differing_all_signed_zero': True, 'diagnostic_only': True}
        if anchored and a.anchor == 'latent':
            pin = {k: row(k) for k in ('A', 'B')}
        elif anchored and a.anchor == 'mixed':
            pin = {'A': row('A')}
        elif anchored and a.anchor == 'guide':
            guide_pin = {k: row(k) for k in ('A', 'B')}
        gate_mode = 'original' if kind == 'qualify-eager' else 'graph'
        routes = 0 if kind == 'qualify-eager' else 48
        new = 96 if (kind == 'qualify-graph' and params['chunk_index'] < 2) else 0
        receipt = {
            'schema': sr.SCHEMA, 'run_name': name, 'prompt_id': pid, 'kind': kind, 'stream_seq': params['stream_seq'],
            'chunk_index': params['chunk_index'], 'scene_id': params['scene_id'], 'seed': params['seed'],
            'frames': a.frames, 'placement': a.placement, 'anchor': a.anchor, 'decoder_graph': a.decoder_graph,
            'levers': dict(LEVER_DICT), 'conditioning_sources': conditioning_sources(params, kind, anchored),
            'server_options': dict(SERVER_OPTIONS), 'snapshots': snapshots_118(params, kind, anchored, timing),
            'node_starts_ns': {'344': timing['sampler_a_start']} if timing.get('sampler_a_start') else {},
            'authority_checks': {'healthy_calls': 30, 'healthy_s': 0.13, 'plan_digest_s': 0.12,
                                 'status_route_calls': 12, 'status_route_s': 0.02, 'window': 'fake'},
            'turnaround': None if not anchored or prev is None else {
                'predecessor_run_name': prev['run_name'],
                'marks_ns': {'receipt_staged': None, 'commit': None, 'commit_written': None, 'executor_exit': None,
                             'first_served': None, 'admission_received': None, 'submit': timing['submit']},
                'receipt_polls_before_served': 0,
                'split': sr.turnaround_split({'submit': timing['submit']}), 'commit_to_executor_exit_s': None},
            'prompt_sha256': c.text_sha256(params['prompt']),
            'prompt_changed': None if params['chunk_index'] == 0 else
            (c.text_sha256(params['prompt']) != prev['text_sha256']),
            'anchored': anchored, 'reset': bool(params['reset']),
            'reset_predecessor_anchor_sha256': params['predecessor_anchor_sha256'] if params['reset'] else None,
            'reuse_text': params['reuse_text'], 'server_text_reuse': a.text_reuse,
            'text': {'reused': bool(params['reuse_text']), 'tensors': [{'sha256': h('text', params['prompt'])}]},
            'tensors': tensors, 'slot0_pin': pin, 'guide_pin': guide_pin,
            'anchor_in': None if not anchored else
            dict({'kind': a.anchor, 'sha256': prev['anchor_sha256'], 'path': prev['anchor_path'],
                  'source_run_name': prev['run_name']}, **({'frame': frame_in} if frame_in else {})),
            'anchor_out': reported,
            'delivery': sr.delivery(params['chunk_index'], a.frames, anchored, a.anchor),
            'decode': {'state': decode_state, 'device': 'xpu:3',
                       'record': str(RUN / 'receipts' / ('decode-%s.json' % name)),
                       'queue_depth_at_submit': DECODE_STATE['pending'], 'submit_blocked_s': 0.0},
            'preview': {'path': str(preview), 'relative_to_output_directory': str(preview.relative_to(OUT)),
                        'bytes': None, 'state': 'queued', 'record': str(RUN / 'receipts' / ('preview-%s.json' % name)),
                        'container': 'mp4', 'lossy': True, 'fps': 24, 'frames': a.frames,
                        'includes_overlap_frame': anchored and a.anchor in c.SLOT0_ANCHORS},
            'predecessor_preview': prior, 'predecessor_decode': prior_decode,
            'decode_at_start': decode_at_start,
            'capture': {'path': capture_path, 'writer': 'decode thread',
                        'record': str(RUN / 'receipts' / ('decode-%s.json' % name))} if kind in c.CAPTURE_KINDS else None,
            'timing_ns': timing,
            'timing_s': {'submit_to_sampler_start': sr.seconds(timing, 'submit', 'sampler_a_start'),
                         'submit_split': sr.submit_split(timing),
                         'sampler_b': sr.seconds(timing, 'sampler_b_start', 'stage_b_done'),
                         'frame_wait': sr.seconds(timing, 'frame_wait_start', 'frame_ready'),
                         'submit_to_anchor_ready': sr.seconds(timing, 'submit', 'anchor_ready'),
                         'anchor_ready_to_receipt_staged': sr.seconds(timing, 'anchor_ready', 'receipt_staged'),
                         'decode_in_chain': (sr.seconds(timing, 'decode_queued', 'anchor_ready')
                                             if a.anchor == 'frame' else sr.seconds(timing, 'decode_queued', 'decode_done')),
                         'video_decode_in_chain': sr.seconds(timing, 'decode_queued', 'video_done'),
                         'anchor_decode_in_chain': (sr.seconds(timing, 'decode_queued', 'video_done')
                                                    if a.anchor == 'frame' else None),
                         'video_done_to_anchor_ready': sr.seconds(timing, 'video_done', 'anchor_ready'),
                         'submit_to_decode_done': sr.seconds(timing, 'submit', 'decode_done'),
                         'submit_to_preview_written': None},
            'graph': {'gate_mode': gate_mode, 'routes': routes, 'signatures_per_route': 0 if routes == 0 else 4,
                      'new_captures': new, 'captures_frozen': kind == 'stream'},
            'memory': {}, 'storage': {'free_bytes': shutil.disk_usage(ROOT).free},
            'sanity': {'finite': True, 'shapes': True, 'anchor_chain': True},
            'plan_sha256': PLAN, 'qualification_id': QID, 'qualification_verdict_sha256': S['verdict'],
            'server_identity_sha256': IDENT, 'runtime_manifest_sha256': a.manifest_sha256}
        sr.validate_receipt(receipt)
        if params['reset']:
            STATS['resets'].append(params['stream_seq'])
        if seq is not None:
            STATS['reuse_text'][str(seq)] = params['reuse_text']
        path = RUN / 'receipts' / ('receipt-%s.json' % name)
        sha = write_exclusive(path, dict(receipt, committed=True, commit_ns=time.time_ns()))
        S['chains'][chain] = {'last_chunk': params['chunk_index'], 'run_name': name, 'anchor_sha256': real_anchor,
                              'anchor_path': anchor_out['path'], 'text_sha256': c.text_sha256(params['prompt']),
                              'previous_anchor_path': prev['anchor_path'] if prev else None,
                              'reported_anchor': reported['sha256'] if (seq is not None and seq == a.corrupt_anchor_at)
                              else real_anchor}
        if kind == 'stream':
            S['stream_receipts'][name] = {'path': str(path), 'sha256': sha}
            while len(S['stream_receipts']) > 64:
                S['stream_receipts'].pop(next(iter(S['stream_receipts'])))
            S['next'] += 1
            S['stream_completed'] += 1
            if prev and prev['previous_anchor_path']:
                try:
                    os.unlink(prev['previous_anchor_path'])   # the two newest anchors are kept
                except FileNotFoundError:
                    pass
            if seq is not None and seq == a.advance_at:
                S['next'] += 1        # as if another client had used the next stream_seq
            STATS['last_commit_mono'] = time.monotonic()
        else:
            S['receipts'][name] = {'path': str(path), 'sha256': sha}
            S['completed'].append(name)
        S['prompt_ids'].add(pid)
    with LOCK:
        S['active'] = None
    save_stats()


def snapshots_118(params, kind, anchored, timing):
    """Packet118: the four-card snapshots the runtime takes (labels in order), the launch mode and the dual policy."""
    middle = {'frame': ['A-before', 'A-after', 'B-before', 'B-after'],
              'mixed': ['B-before', 'B-after']}.get(a.anchor, []) if anchored else []
    seq = params['stream_seq']
    dual = a.snapshot_mode == 'fingerprint' and (kind != 'stream' or seq % 20 == 0)
    if a.snapshot_fail and kind != 'stream':
        dual = False
    base = timing.get('submit') or time.time_ns()
    return [{'label': label, 'mode': a.snapshot_mode, 'dual': dual, 'agree': True if dual else None,
             'start_ns': base + 1000 * i, 'end_ns': base + 1000 * i + 500, 'seconds': 5e-7,
             'parts_s': {}, 'min_margin_bytes': 2 ** 31} for i, label in enumerate(['request-before'] + middle +
                                                                                    ['request-after'])]


def conditioning_sources(params, kind, anchored):
    """Packet117 receipt field: where each anchored frame chunk's stage encodes came from."""
    if a.anchor != 'frame' or not anchored:
        return None
    out = {}
    for stage, lever, on in (('A', 'prep_ahead', LEVERS[2]), ('B', 'bencode_overlap', LEVERS[1])):
        use = bool(on) and kind != 'qualify-eager'
        row = {'stage': stage, 'lever': lever, 'lever_on': use, 'source': 'native', 'reason': None,
               'waited_s': None, 'dual_equal': None, 'precompute': None}
        if use:
            if a.lever_fail == 'precompute' and kind == 'qualify-repeat' and params['chunk_index'] == 1 and stage == 'B':
                row.update(source='native-inline', reason='cancelled')
            else:
                row.update(source='precomputed', waited_s=0.0,
                           precompute={'stage': stage, 'state': 'done', 'source_run_name': None},
                           dual_equal=True if kind == 'qualify-graph' else None)
        out[stage] = row
    return out


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
    DECODES.join()
    PREVIEWS.join()
    with LOCK:
        receipts, decodes, captures, bindings = [], {}, {}, {}
        for p in QPARAMS:
            name = c.run_name(p)
            r = json.loads(Path(S['receipts'][name]['path']).read_text())
            receipts.append(r)
            dpath = RUN / 'receipts' / ('decode-%s.json' % name)
            if not dpath.is_file():
                raise Refusal('action-failed', 'Qualification decode or preview record missing: ' + name)
            raw = dpath.read_bytes()
            decodes[name] = json.loads(raw)
            bindings[name] = {'path': str(dpath), 'sha256': hashlib.sha256(raw).hexdigest()}
            dt = decodes[name]['tensors']
            captures[name] = {'path': r['capture']['path'], 'bytes': 1,
                              'tensors': {'images': dt['images']['sha256'], 'waveform': dt['waveform']['sha256'],
                                          'video_latent': r['tensors']['video_latent']['sha256'],
                                          'audio_latent': r['tensors']['audio_latent']['sha256']},
                              'last_frame_sha256': decodes[name]['last_frame_sha256'], 'header_digest': 'fake'}
        v = qg.decide(receipts, decodes, captures, PLAN, a.frames, a.text_reuse, a.placement, a.anchor,
                      decoder_graph=a.decoder_graph, references=None, levers=LEVERS,
                      server_options=SERVER_OPTIONS)
        if a.qualification == 'lie':
            v = dict(v, passed=True, failures=[],
                     exact_replay=[dict(x, all_identical=True) for x in v['exact_replay']])
        v.update(receipts={n: S['receipts'][n] for n in S['receipts']}, decode_records=bindings,
                 captures=captures, decoder=decode_summary(), preview_writer=preview_summary(), time_ns=time.time_ns())
        sha = write_exclusive(RUN / 'stream-qualification-verdict.json', v)
        if not v['passed']:
            halt('RuntimeError: Qualification failed: ' + '; '.join(v['failures']))
            return {'passed': False, 'failures': v['failures'], 'verdict_sha256': sha}
        S['verdict'] = sha
        S['phase'] = 'stream'
        DG['frozen'] = True
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
                'frames': a.frames, 'placement': a.placement, 'anchor': a.anchor, 'qualification_id': QID,
                'decoder_graph': a.decoder_graph, 'anchor_decode': LEVERS[0], 'bencode_overlap': LEVERS[1],
                'prep_ahead': LEVERS[2], 'snapshot_mode': a.snapshot_mode, 'decoder_graph_pool_cap_bytes': POOL_CAP,
                'snapshot_state': {'mode': a.snapshot_mode, 'fake': True},
                'anchor_decode_state': None if LEVERS[0] != 'cone' else {'fake': True},
                'precompute_state': {'anchor_sha256': None, 'entries': {}, 'history': []},
                'decoder_graph_state': None if not a.decoder_graph else {
                    'signatures': {'forward_pre_diffusion': int(bool(DG['captured'])),
                                   'forward_diff_step': int(bool(DG['captured']))},
                    'captured_graphs': DG['captured'], 'frozen': DG['frozen']},
                'chain': None if chain is None else {'last_stream_seq': chain['last_chunk'],
                                                     'last_run_name': chain['run_name'],
                                                     'anchor_sha256': chain['reported_anchor'],
                                                     'prompt_sha256': chain['text_sha256']},
                'server_identity_sha256': IDENT, 'runtime_manifest_sha256': a.manifest_sha256, 'plan_sha256': PLAN,
                'fault': fault(), 'receipt_dir': str(RUN / 'receipts'),
                'qualified_text_windows': [64] if S['phase'] == 'stream' else None,
                'output_directory': str(OUT), 'packet': c.PACKET,
                'features': {'latent_anchor': a.anchor == 'latent', 'mixed_anchor': a.anchor == 'mixed',
                             'guide_anchor': a.anchor == 'guide', 'frame_anchor': a.anchor == 'frame',
                             'decode_thread': True, 'async_preview': True,
                             'chain_reset': True, 'anchor_diagnostics': True, 'sharpness_diagnostic': True,
                             'chunk_length_choice': True, 'text_reuse_default_on': True, 'video_first_handoff': True,
                             'decoder_graph': a.decoder_graph == 1, 'cone_anchor_decode': LEVERS[0] == 'cone',
                             'bencode_overlap': LEVERS[1] == 1, 'prep_ahead': LEVERS[2] == 1, 'chunk_121': True,
                             'timing_split': True, 'snapshot_fingerprint': a.snapshot_mode == 'fingerprint',
                             'decoder_graph_pool_cap': POOL_CAP is not None},
                'decode_worker': decode_summary(), 'preview_writer': preview_summary(),
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

    def record(self, prefix, failed):
        name = self.path.rsplit('/', 1)[1]
        if not c.RUN_NAME_RE.fullmatch(name):
            return self.send(400, {'error': {'code': 'contract', 'message': 'Invalid run name'}})
        p = RUN / 'receipts' / ('%s-%s.json' % (prefix, name))
        if not p.is_file():
            if failed is not None:
                return self.send(503, {'error': {'code': 'halted', 'message': '%s failed: %s' % (prefix, failed)}})
            return self.send(404, {'error': {'code': 'not-found', 'message': name}})
        return self.send(200, raw=p.read_bytes())

    def do_GET(self):
        if self.path == '/ltx-stream/status':
            STATS['status_gets'] += 1
            if S['action_busy']:
                return self.send(409, {'error': {'code': 'busy', 'message': 'action active'}})
            return self.send(200, status())
        if self.path.startswith('/ltx-stream/receipt/'):
            STATS['receipt_gets'] += 1
            return self.record('receipt', None)
        if self.path.startswith('/ltx-stream/decode/'):
            STATS['decode_gets'] += 1
            return self.record('decode', DECODE_STATE['failed'])
        if self.path.startswith('/ltx-stream/preview/'):
            return self.record('preview', PREVIEW_STATE['failed'])
        self.send(404, {'error': {'code': 'not-found', 'message': self.path}})

    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        try:
            body = json.loads(self.rfile.read(n) or b'null')
        except ValueError:
            return self.refuse(Refusal('contract', 'Body must be JSON', 400))
        if self.path == '/ltx-stream/action':
            if type(body) is not dict or set(body) != {'action'} or body.get('action') != 'qualify-verdict':
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
                seq = d['params']['stream_seq']
                STATS['stream_order'].append(seq)
                prev_name = '%s-s%08d' % (c.RUN_PREFIX, seq - 1)
                if seq > 0 and prev_name not in PREVIEW_STATE['written']:
                    STATS['submitted_before_prev_preview'] += 1
                if seq > 0 and prev_name not in DECODE_STATE['written']:
                    STATS['submitted_before_prev_decode'] += 1
                if STATS['last_commit_mono'] is not None:
                    STATS['submit_after_commit_s'].append(round(time.monotonic() - STATS['last_commit_mono'], 4))
            elif d['params'] is not None or d['kind'] in ('window-probe', 'prepare'):
                STATS['qual_posts'] += 1
            S['queue'].append({'d': d, 'prompt_id': body['prompt_id'], 'submit_ns': submit_ns})
            STATS['max_in_server'] = max(STATS['max_in_server'], len(S['queue']) + (S['active'] is not None))
            COND.notify_all()
        save_stats()
        self.send(200, {'prompt_id': body['prompt_id'], 'number': STATS['posts'], 'node_errors': {}})


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


threading.Thread(target=decode_worker, daemon=True).start()
threading.Thread(target=preview_writer, daemon=True).start()
if a.phase == 'stream':
    FAST[0] = True
    prequalify()
    FAST[0] = False
threading.Thread(target=worker, daemon=True).start()
save_stats()
srv = ThreadingHTTPServer(('127.0.0.1', a.port), H)
srv.daemon_threads = True
(ROOT / 'fake118-ready').write_text(IDENT + '\n')
try:
    srv.serve_forever()
except KeyboardInterrupt:
    pass
