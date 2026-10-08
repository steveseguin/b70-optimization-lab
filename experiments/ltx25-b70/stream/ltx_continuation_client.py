#!/usr/bin/env python3
"""ltx_continuation_client.py - the stream client for the packet 112 / 113 / 114 continuation servers.

    /home/steve/.venvs/ltx25-baseline/bin/python -B ltx_continuation_client.py --work-dir DIR [options]

Follows experiments/ltx25-b70/recovery/20261008-continuation112-stream/CONTRACT.md and LAUNCH.md:

Qualification (default on; --skip-qualification / --qualification-only): the 2 setup + 9
qualification requests of LAUNCH.md section 4 (window probe, prepare, eager chain, graph-replay
chain, exact repeat; chunk 1 repeats chunk 0's prompt, chunk 2 is a cut), strictly serial, one
attempt each, then the single qualify-verdict action. The verdict is accepted only if the server
says passed AND the client re-derives it: the verdict file's SHA-256 equals the server's verdict
digest, and qualification_gate.decide() run here over the nine committed receipts (fetched from
the receipt route) and the server's own capture re-reads passes. Streaming is refused otherwise.

Streaming: one anchor chain. stream_seq 0 is plain text-to-video; every later chunk names the
previous chunk's anchor_out.sha256. Strictly serial (the server admits one request at a time); the
next request is prepared while the current one runs and is posted in the same poll cycle in which
the previous receipt is seen. Scenes come from --scenes and cycle forever; a scene change is a cut
on the same anchor chain. Seeds are --base-seed + stream_seq. Each completed chunk appends one
line to --manifest for ltx_rtmp_sink.py (anchored chunks carry "skip_first_frames": 1).

Packet 113 (--packet 113; default 112 keeps the exact 112 behaviour): the server commits a receipt
when the chunk's anchor is ready and writes the MP4 preview afterwards on one in-order writer
thread. The client submits the next chunk as soon as the receipt exists and only then waits for
the previous chunk's preview record (GET /ltx-stream/preview/<run_name>, bounded by --save-wait;
the MP4 bytes and SHA-256 must match the record) before writing its manifest line, so the sink
never sees a chunk whose MP4 is incomplete. 113 only: --reset-every-chunks N and
--reset-on-scene-change submit chain resets (an unanchored chunk that restarts the anchor chain;
its manifest line has no skip_first_frames).

Packet 114 (--packet 114): as 113, plus the server's anchor mode (status 'anchor': 'latent' or
'frame') and chunk length (49 or 97) are part of every request, run names carry the stream114-
prefix, and the decode runs on an in-order decode thread after the receipt (latent anchor) whose
record GET /ltx-stream/decode/<run_name> the client waits for (bounded by --save-wait, default 30 s
for 114) and validates before the preview record. Qualification is re-derived with the 114 gate
over the nine receipts, the nine decode records and the server's capture re-reads. Text reuse is on
by default on 114 servers; the client sends reuse_text=1 exactly when the server requires it.
Resets are allowed as on 113. 114 manifest lines also carry frames, new_frames, seconds and anchor.

Never retries a refused request, never restarts or signals anything. Halts:
exit 0 clean stop; 2 server halted / execution error; 4 FAULT.json; 5 HTTP failure (> --http-fail-
seconds, or a POST whose outcome is unknown); 6 failed-job receipt (stream-failure-<run>.json);
7 preview MP4 missing/empty/outside the output directory (114: also a decode record that
does not arrive within --save-wait); 8 preflight refused (identity, phase,
module hashes, schedule or prompt check); 9 disk below --min-free-gib; 10 admission refused:
order / stale-anchor; 11 admission refused: contract / malformed (HTTP 400); 12 receipt or
sequence inconsistency; 13 qualification failed or not passed; 14 admission refused: text /
window rule; 15 admission refused: busy / not-streaming / not-prepared / storage / precheck-error
/ unknown code; 16 request did not complete within its bound; 130 second signal.
SIGINT/SIGTERM: stop submitting, wait for the in-flight chunk, write state, exit 0.
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import re
import shutil
import signal
import struct
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

sys.dont_write_bytecode = True          # never leave __pycache__ anywhere (also run with -B)

R = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
# Sealed packets this client speaks to: packet dir, runtime manifest SHA-256 and the sealed module
# hashes (manifest.json files['resolution/components/<name>']). --packet selects one (default 112).
PACKETS = {
    112: {'dir': R / 'prepared-continuation-stream-112',
          'manifest_sha256': 'e49f669d580a55d7f2a99ddfc5c2c5fc4a22dd7168987eb471704e2be6352b91',
          'modules': {'stream_contract': '7749eae14df5ae9e71909eb5a592d84d7f4f69f389c067821adeb8a085de1aca',
                      'stream_receipts': '6b023dd555d61ea4ddad5f13aac57ef2df62fd8a8714db33f98104441bbbb725',
                      'qualification_gate': '828ac51d2b071621b7492f3e1016edd62d7a5ff692e501e11f3fc3a854b2aec1'}},
    113: {'dir': R / 'prepared-continuation-stream-113',
          'manifest_sha256': 'a23dbc946d156df70c3e61134dc3231b147817c5cb110a015f84c8f020f7f28b',
          'modules': {'stream_contract': '5ea528f08d9237beac177f462688f66bbab3358f735b9780e4b0779d5b125205',
                      'stream_receipts': '878b02037fa8fdc8520b058c5186034f48e12c0381bb6a5a13a6ec2348130613',
                      'qualification_gate': '828ac51d2b071621b7492f3e1016edd62d7a5ff692e501e11f3fc3a854b2aec1'}},
}
# ---- PACKET 114: NOT SEALED YET. Fill these after the 114 build (manifest.json of
# prepared-continuation-stream-114 and its files['resolution/components/<name>'] hashes). ----------
# The module hashes below were computed on 2026-10-08 from the author's working files in
# experiments/ltx25-b70/recovery/20261008-continuation114-stream/; re-sync them after the final build.
PACKET114_MANIFEST_SHA256 = '3e8b7abeb21fff903869907fd67c41128dd6179fa17fa441abdd5544468c97f3'
PACKET114_MODULE_SHA256 = {
    'stream_contract': '1efc6f71c1984822a9389c2fa3b1c7dbfd21d88260c8ac18e0faefdde4a0272c',
    'stream_receipts': '15ba85ac5f01478ce3b0e722d19f4f7db735f0136fe03624c5d1670d7a21500d',
    'qualification_gate': 'fa1787006328ee2cbfba72e74ec333342c1eff0dbaf7889379ccaaaf05219cf8'}
PACKETS[114] = {'dir': R / 'prepared-continuation-stream-114',
                'manifest_sha256': PACKET114_MANIFEST_SHA256,
                'modules': PACKET114_MODULE_SHA256}
# ----------------------------------------------------------------------------------------------
PACKET = PACKETS[112]['dir']                     # packet 112 defaults (unchanged)
CONTRACT_DIR = PACKET / 'resolution/components'
MANIFEST_SHA = PACKETS[112]['manifest_sha256']
MODULE_SHA = PACKETS[112]['modules']
TEXT_ENCODER = Path('/mnt/fast-ai/llm-models/LTX-2.5-baseline/text_encoders/'
                    'gemma4-12b-with-proj-ltx-2.5-bf16.safetensors')
DEFAULT_SCENES = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/data/stream/kittens-01.json')
WINDOW_BUCKETS = (64, 128, 256, 512, 1024)      # ltx_text_window.BUCKETS
STREAM_DIR_RE = re.compile(r'stream112-s[0-9]{8}')   # integration.RUN_NAME_RE, stream form only
STREAM_DIR_RE_114 = re.compile(r'stream114-s[0-9]{8}')   # packet 114 (stream_contract.RUN_PREFIX stream114)
PREVIEW_RE = re.compile(r'preview_[0-9]{5}_\.mp4')
SETUP_TIMEOUT_S = 1800                          # qualify_client.py bounds
QUAL_CHUNK_TIMEOUT_S = 900
VERDICT_TIMEOUT_S = 900
FPS = 24
REFUSAL_EXIT = {'order': 10, 'stale-anchor': 10,
                'contract': 11, 'missing-client-id': 11, 'missing-prompt-id': 11,
                'text-reuse-rule': 14, 'text-cache-missing': 14, 'window-not-captured': 14,
                'window-not-qualified': 14,
                'busy': 15, 'not-streaming': 15, 'not-prepared': 15, 'storage': 15, 'precheck-error': 15}


def utc(t=None):
    return dt.datetime.fromtimestamp(time.time() if t is None else t, dt.timezone.utc).isoformat(
        timespec='milliseconds').replace('+00:00', 'Z')


def log(msg):
    print('[c112 %s] %s' % (utc()[11:23], msg), flush=True)


def atomic_write(path, text):
    path = Path(path)
    tmp = path.with_name(path.name + '.tmp%d' % os.getpid())
    with open(tmp, 'w') as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


class Stop(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


# ----------------------------------------------------------------------------------------------
# Sealed contract modules (read-only import; -B and dont_write_bytecode keep the packet clean)
# ----------------------------------------------------------------------------------------------
def load_contract_modules(directory, check_hashes=True, module_sha=None):
    module_sha = MODULE_SHA if module_sha is None else module_sha
    mods = {}
    for name in ('stream_contract', 'stream_receipts', 'qualification_gate'):
        path = Path(directory) / (name + '.py')
        try:
            raw = path.read_bytes()
        except OSError as e:
            raise Stop(8, 'cannot read contract module %s (%s)' % (path, e))
        if check_hashes and sha256_bytes(raw) != module_sha[name]:
            raise Stop(8, '%s differs from the sealed packet module (sha256 %s)' % (path, sha256_bytes(raw)))
        spec = importlib.util.spec_from_file_location(name, str(path))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod             # stream_receipts / qualification_gate import stream_contract
        spec.loader.exec_module(mod)
        mods[name] = mod
    return mods['stream_contract'], mods['stream_receipts'], mods['qualification_gate']


# ----------------------------------------------------------------------------------------------
# Text window check (CONTRACT section 5): real token count incl. BOS must fit a qualified bucket
# ----------------------------------------------------------------------------------------------
class WindowCheck:
    """The server pads to the smallest captured bucket holding the prompt's real token count (BOS
    included; ltx_text_window.select_window). Gemma4SDTokenizer: BOS (2) + the tokenizers encode of
    the text with add_special_tokens=False, the tokenizer read from the text encoder's own
    safetensors (tokenizer_json). mode 'off' skips the client-side count (the server still refuses)."""

    def __init__(self, mode, encoder_path):
        self.mode, self.tk = mode, None
        if mode == 'off':
            return
        try:
            from tokenizers import Tokenizer
        except ImportError as e:
            raise Stop(8, 'the exact window check needs the tokenizers package (run with the ltx25-baseline '
                          'venv) or --token-check off: %s' % e)
        try:
            with open(encoder_path, 'rb') as f:
                n = struct.unpack('<Q', f.read(8))[0]
                if not 2 <= n <= 100_000_000:
                    raise ValueError('bad safetensors header length')
                header = json.loads(f.read(n))
                a, b = header['tokenizer_json']['data_offsets']
                f.seek(8 + n + a)
                raw = f.read(b - a)
            self.tk = Tokenizer.from_str(raw.decode('utf-8'))
            self.source = '%s tokenizer_json (%d bytes, sha256 %s)' % (encoder_path, len(raw), sha256_bytes(raw)[:16])
        except (OSError, ValueError, KeyError) as e:
            raise Stop(8, 'cannot load the Gemma tokenizer from %s: %s' % (encoder_path, e))

    def tokens(self, prompt):
        if self.tk is None:
            return None
        return 1 + len(self.tk.encode(prompt, add_special_tokens=False).ids)

    @staticmethod
    def bucket(n):
        for w in WINDOW_BUCKETS:
            if n <= w:
                return w
        return 1024


# ----------------------------------------------------------------------------------------------
# Scene schedule
# ----------------------------------------------------------------------------------------------
def scene_id_for(raw_id, k):
    s = re.sub(r'[^a-z0-9]', '', str(raw_id).lower())[:32]
    return s or 'scene%d' % k


class Schedule:
    def __init__(self, path, default_chunks):
        try:
            data = json.loads(Path(path).read_text())
        except (OSError, ValueError) as e:
            raise Stop(8, 'cannot read scenes file %s: %s' % (path, e))
        if isinstance(data, dict):
            rows = data.get('scenes', data.get('fixtures'))
        else:
            rows = data
        if not isinstance(rows, list) or not rows:
            raise Stop(8, 'scenes file %s has no scenes (expected a list, {"scenes": [...]} or {"fixtures": [...]})'
                       % path)
        self.scenes = []
        for k, r in enumerate(rows):
            if not isinstance(r, dict) or not isinstance(r.get('prompt'), str):
                raise Stop(8, 'scene %d has no prompt' % k)
            chunks = r.get('chunks', default_chunks)
            if type(chunks) is not int or chunks < 1:
                raise Stop(8, 'scene %d: chunks must be a positive integer' % k)
            raw_id = r.get('id', 'scene%d' % k)
            self.scenes.append({'id': str(raw_id), 'scene_id': scene_id_for(raw_id, k), 'prompt': r['prompt'],
                                'chunks': chunks})
        self.cycle = sum(s['chunks'] for s in self.scenes)
        self.path = str(path)
        self.sha256 = sha256_bytes(Path(path).read_bytes())

    def at(self, pos):
        """(scene, scene index, chunk within scene, cycle) of schedule position pos."""
        cycle, r = divmod(pos, self.cycle)
        for i, s in enumerate(self.scenes):
            if r < s['chunks']:
                return s, i, r, cycle
            r -= s['chunks']
        raise AssertionError

    def next_scene_start(self, pos):
        s, _, r, _ = self.at(pos)
        return pos - r + s['chunks']

    def validate(self, contract, window, allowed_windows, frames, placement, anchor=None):
        problems = []
        for s in self.scenes:
            p = s['prompt']
            try:
                probe = {'kind': 'stream', 'frames': frames, 'placement': placement,
                         'scene_id': s['scene_id'], 'chunk_index': 0, 'seed': 0, 'prompt': p,
                         'predecessor_anchor_sha256': '', 'stream_seq': 0, 'reuse_text': 0}
                if anchor is not None:          # packet 114 parameters carry the anchor mode
                    probe['anchor'] = anchor
                contract.validate_params(probe)
            except ValueError as e:
                problems.append('%s: %s' % (s['id'], e))
                continue
            if '\\' in p or 'embedding:' in p:
                problems.append('%s: backslashes and "embedding:" change the encoder\'s tokenization; not allowed'
                                % s['id'])
                continue
            n = window.tokens(p)
            if n is not None:
                s['tokens'], s['window'] = n, window.bucket(n)
                if s['window'] not in allowed_windows:
                    problems.append('%s: %d tokens (BOS included) needs the %d-row window; qualified windows %s '
                                    '(the 64-row window holds at most 64 tokens)' % (s['id'], n, s['window'],
                                                                                     sorted(allowed_windows)))
        if problems:
            raise Stop(8, 'scene schedule refused: ' + '; '.join(problems))


# ----------------------------------------------------------------------------------------------
# HTTP (stdlib). The server's routes only: /ltx-stream/status, /ltx-stream/receipt/<run>,
# /ltx-stream/action, POST /prompt.
# ----------------------------------------------------------------------------------------------
class Api:
    def __init__(self, base, fail_seconds):
        self.base, self.fail_seconds = base, fail_seconds
        self.first_failure = None

    def _raw(self, method, path, body=None, timeout=30):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    @staticmethod
    def parse(raw):
        try:
            return json.loads(raw or b'null')
        except ValueError:
            return {'unparsed': raw[:500].decode('utf-8', 'replace')}

    def _failed(self, what, e):
        now = time.monotonic()
        if self.first_failure is None:
            self.first_failure = now
            log('HTTP %s failed (%s); trying again on later cycles for up to %d s' % (what, e, self.fail_seconds))
        if now - self.first_failure > self.fail_seconds:
            raise Stop(5, 'HTTP failing for %.0f s (last: %s: %s)' % (now - self.first_failure, what, e))

    def get(self, path):
        """One GET -> (status, raw bytes), or None on a transport failure (Stop(5) once failures have
        persisted longer than fail_seconds)."""
        try:
            out = self._raw('GET', path, timeout=min(60, max(2, self.fail_seconds // 2)))
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            self._failed('GET ' + path, e)
            return None
        self.first_failure = None
        return out

    def post(self, path, body, timeout):
        """POST exactly once -> (status, parsed). None only when the connection was refused at connect
        (provably not sent). Any other transport failure: Stop(5) (the outcome is unknown)."""
        try:
            status, raw = self._raw('POST', path, body, timeout=timeout)
        except urllib.error.URLError as e:
            if isinstance(getattr(e, 'reason', None), ConnectionRefusedError):
                self._failed('POST %s (connection refused; nothing was sent)' % path, e)
                return None
            raise Stop(5, 'POST %s failed (%s); not retried: the submission state is unknown (a later run '
                          'resolves it from /ltx-stream/status)' % (path, e))
        except (TimeoutError, ConnectionError, OSError) as e:
            raise Stop(5, 'POST %s failed (%s); not retried: the submission state is unknown' % (path, e))
        self.first_failure = None
        return status, self.parse(raw)


def refusal(status, body):
    err = body.get('error') if isinstance(body, dict) else None
    code = err.get('code') if isinstance(err, dict) else None
    msg = err.get('message') if isinstance(err, dict) else json.dumps(body)[:800]
    if status == 503 and code == 'halted':
        return Stop(2, 'server halted (HTTP 503): %s' % msg)
    exit_code = REFUSAL_EXIT.get(code, 15)
    if status == 400:
        exit_code = 11
    return Stop(exit_code, 'request refused (HTTP %d, code %s): %s' % (status, code, msg))


# ----------------------------------------------------------------------------------------------
# The client
# ----------------------------------------------------------------------------------------------
class Client:
    def __init__(self, a, contract, receipts, gate):
        self.a, self.c, self.rc, self.gate = a, contract, receipts, gate
        self.api = Api('http://%s:%d' % (a.host, a.port), a.http_fail_seconds)
        self.client_id = ('stream114-client-' if a.packet == 114 else 'stream112-client-') + uuid.uuid4().hex[:12]
        self.stream_dir_re = STREAM_DIR_RE_114 if a.packet == 114 else STREAM_DIR_RE
        self.anchor = None
        self.state = json.loads(a.state.read_text()) if a.state.is_file() else {}
        self.stopping = False
        self.signals = 0
        self.run_dir = self.root = self.output_dir = None
        self.sink_cache = (0.0, None)
        self.throttled_since = None
        self.chunks_this_run = 0

    # ---- state ---------------------------------------------------------------------------
    def save_state(self):
        self.state['updated_utc'] = utc()
        atomic_write(self.a.state, json.dumps(self.state, indent=1, sort_keys=True) + '\n')

    # ---- signals -------------------------------------------------------------------------
    def on_signal(self, signum, _frame):
        self.signals += 1
        if self.signals == 1:
            log('signal %d: no new submissions; waiting for the in-flight request, then a clean stop' % signum)
            self.stopping = True
        else:
            raise Stop(130, 'second signal: abandoning the wait (state written)')

    # ---- observation ---------------------------------------------------------------------
    def bind_dirs(self, st):
        run = Path(st['receipt_dir']).parent
        out = Path(st['output_directory'])
        if run.parent != self.a.root or out != self.a.root / 'output':
            raise Stop(8, 'server run dir %s / output %s are not under --root %s' % (run, out, self.a.root))
        self.run_dir, self.root, self.output_dir = run, run.parent, out

    def check_fault_files(self, run_name=None):
        if self.root is None:
            return
        if (self.root / 'FAULT.json').exists():
            raise Stop(4, 'FAULT.json present (%s): device fault latched; halting requests' % (self.root / 'FAULT.json'))
        if run_name and (self.run_dir / ('stream-failure-%s.json' % run_name)).exists():
            raise Stop(6, 'FAILED JOB: %s exists; the server latched' % (self.run_dir / ('stream-failure-%s.json' % run_name)))
        if self.a.packet in (113, 114):
            fails = sorted(self.run_dir.glob('stream-preview-failure-*.json'))
            if fails:
                raise Stop(6, 'PREVIEW WRITE FAILED: %s; the server latched' % fails[-1])
        if self.a.packet == 114:
            fails = sorted(self.run_dir.glob('stream-decode-failure-*.json'))
            if fails:
                raise Stop(2, 'DECODE FAILED: %s; the server halted (decode thread latched)' % fails[-1])

    def halted(self, st, run_name=None):
        self.check_fault_files(run_name)
        fails = sorted(self.run_dir.glob('stream-failure-*.json')) if self.run_dir else []
        if fails:
            raise Stop(6, 'FAILED JOB: %s; server halted: %s' % (fails[-1], st.get('halted')))
        raise Stop(2, 'server halted: %s' % st.get('halted'))

    def status(self, wait_busy=True):
        """GET /ltx-stream/status -> dict. 409 busy (verdict action running) is waited out (bounded);
        transport failures are held for --http-fail-seconds."""
        deadline = time.monotonic() + VERDICT_TIMEOUT_S
        while True:
            self.check_fault_files()
            r = self.api.get('/ltx-stream/status')
            if r is not None:
                code, raw = r
                body = self.api.parse(raw)
                if code == 200 and isinstance(body, dict):
                    return body
                if code != 409 or not wait_busy:
                    raise Stop(5, 'status route answered HTTP %d: %s' % (code, json.dumps(body)[:500]))
            if time.monotonic() > deadline:
                raise Stop(16, 'status route busy/unreachable for %d s' % VERDICT_TIMEOUT_S)
            time.sleep(self.a.poll)

    def preflight(self, st):
        problems = []
        if st.get('runtime_manifest_sha256') != self.a.manifest_sha256:
            problems.append('runtime_manifest_sha256 %s is not the packet 112 build %s'
                            % (st.get('runtime_manifest_sha256'), self.a.manifest_sha256))
        for key, want in (('frames', self.a.expect_frames), ('placement', self.a.expect_placement),
                          ('text_reuse', self.a.expect_text_reuse), ('anchor', self.a.expect_anchor)):
            if want is not None and st.get(key) != want:
                problems.append('server %s=%r, expected %r' % (key, st.get(key), want))
        if st.get('frames') not in self.c.FRAME_CHOICES or st.get('placement') not in self.c.PLACEMENTS or \
                st.get('text_reuse') not in (0, 1):
            problems.append('status frames/placement/text_reuse invalid: %r/%r/%r'
                            % (st.get('frames'), st.get('placement'), st.get('text_reuse')))
        elif self.a.packet == 114:
            if st.get('anchor') not in self.c.ANCHORS:
                problems.append('status anchor invalid: %r' % st.get('anchor'))
            elif st.get('qualification_id') != self.c.qualification_id(st['frames'], st['placement'], st['anchor']):
                problems.append('qualification_id %s differs from the contract for %s/%s/%s'
                                % (st.get('qualification_id'), st['frames'], st['placement'], st['anchor']))
        elif st.get('qualification_id') != self.c.qualification_id(st['frames'], st['placement']):
            problems.append('qualification_id %s differs from the contract for %s/%s'
                            % (st.get('qualification_id'), st['frames'], st['placement']))
        if not isinstance(st.get('server_identity_sha256'), str) or not st.get('receipt_dir'):
            problems.append('status lacks server identity / receipt_dir')
        feats = st.get('features') or {}
        if self.a.packet == 113 and not (st.get('packet') == 113 and feats.get('async_preview') is True and
                                         feats.get('chain_reset') is True):
            problems.append('--packet 113 needs a packet 113 server (status packet=%r features=%r)'
                            % (st.get('packet'), feats))
        if self.a.packet == 114 and not (st.get('packet') == 114 and all(feats.get(k) is True for k in (
                'decode_thread', 'async_preview', 'chain_reset', 'chunk_length_choice')) and
                feats.get('latent_anchor') is (st.get('anchor') == 'latent')):
            problems.append('--packet 114 needs a packet 114 server (status packet=%r anchor=%r features=%r)'
                            % (st.get('packet'), st.get('anchor'), feats))
        if problems:
            raise Stop(8, 'preflight refused: ' + '; '.join(problems))
        self.bind_dirs(st)
        if st.get('halted') or st.get('fault'):
            if st.get('phase') != 'stream':
                raise Stop(13, 'server is halted before streaming (qualification failed or refused): %s'
                           % st.get('halted'))
            self.halted(st)

    # ---- qualification -------------------------------------------------------------------
    def qual_params(self, st):
        if self.a.packet == 114:
            return self.c.qualification_params(st['frames'], st['text_reuse'], st['placement'], st['anchor'])
        return self.c.qualification_params(st['frames'], st['text_reuse'], st['placement'])

    def qualification_rows(self, st):
        rows = [(r['name'], r['graph']) for r in self.c.setup_graphs()]
        for params in self.qual_params(st):
            rows.append((self.c.run_name(params), self.c.build_chunk_graph(params)))
        return rows

    def qualify(self, st):
        rows = self.qualification_rows(st)
        names = [n for n, _ in rows]
        done = list(st.get('completed_fixed_requests') or [])
        if done != names[:len(done)]:
            raise Stop(8, 'server completed requests %s do not match the LAUNCH.md order' % done)
        if done:
            log('qualification already %d/11 requests in on this server; continuing with the next one '
                '(each request is still submitted exactly once)' % len(done))
        qlog = self.a.work_dir / 'qualification.jsonl'
        active = st.get('active')
        if active:
            if active.get('name') not in names or active.get('name') != names[len(done)]:
                raise Stop(15, 'server is busy with %s, not the next qualification request' % active.get('name'))
            log('adopting the running qualification request %s' % active['name'])
            self.wait_fixed(active['name'], len(done))
            done.append(active['name'])
        for k in range(len(done), len(rows)):
            if self.stopping:
                raise Stop(13, 'stopped by signal during qualification after %d/11 requests; the next run '
                               'continues from the server\'s completed list' % k)
            name, graph = rows[k]
            prompt_id = str(uuid.uuid4())
            t0 = time.time()
            r = self.api.post('/prompt', {'prompt': graph, 'client_id': self.client_id, 'prompt_id': prompt_id},
                              timeout=300)
            if r is None:
                raise Stop(5, 'server refused the connection for qualification request %s' % name)
            status, body = r
            if status != 200:
                raise refusal(status, body)
            log('Q%02d %s submitted (graph sha256 %s)' % (k + 1, name, self.c.sha256(self.c.canonical(graph))[:12]))
            st2 = self.wait_fixed(name, k)
            row = {'name': name, 'prompt_id': prompt_id, 'wall_s': round(time.time() - t0, 3),
                   'phase': st2['phase'], 'utc': utc()}
            with open(qlog, 'a') as f:
                f.write(json.dumps(row) + '\n')
            log('Q%02d %s completed in %.1f s' % (k + 1, name, row['wall_s']))
        if self.stopping:
            raise Stop(13, 'stopped by signal before the verdict action')
        log('all 11 qualification requests completed; requesting the qualify-verdict action (runs once)')
        r = self.api.post('/ltx-stream/action', {'action': 'qualify-verdict'}, timeout=VERDICT_TIMEOUT_S)
        if r is None:
            raise Stop(5, 'server refused the connection for the verdict action')
        status, verdict = r
        with open(qlog, 'a') as f:
            f.write(json.dumps({'verdict_http_status': status, 'verdict': verdict, 'utc': utc()}) + '\n')
        if status != 200 or not isinstance(verdict, dict) or verdict.get('passed') is not True:
            fails = verdict.get('failures') if isinstance(verdict, dict) else None
            raise Stop(13, 'QUALIFICATION DID NOT PASS (HTTP %d): %s' % (status, json.dumps(fails or verdict)[:1500]))
        if verdict.get('phase') != 'stream' or verdict.get('qualified_text_windows') != [64] or \
                not re.fullmatch('[0-9a-f]{64}', str(verdict.get('verdict_sha256'))):
            raise Stop(13, 'verdict response is not the LAUNCH.md pass form: %s' % json.dumps(verdict)[:800])
        return verdict

    def wait_fixed(self, name, index):
        timeout = SETUP_TIMEOUT_S if index < 2 else QUAL_CHUNK_TIMEOUT_S
        deadline = time.monotonic() + timeout
        while True:
            self.check_fault_files(name)
            st = self.status()
            if st.get('halted'):
                fails = sorted(self.run_dir.glob('stream-failure-*.json'))
                raise Stop(13, 'server halted during qualification request %s: %s%s'
                           % (name, st['halted'], (' (evidence %s)' % fails[-1]) if fails else ''))
            if name in (st.get('completed_fixed_requests') or []):
                return st
            if time.monotonic() > deadline:
                raise Stop(16, 'qualification request %s not completed after %d s; no retry' % (name, timeout))
            time.sleep(self.a.poll)

    def verify_qualification(self, st, verdict=None):
        """Re-derive the pass verdict from the server's evidence. Raises Stop(13)."""
        if st.get('phase') != 'stream':
            raise Stop(13, 'server phase is %r, not stream: qualification has not passed' % st.get('phase'))
        vsha = st.get('qualification_verdict_sha256')
        if not re.fullmatch('[0-9a-f]{64}', str(vsha)):
            raise Stop(13, 'no qualification verdict digest on this server')
        if verdict is not None and verdict.get('verdict_sha256') != vsha:
            raise Stop(13, 'verdict response digest %s differs from the status digest %s'
                       % (verdict.get('verdict_sha256'), vsha))
        path = self.run_dir / 'stream-qualification-verdict.json'
        try:
            raw = path.read_bytes()
        except OSError as e:
            raise Stop(13, 'cannot read %s: %s' % (path, e))
        if sha256_bytes(raw) != vsha:
            raise Stop(13, '%s does not hash to the server verdict digest' % path)
        v = json.loads(raw)
        pairs = v.get('exact_replay') or []
        same_key = 'all_identical' if self.a.packet == 114 else 'all_four_identical'   # 114 gate field name
        if v.get('passed') is not True or v.get('failures') != [] or len(pairs) != 3 or \
                not all(p.get(same_key) is True for p in pairs):
            raise Stop(13, 'verdict file is not a pass: passed=%r failures=%r' % (v.get('passed'), v.get('failures')))
        if v.get('plan_sha256') != st.get('plan_sha256'):
            raise Stop(13, 'verdict plan_sha256 differs from the server plan')
        # Independent re-derivation: the nine committed receipts from the receipt route, the server's
        # own capture re-reads from the verdict file, and the sealed decision function.
        receipts = []
        decodes = {}
        for params in self.qual_params(st):
            name = self.c.run_name(params)
            raw_r = self.fetch_receipt_raw(name)
            binding = (v.get('receipts') or {}).get(name) or {}
            if binding.get('sha256') and sha256_bytes(raw_r) != binding['sha256']:
                raise Stop(13, 'receipt %s differs from the one the verdict bound' % name)
            rec = json.loads(raw_r)
            try:
                self.rc.validate_receipt(rec)
            except ValueError as e:
                raise Stop(13, 'qualification receipt %s fails the receipt schema: %s' % (name, e))
            receipts.append(rec)
            if self.a.packet == 114:
                # The decode thread's record of this chunk, from the decode route, bound to the verdict.
                raw_d = self.fetch_record_raw('decode', name, 13)
                dbind = (v.get('decode_records') or {}).get(name) or {}
                if not dbind.get('sha256') or sha256_bytes(raw_d) != dbind['sha256']:
                    raise Stop(13, 'decode record %s differs from the one the verdict bound' % name)
                try:
                    decodes[name] = self.rc.validate_decode_record(json.loads(raw_d), rec)
                except ValueError as e:
                    raise Stop(13, 'qualification decode record %s fails its schema: %s' % (name, e))
        captures = v.get('captures') or {}
        if self.a.packet == 114:
            mine = self.gate.decide(receipts, decodes, captures, st.get('plan_sha256'), st['frames'],
                                    st['text_reuse'], st['placement'], st['anchor'])
        else:
            mine = self.gate.decide(receipts, captures, st.get('plan_sha256'), st['frames'], st['text_reuse'],
                                    st['placement'])
        if not mine['passed']:
            raise Stop(13, 'client-side re-derivation of the verdict FAILED: %s' % '; '.join(mine['failures'])[:1500])
        sigs = mine['signatures_per_route']
        log('qualification verified: verdict %s; client re-derivation passed (exact replay %s, %d signatures '
            'per route%s); qualified text windows %s' % (
                vsha[:12], ' '.join('c%d=%s' % (p['chunk'], p[same_key]) for p in mine['exact_replay']),
                sigs, '' if sigs == 4 else ' (4 expected, unverified)', st.get('qualified_text_windows')))
        self.state['qualification'] = {'server_identity_sha256': st['server_identity_sha256'],
                                       'verdict_sha256': vsha, 'verified_utc': utc(),
                                       'signatures_per_route': sigs}

    def fetch_record_raw(self, kind, name, missing_code):
        """Packet 114: one committed decode/preview record that must already exist (qualification)."""
        deadline = time.monotonic() + self.a.http_fail_seconds
        while True:
            r = self.api.get('/ltx-stream/%s/%s' % (kind, name))
            if r is not None:
                code, raw = r
                if code == 200:
                    return raw
                raise Stop(missing_code, '%s route for %s answered HTTP %d: %s' % (kind, name, code, raw[:300]))
            if time.monotonic() > deadline:
                raise Stop(5, '%s route unreachable for %s' % (kind, name))
            time.sleep(self.a.poll)

    def fetch_receipt_raw(self, name):
        deadline = time.monotonic() + self.a.http_fail_seconds
        while True:
            r = self.api.get('/ltx-stream/receipt/' + name)
            if r is not None:
                code, raw = r
                if code == 200:
                    return raw
                raise Stop(12, 'receipt route for %s answered HTTP %d: %s' % (name, code, raw[:300]))
            if time.monotonic() > deadline:
                raise Stop(5, 'receipt route unreachable for %s' % name)
            time.sleep(self.a.poll)

    # ---- manifest ------------------------------------------------------------------------
    def read_manifest(self):
        rows = []
        if self.a.manifest.is_file():
            for ln in self.a.manifest.read_text().splitlines():
                try:
                    rows.append(json.loads(ln))
                except ValueError:
                    continue
        return rows

    def append_manifest(self, line):
        with open(self.a.manifest, 'a') as f:
            f.write(json.dumps(line) + '\n')
            f.flush()
            os.fsync(f.fileno())

    # ---- throttle / disk / disposal ------------------------------------------------------
    def sink_last_played(self):
        if not self.a.sink_stats:
            return None
        now = time.monotonic()
        if now - self.sink_cache[0] < 1.0:
            return self.sink_cache[1]
        val = None
        try:
            val = int(json.loads(Path(self.a.sink_stats).read_text()).get('last_played_seq', -1))
        except (OSError, ValueError, TypeError):
            val = None
        self.sink_cache = (now, val)
        return val

    def ahead_seconds(self, extra_seconds=0.0):
        played = self.sink_last_played()
        if played is None:
            return None
        produced = self.state['next_manifest_seq'] - 1
        return max(0, produced - played) * self.chunk_seconds + extra_seconds

    def throttle_ok(self, pending_seconds):
        ahead = self.ahead_seconds(pending_seconds)
        if ahead is not None and ahead + self.chunk_seconds > self.a.max_ahead_seconds:
            if self.throttled_since is None:
                self.throttled_since = time.monotonic()
                log('throttle: %.0f s of video ahead of the sink (limit %.0f s); holding the next chunk'
                    % (ahead, self.a.max_ahead_seconds))
            return False
        if self.throttled_since is not None:
            log('throttle released after %.1f s' % (time.monotonic() - self.throttled_since))
            self.throttled_since = None
        return True

    def check_disk(self):
        free = shutil.disk_usage(self.root).free / 2 ** 30
        if free < self.a.min_free_gib:
            raise Stop(9, 'only %.1f GiB free under %s (limit %.1f); stopping submissions'
                       % (free, self.root, self.a.min_free_gib))

    def disposable(self, path):
        """The preview path if the client may delete it: <output>/<stream112-sNNNNNNNN>/preview_NNNNN_.mp4."""
        p = Path(path)
        pattern = getattr(self, 'stream_dir_re', STREAM_DIR_RE)
        return (p.parent.parent == self.output_dir and pattern.fullmatch(p.parent.name) is not None and
                PREVIEW_RE.fullmatch(p.name) is not None and not p.is_symlink() and not p.parent.is_symlink())

    def dispose(self):
        if not self.a.delete_consumed_previews:
            return
        played = self.sink_last_played()
        if played is None:
            return
        todo = self.state.setdefault('undisposed', [])
        keep = []
        changed = False
        for item in todo:
            if item['seq'] > played - self.a.dispose_margin:
                keep.append(item)
                continue
            p = Path(item['path'])
            changed = True
            if not self.disposable(p):
                log('dispose: %s does not match the 112 stream preview pattern; left alone' % p)
                continue
            try:
                p.unlink()
            except FileNotFoundError:
                pass
            except OSError as e:
                log('dispose: cannot delete %s (%s)' % (p, e))
                continue
            try:
                p.parent.rmdir()                # only if now empty; anything else stays
            except OSError:
                pass
        if changed:
            self.state['undisposed'] = keep
            self.save_state()

    # ---- receipts ------------------------------------------------------------------------
    def verify_receipt(self, raw, st_binding, expect):
        """expect: dict with run_name, stream_seq, predecessor and (for our own submissions) prompt_id,
        prompt, seed, scene_id, reuse_text. Returns the receipt."""
        name = expect['run_name']
        if st_binding and st_binding.get('sha256') and sha256_bytes(raw) != st_binding['sha256']:
            raise Stop(12, 'receipt %s differs from the server\'s committed digest' % name)
        try:
            r = self.rc.validate_receipt(json.loads(raw))
        except ValueError as e:
            raise Stop(12, 'receipt %s fails the receipt schema: %s' % (name, e))
        problems = []
        want = {'run_name': name, 'kind': 'stream', 'stream_seq': expect['stream_seq'],
                'chunk_index': expect['stream_seq'], 'frames': self.frames, 'placement': self.placement,
                'committed': True, 'server_identity_sha256': self.ident}
        if self.a.packet == 114:
            want['anchor'] = self.anchor
        for key in ('prompt_id', 'seed', 'scene_id', 'reuse_text'):
            if key in expect:
                want[key] = expect[key]
        if 'prompt' in expect:
            want['prompt_sha256'] = self.c.text_sha256(expect['prompt'])
        for k, v in want.items():
            if r.get(k) != v:
                problems.append('%s=%r (expected %r)' % (k, r.get(k), v))
        if 'reset' in expect and bool(r.get('reset')) != bool(expect['reset']):
            problems.append('reset=%r (expected %r)' % (r.get('reset'), bool(expect['reset'])))
        if expect['stream_seq'] == 0 or r.get('reset') is True:
            if r.get('anchor_in') is not None:
                problems.append('an unanchored chunk consumed an anchor')
        elif (r.get('anchor_in') or {}).get('sha256') != expect['predecessor']:
            problems.append('anchor_in %s is not the predecessor anchor %s'
                            % ((r.get('anchor_in') or {}).get('sha256'), expect['predecessor']))
        if r.get('qualification_verdict_sha256') not in (None, self.verdict_sha):
            problems.append('qualification_verdict_sha256 differs from this server\'s verdict')
        if problems:
            raise Stop(12, 'receipt %s inconsistent with the request: %s' % (name, '; '.join(problems)))
        return r

    def preview_path(self, r):
        prev = r['preview']
        p = Path(prev['path'])
        name = r['run_name']
        if p.parent != self.output_dir / name or not PREVIEW_RE.fullmatch(p.name):
            raise Stop(7, 'preview of %s is not at %s/<counter>.mp4: %s' % (name, self.output_dir / name, p))
        deadline = time.monotonic() + self.a.save_wait
        while True:
            try:
                size = p.stat().st_size
            except OSError:
                size = -1
            if size > 0:
                if size != prev['bytes']:
                    raise Stop(7, 'preview %s has %d bytes, the receipt says %d' % (p, size, prev['bytes']))
                return p
            if time.monotonic() > deadline:
                raise Stop(7, 'preview %s missing or empty' % p)
            time.sleep(0.1)

    def wait_decode(self, r, deadline):
        """Packet 114: the decode thread commits receipts/decode-<run>.json after the receipt (latent
        anchor) or before it (frame anchor). Wait for it until `deadline` (the --save-wait bound that
        also covers the preview), validate it against the receipt. 503 / a halted server: exit 2;
        never written: exit 7."""
        name = r['run_name']
        while True:
            self.check_fault_files(name)
            got = self.api.get('/ltx-stream/decode/' + name)
            if got is not None:
                code, raw = got
                if code == 200:
                    break
                if code == 503:
                    self.halted(self.status())
                if code != 404:
                    raise Stop(7, 'decode route for %s answered HTTP %d: %s' % (name, code, raw[:300]))
            if time.monotonic() > deadline:
                st = self.status()
                if st.get('halted'):
                    self.halted(st, name)
                raise Stop(7, 'decode record of %s not written %.1f s after its receipt was seen (--save-wait)'
                           % (name, self.a.save_wait))
            time.sleep(min(self.a.poll, 0.1))
        try:
            return self.rc.validate_decode_record(json.loads(raw), r)
        except ValueError as e:
            raise Stop(12, 'decode record of %s fails its schema / receipt binding: %s' % (name, e))

    def wait_preview(self, r, deadline=None):
        """Packet 113 bounded wait rule: the MP4 is written after the receipt. Wait at most --save-wait
        seconds for its preview record, then require the file to match the record's bytes and SHA-256.
        A halted server ends the wait at once (exit 2/6); a record that never appears is exit 7."""
        name = r['run_name']
        prev = r['preview']
        p = Path(prev['path'])
        if p.parent != self.output_dir / name or not PREVIEW_RE.fullmatch(p.name):
            raise Stop(7, 'preview of %s is not at %s/<counter>.mp4: %s' % (name, self.output_dir / name, p))
        if deadline is None:
            deadline = time.monotonic() + self.a.save_wait
        while True:
            self.check_fault_files(name)
            got = self.api.get('/ltx-stream/preview/' + name)
            if got is not None:
                code, raw = got
                if code == 200:
                    break
                if code == 503:
                    self.halted(self.status())
                if code != 404:
                    raise Stop(7, 'preview route for %s answered HTTP %d: %s' % (name, code, raw[:300]))
            if time.monotonic() > deadline:
                st = self.status()
                if st.get('halted'):
                    self.halted(st, name)
                raise Stop(7, 'preview record of %s not written %.1f s after its receipt was seen (--save-wait)'
                           % (name, self.a.save_wait))
            time.sleep(min(self.a.poll, 0.1))
        try:
            rec = self.rc.validate_preview_record(json.loads(raw), r)
        except ValueError as e:
            raise Stop(7, 'preview record of %s fails its schema: %s' % (name, e))
        try:
            data = p.read_bytes()
        except OSError as e:
            raise Stop(7, 'preview %s unreadable: %s' % (p, e))
        if len(data) != rec['bytes'] or sha256_bytes(data) != rec['sha256']:
            raise Stop(7, 'preview %s (%d bytes) differs from its record (%d bytes)' % (p, len(data), rec['bytes']))
        return p, rec

    def record_chunk(self, r, path, pos, adopted=False):
        """Manifest line + state + log for one verified chunk."""
        precord = drec = None
        if path is None and self.a.packet == 114:
            # Packet 114: decode record first, then the preview record; one --save-wait bound for both.
            deadline = time.monotonic() + self.a.save_wait
            drec = self.wait_decode(r, deadline)
            path, precord = self.wait_preview(r, deadline)
        elif path is None:                       # packet 113: the preview is written after the receipt
            path, precord = self.wait_preview(r)
        seq = self.state['next_manifest_seq']
        timing = r.get('timing_s') or {}
        tn = r.get('timing_ns') or {}
        lag = timing.get('submit_to_preview_written')
        if precord is not None:
            lag = precord['timing_s']['submit_to_preview_written']
        scene, si, k, cycle = self.schedule.at(pos) if pos is not None else (None, None, None, None)
        label = '%s %s seed %d s%d' % (r['scene_id'], '%d/%d' % (k + 1, scene['chunks'])
                                       if scene and scene['scene_id'] == r['scene_id'] else '', r['seed'],
                                       r['stream_seq'])
        gen = (precord or {}).get('timing_ns', {}).get('preview_written') or tn.get('preview_written') or \
            r.get('commit_ns') or time.time_ns()
        line = {'seq': seq, 'path': str(path), 'generated_utc': utc(gen / 1e9), 'label': label,
                'index': r['stream_seq'], 'stream_seq': r['stream_seq'], 'scene': r['scene_id'],
                'seed': r['seed'], 'anchor_sha256': r['anchor_out']['sha256'],
                'predecessor_anchor_sha256': (r.get('anchor_in') or {}).get('sha256', ''),
                'submit_to_preview_written': lag, 'run_name': r['run_name'], 'prompt_id': r['prompt_id'],
                'new_frames': r['delivery']['new_frames'], 'schedule_pos': pos,
                'server_identity_sha256': self.ident}
        if r['stream_seq'] > 0 and r['delivery']['drop_leading_frames']:
            line['skip_first_frames'] = r['delivery']['drop_leading_frames']
        if drec is not None:
            diag = drec.get('anchor_diagnostics') or {}
            new = r['delivery']['new_frames']
            line.update(frames=r['frames'], seconds=round(new / FPS, 6), anchor=r['anchor'],
                        reset=bool(r.get('reset')), reuse_text=r['reuse_text'],
                        submit_to_anchor_ready=timing.get('submit_to_anchor_ready'),
                        submit_to_decode_done=(drec.get('timing_s') or {}).get('submit_to_decode_done'),
                        preview_sha256=precord['sha256'], last_frame_sha256=drec['last_frame_sha256'],
                        images_sha256=drec['tensors']['images']['sha256'],
                        border_to_centre_chroma_ratio=diag.get('border_to_centre_chroma_ratio'),
                        border_mean_chroma=diag.get('border_mean_chroma'),
                        centre_mean_chroma=diag.get('centre_mean_chroma'))
        elif precord is not None:
            diag = r.get('anchor_diagnostics') or {}
            line.update(reset=bool(r.get('reset')), submit_to_anchor_ready=timing.get('submit_to_anchor_ready'),
                        preview_sha256=precord['sha256'],
                        border_to_centre_chroma_ratio=diag.get('border_to_centre_chroma_ratio'),
                        border_mean_chroma=diag.get('border_mean_chroma'),
                        centre_mean_chroma=diag.get('centre_mean_chroma'))
        self.append_manifest(line)
        st = self.state
        st['next_manifest_seq'] = seq + 1
        st['last_manifested_stream_seq'] = r['stream_seq']
        st['chunks_total'] = st.get('chunks_total', 0) + 1
        if self.a.delete_consumed_previews:
            st.setdefault('undisposed', []).append({'seq': seq, 'path': str(path)})
        self.save_state()

        def d(a_key, b_key):
            a, b = tn.get(a_key), tn.get(b_key)
            return None if a is None or b is None else (b - a) / 1e9
        stages = [('queue', d('submit', 'execution_start')), ('text+A-prep', d('execution_start', 'sampler_a_start')),
                  ('samplerA', d('sampler_a_start', 'sampler_b_start')), ('samplerB', d('sampler_b_start', 'decode_start')),
                  ('decode', d('decode_start', 'decode_done')), ('preview', d('decode_done', 'preview_written'))]
        if drec is not None:
            stages = [('queue', d('submit', 'execution_start')),
                      ('text+A-prep', d('execution_start', 'sampler_a_start')),
                      ('samplerA', d('sampler_a_start', 'stage_a_done')),
                      ('upsample+B-prep', d('stage_a_done', 'sampler_b_start')),
                      ('samplerB', d('sampler_b_start', 'stage_b_done')),
                      ('anchor', d('stage_b_done', 'anchor_ready')),
                      ('decode(%s)' % ('in-chain' if r['anchor'] == 'frame' else 'off-chain'),
                       (drec.get('timing_s') or {}).get('decode')),
                      ('preview(off-chain)', (precord.get('timing_s') or {}).get('write'))]
        elif precord is not None:
            stages[-1] = ('anchor', d('decode_done', 'anchor_ready'))
            stages.append(('preview(off-chain)', precord['timing_s']['anchor_ready_to_preview_written']))
        stxt = ' '.join('%s %.2f' % (n, v) for n, v in stages if v is not None)
        extra = ''
        if precord is not None:
            ready = timing.get('submit_to_anchor_ready')
            extra = ' submit->anchor %s s%s' % ('n/a' if ready is None else '%.3f' % ready,
                                                 ' RESET' if r.get('reset') else '')
        log('seq %d stream_seq %d scene %s seed %d submit->preview %s s%s%s anchor %s%s' % (
            seq, r['stream_seq'], r['scene_id'], r['seed'], 'n/a' if lag is None else '%.3f' % lag, extra,
            (' [' + stxt + ']') if stxt else '', r['anchor_out']['sha256'][:12], ' (adopted)' if adopted else ''))

    # ---- streaming -----------------------------------------------------------------------
    def wants_reset(self, n, scene_id, prompt, prev_prompt_sha):
        """Packet 113/114 chain reset policy (both off by default): every N chunks, and/or on a scene change."""
        if n == 0 or self.a.packet not in (113, 114):
            return False
        if self.a.reset_every_chunks and n % self.a.reset_every_chunks == 0:
            return True
        prev_scene = getattr(self, 'last_scene_id', None)
        changed = (prev_scene is not None and scene_id != prev_scene) or self.c.text_sha256(prompt) != prev_prompt_sha
        return bool(self.a.reset_on_scene_change and changed)

    def prepare(self, n, predecessor, prev_prompt_sha):
        pos = self.origin + n
        scene, si, k, cycle = self.schedule.at(pos)
        seed = self.a.base_seed + n
        if seed > self.c.SEED_MAX:
            raise Stop(8, 'seed %d exceeds uint64' % seed)
        prompt = scene['prompt']
        reset = int(self.wants_reset(n, scene['scene_id'], prompt, prev_prompt_sha))
        reuse = int(self.text_reuse == 1 and n > 0 and not reset and self.c.text_sha256(prompt) == prev_prompt_sha)
        extra = {'reset': reset} if self.a.packet in (113, 114) else {}
        if self.a.packet == 114:
            extra['anchor'] = self.anchor
        params = self.c.stream_params(self.frames, n, prompt, seed, predecessor, scene['scene_id'], reuse,
                                      placement=self.placement, **extra)
        graph = self.c.build_chunk_graph(params)
        return {'stream_seq': n, 'run_name': self.c.run_name(params), 'params': params, 'graph': graph,
                'prompt': prompt, 'seed': seed, 'scene_id': scene['scene_id'], 'reuse_text': reuse, 'reset': reset,
                'predecessor': predecessor, 'pos': pos, 'cut': n > 0 and self.c.text_sha256(prompt) != prev_prompt_sha}

    def submit(self, p):
        prompt_id = str(uuid.uuid4())
        self.state['pending'] = {'stream_seq': p['stream_seq'], 'run_name': p['run_name'], 'prompt_id': prompt_id,
                                 'pos': p['pos'], 'seed': p['seed'], 'scene_id': p['scene_id'],
                                 'predecessor': p['predecessor'], 'submitted_utc': utc()}
        self.save_state()
        while True:
            r = self.api.post('/prompt', {'prompt': p['graph'], 'client_id': self.client_id, 'prompt_id': prompt_id},
                              timeout=min(300, max(5, self.a.http_fail_seconds)))
            if r is not None:
                break
            time.sleep(max(self.a.poll, 1.0))       # connection refused at connect: provably not sent
        status, body = r
        if status != 200:
            self.state['pending'] = None
            self.save_state()
            raise refusal(status, body)
        p['prompt_id'] = prompt_id
        p['submitted_mono'] = time.monotonic()
        return prompt_id

    def wait_chunk(self, n, run_name):
        """Poll the status route until chunk n is committed (next_stream_seq > n, nothing active)."""
        deadline = time.monotonic() + self.a.chunk_timeout
        while True:
            self.check_fault_files(run_name)
            st = self.status()
            if st.get('halted'):
                self.halted(st, run_name)
            nxt = st.get('next_stream_seq')
            if type(nxt) is not int or nxt > n + 1:
                raise Stop(12, 'server next_stream_seq %r jumped past %d: another client is submitting' % (nxt, n + 1))
            if nxt == n + 1 and st.get('active') is None:
                binding = next((b for b in st.get('last_stream_receipts') or []
                                if Path(b.get('path', '')).name == 'receipt-%s.json' % run_name), None)
                return st, binding
            if time.monotonic() > deadline:
                raise Stop(16, 'chunk %s not committed after %d s; no retry (inspect the server run dir)'
                           % (run_name, self.a.chunk_timeout))
            time.sleep(self.a.poll)

    def complete(self, n, expect):
        st, binding = self.wait_chunk(n, expect['run_name'])
        raw = self.fetch_receipt_raw(expect['run_name'])
        r = self.verify_receipt(raw, binding, expect)
        # 112: the MP4 exists before the receipt. 113: it is waited for after the next submit.
        path = self.preview_path(r) if self.a.packet == 112 else None
        chain = st.get('chain') or {}
        if chain.get('anchor_sha256') != r['anchor_out']['sha256'] or chain.get('last_run_name') != r['run_name']:
            raise Stop(12, 'status chain %s/%s differs from receipt %s' % (chain.get('last_run_name'),
                                                                         chain.get('anchor_sha256'), r['run_name']))
        return r, path

    def resume(self, st):
        """Decide where the chain stands from the server (status + receipts), recover anything the
        manifest is missing, adopt an in-flight chunk. Returns (next stream_seq, predecessor, prompt sha)."""
        a, ident = self.a, self.ident
        same = self.state.get('server_identity_sha256') == ident
        rows = self.read_manifest()
        top = max((int(x['seq']) for x in rows if isinstance(x.get('seq'), int)), default=-1)
        self.state['next_manifest_seq'] = max(self.state.get('next_manifest_seq', 0), top + 1)
        mine = [x for x in rows if x.get('server_identity_sha256') == ident and isinstance(x.get('stream_seq'), int)]
        withpos = [x for x in rows if isinstance(x.get('schedule_pos'), int)]
        pending = self.state.get('pending') if same else None
        n = st['next_stream_seq']
        # schedule origin
        if same and isinstance(self.state.get('schedule_origin'), int):
            self.origin = self.state['schedule_origin']
        elif mine and isinstance(mine[-1].get('schedule_pos'), int):
            self.origin = mine[-1]['schedule_pos'] - mine[-1]['stream_seq']
        elif n == 0 and withpos:
            self.origin = self.schedule.next_scene_start(withpos[-1]['schedule_pos'])
        else:
            self.origin = 0
        if not same:
            if self.state.get('server_identity_sha256'):
                log('state belongs to another server launch: this server\'s chain starts/continues at stream_seq %d; '
                    'manifest seq continues at %d' % (n, self.state['next_manifest_seq']))
            for k in ('pending', 'last_manifested_stream_seq'):
                self.state.pop(k, None)
        self.state.update(server_identity_sha256=ident, schedule_origin=self.origin,
                          schedule_sha256=self.schedule.sha256, base_seed=a.base_seed,
                          server_run=self.run_dir.name)
        self.save_state()
        # an in-flight chunk (ours from before a crash, or unknown)
        active = st.get('active')
        if active:
            if active.get('kind') != 'stream' or active.get('name') != self.c.run_name(
                    {'kind': 'stream', 'stream_seq': n}):
                raise Stop(15, 'server is busy with %s; not a chunk this client can adopt' % active.get('name'))
            if pending and pending.get('prompt_id') != active.get('prompt_id'):
                log('warning: the running chunk %s is not the one this client recorded as pending' % active['name'])
            log('adopting the in-flight chunk %s (prompt %s)' % (active['name'], active.get('prompt_id')))
            prm = active.get('params') or {}
            expect = {'run_name': active['name'], 'stream_seq': n, 'prompt_id': active.get('prompt_id'),
                      'predecessor': prm.get('predecessor_anchor_sha256', '')}
            if prm.get('reset'):
                expect['reset'] = True
            self.complete(n, expect)            # verified; recorded by the backfill below
            st = self.status()
            n = st['next_stream_seq']
        self.state['pending'] = None
        if n == 0:
            log('new chain on this server: stream_seq 0 (unanchored), schedule position %d, manifest seq %d'
                % (self.origin, self.state['next_manifest_seq']))
            return 0, '', None
        last_m = max((x['stream_seq'] for x in mine), default=-1)
        start = last_m + 1 if mine else max(0, n - a.recover_max)
        if not mine and start > 0:
            log('this manifest has no chunks of this server; recovering only the last %d of %d (stream_seq %d..%d)'
                % (n - start, n, start, n - 1))
        prev_anchor = None
        if start > 0:
            prev_anchor = json.loads(self.fetch_receipt_raw(self.c.run_name({'kind': 'stream',
                                                                              'stream_seq': start - 1})))['anchor_out']['sha256']
        r = None
        for k in range(start, n):
            name = self.c.run_name({'kind': 'stream', 'stream_seq': k})
            raw = self.fetch_receipt_raw(name)
            expect = {'run_name': name, 'stream_seq': k, 'predecessor': prev_anchor or ''}
            if self.a.packet in (113, 114):
                head = json.loads(raw)
                if head.get('reset') is True:          # a reset names (at most) its predecessor; it is unanchored
                    expect['reset'] = True
            r = self.verify_receipt(raw, None, expect)
            path = self.preview_path(r) if self.a.packet == 112 else None
            self.record_chunk(r, path, self.origin + k if (mine or same) else None, adopted=True)
            prev_anchor = r['anchor_out']['sha256']
        if r is None:
            r = json.loads(self.fetch_receipt_raw(self.c.run_name({'kind': 'stream', 'stream_seq': n - 1})))
        chain = st.get('chain') or {}
        if chain.get('anchor_sha256') != r['anchor_out']['sha256'] or chain.get('last_stream_seq') != n - 1:
            raise Stop(12, 'server chain %r does not end at receipt %s' % (chain, r['run_name']))
        self.last_scene_id = r.get('scene_id')
        log('resuming this server\'s chain at stream_seq %d on anchor %s (schedule position %d, manifest seq %d)'
            % (n, r['anchor_out']['sha256'][:12], self.origin + n, self.state['next_manifest_seq']))
        return n, r['anchor_out']['sha256'], chain.get('prompt_sha256')

    def stream(self, st):
        self.frames, self.placement, self.text_reuse = st['frames'], st['placement'], st['text_reuse']
        if self.a.packet == 114:
            self.anchor = st['anchor']
        self.chunk_seconds = (self.frames - 1) / FPS
        n, predecessor, prev_sha = self.resume(st)
        p = self.prepare(n, predecessor, prev_sha)
        pending_record = None
        last_done = None
        while True:
            submitted = False
            if not self.stopping and (not self.a.max_chunks or self.chunks_this_run < self.a.max_chunks):
                pend_s = pending_record[0]['delivery']['new_frames'] / FPS if pending_record else 0.0
                if self.throttle_ok(pend_s):
                    self.check_disk()
                    self.check_fault_files()
                    self.submit(p)
                    submitted = True
                    gap = '' if last_done is None else ' %.3f s after the previous receipt' % (time.monotonic() - last_done)
                    log('submitted %s (scene %s%s%s, seed %d, reuse_text %d)%s' % (
                        p['run_name'], p['scene_id'], ', cut' if p['cut'] else '', ', RESET' if p['reset'] else '',
                        p['seed'], p['reuse_text'], gap))
            if pending_record is not None:
                self.record_chunk(*pending_record)
                pending_record = None
            self.dispose()
            if not submitted:
                if self.stopping or (self.a.max_chunks and self.chunks_this_run >= self.a.max_chunks):
                    log('clean stop: %d chunks this run, next stream_seq %d, next manifest seq %d'
                        % (self.chunks_this_run, p['stream_seq'], self.state['next_manifest_seq']))
                    return 0
                time.sleep(self.a.poll)
                continue
            expect = {'run_name': p['run_name'], 'stream_seq': p['stream_seq'], 'prompt_id': p['prompt_id'],
                      'prompt': p['prompt'], 'seed': p['seed'], 'scene_id': p['scene_id'],
                      'reuse_text': p['reuse_text'], 'predecessor': p['predecessor']}
            if self.a.packet in (113, 114):
                expect['reset'] = bool(p['reset'])
            r, path = self.complete(p['stream_seq'], expect)
            self.last_scene_id = r['scene_id']
            last_done = time.monotonic()
            self.chunks_this_run += 1
            self.state['pending'] = None
            pending_record = (r, path, p['pos'])
            p = self.prepare(p['stream_seq'] + 1, r['anchor_out']['sha256'], r['prompt_sha256'])

    # ---- main ----------------------------------------------------------------------------
    def run(self):
        a = self.a
        st = self.status()
        self.preflight(st)
        self.ident = st['server_identity_sha256']
        log('server %s identity %s phase %s frames %s placement %s text_reuse %s next_stream_seq %s%s' % (
            self.run_dir.name, self.ident[:12], st.get('phase'), st.get('frames'), st.get('placement'),
            st.get('text_reuse'), st.get('next_stream_seq'),
            (' anchor %s packet 114' % st.get('anchor')) if self.a.packet == 114 else ''))
        anchor_kw = {'anchor': st['anchor']} if self.a.packet == 114 else {}
        self.schedule = Schedule(a.scenes, a.default_chunks)
        window = WindowCheck(a.token_check, a.text_encoder)
        allowed = set(st.get('qualified_text_windows') or [64])
        self.schedule.validate(self.c, window, allowed, st['frames'], st['placement'], **anchor_kw)
        log('scenes: %d from %s, %d chunks per cycle; %s' % (
            len(self.schedule.scenes), a.scenes, self.schedule.cycle,
            'tokens ' + ', '.join('%s=%d' % (s['scene_id'], s['tokens']) for s in self.schedule.scenes)
            if a.token_check == 'exact' else 'client-side token check off'))
        verdict = None
        if st.get('phase') in ('stream_setup', 'stream_qualification'):
            if a.skip_qualification:
                raise Stop(13, 'server phase %s: qualification has not passed and --skip-qualification was given'
                           % st['phase'])
            verdict = self.qualify(st)
            st = self.status()
        elif st.get('phase') == 'stream':
            if not a.skip_qualification:
                log('this server already passed qualification; verifying its verdict instead of re-running it')
        else:
            raise Stop(8, 'unknown server phase %r' % st.get('phase'))
        self.verify_qualification(st, verdict)
        self.verdict_sha = st['qualification_verdict_sha256']
        self.save_state()
        allowed = set(st.get('qualified_text_windows') or [])
        self.schedule.validate(self.c, window, allowed, st['frames'], st['placement'], **anchor_kw)
        if a.qualification_only:
            log('--qualification-only: qualification passed and verified; nothing streamed')
            return 0
        if st.get('halted'):
            self.halted(st)
        return self.stream(st)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--work-dir', type=Path, required=True)
    ap.add_argument('--manifest', type=Path, help='sink manifest (default WORK/manifest.jsonl)')
    ap.add_argument('--state', type=Path, help='client state (default WORK/client-state.json)')
    ap.add_argument('--scenes', type=Path, default=DEFAULT_SCENES,
                    help='scene schedule JSON: [{"id","prompt","chunks"}], {"scenes": [...]} or {"fixtures": [...]}')
    ap.add_argument('--default-chunks', type=int, default=4, help='chunks for a scene without "chunks"')
    ap.add_argument('--base-seed', type=int, default=11200000, help='seed = base + stream_seq')
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=8188)
    ap.add_argument('--root', type=Path, default=R, help='results root holding the server run dir and output/')
    ap.add_argument('--packet', type=int, choices=sorted(PACKETS), default=112,
                    help='server packet: 112 (default, unchanged behaviour), 113 (preview after receipt, resets) '
                         'or 114 (latent/frame anchor, decode thread, 49/97 frames, text reuse on by default)')
    ap.add_argument('--manifest-sha256', help='expected runtime_manifest_sha256 (default: the --packet build)')
    ap.add_argument('--contract-dir', type=Path, help='sealed stream_contract.py location (default: the --packet build)')
    ap.add_argument('--reset-every-chunks', type=int, default=0,
                    help='113/114 only: submit a chain reset (unanchored chunk) at every stream_seq divisible by N (0 = never)')
    ap.add_argument('--reset-on-scene-change', action='store_true',
                    help='113/114 only: submit a chain reset whenever the scene (or its prompt) changes')
    ap.add_argument('--expect-frames', type=int, choices=(49, 25, 97))
    ap.add_argument('--expect-anchor', choices=('latent', 'frame'), help='114 only: the server anchor mode')
    ap.add_argument('--expect-placement', choices=('two-way', 'two-way20-28'))
    ap.add_argument('--expect-text-reuse', type=int, choices=(0, 1))
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--skip-qualification', action='store_true',
                   help='never submit qualification requests (the server must already be in phase stream)')
    g.add_argument('--qualification-only', action='store_true')
    ap.add_argument('--token-check', choices=('exact', 'off'), default='exact')
    ap.add_argument('--text-encoder', type=Path, default=TEXT_ENCODER)
    ap.add_argument('--sink-stats', help="the sink's --stats JSON (last_played_seq)")
    ap.add_argument('--max-ahead-seconds', type=float, default=60.0)
    ap.add_argument('--delete-consumed-previews', action='store_true')
    ap.add_argument('--dispose-margin', type=int, default=50, help='manifest seqs behind last_played_seq')
    ap.add_argument('--min-free-gib', type=float, default=52.0)
    ap.add_argument('--http-fail-seconds', type=int, default=120)
    ap.add_argument('--chunk-timeout', type=int, default=900, help='bound on one chunk, submit to receipt')
    ap.add_argument('--save-wait', type=float, default=None,
                    help='seconds to wait for a receipt\'s preview file (default 10; --packet 114: 30, covering '
                         'its decode record and preview record)')
    ap.add_argument('--recover-max', type=int, default=8,
                    help='with no manifest record of this server, recover at most this many completed chunks')
    ap.add_argument('--poll', type=float, default=0.5)
    ap.add_argument('--max-chunks', type=int, default=0, help='clean stop after N chunks this run (0 = forever)')
    a = ap.parse_args(argv)
    sealed = PACKETS[a.packet]
    a.manifest_sha256 = a.manifest_sha256 or sealed['manifest_sha256']
    a.contract_dir = a.contract_dir or sealed['dir'] / 'resolution/components'
    if a.save_wait is None:
        a.save_wait = 30.0 if a.packet == 114 else 10.0
    if a.packet not in (113, 114) and (a.reset_every_chunks or a.reset_on_scene_change):
        raise SystemExit('--reset-every-chunks / --reset-on-scene-change need --packet 113 or 114')
    if a.expect_anchor is not None and a.packet != 114:
        raise SystemExit('--expect-anchor needs --packet 114')
    if a.reset_every_chunks < 0:
        raise SystemExit('--reset-every-chunks must be >= 0')
    a.work_dir = a.work_dir.resolve()
    a.manifest = (a.manifest or a.work_dir / 'manifest.jsonl').resolve()
    a.state = (a.state or a.work_dir / 'client-state.json').resolve()
    a.root = a.root.resolve()
    for p in (a.work_dir, a.manifest, a.state):
        if str(p).startswith(str(R.resolve()) + '/prepared-'):
            raise SystemExit('refusing to write under %s/prepared-*: %s' % (R, p))
    if a.port == 8188 and a.contract_dir.resolve() != sealed['dir'] / 'resolution/components':
        raise SystemExit('the live port needs the sealed --contract-dir of --packet %d' % a.packet)
    a.work_dir.mkdir(parents=True, exist_ok=True)
    client = None
    try:
        contract, receipts, gate = load_contract_modules(a.contract_dir, module_sha=sealed['modules'])
        client = Client(a, contract, receipts, gate)
        signal.signal(signal.SIGINT, client.on_signal)
        signal.signal(signal.SIGTERM, client.on_signal)
        rc = client.run()
        client.save_state()
        return rc
    except Stop as s:
        if client is not None:
            try:
                client.state['last_stop'] = {'code': s.code, 'reason': str(s)[:2000], 'utc': utc()}
                client.save_state()
            except Exception as e:      # noqa: BLE001
                log('could not write state: %r' % e)
        log('STOPPED (exit %d): %s' % (s.code, s))
        if s.code != 130:
            log('no retry, no restart: inspect the evidence before running again')
        return s.code


if __name__ == '__main__':
    sys.exit(main())
