#!/usr/bin/env python3
"""SC117 Qwen3.8 Flash-Next IQ3_S on our corrected two-rank native engine, served to the LAN.

Serial (one generation at a time), MTP on, greedy only, 4096-token context.
Run only as the systemd user unit in this directory (Restart=no, no SIGKILL).
On a GPU/kernel fault, a lost rank or a foreign holder on the target cards it
stops intake, sends the single cooperative stop, waits for physical drain and
exits. It never retries, restarts, resets a device or kills a rank.
"""
import argparse, hashlib, http.server, importlib.util, ipaddress, json, os, resource, shutil, signal, socket, subprocess
import re, sys, threading, time, traceback
from datetime import datetime, timezone
from pathlib import Path

P = Path(__file__).resolve().parent
LANE = P.parents[1]
CONTROL_PARENT = Path('/home/steve/own-xpu-runtime-results/sc117-lan')
EVIDENCE_PARENT = Path('/mnt/usb-models/own-xpu-runtime-results/sc117-lan')
BDFS = ('0000:23:00.0', '0000:47:00.0')
LAN = ipaddress.ip_network('192.168.2.0/24')
ROOT_FLOOR = 27_000_000_000
ROOT_START = ROOT_FLOOR + 256 * 1024**2
ROOT_ONGOING = ROOT_FLOOR + 128 * 1024**2
EXTERNAL_FLOOR = 2 * 1024**3
DUMP_BYTES = 310_364_224 + 9_699_332          # one RESET target + draft dump (or one explicit DUMP)
META_RESERVE = 64 * 1024**2
MEM_START = 98_806_740_766                    # corrected-engine admission (recurrent-f32 plans)
MEM_ONGOING = 8 * 1024**3
NATIVE_SECONDS = 172_800                      # native hard maximum; engine deadline starts at load
SAMPLE_SECONDS = 3.0
INCONCLUSIVE_LIMIT = 10                       # consecutive unusable observations before halting
QUEUE_LIMIT = 8
KEY_FILE = Path('/home/steve/.config/sc117-lan/api_key')
UNIT = 'sc117-lan.service'
UNIT_PROPERTIES = {'Restart': 'no', 'SendSIGKILL': 'no', 'KillMode': 'process', 'TimeoutStopUSec': 'infinity', 'LimitAS': 'infinity'}
AFFINITY = [0, 1, 2, 3, 16, 17, 18, 19]
COORD = Path('/home/steve/own-xpu-runtime-results/coordination/chain-lanes-v1')
MARKERS = tuple(COORD / n for n in ('active-lane-A.json', 'active-lane-B.json', 'hold-lane-B'))
REPO = LANE.parents[2]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ADAPTER_FILE = os.environ.get('SC117_ADAPTER', 'adapter5.py')
A = load(P / ADAPTER_FILE, 'sc117_lan_adapter')
SP = load(LANE / 'service-speed/a-reset-stream/stream_parser.py', 'sc117_stream_parser')
B0_LAUNCH_B = LANE / 'recurrent-f32/operating/launch-b/evidence/device-b/review.json'
B0_LONGER_A = LANE / 'recurrent-f32/operating/longer-a/evidence/actual/external/prompt-00-none/request-result.json'
OBS = load(LANE / 'operating/observe.py', 'sc117_lan_observe')
CHAT = load(P / 'chat.py', 'sc117_lan_chat')


def utc():
    return datetime.now(timezone.utc).isoformat()


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def save(path, value):
    tmp = Path(str(path) + '.tmp')
    with open(tmp, 'w') as f:
        json.dump(value, f, indent=2)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def parent_pid(pid):
    try:
        return int(Path(f'/proc/{int(pid)}/stat').read_text().rsplit(')', 1)[1].split()[1])
    except (OSError, ValueError, IndexError):
        return None


class Monitor:
    """Passive host observation on its own thread. check() is O(1) for the rank I/O loop."""

    def __init__(self, control):
        self.control = control
        self.lock = threading.Lock()
        self.first = None
        self.identities = []
        self.contacts = [False, False]
        self.baseline = None
        self.latest = None
        self.samples = 0
        self.inconclusive = 0
        self.notes = []
        self.wake = threading.Event()

    def latch(self, error):
        with self.lock:
            if self.first is None:
                self.first = error
                self.wake.set()

    def check(self):
        if self.first is not None:
            raise self.first

    def register(self, pid):
        identity = OBS.process_identity(pid)
        require(identity is not None, 'new rank identity unavailable')
        with self.lock:
            require(len(self.identities) < 2, 'only two rank launches')
            self.identities.append((pid, identity['start_ticks']))

    def admit(self):
        require(not any(os.path.lexists(m) for m in MARKERS), 'a campaign lane marker is present; not starting')
        s = OBS.observe()
        require(s['known_fault_baseline_matches'], 'kernel fault list differs from the recorded baseline; not starting')
        require(not s['identity_races'] and not s['inventory']['errors'], 'inconclusive holder inventory at admission')
        self.target = {b: OBS.target_nodes(s, b) for b in BDFS}
        busy = [h for h in s['inventory']['holders'] if any(h['node'] in n for n in self.target.values())]
        require(not busy, f'target cards already held: {busy}')
        require(s['memory']['MemAvailable'] >= MEM_START, f"MemAvailable {s['memory']['MemAvailable']} < {MEM_START}")
        require(s['root_free_bytes'] >= ROOT_START, f"root free {s['root_free_bytes']} < {ROOT_START}")
        ext = shutil.disk_usage(EVIDENCE_PARENT).free
        require(ext >= EXTERNAL_FLOOR + DUMP_BYTES + META_RESERVE, f'evidence disk free {ext} below floor+dump')
        self.baseline = s
        self.latest = s
        return s

    def validate(self, s, holders=True):
        b = self.baseline
        require(s['boot'] == b['boot'], 'boot changed')
        known = {(f['message'], f['timestamp']) for f in b['kernel']['faults']}
        new = [f for f in s['kernel']['faults'] if (f['message'], f['timestamp']) not in known]
        require(not new, 'new kernel GPU fault: ' + json.dumps(new)[:2000])
        require(s['drm'] == b['drm'], 'DRM topology changed')
        require(s['memory']['MemAvailable'] >= MEM_ONGOING, 'MemAvailable below 8 GiB')
        if not holders:
            return
        with self.lock:
            identities = list(self.identities)
        for h in s['inventory']['holders']:
            for rank, bdf in enumerate(BDFS):
                if h['node'] in self.target[bdf]:
                    key = (h['pid'], (s['holders'].get(str(h['pid'])) or {}).get('start_ticks'))
                    if key not in identities and len(identities) < 2 and parent_pid(h['pid']) == os.getpid():
                        continue  # our rank between Popen and registration
                    require(key in identities, f"foreign holder {key} on target card {bdf}")
                    require(identities.index(key) == rank, f'rank contacted the wrong card {bdf}')
                    self.contacts[rank] = True
            if (h['pid'], (s['holders'].get(str(h['pid'])) or {}).get('start_ticks')) in identities:
                require(any(h['node'] in n for n in self.target.values()), 'rank contacted a non-target card ' + h['node'])
        vision = s['units'].get('qwen38-27b-vision', {}).get('MainPID')
        if vision != b['units'].get('qwen38-27b-vision', {}).get('MainPID') and 'vision' not in self.notes:
            self.notes.append('vision')  # recorded only; not ours to protect by halting

    def sample(self):
        try:
            s = OBS.observe()
        except Exception as error:
            self.inconclusive += 1
            if self.inconclusive >= INCONCLUSIVE_LIMIT:
                self.latch(RuntimeError('passive observation failing repeatedly: ' + repr(error)))
            return None
        self.samples += 1
        self.latest = s
        if s['identity_races'] or s['inventory']['errors']:
            try:
                self.validate(s, holders=False)  # fault/memory/boot checks still apply
            except Exception as error:
                self.latch(error)
            self.inconclusive += 1
            if self.inconclusive >= INCONCLUSIVE_LIMIT:
                self.latch(RuntimeError('passive inventory inconclusive repeatedly'))
            return None
        self.inconclusive = 0
        try:
            self.validate(s)
        except Exception as error:
            self.latch(error)
        return s

    def run(self, stop):
        while not stop.is_set():
            self.sample()
            try:
                save(self.control / 'monitor.json', dict(utc=utc(), samples=self.samples, first_error=repr(self.first) if self.first else None,
                     identities=self.identities, contacts=self.contacts, inconclusive=self.inconclusive, notes=self.notes,
                     root_free=self.latest and self.latest['root_free_bytes'],
                     mem_available=self.latest and self.latest['memory']['MemAvailable']))
            except Exception:
                pass
            stop.wait(SAMPLE_SECONDS)

    def drained(self, transport):
        try:
            return self._drained(transport)
        except Exception:
            return False

    def _drained(self, transport):
        if transport is not None:
            for child in getattr(transport, 'children', []):
                if child.poll() is None:
                    return False
            if getattr(transport, 'spawn_uncertain', False):
                return False
        try:
            s = OBS.observe()
        except Exception:
            return False
        if s['identity_races'] or s['inventory']['errors'] or s['drm'] != self.baseline['drm']:
            return False
        nodes = set().union(*[set(n) for n in self.target.values()])
        if any(h['node'] in nodes for h in s['inventory']['holders']):
            return False
        return not any((i := OBS.process_identity(pid)) is not None and i['start_ticks'] == t for pid, t in self.identities)


class Engine:
    def __init__(self, control, evidence, monitor):
        self.control = control
        self.evidence = evidence
        self.monitor = monitor
        self.lock = threading.Lock()
        self.t = None
        self.count = 0
        self.previous = None
        self.log = control / 'requests.jsonl'
        self.log_bytes = 0
        self.prefill_rows = 0      # batched prefill rows for requests; set only after this binary's prefill gate passed
        self.last_result = None    # last native result (gate use only; never logged)

    def start(self):
        plan = A.build_plan(self.control / 'ranks', mini=False, max_new=128, seconds=NATIVE_SECONDS,
                            evidence_output=self.evidence)
        save(self.control / 'plan.json', plan)
        t = A.Transport.__new__(A.Transport)
        self.t = t
        t.__init__(plan, admit=lambda p: require(p == plan, 'plan identity'), check=self.monitor.check,
                   launch_hook=self.monitor.register)
        return plan

    def storage_ok(self):
        try:
            root = shutil.disk_usage(self.control).free
            ext = shutil.disk_usage(self.evidence).free
        except OSError as error:
            return 'storage check failed: ' + repr(error)
        if root < ROOT_ONGOING:
            return f'root disk free {root} is below the protected floor {ROOT_ONGOING}'
        need = EXTERNAL_FLOOR + META_RESERVE + (0 if self.dump_free() else DUMP_BYTES)
        if ext < need:
            return f'evidence disk free {ext} is below {need}'
        return None

    def dump_free(self):
        return self.t is not None and '--reset-dump' in getattr(self.t, 'plan', {}).get('service_flags', [])

    def activations(self):
        flags = getattr(self.t, 'plan', {}).get('service_flags', []) if self.t is not None else []
        return flags[flags.index('--activations') + 1] if '--activations' in flags else 'bf16'

    def streaming(self):
        return self.t is not None and 'jsonl' in getattr(self.t, 'plan', {}).get('service_flags', [])

    def release(self, previous):
        """Service retention: delete the RESET dump(s) written into the previous request's directory."""
        if previous is None:
            return 0
        removed = 0
        if previous == self.t.out:  # first request ran in the rank root dirs
            targets = [previous / 'rank0/state-2147483647', previous / 'rank1/state-2147483647', previous / 'rank0/draft-final-state']
        else:
            require(previous.parent == self.t.out and previous.name.startswith('req-'), 'retention path')
            targets = [previous]
        for path in targets:
            if path.exists():
                removed += sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
                shutil.rmtree(path)
        return removed

    @staticmethod
    def pump(stream):
        if stream['fd'] is None:
            try:
                stream['fd'] = os.open(stream['path'], os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
            except FileNotFoundError:
                return
        while True:
            data = os.read(stream['fd'], 65536)
            if not data:
                return
            for row in stream['parser'].feed(data):
                if stream['cb'] is not None:
                    try:
                        stream['cb'](row['token_id'])
                    except Exception:
                        stream['cb'] = None  # a client problem never touches the engine

    def dump_hashes(self):
        """Explicit full target-state DUMP on both ranks; physical file hashes; dump removed after hashing."""
        t, out = self.t, {}
        for rank in (0, 1):
            t.call(rank, A.BASE.DUMP, position=2147483647)
            d = t.request_output / f'rank{rank}' / 'state-2147483647'
            A.BUNDLE.read_state(d)  # independent seal/index/payload verification
            out[f'rank{rank}'] = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(d.iterdir())}
            shutil.rmtree(d)
        return out

    def dump_buffers(self):
        """Explicit full target-state DUMP on both ranks; per-buffer content hashes; dump removed after hashing."""
        t, out = self.t, {}
        for rank in (0, 1):
            t.call(rank, A.BASE.DUMP, position=2147483647)
            d = t.request_output / f'rank{rank}' / 'state-2147483647'
            out[f'rank{rank}'] = {k: v for k, v in A.BUNDLE.read_state(d).items() if k != 'state.json'}
            shutil.rmtree(d)
        return out

    def generate(self, prompt, max_new, label, on_token=None, mode='mtp', force_reset=False, prefill=None):
        """Caller holds self.lock. Returns (tokens, result-summary).

        With the streaming build, rank0 appends each target-confirmed token to
        confirmed-tokens.jsonl; we tail it from the transport's health callback
        and the final list must equal native-result.json exactly.
        """
        t = self.t
        self.monitor.check()
        t.check_alive()
        self.count += 1
        started = time.monotonic()
        reset_ms = released = 0
        stale = None
        if self.count > 1 or force_reset:
            dest = t.out / f'req-{self.count:06d}'
            r0 = time.monotonic()
            A.reset(t, dest)
            reset_ms = (time.monotonic() - r0) * 1000
            stale, self.previous = self.previous, dest
        else:
            t.request_output = t.out
            self.previous = t.out
        stream = None
        if self.streaming():
            stream = dict(path=t.request_output / 'rank0' / 'confirmed-tokens.jsonl', fd=None,
                          parser=SP.ConfirmedTokens(t.seq[0] + 1, max_new, 248320), cb=on_token)
            require(not stream['path'].exists(), 'stale token stream file')
            original_check = t.check

            def check():
                original_check()
                self.pump(stream)
            t.check = check
        try:
            if prefill is None:
                prefill = self.prefill_rows
            if hasattr(A, 'NativeController'):  # adapter6+: optional batched prefill rows per request
                r = A.NativeController(t, A.BASE.Draft(mode), True, False, prefill=prefill).run(prompt, max_new, CHAT.EOS)
            else:
                require(not prefill, 'adapter has no batched prefill')
                r = A.BASE.NativeController(t, A.BASE.Draft(mode), True, False).run(prompt, max_new, CHAT.EOS)
        finally:
            if stream is not None:
                t.check = original_check
        if stream is not None:
            self.pump(stream)
            streamed = stream['parser'].finish(r)  # exact equality to the native result, or StreamError
            os.close(stream['fd'])
            require(streamed == list(r['tokens']), 'stream/result mismatch')
        # Retention: the dump RESET just wrote is not needed; drop it before the next RESET.
        released = self.release(stale)
        self.last_result = r
        tokens = list(r['tokens'])
        require(0 < len(tokens) <= max_new and all(0 <= x < 248320 for x in tokens), 'native output bounds')
        stats = r['stats']
        summary = dict(request=self.count, label=label, mode=mode, streamed=stream is not None, prompt_tokens=len(prompt), output_tokens=len(tokens),
                       mtp=dict(guesses=stats['guesses'], hits=stats['hits'], misses=stats['misses']),
                       prompt_wall_ms=r.get('prompt_wall_ms'), decode_wall_ms=r.get('decode_wall_ms'),
                       decode_tok_s=r.get('decode_tok_s'), reset_ms=reset_ms, released_dump_bytes=released, prefill_rows=prefill or 0,
                       wall_s=time.monotonic() - started)
        line = json.dumps(dict(utc=utc(), **summary)) + '\n'
        if self.log_bytes < 50 * 1024**2:
            with open(self.log, 'a') as f:
                f.write(line)
            self.log_bytes += len(line)
        return tokens, summary


class State:
    def __init__(self):
        self.phase = 'starting'
        self.detail = ''
        self.waiting = 0
        self.lock = threading.Lock()
        self.stop = threading.Event()


def b0_gate(engine, selftest):
    """One-time device gate for a new binary: tokens and full target state must equal engine 5926."""
    review = json.loads(B0_LAUNCH_B.read_text())
    want = {f'rank{r}': next(c['physical_sha256'] for c in review['captures'] if c['path'] == f'prompt-00-mtp/rank{r}/state-2147483647') for r in (0, 1)}
    require(review['native_binary_sha256'] == '5926a24746c62c6b0ecdc5c3e4895f310145e0f9d74a90a5d657035b9a8151f4', 'launch-b oracle identity')
    longer = json.loads(B0_LONGER_A.read_text())
    inc_prompt, inc_tokens = longer['prompt_tokens'], longer['result']['tokens']
    require(len(inc_tokens) == 512 and longer['mode'] == 'none', 'longer-a oracle identity')
    rows = []
    def step(name, prompt, n, expected, mode='mtp', state=False, force_reset=False):
        with engine.lock:
            seen = []
            tokens, summary = engine.generate(prompt, n, name, on_token=seen.append, mode=mode, force_reset=force_reset)
            row = dict(name=name, mode=mode, tokens_equal=tokens == expected, stream_equal=seen == tokens if engine.streaming() else None,
                       first_difference=next((i for i, (a, b) in enumerate(zip(tokens, expected)) if a != b), None), summary=summary)
            if state:
                got = engine.dump_hashes()
                row.update(state_equal=got == want, state=got)
            rows.append(row)
        require(row['tokens_equal'], f'B0 gate {name}: tokens differ from engine 5926 at {row["first_difference"]}')
        require(row['stream_equal'] in (True, None), f'B0 gate {name}: confirmed-token stream differs')
        require(row.get('state_equal', True), f'B0 gate {name}: full target state differs from launch-b')
    # launch-b lifecycle: RESET, request, DUMP
    step('selftest-after-reset', selftest['prompt_tokens'], 32, selftest['expected_tokens'], state=True, force_reset=True)
    step('incident512-target-only', inc_prompt, 512, inc_tokens, mode='none')
    step('incident512-mtp', inc_prompt, 512, inc_tokens)
    step('selftest-after-long', selftest['prompt_tokens'], 32, selftest['expected_tokens'], state=True)
    return dict(passed=True, binary_sha256=engine.t.plan['binary_sha256'], service_flags=engine.t.plan['service_flags'],
                oracle=dict(state='launch-b prompt-00-mtp physical state hashes (engine 5926)', tokens='launch-b selftest 32 + longer-a incident 512 target-only (engine 5926)'),
                rows=rows, utc=utc())


PREFILL_SUITE = P.parent.parent / 'service-speed/e-reference/runs/f32suite/inputs'
PREFILL_SCALAR = P.parent.parent / 'service-speed/e-reference/runs/f32-suite.json'
LAYER = re.compile(r'^(alternate-)?blk\.(\d+)\.')


def split_differences(want, got, split, oracle_split=24):
    """F32 oracle comparison when layers [split, oracle_split) moved from rank 0 to rank 1 (pipeline stage boundaries
    only copy activations, so every layer's arithmetic is unchanged). Exact per rank for unmoved layers and global
    buffers. A moved layer's persistent state (KV, pooled keys, recurrent state, histories) must equal one of the two
    rank-0 banks in the oracle (rank 0 alternates banks for speculation; rank 1 keeps one). Not compared, by
    construction: rank 0's boundary hand-off streams.bin, and a moved layer's transient buffers, which on rank 0 hold
    the last speculative position."""
    out = {r: [] for r in want}
    for r, table in want.items():
        for k, v in table.items():
            m = LAYER.match(k)
            if not m:
                if not (r == 'rank0' and k == 'streams.bin') and got[r].get(k) != v:
                    out[r].append(k)
                continue
            layer = int(m.group(2))
            moved = r == 'rank0' and split <= layer < oracle_split
            if not moved:
                if got[r].get(k) != v:
                    out[r].append(k)
            elif not m.group(1) and PERSISTENT.search(k):
                if got['rank1'].get(k) not in (v, table.get('alternate-' + k)):
                    out['rank1'].append(k)
    return {r: sorted(v) for r, v in out.items()}


PERSISTENT = re.compile(r'(^alternate-|\.(keys|values|raw|pooled|state)\.bin$|history\.bin$|^position\.bin$|^token_history\.bin$)')


def prefill_gate(engine, rows):
    """One-time device gate for batched prefill on this binary, in F32 mode.

    1. The binary's token-by-token path still reproduces the serving engine 32654dfb's F32 suite output.
    2. For each case, the same request runs token-by-token and then batched (each after a RESET): every emitted
       token, every MTP guess and every persistent target state buffer (KV, pooled/raw keys, both recurrent banks,
       histories, position) must be identical. Other buffers are reported, not gated.
    Returns the evidence dict; passed is False on any mismatch (device errors raise).
    """
    suite = {r['prompt_id']: r for r in json.loads(PREFILL_SCALAR.read_text())['rows']}
    def source(pid):
        return json.loads((PREFILL_SUITE / f'in-{pid}.json').read_text())['tokens']
    report, passed = [], True
    # 1. Unchanged token-by-token path: first 64 outputs of two suite prompts.
    for pid in ('code-review', 'customer-email'):
        r = suite[pid]
        with engine.lock:
            tokens, summary = engine.generate(r['prompt_token_ids'], 64, f'prefill-gate-scalar-{pid}', force_reset=True, prefill=0)
        first = next((i for i, (a, b) in enumerate(zip(tokens, r['output_token_ids'])) if a != b), None)
        # A changed token-by-token path is not a prefill problem: refuse to serve this binary at all.
        require(tokens == r['output_token_ids'][:64], f'new binary token-by-token output differs from engine 32654dfb ({pid}, output {first})')
        report.append(dict(case=f'scalar-vs-32654dfb-{pid}', passed=True))
    # 2. Batched against token-by-token. (source, prompt length, outputs, mode, rows per chunk)
    long_text = source('technical-guide')
    cases = [('code-review', rows + 2, 24, 'mtp', rows), ('code-review', rows + 3, 24, 'mtp', rows),
             ('sql-debugging', 2 * rows + 2, 24, 'mtp', rows), ('sql-debugging', 35, 24, 'mtp', rows),
             ('decision-memo', 66, 24, 'none', rows), ('decision-memo', 67, 24, 'mtp', rows),
             ('risk-register', 53, 24, 'mtp', 13), ('risk-register', 40, 24, 'mtp', 7),
             ('release-plan', None, 32, 'mtp', rows), ('incident-retrospective', None, 32, 'none', rows),
             ('technical-guide', 600, 32, 'mtp', rows)]
    for pid, length, n, mode, chunk in cases:
        prompt = suite[pid]['prompt_token_ids'] if length is None else (long_text if pid == 'technical-guide' else source(pid))[:length]
        runs = []
        for pf in (0, chunk):
            with engine.lock:
                tokens, summary = engine.generate(prompt, n, f'prefill-gate-{pid}-{len(prompt)}-{pf}', mode=mode, force_reset=True, prefill=pf)
                guesses = list(engine.last_result.get('guess_sequence') or [])
                state = engine.dump_buffers()
            runs.append(dict(tokens=tokens, guesses=guesses, state=state, prompt_wall_ms=summary['prompt_wall_ms']))
        a, b = runs
        differ = {rank: sorted(k for k in a['state'][rank] if a['state'][rank][k] != b['state'][rank].get(k)) for rank in a['state']}
        persistent = {rank: [k for k in names if PERSISTENT.search(k)] for rank, names in differ.items()}
        ok = a['tokens'] == b['tokens'] and a['guesses'] == b['guesses'] and not any(persistent.values())
        passed &= ok
        report.append(dict(case=f'{pid}-{len(prompt)}-{mode}-rows{chunk}', passed=ok, prompt_tokens=len(prompt), tokens_equal=a['tokens'] == b['tokens'],
                           guesses_equal=a['guesses'] == b['guesses'], persistent_differences=persistent, other_differences=differ,
                           prompt_wall_ms=dict(token_by_token=a['prompt_wall_ms'], batched=b['prompt_wall_ms'])))
    return dict(passed=passed, binary_sha256=engine.t.plan['binary_sha256'], rows=rows, cases=report, utc=utc())


def make_handler(state, engine, chat, key):
    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'
        server_version = 'sc117-ownrt'
        timeout = 900  # a stalled client cannot pin a handler thread forever

        def log_message(self, *args):
            pass

        def reply(self, code, obj, extra=()):
            raw = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            for k, v in extra:
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(raw)

        def error(self, code, message, kind='invalid_request_error'):
            self.close_connection = True  # the request body may be unread
            extra = [('Retry-After', '30')] if code in (429, 503, 507) else []
            self.reply(code, {'error': {'message': message, 'type': kind, 'code': code}}, extra + [('Connection', 'close')])

        def allowed(self):
            ip = ipaddress.ip_address(self.client_address[0])
            if not (ip.is_loopback or ip in LAN):
                self.error(403, 'LAN clients only', 'permission_error')
                return False
            if key and self.headers.get('Authorization', '') != 'Bearer ' + key:
                self.error(401, 'missing or wrong API key', 'authentication_error')
                return False
            return True

        def do_GET(self):
            if not self.allowed():
                return
            path = self.path.split('?', 1)[0]
            if path in ('/health', '/v1/health'):
                code = 200 if state.phase == 'ready' else 503
                self.reply(code, {'status': state.phase, 'detail': state.detail, 'waiting': state.waiting,
                                  'activations': engine.activations() if engine.t is not None else None,
                                  'prefill_rows': engine.prefill_rows,
                                  'requests_served': engine.count, 'model': CHAT.MODEL_ID})
            elif path == '/v1/models':
                self.reply(200, {'object': 'list', 'data': [{'id': CHAT.MODEL_ID, 'object': 'model', 'owned_by': 'ownrt',
                                 'context_length': CHAT.CONTEXT}]})
            else:
                self.error(404, 'not found')

        def do_POST(self):
            if not self.allowed():
                return
            if self.path.split('?', 1)[0] not in ('/v1/chat/completions', '/chat/completions'):
                return self.error(404, 'only /v1/chat/completions is served')
            try:
                n = int(self.headers.get('Content-Length', '0'))
                require(0 < n <= 4 * 1024**2, 'body size')
                body = json.loads(self.rfile.read(n))
                req = CHAT.parse(body, chat)
            except CHAT.RequestError as e:
                return self.error(400, str(e))
            except Exception as e:
                return self.error(400, 'bad request: ' + str(e))
            if state.phase != 'ready':
                return self.error(503, f'service {state.phase}: {state.detail}', 'unavailable')
            with state.lock:
                if state.waiting >= QUEUE_LIMIT:
                    return self.error(429, 'queue full; one generation runs at a time', 'rate_limit')
                state.waiting += 1
            streaming = req['stream']
            self.wlock = threading.Lock()
            queued = True
            try:
                if streaming:
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/event-stream')
                    self.send_header('Cache-Control', 'no-cache')
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    self.close_connection = True
                got = False
                while not got:
                    got = engine.lock.acquire(timeout=10)
                    if not got and streaming:
                        self.send_bytes(b': queued\n\n')
                    if state.phase != 'ready':
                        if got:
                            engine.lock.release()
                        return self.stream_error(streaming, 503, f'service {state.phase}')
                try:
                    with state.lock:
                        state.waiting -= 1
                        queued = False
                    reason = engine.storage_ok()
                    if reason:
                        return self.stream_error(streaming, 507, reason)
                    tokens, summary = self.run_engine(req, streaming)
                finally:
                    engine.lock.release()
            except _Halt as h:
                return self.stream_error(streaming, 503, 'engine halted: ' + str(h))
            except OSError:
                return
            finally:
                if queued:
                    with state.lock:
                        state.waiting -= 1
            summary['ignored_sampling_parameters'] = req['ignored_sampling']
            summary['output_token_ids'] = list(tokens)  # response only; never written to the request log
            summary['activations'] = engine.activations()
            summary['decoding'] = 'greedy (target argmax); MTP proposals are verified by the target'
            full = CHAT.completion(req, tokens, summary, chat)
            if not streaming:
                return self.reply(200, full)
            try:
                tail, finish = self.streamer.finish(tokens)
                for field, text in tail:
                    self.send_delta({field: text})
                summary['stream_text_mismatch'] = self.streamer.mismatch
                self.send_chunk({}, finish)
                if req['include_usage']:
                    self.send_bytes(b'data: ' + json.dumps(dict(self.chunk_base, choices=[], usage=full['usage'])).encode() + b'\n\n')
                self.send_bytes(b'data: [DONE]\n\n')
            except OSError:
                pass

        def send_chunk(self, delta, finish=None):
            if not self.role_sent:
                delta = dict(role='assistant', **delta)
                self.role_sent = True
            chunk = dict(self.chunk_base, choices=[{'index': 0, 'delta': delta, 'finish_reason': finish}])
            self.send_bytes(b'data: ' + json.dumps(chunk).encode() + b'\n\n')

        def send_delta(self, delta):
            self.send_chunk(delta)

        def send_bytes(self, raw):
            with self.wlock:
                self.wfile.write(raw)
                self.wfile.flush()

        def run_engine(self, req, streaming):
            on_token = writer = None
            if streaming:
                import queue, uuid
                self.chunk_base = {'id': 'chatcmpl-' + uuid.uuid4().hex, 'object': 'chat.completion.chunk',
                                   'created': int(time.time()), 'model': CHAT.MODEL_ID}
                self.role_sent = False
                self.streamer = CHAT.Streamer(req, chat)
                tokens_q = queue.Queue()
                on_token = tokens_q.put

                def write():
                    # Decoding and socket writes happen here, never on the engine thread.
                    alive = True
                    while True:
                        try:
                            item = tokens_q.get(timeout=10)
                        except queue.Empty:
                            item = False
                        if item is None:
                            return
                        if not alive:
                            continue
                        try:
                            if item is False:
                                self.send_bytes(b': generating\n\n')
                                continue
                            for field, text in self.streamer.feed(item):
                                self.send_delta({field: text})
                        except OSError:
                            alive = False
                writer = threading.Thread(target=write, daemon=True)
                writer.start()
            try:
                return engine.generate(req['prompt_ids'], req['max_new'], 'client', on_token=on_token)
            except BaseException as error:
                state.fault(error)
                raise _Halt(repr(error))
            finally:
                if writer is not None:
                    tokens_q.put(None)
                    writer.join()

        def stream_error(self, streaming, code, message):
            if not streaming:
                return self.error(code, message, 'unavailable')
            try:
                self.send_bytes(b'data: ' + json.dumps({'error': {'message': message, 'code': code}}).encode() + b'\n\n')
            except OSError:
                pass
    return Handler


class _Halt(RuntimeError):
    pass


class Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def lan_address(address):
    for line in os.popen('ip -4 -o addr show').read().splitlines():
        if f' {address}/' in line:
            return line.split()[1]
    raise RuntimeError(f'{address} is not assigned to any interface')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--bind', default='192.168.2.44')
    ap.add_argument('--port', type=int, default=18160)
    ap.add_argument('--lifetime-hours', type=float, default=47.0)
    a = ap.parse_args()
    require(0.1 <= a.lifetime_hours <= NATIVE_SECONDS / 3600 - 0.5, 'lifetime must end before the native deadline')
    require(os.environ.get('INVOCATION_ID'), 'run through the systemd user unit, not directly')
    text = subprocess.run(['systemctl', '--user', 'show', UNIT, '--property=' + ','.join(['MainPID', *UNIT_PROPERTIES])],
                          capture_output=True, text=True, timeout=30).stdout
    row = dict(line.split('=', 1) for line in text.splitlines() if '=' in line)
    require(row.get('MainPID') == str(os.getpid()), f'must run as {UNIT}')
    for k, v in UNIT_PROPERTIES.items():
        require(row.get(k) == v, f'unsafe unit property {k}={row.get(k)}')
    require(resource.getrlimit(resource.RLIMIT_AS) == (resource.RLIM_INFINITY, resource.RLIM_INFINITY), 'unlimited address space required')
    require(os.getpriority(os.PRIO_PROCESS, 0) == 19 and sorted(os.sched_getaffinity(0)) == AFFINITY, 'nice 19 / CPUs 0-3,16-19 required')
    for d in (P, Path('/home/steve'), REPO):
        require(not (d / 'igdrcl.config').exists(), f'unadmitted driver config in {d}')
    interface = lan_address(a.bind)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    for parent in (CONTROL_PARENT, EVIDENCE_PARENT):
        parent.mkdir(mode=0o700, exist_ok=True)
    control = CONTROL_PARENT / f'run-{stamp}'
    control.mkdir(mode=0o700)
    (CONTROL_PARENT / 'current').unlink(missing_ok=True)
    (CONTROL_PARENT / 'current').symlink_to(control.name)
    evidence = EVIDENCE_PARENT / f'run-{stamp}'
    key = KEY_FILE.read_text().strip() if KEY_FILE.exists() else None

    state = State()
    monitor = Monitor(control)
    engine = Engine(control, evidence, monitor)
    chat = CHAT.Chat()
    status = dict(schema='sc117.lan.run.v1', started=utc(), pid=os.getpid(), bind=a.bind, interface=interface, port=a.port,
                  control=str(control), evidence=str(evidence), api_key_required=bool(key), lifetime_hours=a.lifetime_hours,
                  tokenizer=chat.authority, model=str(A.MODEL), draft_model=str(A.DRAFT_MODEL))
    save(control / 'run.json', status)
    faults = []
    fault_lock = threading.Lock()

    def fault(error):
        with fault_lock:
            if faults:
                return
            faults.append(error)
            state.phase = 'halted'
            state.detail = repr(error)[:500]
            state.stop.set()
            monitor.wake.set()
    state.fault = fault

    def on_signal(sig, frame):
        if state.phase == 'starting':
            # Cooperative stop of a load in progress: the rank ready-wait polls monitor.check().
            monitor.latch(RuntimeError(f'stop requested by signal {sig} during startup'))
        elif state.phase == 'ready':
            state.phase = 'stopping'
            state.detail = f'signal {sig}: finishing current request, then stopping'
        state.stop.set()
        monitor.wake.set()
    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)

    handler = make_handler(state, engine, chat, key)
    servers = [Server((a.bind, a.port), handler), Server(('127.0.0.1', a.port), handler)]
    for s in servers:
        threading.Thread(target=s.serve_forever, daemon=True).start()
    print(json.dumps(dict(listening=[f'http://{a.bind}:{a.port}', f'http://127.0.0.1:{a.port}'], control=str(control))), flush=True)

    monitor_stop = threading.Event()
    result = dict(passed=False)
    try:
        state.detail = 'admission checks'
        monitor.admit()
        threading.Thread(target=monitor.run, args=(monitor_stop,), daemon=True).start()
        require(not state.stop.is_set(), 'stopped before load')
        state.detail = 'loading model on both cards'
        engine.start()
        st = json.loads((P / 'selftest.json').read_text())
        rows = []
        marker = P / 'evidence' / f"b0-{engine.t.plan['binary_sha256'][:16]}.json"
        mode = engine.activations()
        status['activations'] = mode
        save(control / 'run.json', status)
        if mode == 'bf16' and engine.t.plan['binary_sha256'] != '5926a24746c62c6b0ecdc5c3e4895f310145e0f9d74a90a5d657035b9a8151f4' and not marker.exists():
            state.detail = 'one-time B0 device gate for the new binary (tokens + full state vs engine 5926)'
            gate = b0_gate(engine, st)
            marker.parent.mkdir(exist_ok=True)
            save(marker, gate)
            save(control / 'b0-gate.json', gate)
        for i in range(2):  # fresh state, then after RESET + retention: both must equal launch-b
            require(not state.stop.is_set(), 'stopped during self-test')
            state.detail = f'startup self-test {i + 1}/2 (fixed 32-token MTP output)'
            with engine.lock:
                tokens, summary = engine.generate(st['prompt_tokens'], st['max_new'], f'selftest-{i + 1}')
            if mode == 'bf16':
                require(tokens == st['expected_tokens'], f'self-test {i + 1} output differs from launch-b: {tokens}')
            rows.append(dict(summary, tokens=tokens))
        if mode == 'f32':
            # Exact mode differs from the BF16 engine by design. Gate: deterministic within the process, and equal to
            # the pinned record of this binary's first F32 run (whose agreement with the exact reference is checked offline).
            require(rows[0]['tokens'] == rows[1]['tokens'], 'F32 self-test not deterministic across RESET')
            record = P / 'evidence' / f"f32-selftest-{engine.t.plan['binary_sha256'][:16]}.json"
            if record.exists():
                require(json.loads(record.read_text())['tokens'] == rows[0]['tokens'], 'F32 self-test differs from this binary\'s pinned F32 record')
            else:
                record.parent.mkdir(exist_ok=True)
                save(record, dict(binary_sha256=engine.t.plan['binary_sha256'], prompt_tokens=st['prompt_tokens'], tokens=rows[0]['tokens'],
                                  status='first F32 run; reference agreement checked offline (service-speed/e-reference)', utc=utc()))
        if mode == 'f32':
            # Decode-path exactness: after a RESET and the fixed self-test, every target state buffer on both ranks must
            # equal the pinned F32 oracle (recorded once from a gated binary). Kernel changes that claim to be exact must
            # pass this before anything else.
            with engine.lock:
                engine.generate(st['prompt_tokens'], st['max_new'], 'f32-state-check', force_reset=True, prefill=0)
                f32_state = engine.dump_buffers()
            oracle = P / 'evidence' / 'f32-state-oracle.json'
            if oracle.exists():
                want = json.loads(oracle.read_text())
                split = int(os.environ.get('SC117_TARGET_SPLIT', '24'))
                differ = (split_differences(want['state'], f32_state, split) if split != 24 else
                          {r: sorted(k for k in want['state'][r] if want['state'][r][k] != f32_state[r].get(k)) for r in want['state']})
                (P / 'evidence' / f"f32-state-{engine.t.plan['binary_sha256'][:16]}{'' if split == 24 else f'-split{split}'}.json").write_text(json.dumps(
                    dict(binary_sha256=engine.t.plan['binary_sha256'], oracle_binary_sha256=want['binary_sha256'], differences=differ, utc=utc()), indent=2) + '\n')
                require(not any(differ.values()), f"F32 decode state differs from the oracle binary {want['binary_sha256'][:12]}: {differ}")
            else:
                save(oracle, dict(binary_sha256=engine.t.plan['binary_sha256'], selftest='selftest.json prompt, 32 tokens MTP, after RESET',
                                  state=f32_state, utc=utc()))
        rows_wanted = getattr(A, 'PREFILL_ROWS', 0)
        if rows_wanted and mode == 'f32':
            # Kernel-choice overrides change the arithmetic path: each combination gets its own gate.
            overrides = ''.join(f"-{k[len('OWNRT_PREFILL_'):].lower()}{v}" for k, v in sorted(os.environ.items())
                                if k.startswith('OWNRT_PREFILL_') and k != 'OWNRT_PREFILL_PROFILE')
            overrides += ''.join(f"-{k[len('OWNRT_'):].lower()}{v}" for k, v in sorted(os.environ.items())
                                 if k.startswith('OWNRT_') and not k.startswith('OWNRT_PREFILL_') and 'PROFILE' not in k)
            if os.environ.get('SC117_TARGET_SPLIT', '24') != '24':
                overrides += '-split' + os.environ['SC117_TARGET_SPLIT']
            if os.environ.get('SC117_DISPATCH'):
                overrides += '-dispatch' + hashlib.sha256(Path(os.environ['SC117_DISPATCH']).read_bytes()).hexdigest()[:12]
            if len(overrides) > 120:  # long switch lists: keep the file name bounded, the hash still keys the gate
                overrides = '-ov' + hashlib.sha256(overrides.encode()).hexdigest()[:16]
            marker = P / 'evidence' / f"prefill-{engine.t.plan['binary_sha256'][:16]}-rows{rows_wanted}{overrides}.json"
            if not marker.exists():
                state.detail = f'one-time batched-prefill gate ({rows_wanted} rows): tokens, guesses and persistent state vs token-by-token'
                gate = prefill_gate(engine, rows_wanted)
                marker.parent.mkdir(exist_ok=True)
                save(marker, gate)
                save(control / 'prefill-gate.json', gate)
            gate = json.loads(marker.read_text())
            engine.prefill_rows = rows_wanted if gate['passed'] else 0
            status['prefill_rows'] = engine.prefill_rows
            (control / 'run.json').write_text(json.dumps(status, indent=2) + '\n')
        require(all(monitor.contacts), 'both rank contacts must be observed on their target cards')
        save(control / 'selftest-result.json', dict(passed=True, tokens=tokens, runs=rows))
        summary = rows
        if not state.stop.is_set():
            state.phase = 'ready'
            state.detail = ''
        deadline = engine.t.start_time + a.lifetime_hours * 3600  # same clock as the transport deadline
        print(json.dumps(dict(ready=True, selftest=summary)), flush=True)
        while not state.stop.is_set():
            if monitor.first is not None:
                fault(monitor.first)
                break
            if time.monotonic() > deadline:
                state.detail = 'planned lifetime reached (native engine deadline); start the unit again to continue'
                break
            if engine.lock.acquire(blocking=False):
                try:
                    engine.t.check_alive()
                except BaseException as error:
                    fault(error)
                finally:
                    engine.lock.release()
            monitor.wake.wait(5)
            monitor.wake.clear()
    except BaseException as error:
        fault(error)
        traceback.print_exc()

    # ---- shutdown: graceful FINISH, or single cooperative stop on fault. Never kill or retry.
    if state.phase != 'halted':
        state.phase = 'stopping'
    retained = None
    original = faults[0] if faults else None
    with engine.lock:
        t = engine.t
        if t is not None and hasattr(t, 'children'):
            try:
                if original is None:
                    t.close(True)
                else:
                    secondary = A.cleanup_failure(t, original)
                    result['secondary'] = secondary
            except A.RetainedOwner as error:
                retained = error.transport
                result['retained'] = repr(error.original)
            except BaseException as error:
                if original is None:
                    original = error
                    fault(error)
                try:
                    A.cleanup_failure(t, error)
                except A.RetainedOwner as again:
                    retained = again.transport
                except BaseException:
                    pass
        # Wait for physical drain of the target cards; no signals, no device resets.
        while engine.t is not None and not monitor.drained(retained or engine.t):
            time.sleep(2)
    monitor_stop.set()
    clean = original is None and monitor.first is None
    result.update(passed=clean, stopped=utc(), requests=engine.count, first_error=repr(original) if original else None,
                  monitor_first=repr(monitor.first) if monitor.first else None, notes=monitor.notes, drained=True,
                  restarts=0, kills=0, retries=0)
    save(control / ('terminal.json' if clean else 'incident.json'), result)
    for s in servers:
        s.shutdown()
    print(json.dumps(result), flush=True)
    return 0 if clean else 1


if __name__ == '__main__':
    sys.exit(main())
