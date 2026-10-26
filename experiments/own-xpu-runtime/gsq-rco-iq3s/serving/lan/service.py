#!/usr/bin/env python3
"""SC117 Qwen3.8 Flash-Next IQ3_S on our corrected two-rank native engine, served to the LAN.

Serial (one generation at a time), MTP on, greedy only, 4096-token context (SC117_CONTEXT=32768 for 32K).
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
# A relocated copy (lab) reads the lane's shared inputs in place; at its repo location this is P.parents[1].
LANE = P.parents[1] if (P.parents[1] / 'operating').is_dir() else Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s')
CONTROL_PARENT = Path('/home/steve/own-xpu-runtime-results/sc117-lan')
# Rank output directories (per-token streams, RESET dumps). Must be a local filesystem: on the ntfs-3g USB mount a busy
# FUSE daemon stalls rank 0's per-token appends and decode drops from ~49.5 to ~40 tok/s (2026-10-25, 1 GiB dd test).
EVIDENCE_PARENT = Path(os.environ.get('SC117_EVIDENCE_PARENT', '/mnt/usb-models/own-xpu-runtime-results/sc117-lan'))
BDFS = ('0000:23:00.0', '0000:47:00.0')
LAN = ipaddress.ip_network('192.168.2.0/24')
ROOT_FLOOR = 27_000_000_000
ROOT_START = ROOT_FLOOR + 256 * 1024**2
ROOT_ONGOING = ROOT_FLOOR + 128 * 1024**2
EXTERNAL_FLOOR = 2 * 1024**3
DUMP_BYTES = (310_364_224 + 9_699_332) * (int(os.environ.get('SC117_CONTEXT', '4096')) // 4096)  # one RESET target + draft dump at 4096, scaled up as a bound
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


SESSIONS = os.environ.get('SC117_SESSIONS', '0') == '1'   # opt-in session parking; default off (unchanged service)
SESSION_DIR = Path(os.environ.get('SC117_SESSION_DIR', '/dev/shm/sc117-sessions'))
SESSION_BUDGET = int(float(os.environ.get('SC117_SESSION_BUDGET_GB', '16')) * 1024**3)
SESSION_MIN_TOKENS = 256                     # park only conversations at least this long
# VERIFY holds each rank's bundle in that rank's anonymous memory until APPLY (rank 1: ~59 MB + 33 KB/token), which the
# transport's aggregate rank anonymous-memory bound counts. Longer conversations are not parked unless raised.
SESSION_MAX_TOKENS = int(os.environ.get('SC117_SESSION_MAX_TOKENS', '16384'))
SESSION_MEMORY_MARGIN = int(float(os.environ.get('SC117_SESSION_MEMORY_MARGIN_GB', '8')) * 1024**3)  # RAM store: MemAvailable >= MEM_ONGOING + this
SESSION_READBACK = os.environ.get('SC117_SESSION_READBACK', '0') == '1'  # APPLY reads every uploaded region back
# Upper bounds for one parked session of this model (12 QSA layers x 4736 B/position F32 plus the draft's BF16 rows;
# 36 GDN states/histories, PLE history and bundle metadata), for admission before the real size is known.
SESSION_TOKEN_BYTES = 64 * 1024
SESSION_FIXED_BYTES = 160 * 1024**2


def mem_available():
    for line in Path('/proc/meminfo').read_text().splitlines():
        if line.startswith('MemAvailable:'):
            return int(line.split()[1]) * 1024
    raise RuntimeError('MemAvailable missing')


def fs_type(path):
    """Filesystem type of the mount holding `path` (longest mount-point prefix in /proc/self/mounts)."""
    path, best, kind = str(Path(path).resolve()), '', ''
    for line in Path('/proc/self/mounts').read_text().splitlines():
        fields = line.split()
        if len(fields) >= 3:
            mount = fields[1].replace('\\040', ' ')
            if (path == mount or path.startswith(mount.rstrip('/') + '/')) and len(mount) > len(best):
                best, kind = mount, fields[2]
    return kind


def session_floors(control, evidence):
    """The service's own storage floors (storage_ok): a session store on the same filesystem must keep them."""
    return [(control, ROOT_ONGOING), (evidence, EXTERNAL_FLOOR + META_RESERVE + DUMP_BYTES)]


class Sessions:
    """Parked conversations (policy only; the adapter owns the two-rank protocol, files, manifest and locks).

    Park: when the live state of a client conversation (>= SESSION_MIN_TOKENS) is about to be evicted by a RESET for a
    different prompt. Restore: when a prompt does not continue the live state, the longest parked token list H with
    prompt[:N] == H, prompt[N] == its pending token and len(prompt) >= N + 2 (the in-memory continuation rule) is
    restored and the request continues from N. Bounded by an LRU byte budget, and never admitted below the service's
    own floors: the store's filesystem floor and, on a RAM filesystem, MemAvailable >= MEM_ONGOING + margin."""

    def __init__(self, root, budget, ops, floors=(), meminfo=mem_available, ram=None, min_tokens=SESSION_MIN_TOKENS,
                 readback=SESSION_READBACK, max_tokens=SESSION_MAX_TOKENS):
        self.root, self.budget, self.ops, self.meminfo, self.min_tokens, self.readback = Path(root), budget, ops, meminfo, min_tokens, readback
        self.max_tokens = max_tokens
        self.floors = list(floors)   # [(path, floor bytes)]: a store on the same filesystem keeps that floor
        self.ram = ram
        self.index = {}              # id -> dict(path, tokens, pending, identity, bytes, used)
        self.events = []             # last decisions (request summaries)
        self.stats = dict(parked=0, restored=0, park_skipped=0, park_refused=0, restore_refused=0, evicted=0)

    def note(self, kind, **fields):
        self.events = (self.events + [dict(kind=kind, **fields)])[-32:]

    def prepare(self, identity=None):
        """Create/scan the store. Broken entries, staging leftovers and (given an identity) other engines' sessions go."""
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        st = self.root.stat()
        require(st.st_uid == os.getuid() and st.st_mode & 0o077 == 0, f'session directory {self.root} must be private and owned')
        if self.ram is None:
            self.ram = fs_type(self.root) in ('tmpfs', 'ramfs')
        for p in self.root.iterdir():
            if p.name.startswith('.') and p.name.endswith('.staging'):
                shutil.rmtree(p, ignore_errors=True)
        self.index = {}
        for path, m, error in self.ops.session_list(self.root):
            if m is None or (identity is not None and m['identity'] != identity):
                if self.ops.session_delete(path):
                    self.note('purged', id=path.name, reason=error or 'identity')
                continue
            self.index[m['id']] = dict(path=path, tokens=m['tokens'], pending=m['pending_token'], identity=m['identity'],
                                       bytes=m['bytes'], used=path.stat().st_mtime)

    def used_bytes(self):
        return sum(e['bytes'] for e in self.index.values())

    def match(self, prompt, identity):
        best = None
        for e in self.index.values():
            h, n = e['tokens'], len(e['tokens'])
            if e['identity'] == identity and len(prompt) >= n + 2 and prompt[n] == e['pending'] and prompt[:n] == h:
                if best is None or n > len(best['tokens']):
                    best = e
        return best

    def evict_one(self, keep=None):
        for sid, e in sorted(self.index.items(), key=lambda kv: kv[1]['used']):
            if sid != keep and self.ops.session_delete(e['path']):
                del self.index[sid]
                self.stats['evicted'] += 1
                self.note('evicted', id=sid, bytes=e['bytes'])
                return True
        return False

    def floor_ok(self, need):
        """None if `need` more bytes fit in the store without breaking a service floor, else the reason."""
        try:
            free = shutil.disk_usage(self.root).free
            dev = self.root.stat().st_dev
            floor = max([f for p, f in self.floors if Path(p).exists() and Path(p).stat().st_dev == dev] + [1024**3])
            if free - need < floor:
                return f'store free {free} - {need} below floor {floor}'
            if self.ram and self.meminfo() - need < MEM_ONGOING + SESSION_MEMORY_MARGIN:
                return f'MemAvailable {self.meminfo()} - {need} below {MEM_ONGOING + SESSION_MEMORY_MARGIN}'
        except OSError as error:
            return 'store check failed: ' + repr(error)
        return None

    def relieve_memory(self, need):
        """Startup admission: evict parked sessions (LRU) while MemAvailable is below `need`."""
        while self.index and self.meminfo() < need and self.evict_one():
            pass

    def park(self, t, tokens, pending, identity):
        """Save the live state. Returns the parked id, or None (skipped or refused; the live state is unchanged)."""
        if len(tokens) < self.min_tokens:
            return None
        sid = self.ops.session_id(tokens)
        e = self.index.get(sid)
        if e is not None and e['identity'] == identity and e['pending'] == pending:
            e['used'] = time.time()
            os.utime(e['path'])
            return sid
        estimate = SESSION_FIXED_BYTES + SESSION_TOKEN_BYTES * len(tokens)
        if estimate > self.budget or len(tokens) > self.max_tokens:
            self.stats['park_skipped'] += 1
            self.note('park-skipped', reason='larger than the budget or SC117_SESSION_MAX_TOKENS', tokens=len(tokens))
            return None
        while (self.used_bytes() + estimate > self.budget or self.floor_ok(estimate)) and self.evict_one():
            pass
        reason = self.floor_ok(estimate) or (None if self.used_bytes() + estimate <= self.budget else 'budget')
        if reason:
            self.stats['park_skipped'] += 1
            self.note('park-skipped', reason=reason, tokens=len(tokens))
            return None
        try:
            m = self.ops.session_save(t, self.root, tokens, pending)
        except self.ops.SessionRefused as error:
            self.stats['park_refused'] += 1
            self.note('park-refused', reason=str(error), tokens=len(tokens))
            return None
        self.index[m['id']] = dict(path=self.root / m['id'], tokens=m['tokens'], pending=m['pending_token'], identity=m['identity'],
                                   bytes=m['bytes'], used=time.time())
        while self.used_bytes() > self.budget and self.evict_one(keep=m['id']):
            pass
        self.stats['parked'] += 1
        self.note('parked', id=m['id'], tokens=len(tokens), bytes=m['bytes'])
        return m['id']

    def restore(self, t, entry, destination):
        """The adapter's two-rank restore. A refusal about the stored session itself (not a lock) drops that session."""
        try:
            r = self.ops.session_restore(t, entry['path'], destination, readback=self.readback)
        except self.ops.SessionRefused as error:
            self.stats['restore_refused'] += 1
            self.note('restore-refused', id=entry['path'].name, reason=str(error), engine=error.engine)
            if 'locked' not in str(error) and self.ops.session_delete(entry['path']):
                self.index.pop(entry['path'].name, None)
            raise
        entry['used'] = time.time()
        self.stats['restored'] += 1
        self.note('restored', id=r['id'], tokens=r['position'])
        return r


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
        # Conversation continuation (set only after this binary's continuation gate passed): the tokens whose state
        # the ranks hold (prompt + answer minus its last token) and that last token, after a clean request.
        self.continuation = False
        self.convo = None
        self.convo_last = None
        self.convo_parkable = False  # the held state came from a client request (sessions park only those)
        self.sessions = None         # Sessions when SC117_SESSIONS=1 (adapter6+); set in start()
        self.session_identity = None

    def start(self):
        plan = A.build_plan(self.control / 'ranks', mini=False, max_new=128, seconds=NATIVE_SECONDS,
                            evidence_output=self.evidence)
        save(self.control / 'plan.json', plan)
        t = A.Transport.__new__(A.Transport)
        self.t = t
        t.__init__(plan, admit=lambda p: require(p == plan, 'plan identity'), check=self.monitor.check,
                   launch_hook=self.monitor.register)
        if SESSIONS:
            require(hasattr(A, 'session_save'), 'SC117_SESSIONS=1 needs an adapter with session parking (adapter6)')
            self.session_identity = A.session_identity(t)
            self.sessions = Sessions(SESSION_DIR, SESSION_BUDGET, A, floors=session_floors(self.control, self.evidence))
            self.sessions.prepare(self.session_identity)
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

    def session_boundary(self, prompt, held):
        """Sessions on, the prompt does not continue the live state: park the live conversation before the RESET that
        evicts it, then restore the longest parked prefix of the prompt (or reset as usual). Returns (session summary,
        continuation start, reset ms, stale request directories). The caller's existing paths are unchanged."""
        t, s = self.t, self.sessions
        info = dict(parked=None, restored=None, refused=None)
        stale = [self.previous]
        if held is not None and self.convo_parkable and self.continuation and self.convo_last is not None:
            p0 = time.monotonic()
            info['parked'] = s.park(t, held, self.convo_last, self.session_identity)
            info['park_ms'] = (time.monotonic() - p0) * 1000
        candidate = s.match(prompt, self.session_identity) if self.continuation else None
        start = reset_ms = 0
        if candidate is None and self.count == 1:
            t.request_output = t.out
            self.previous = t.out
            return info, 0, 0, [x for x in stale if x is not None]
        dest = t.out / f'req-{self.count:06d}'
        r0 = time.monotonic()
        if candidate is not None:
            try:
                r = s.restore(t, candidate, dest)
                start = r['position']
                info['restored'] = dict(id=r['id'], position=r['position'], verify_ms=r['verify_ms'], apply_ms=r['apply_ms'])
            except s.ops.SessionRefused as error:
                info['refused'] = dict(reason=str(error)[:500], engine=error.engine)
                if error.engine == 'untouched':
                    A.reset(t, dest)  # nothing was sent: the ordinary reset of a fresh request
                elif error.engine == 'partial':
                    stale.append(dest)  # one rank applied: reset both again, then read the prompt fresh
                    dest = t.out / f'req-{self.count:06d}-retry'
                    A.reset(t, dest)
                # 'fresh': both ranks already sit at the fresh reset into dest; read the prompt fresh
        else:
            A.reset(t, dest)
        reset_ms = (time.monotonic() - r0) * 1000
        self.previous = dest
        info['restore_ms'] = reset_ms if candidate is not None else None
        info['store'] = dict(sessions=len(s.index), bytes=s.used_bytes(), **s.stats)
        return info, start, reset_ms, [x for x in stale if x is not None]

    def continuation_start(self, prompt, mode):
        """Position from which `prompt` can continue the held state, or 0 (fresh request)."""
        h = self.convo
        if not self.continuation or h is None or mode != 'mtp' or len(prompt) < len(h) + 2:
            return 0
        if prompt[len(h)] != self.convo_last or prompt[:len(h)] != h:
            return 0
        return len(h)

    def generate(self, prompt, max_new, label, on_token=None, mode='mtp', force_reset=False, prefill=None,
                 continue_ok=False):
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
        start = self.continuation_start(prompt, mode) if continue_ok and not force_reset else 0
        held, self.convo = self.convo, None  # cleared until this request completes cleanly
        session = None
        if start:
            dest = t.out / f'req-{self.count:06d}'
            A.redirect(t, dest)
            stale, self.previous = self.previous, dest
        elif self.sessions is not None and continue_ok and not force_reset and mode == 'mtp':
            session, start, reset_ms, stale = self.session_boundary(prompt, held)
        elif self.count > 1 or force_reset:
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
                r = A.NativeController(t, A.BASE.Draft(mode), True, False, prefill=prefill, start=start).run(prompt, max_new, CHAT.EOS)
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
        released = sum(self.release(x) for x in stale) if isinstance(stale, list) else self.release(stale)
        self.last_result = r
        tokens = list(r['tokens'])
        require(0 < len(tokens) <= max_new and all(0 <= x < 248320 for x in tokens), 'native output bounds')
        if mode == 'mtp':  # the state now holds prompt + tokens[:-1]; the next turn may continue it
            self.convo, self.convo_last = list(prompt) + tokens[:-1], tokens[-1]
            self.convo_parkable = bool(continue_ok and not force_reset)
        stats = r['stats']
        summary = dict(request=self.count, label=label, mode=mode, streamed=stream is not None, prompt_tokens=len(prompt), output_tokens=len(tokens),
                       mtp=dict(guesses=stats['guesses'], hits=stats['hits'], misses=stats['misses']),
                       prompt_wall_ms=r.get('prompt_wall_ms'), decode_wall_ms=r.get('decode_wall_ms'),
                       decode_tok_s=r.get('decode_tok_s'), reset_ms=reset_ms, released_dump_bytes=released, prefill_rows=prefill or 0,
                       continued_from=start,
                       wall_s=time.monotonic() - started)
        if session is not None:
            summary['session'] = session
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


PREFILL_SUITE = LANE / 'service-speed/e-reference/runs/f32suite/inputs'
PREFILL_SCALAR = LANE / 'service-speed/e-reference/runs/f32-suite.json'
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


def continuation_gate(engine, prompt):
    """One-time gate per binary and configuration for conversation continuation. For a long follow-up (read in batched
    chunks) and a short one (token by token): turn 1 runs fresh, turn 2 continues its state, and the same turn 2 runs
    fresh after a RESET. Both turn-2 runs must emit the same tokens and MTP guesses and leave the same full target state
    on both ranks (every buffer except the spare recurrent banks, whose roles depend on the step parity)."""
    cases, passed = [], True
    for name, suffix in (('long', (list(prompt) * 2)[:72]), ('short', list(prompt)[:3])):
        first, _ = engine.generate(prompt, 16, f'continue-gate-{name}-turn1', force_reset=True)
        turn2 = list(prompt) + first + suffix
        cont, summary_c = engine.generate(turn2, 32, f'continue-gate-{name}-continued', continue_ok=True)
        guesses_c = engine.last_result.get('guess_sequence')
        state_c = engine.dump_buffers()
        fresh, summary_f = engine.generate(turn2, 32, f'continue-gate-{name}-fresh', force_reset=True)
        guesses_f = engine.last_result.get('guess_sequence')
        state_f = engine.dump_buffers()
        differ = {r: sorted(k for k in state_f[r] if not k.startswith('alternate-') and state_f[r][k] != state_c[r].get(k))
                  for r in state_f}
        row = dict(case=name, prompt_tokens=len(turn2), continued_from=summary_c['continued_from'],
                   tokens_equal=cont == fresh, guesses_equal=guesses_c == guesses_f, state_differences=differ,
                   decode_tok_s=[summary_c['decode_tok_s'], summary_f['decode_tok_s']],
                   prompt_wall_ms=[summary_c['prompt_wall_ms'], summary_f['prompt_wall_ms']])
        row['passed'] = bool(summary_c['continued_from']) and row['tokens_equal'] and row['guesses_equal'] and not any(differ.values())
        passed = passed and row['passed']
        cases.append(row)
    engine.convo = None
    return dict(passed=passed, binary_sha256=engine.t.plan['binary_sha256'], cases=cases, utc=utc())


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
                require(0 < n <= 64 * 1024**2, 'body size')  # agents resend whole histories
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
                return engine.generate(req['prompt_ids'], req['max_new'], 'client', on_token=on_token, continue_ok=req.get('reuse', True))
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
        if SESSIONS:  # parked sessions in RAM must not block the startup memory admission: evict LRU until it can pass
            require(hasattr(A, 'session_list'), 'SC117_SESSIONS=1 needs an adapter with session parking (adapter6)')
            pre = Sessions(SESSION_DIR, SESSION_BUDGET, A)
            pre.prepare()
            pre.relieve_memory(MEM_START)
            status['sessions'] = dict(directory=str(SESSION_DIR), budget_bytes=SESSION_BUDGET, parked_at_start=len(pre.index),
                                      readback=SESSION_READBACK, min_tokens=SESSION_MIN_TOKENS, max_tokens=SESSION_MAX_TOKENS)
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
            # Context-sized buffers (KV, pooled keys, attention scratch) change extent with the context, so each
            # context has its own oracle; a new one is recorded once, after the self-test tokens above matched the
            # binary's pinned record, and the 12-prompt suite must then reproduce the 4096-context outputs.
            oracle = P / 'evidence' / ('f32-state-oracle.json' if CHAT.CONTEXT == 4096 else f'f32-state-oracle-ctx{CHAT.CONTEXT}.json')
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
            if CHAT.CONTEXT != 4096:  # buffers and extents change with the context: its own gates
                overrides += f'-ctx{CHAT.CONTEXT}'
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
            # Conversation continuation: its own one-time gate per binary and configuration (needs batched prefill).
            if engine.prefill_rows and os.environ.get('SC117_CONTINUE', '1') == '1':
                cmarker = marker.with_name(marker.name.replace('prefill-', 'continue-', 1))
                if not cmarker.exists():
                    state.detail = 'one-time continuation gate: continued turn vs fresh turn (tokens, guesses, full state)'
                    engine.continuation = True
                    save(cmarker, continuation_gate(engine, st['prompt_tokens']))
                engine.continuation = bool(json.loads(cmarker.read_text())['passed'])
                status['continuation'] = engine.continuation
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
