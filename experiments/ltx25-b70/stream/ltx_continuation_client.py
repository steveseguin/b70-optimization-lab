#!/usr/bin/env python3
"""ltx_continuation_client.py - the stream client for the packet 112 continuation server.

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

Never retries a refused request, never restarts or signals anything. Halts:
exit 0 clean stop; 2 server halted / execution error; 4 FAULT.json; 5 HTTP failure (> --http-fail-
seconds, or a POST whose outcome is unknown); 6 failed-job receipt (stream-failure-<run>.json);
7 preview MP4 missing/empty/outside the output directory; 8 preflight refused (identity, phase,
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
PACKET = R / 'prepared-continuation-stream-112'
CONTRACT_DIR = PACKET / 'resolution/components'
MANIFEST_SHA = 'e49f669d580a55d7f2a99ddfc5c2c5fc4a22dd7168987eb471704e2be6352b91'
# The sealed module hashes (manifest.json files['resolution/components/<name>']).
MODULE_SHA = {'stream_contract': '7749eae14df5ae9e71909eb5a592d84d7f4f69f389c067821adeb8a085de1aca',
              'stream_receipts': '6b023dd555d61ea4ddad5f13aac57ef2df62fd8a8714db33f98104441bbbb725',
              'qualification_gate': '828ac51d2b071621b7492f3e1016edd62d7a5ff692e501e11f3fc3a854b2aec1'}
TEXT_ENCODER = Path('/mnt/fast-ai/llm-models/LTX-2.5-baseline/text_encoders/'
                    'gemma4-12b-with-proj-ltx-2.5-bf16.safetensors')
DEFAULT_SCENES = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/data/stream/kittens-01.json')
WINDOW_BUCKETS = (64, 128, 256, 512, 1024)      # ltx_text_window.BUCKETS
STREAM_DIR_RE = re.compile(r'stream112-s[0-9]{8}')   # integration.RUN_NAME_RE, stream form only
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
def load_contract_modules(directory, check_hashes=True):
    mods = {}
    for name in ('stream_contract', 'stream_receipts', 'qualification_gate'):
        path = Path(directory) / (name + '.py')
        try:
            raw = path.read_bytes()
        except OSError as e:
            raise Stop(8, 'cannot read contract module %s (%s)' % (path, e))
        if check_hashes and sha256_bytes(raw) != MODULE_SHA[name]:
            raise Stop(8, '%s differs from the sealed packet 112 module (sha256 %s)' % (path, sha256_bytes(raw)))
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

    def validate(self, contract, window, allowed_windows, frames, placement):
        problems = []
        for s in self.scenes:
            p = s['prompt']
            try:
                contract.validate_params({'kind': 'stream', 'frames': frames, 'placement': placement,
                                          'scene_id': s['scene_id'], 'chunk_index': 0, 'seed': 0, 'prompt': p,
                                          'predecessor_anchor_sha256': '', 'stream_seq': 0, 'reuse_text': 0})
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
        self.client_id = 'stream112-client-' + uuid.uuid4().hex[:12]
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
                          ('text_reuse', self.a.expect_text_reuse)):
            if want is not None and st.get(key) != want:
                problems.append('server %s=%r, expected %r' % (key, st.get(key), want))
        if st.get('frames') not in self.c.FRAME_CHOICES or st.get('placement') not in self.c.PLACEMENTS or \
                st.get('text_reuse') not in (0, 1):
            problems.append('status frames/placement/text_reuse invalid: %r/%r/%r'
                            % (st.get('frames'), st.get('placement'), st.get('text_reuse')))
        elif st.get('qualification_id') != self.c.qualification_id(st['frames'], st['placement']):
            problems.append('qualification_id %s differs from the contract for %s/%s'
                            % (st.get('qualification_id'), st['frames'], st['placement']))
        if not isinstance(st.get('server_identity_sha256'), str) or not st.get('receipt_dir'):
            problems.append('status lacks server identity / receipt_dir')
        if problems:
            raise Stop(8, 'preflight refused: ' + '; '.join(problems))
        self.bind_dirs(st)
        if st.get('halted') or st.get('fault'):
            if st.get('phase') != 'stream':
                raise Stop(13, 'server is halted before streaming (qualification failed or refused): %s'
                           % st.get('halted'))
            self.halted(st)

    # ---- qualification -------------------------------------------------------------------
    def qualification_rows(self, st):
        rows = [(r['name'], r['graph']) for r in self.c.setup_graphs()]
        for params in self.c.qualification_params(st['frames'], st['text_reuse'], st['placement']):
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
        if v.get('passed') is not True or v.get('failures') != [] or len(pairs) != 3 or \
                not all(p.get('all_four_identical') is True for p in pairs):
            raise Stop(13, 'verdict file is not a pass: passed=%r failures=%r' % (v.get('passed'), v.get('failures')))
        if v.get('plan_sha256') != st.get('plan_sha256'):
            raise Stop(13, 'verdict plan_sha256 differs from the server plan')
        # Independent re-derivation: the nine committed receipts from the receipt route, the server's
        # own capture re-reads from the verdict file, and the sealed decision function.
        receipts = []
        for params in self.c.qualification_params(st['frames'], st['text_reuse'], st['placement']):
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
        captures = v.get('captures') or {}
        mine = self.gate.decide(receipts, captures, st.get('plan_sha256'), st['frames'], st['text_reuse'],
                                st['placement'])
        if not mine['passed']:
            raise Stop(13, 'client-side re-derivation of the verdict FAILED: %s' % '; '.join(mine['failures'])[:1500])
        sigs = mine['signatures_per_route']
        log('qualification verified: verdict %s; client re-derivation passed (exact replay %s, %d signatures '
            'per route%s); qualified text windows %s' % (
                vsha[:12], ' '.join('c%d=%s' % (p['chunk'], p['all_four_identical']) for p in mine['exact_replay']),
                sigs, '' if sigs == 4 else ' (4 expected, unverified)', st.get('qualified_text_windows')))
        self.state['qualification'] = {'server_identity_sha256': st['server_identity_sha256'],
                                       'verdict_sha256': vsha, 'verified_utc': utc(),
                                       'signatures_per_route': sigs}

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
        return (p.parent.parent == self.output_dir and STREAM_DIR_RE.fullmatch(p.parent.name) is not None and
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
        for key in ('prompt_id', 'seed', 'scene_id', 'reuse_text'):
            if key in expect:
                want[key] = expect[key]
        if 'prompt' in expect:
            want['prompt_sha256'] = self.c.text_sha256(expect['prompt'])
        for k, v in want.items():
            if r.get(k) != v:
                problems.append('%s=%r (expected %r)' % (k, r.get(k), v))
        if expect['stream_seq'] == 0:
            if r.get('anchor_in') is not None:
                problems.append('chunk 0 consumed an anchor')
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

    def record_chunk(self, r, path, pos, adopted=False):
        """Manifest line + state + log for one verified chunk."""
        seq = self.state['next_manifest_seq']
        timing = r.get('timing_s') or {}
        tn = r.get('timing_ns') or {}
        lag = timing.get('submit_to_preview_written')
        scene, si, k, cycle = self.schedule.at(pos) if pos is not None else (None, None, None, None)
        label = '%s %s seed %d s%d' % (r['scene_id'], '%d/%d' % (k + 1, scene['chunks'])
                                       if scene and scene['scene_id'] == r['scene_id'] else '', r['seed'],
                                       r['stream_seq'])
        gen = tn.get('preview_written') or r.get('commit_ns') or time.time_ns()
        line = {'seq': seq, 'path': str(path), 'generated_utc': utc(gen / 1e9), 'label': label,
                'index': r['stream_seq'], 'stream_seq': r['stream_seq'], 'scene': r['scene_id'],
                'seed': r['seed'], 'anchor_sha256': r['anchor_out']['sha256'],
                'predecessor_anchor_sha256': (r.get('anchor_in') or {}).get('sha256', ''),
                'submit_to_preview_written': lag, 'run_name': r['run_name'], 'prompt_id': r['prompt_id'],
                'new_frames': r['delivery']['new_frames'], 'schedule_pos': pos,
                'server_identity_sha256': self.ident}
        if r['stream_seq'] > 0:
            line['skip_first_frames'] = r['delivery']['drop_leading_frames']
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
        stxt = ' '.join('%s %.2f' % (n, v) for n, v in stages if v is not None)
        log('seq %d stream_seq %d scene %s seed %d submit->preview %s s%s anchor %s%s' % (
            seq, r['stream_seq'], r['scene_id'], r['seed'], 'n/a' if lag is None else '%.3f' % lag,
            (' [' + stxt + ']') if stxt else '', r['anchor_out']['sha256'][:12], ' (adopted)' if adopted else ''))

    # ---- streaming -----------------------------------------------------------------------
    def prepare(self, n, predecessor, prev_prompt_sha):
        pos = self.origin + n
        scene, si, k, cycle = self.schedule.at(pos)
        seed = self.a.base_seed + n
        if seed > self.c.SEED_MAX:
            raise Stop(8, 'seed %d exceeds uint64' % seed)
        prompt = scene['prompt']
        reuse = int(self.text_reuse == 1 and n > 0 and self.c.text_sha256(prompt) == prev_prompt_sha)
        params = self.c.stream_params(self.frames, n, prompt, seed, predecessor, scene['scene_id'], reuse,
                                      placement=self.placement)
        graph = self.c.build_chunk_graph(params)
        return {'stream_seq': n, 'run_name': self.c.run_name(params), 'params': params, 'graph': graph,
                'prompt': prompt, 'seed': seed, 'scene_id': scene['scene_id'], 'reuse_text': reuse,
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
        path = self.preview_path(r)
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
            r = self.verify_receipt(raw, None, expect)
            path = self.preview_path(r)
            self.record_chunk(r, path, self.origin + k if (mine or same) else None, adopted=True)
            prev_anchor = r['anchor_out']['sha256']
        if r is None:
            r = json.loads(self.fetch_receipt_raw(self.c.run_name({'kind': 'stream', 'stream_seq': n - 1})))
        chain = st.get('chain') or {}
        if chain.get('anchor_sha256') != r['anchor_out']['sha256'] or chain.get('last_stream_seq') != n - 1:
            raise Stop(12, 'server chain %r does not end at receipt %s' % (chain, r['run_name']))
        log('resuming this server\'s chain at stream_seq %d on anchor %s (schedule position %d, manifest seq %d)'
            % (n, r['anchor_out']['sha256'][:12], self.origin + n, self.state['next_manifest_seq']))
        return n, r['anchor_out']['sha256'], chain.get('prompt_sha256')

    def stream(self, st):
        self.frames, self.placement, self.text_reuse = st['frames'], st['placement'], st['text_reuse']
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
                    log('submitted %s (scene %s%s, seed %d, reuse_text %d)%s' % (
                        p['run_name'], p['scene_id'], ', cut' if p['cut'] else '', p['seed'], p['reuse_text'], gap))
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
            r, path = self.complete(p['stream_seq'], expect)
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
        log('server %s identity %s phase %s frames %s placement %s text_reuse %s next_stream_seq %s' % (
            self.run_dir.name, self.ident[:12], st.get('phase'), st.get('frames'), st.get('placement'),
            st.get('text_reuse'), st.get('next_stream_seq')))
        self.schedule = Schedule(a.scenes, a.default_chunks)
        window = WindowCheck(a.token_check, a.text_encoder)
        allowed = set(st.get('qualified_text_windows') or [64])
        self.schedule.validate(self.c, window, allowed, st['frames'], st['placement'])
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
        self.schedule.validate(self.c, window, allowed, st['frames'], st['placement'])
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
    ap.add_argument('--manifest-sha256', default=MANIFEST_SHA, help='expected runtime_manifest_sha256')
    ap.add_argument('--contract-dir', type=Path, default=CONTRACT_DIR, help='sealed stream_contract.py location')
    ap.add_argument('--expect-frames', type=int, choices=(49, 25))
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
    ap.add_argument('--save-wait', type=float, default=10.0, help='seconds to wait for a receipt\'s preview file')
    ap.add_argument('--recover-max', type=int, default=8,
                    help='with no manifest record of this server, recover at most this many completed chunks')
    ap.add_argument('--poll', type=float, default=0.5)
    ap.add_argument('--max-chunks', type=int, default=0, help='clean stop after N chunks this run (0 = forever)')
    a = ap.parse_args(argv)
    a.work_dir = a.work_dir.resolve()
    a.manifest = (a.manifest or a.work_dir / 'manifest.jsonl').resolve()
    a.state = (a.state or a.work_dir / 'client-state.json').resolve()
    a.root = a.root.resolve()
    for p in (a.work_dir, a.manifest, a.state):
        if str(p).startswith(str(R.resolve()) + '/prepared-'):
            raise SystemExit('refusing to write under %s/prepared-*: %s' % (R, p))
    if a.port == 8188 and a.contract_dir.resolve() != CONTRACT_DIR:
        raise SystemExit('the live port needs the sealed --contract-dir')
    a.work_dir.mkdir(parents=True, exist_ok=True)
    client = None
    try:
        contract, receipts, gate = load_contract_modules(a.contract_dir)
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
