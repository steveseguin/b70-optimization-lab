#!/usr/bin/env python3
"""SC117 Qwen3.8 Flash-Next IQ3_S on our corrected two-rank native engine, served to the LAN.

Serial (one generation at a time), MTP on, greedy only, 4096-token context.
Run only as the systemd user unit in this directory (Restart=no, no SIGKILL).
On a GPU/kernel fault, a lost rank or a foreign holder on the target cards it
stops intake, sends the single cooperative stop, waits for physical drain and
exits. It never retries, restarts, resets a device or kills a rank.
"""
import argparse, hashlib, http.server, importlib.util, ipaddress, json, os, resource, shutil, signal, socket, subprocess
import sys, threading, time, traceback
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
DUMP_BYTES = 310_364_224 + 9_699_332          # one RESET target + draft dump
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


A = load(P / 'adapter.py', 'sc117_lan_adapter')
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
        if ext < EXTERNAL_FLOOR + DUMP_BYTES + META_RESERVE:
            return f'evidence disk free {ext} is below floor + one RESET dump'
        return None

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

    def generate(self, prompt, max_new, label):
        """Caller holds self.lock. Returns (tokens, result-summary)."""
        t = self.t
        self.monitor.check()
        t.check_alive()
        self.count += 1
        started = time.monotonic()
        reset_ms = released = 0
        stale = None
        if self.count > 1:
            dest = t.out / f'req-{self.count:06d}'
            r0 = time.monotonic()
            A.reset(t, dest)
            reset_ms = (time.monotonic() - r0) * 1000
            stale, self.previous = self.previous, dest
        else:
            t.request_output = t.out
            self.previous = t.out
        r = A.BASE.NativeController(t, A.BASE.Draft('mtp'), True, False).run(prompt, max_new, CHAT.EOS)
        # Retention: the dump RESET just wrote is not needed; drop it before the next RESET.
        released = self.release(stale)
        tokens = list(r['tokens'])
        require(0 < len(tokens) <= max_new and all(0 <= x < 248320 for x in tokens), 'native output bounds')
        stats = r['stats']
        summary = dict(request=self.count, label=label, prompt_tokens=len(prompt), output_tokens=len(tokens),
                       mtp=dict(guesses=stats['guesses'], hits=stats['hits'], misses=stats['misses']),
                       prompt_wall_ms=r.get('prompt_wall_ms'), decode_wall_ms=r.get('decode_wall_ms'),
                       decode_tok_s=r.get('decode_tok_s'), reset_ms=reset_ms, released_dump_bytes=released,
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
            summary['decoding'] = 'greedy (target argmax); MTP proposals are verified by the target'
            full = CHAT.completion(req, tokens, summary, chat)
            if not streaming:
                return self.reply(200, full)
            try:
                for chunk in CHAT.chunks(full):
                    self.send_bytes(b'data: ' + json.dumps(chunk).encode() + b'\n\n')
                if req['include_usage']:
                    usage = {k: full[k] for k in ('id', 'created', 'model')}
                    usage.update(object='chat.completion.chunk', choices=[], usage=full['usage'])
                    self.send_bytes(b'data: ' + json.dumps(usage).encode() + b'\n\n')
                self.send_bytes(b'data: [DONE]\n\n')
            except OSError:
                pass

        def send_bytes(self, raw):
            with self.wlock:
                self.wfile.write(raw)
                self.wfile.flush()

        def run_engine(self, req, streaming):
            done = threading.Event()
            if streaming:
                def keepalive():
                    while not done.wait(10):
                        try:
                            self.send_bytes(b': generating\n\n')
                        except OSError:
                            return
                threading.Thread(target=keepalive, daemon=True).start()
            try:
                return engine.generate(req['prompt_ids'], req['max_new'], 'client')
            except BaseException as error:
                state.fault(error)
                raise _Halt(repr(error))
            finally:
                done.set()

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
        for i in range(2):  # fresh state, then after RESET + retention: both must equal launch-b
            require(not state.stop.is_set(), 'stopped during self-test')
            state.detail = f'startup self-test {i + 1}/2 (fixed 32-token MTP output)'
            with engine.lock:
                tokens, summary = engine.generate(st['prompt_tokens'], st['max_new'], f'selftest-{i + 1}')
            require(tokens == st['expected_tokens'], f'self-test {i + 1} output differs from launch-b: {tokens}')
            rows.append(summary)
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
