#!/usr/bin/env python3
"""ltx_stream_driver.py - continuous clip generation against ONE packet 97 server.

    /home/steve/.venvs/ltx25-baseline/bin/python -B ltx_stream_driver.py [options]

Phase A ("warm-up") replays, step for step, the server-side preparation that
scripts/run-campaign-97.sh performs for `two-way 2 2 1 xpu:2` before its timed arm
(text-window probe, memory plan, serial capture pass with live headroom checks and
done-marker waits, coverage, pool calibration, decode probe, freeze, post-freeze
self-check, reference presence, proof arms + proof checks). It CALLS the same helper
scripts with the same arguments; only request names and index bases differ (see
DRIVER-NOTES.md for the step table). Benchmark-only steps are skipped (listed there).

Phase B ("stream forever") submits the runner's timed-arm graph
(graph-capture-all48-pipe-samp2-tsh-rep-wlean-b2-w2.json, arm
pipe-samp2-tsh-rep-wlean-b2-w2) one prompt at a time with the same per-prompt
mutations as scripts/run-throughput-fixtures-96.py, keeps at most --in-flight prompts
in the server, polls /history only for the OLDEST outstanding prompt, maps every
completed prompt to the clip it EMITTED (decode receipt emitted_index), finds that
clip's MP4 through the server's own save receipts, checks cycle-0 clips byte-for-byte
against the stability-01-b2 references (compare-clip.py, as the runner's client
does) and appends one JSON line per clip to --manifest, strictly in clip order.

Never retries a POST, never restarts or signals anything, never retry-loops: any
server error, failed-job receipt, persistent HTTP failure, FAULT.json, sequence error
or reference mismatch stops submission and exits non-zero.

Exit codes: 0 clean stop; 2 execution error; 3 reference mismatch / non-finite clip;
4 FAULT.json; 5 HTTP failure; 6 failed-job receipt; 7 preview MP4 missing/failed;
8 preflight refused; 9 disk below --min-free-gib; 12 emission sequence wrong;
13 Phase A step failed; 130 second signal (state written, in-flight abandoned).
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
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.dont_write_bytecode = True          # never leave __pycache__ anywhere (also run with -B)

LANE = Path('/home/steve/llm-optimizations/experiments/ltx25-b70')
SCRIPTS = LANE / 'scripts'
R = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
P = R / 'prepared-encoder-place-97'
MANIFEST_SHA = '6e232f72a9835727323c383bc9baaa167844b58dc6400a5de43a3b9eb4e44b9f'
PY = sys.executable
# The combination this driver reproduces (run-campaign-97.sh two-way 2 2 1 xpu:2).
LAYOUT, WORKERS, BATCH, POOL, SPEC = 'two-way', 2, 2, 1, 'xpu:2'
EXPECTED_ENV = {'NEOReadDebugKeys': '1', 'EnableDeferBacking': '0', 'LTX_BUSY_WINDOWS': '0',
                'LTX_SAMPLER_PLACEMENT': LAYOUT, 'LTX_SAMPLER_WORKERS': str(WORKERS),
                'LTX_SAMPLER_BATCH': str(BATCH), 'LTX_SAMPLER_SHARED_POOL': str(POOL),
                'LTX_DECODE_REPLICA_DEVICE': SPEC}
ENV_DEFAULTS = {'LTX_SAMPLER_PLACEMENT': 'two-way', 'LTX_SAMPLER_WORKERS': '2', 'LTX_SAMPLER_BATCH': '1',
                'LTX_SAMPLER_SHARED_POOL': '0', 'LTX_DECODE_REPLICA_DEVICE': 'xpu:1', 'LTX_DECODE_REPLICAS': '1'}
CAP_ARM = 'pipe-samp2-tsh-win-b2'
TIMED_ARM = 'pipe-samp2-tsh-rep-wlean-b2-w2'
REF_ARM = 'pipe-samp2-tsh-rep-wlean-b2-ref'
W93C = LANE / 'data/stability-01-window-prereg.json'
BPREREG = LANE / 'data/stability-01-batch2-prereg.json'
CLIP_SECONDS = 25 / 24
# Index plan. Nodes accept clip_index <= 100,000,000 (ltx_pipeline.CLIP_INDEX_MAX). The runner's
# short arms live below 12,592,000 and its timed arms below 45,920,000 (20,000,000 + 10,000 x 2592),
# so everything from 50,000,000 up is unused by any runner combination, repeat or timed length.
CLIP_INDEX_MAX = 100_000_000
WARM_BASE = 50_000_000                   # Phase A short arms, runner offsets: cap +0/+10, self +100,
STREAM_BASE = 50_001_000                 # proofn +300, proofs +400 (max +416); the stream from here
DEFAULT_RUN = 'encoder-server-place-97-two-way-w2-b2-p1-dxpu2-stream01'
DEFAULT_PREFIX = 's97-twowayw2b2p1dxpu2-stream01'


def utc(t=None):
    return dt.datetime.fromtimestamp(time.time() if t is None else t, dt.timezone.utc).isoformat(
        timespec='milliseconds').replace('+00:00', 'Z')


def log(msg):
    print('[driver %s] %s' % (utc()[11:23], msg), flush=True)


def atomic_write(path, text):
    path = Path(path)
    tmp = path.with_name(path.name + '.tmp%d' % os.getpid())
    with open(tmp, 'w') as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Stop(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


# ----------------------------------------------------------------------------------------------
# HTTP: the calls the runner's client makes (POST /prompt, GET /history/<id>, GET /queue) only.
# ----------------------------------------------------------------------------------------------
class Api:
    def __init__(self, base, root, fail_seconds):
        self.base, self.root, self.fail_seconds = base, root, fail_seconds
        self.first_failure = None

    def _fault(self):
        if (self.root / 'FAULT.json').exists():
            raise Stop(4, 'FAULT.json present (%s): device fault latched; halting requests' % (self.root / 'FAULT.json'))

    def get(self, path):
        """One GET. A transport failure returns None; failures persisting longer than
        fail_seconds raise Stop(5). The caller simply tries again on its next cycle."""
        self._fault()
        try:
            with urllib.request.urlopen(self.base + path, timeout=min(60, max(2, self.fail_seconds // 2))) as r:
                out = json.loads(r.read() or b'{}')
            self.first_failure = None
            return out
        except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError, OSError) as e:
            now = time.monotonic()
            if self.first_failure is None:
                self.first_failure = now
                log('HTTP GET %s failed (%s); will retry on later cycles for up to %d s'
                    % (path, e, self.fail_seconds))
            if now - self.first_failure > self.fail_seconds:
                raise Stop(5, 'HTTP GET failing for %.0f s (last: %s %s)' % (now - self.first_failure, path, e))
            return None

    def post_prompt(self, payload):
        """POST /prompt exactly once. Any failure is fatal (a retry could double-submit)."""
        self._fault()
        req = urllib.request.Request(self.base + '/prompt', data=json.dumps(payload).encode(),
                                     headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=min(300, max(5, self.fail_seconds))) as r:
                return json.loads(r.read() or b'{}')
        except urllib.error.HTTPError as e:
            body = e.read()[:2000].decode('utf-8', 'replace')
            raise Stop(2, 'POST /prompt refused (HTTP %d): %s' % (e.code, body))
        except urllib.error.URLError as e:
            if isinstance(getattr(e, 'reason', None), ConnectionRefusedError):
                # Refused at connect: the request was provably never sent, so nothing was queued. Counts
                # toward the same --http-fail-seconds window as a failing GET; submitted again next cycle.
                now = time.monotonic()
                if self.first_failure is None:
                    self.first_failure = now
                    log('POST /prompt: connection refused; nothing was sent; holding for up to %d s'
                        % self.fail_seconds)
                if now - self.first_failure > self.fail_seconds:
                    raise Stop(5, 'server refusing connections for %.0f s' % (now - self.first_failure))
                return None
            raise Stop(5, 'POST /prompt failed (%s); not retried (the submission state is unknown; '
                          'a later run resolves it from /queue and the sampler receipt)' % e)
        except (TimeoutError, ConnectionError, json.JSONDecodeError, OSError) as e:
            raise Stop(5, 'POST /prompt failed (%s); not retried (the submission state is unknown; '
                          'a later run resolves it from /queue and the sampler receipt)' % e)


# ----------------------------------------------------------------------------------------------
# Server identity and preflight (runner lines 342-387, file/proc reads only)
# ----------------------------------------------------------------------------------------------
def read_identity(run):
    p = run / 'server-identity.json'
    if not p.is_file():
        raise Stop(8, 'no %s: the server is not %s (or not up yet); refusing' % (p, run.name))
    ident = json.loads(p.read_text())
    return ident, sha256(p)


def proc_ticks(pid):
    try:
        return Path('/proc/%d/stat' % int(pid)).read_text().split(') ')[1].split()[19]
    except (OSError, IndexError, ValueError):
        return None


def proc_env(pid):
    try:
        raw = Path('/proc/%d/environ' % int(pid)).read_bytes()
    except OSError:
        return None
    out = {}
    for item in raw.split(b'\0'):
        if b'=' in item:
            k, v = item.split(b'=', 1)
            out[k.decode(errors='replace')] = v.decode(errors='replace')
    return out


def preflight(a, run, strict):
    """strict=True: the full runner preflight (live server); False: test servers (fake identity)."""
    ident, ident_sha = read_identity(run)
    problems = []
    if Path('/proc/sys/kernel/random/boot_id').read_text().strip() != ident.get('boot_id'):
        problems.append('server identity boot_id is not this boot')
    pid = ident.get('pid')
    if proc_ticks(pid) != str(ident.get('proc_start_ticks')):
        problems.append('server pid %s is not running with the recorded start ticks' % pid)
    mv = a.root / 'model-verification.json'
    if not mv.is_file() or json.loads(mv.read_text()).get('status') != 'passed':
        problems.append('model-verification.json missing or not passed')
    if strict:
        if sha256(P / 'manifest.json') != MANIFEST_SHA:
            problems.append('packet manifest differs from the reviewed one')
        if ident.get('source_packet_manifest_sha256') != MANIFEST_SHA:
            problems.append('server is not the packet 97 build')
        try:
            cmd = Path('/proc/%d/cmdline' % int(pid)).read_bytes().replace(b'\0', b' ').decode()
        except OSError:
            cmd = ''
        if not re.search(r'serve-encoder\.py .*--run-name %s( |$)' % re.escape(run.name), cmd.strip()):
            problems.append('pid %s is not the serve-encoder.py launcher of %s' % (pid, run.name))
        env = proc_env(pid)
        if env is None:
            problems.append('cannot read the server environment')
        else:
            for k, want in EXPECTED_ENV.items():
                got = env.get(k, ENV_DEFAULTS.get(k))
                if got != want:
                    problems.append('server %s=%r, this combination needs %r' % (k, got, want))
            if env.get('LTX_DECODE_REPLICAS', '1') != '1':
                problems.append('server LTX_DECODE_REPLICAS=%r, needs 1' % env.get('LTX_DECODE_REPLICAS'))
        rc = subprocess.run(['/home/steve/llm-optimizations/scripts/check-b70-runtime-pm.sh'],
                            capture_output=True, text=True, timeout=60)
        if rc.returncode != 0:
            problems.append('runtime PM unsafe: ' + ((rc.stdout or '').strip().splitlines() or ['check failed'])[-1])
        for f in (W93C, BPREREG):
            if not f.is_file():
                problems.append('missing ' + str(f))
    if problems:
        raise Stop(8, 'preflight refused: ' + '; '.join(problems))
    return ident, ident_sha


# ----------------------------------------------------------------------------------------------
# Phase A
# ----------------------------------------------------------------------------------------------
def arm_timeouts(n):
    """run-campaign-97.sh arm_timeouts: client 1800 + 2.5 s per prompt (rounded up), outer +300."""
    c = 1800 + (5 * n + 1) // 2
    return c, c + 300


def warmup_plan(a, run, out):
    """The ordered Phase A steps. Each is (kind, label, payload). Pure; also used by --print-warmup-plan."""
    sys.path.insert(0, str(SCRIPTS))
    import ltx_sampler_batch as b      # noqa: E402  (no torch import; CPU tests import it too)
    g_ref = json.loads((P / 'graphs' / ('graph-capture-all48-%s.json' % REF_ARM)).read_text())
    g_tim = json.loads((P / 'graphs' / ('graph-capture-all48-%s.json' % TIMED_ARM)).read_text())
    sd, dd = g_ref['428']['inputs']['depth'], g_ref['426']['inputs']['depth']
    assert sd == b.serial_depth(BATCH), sd
    ref_k = len(b.ORDERS[BATCH]['ref'])
    ref_n = ref_k + sd + dd
    depth = (WORKERS + 1) * BATCH - 1
    self_n = depth + 4
    assert g_tim['428']['inputs']['depth'] == depth, (g_tim['428']['inputs']['depth'], depth)
    t = a.prefix
    cap_base, self_base = WARM_BASE, WARM_BASE + 100
    proofn_base, proofs_base = WARM_BASE + 300, WARM_BASE + 400
    pyb = [PY, '-B']
    m = ['--manifest', MANIFEST_SHA]
    steps = []

    def arm(name, graph_arm, count, base, fixtures, order, no_oracle=False):
        ct, ot = arm_timeouts(count)
        cmd = pyb + [str(SCRIPTS / 'run-throughput-fixtures-96.py'), name,
                     '--graph', str(P / 'graphs' / ('graph-capture-all48-%s.json' % graph_arm)),
                     '--arm', graph_arm, '--server-run', str(run), '--count', str(count),
                     '--index-base', str(base), '--out', str(out), '--fixtures', str(fixtures),
                     '--order', order, '--batch', str(BATCH), '--timeout', str(ct)]
        if no_oracle:
            cmd.append('--no-oracle')
        steps.append(('arm', name, {'cmd': cmd, 'timeout': ot}))

    steps.append(('rest', 'rest 60 s after construction', {'seconds': 60}))
    steps.append(('queue-empty', 'before the window probe', {}))
    steps.append(('cmd', t + '-wprobe', {'cmd': pyb + [str(SCRIPTS / 'run-text-window-probe.py'), t + '-wprobe',
                                                         '--graph', str(P / 'graphs/text-window-probe.json'),
                                                         '--server-run', str(run)],
                                         'timeout': 2400,
                                         'copy': [run / ('text-window-probe-%s-wprobe.json' % t)]}))
    steps.append(('cmd', 'memory plan', {'cmd': pyb + [str(SCRIPTS / 'worker-headroom-97.py'), 'plan', LAYOUT,
                                                       str(WORKERS), str(BATCH), str(POOL), '--replicas', SPEC] + m,
                                         'timeout': 120, 'stdout_to': out / 'headroom-plan.json'}))
    first_live = 1          # batch != 1 or pool == 1
    for k in range(WORKERS):
        idx_k = cap_base + 10 * k
        steps.append(('queue-empty', 'capture pass, worker %d' % k, {}))
        if k >= first_live:
            room = run / ('sampler-capture-coverage-%s-room%d.json' % (t, k))
            steps.append(('cmd', '%s-room%d' % (t, k), {
                'cmd': pyb + [str(SCRIPTS / 'run-capture-freeze-94.py'), '%s-room%d' % (t, k),
                              '--graph', str(P / 'graphs/sampler-capture-coverage.json'), '--server-run', str(run)],
                'timeout': 120, 'ignore_rc': True, 'quiet': True, 'copy': [room]}))
            prev = [str(run / ('sampler-capture-coverage-%s-room%d.json' % (t, k - 1)))] if k - 1 >= first_live else []
            steps.append(('cmd', 'live headroom, worker %d' % k, {
                'cmd': pyb + [str(SCRIPTS / 'worker-headroom-97.py'), 'live', str(room), LAYOUT, str(BATCH),
                              str(POOL)] + prev + ['--replicas', SPEC] + m,
                'timeout': 120, 'stdout_to': out / ('headroom-w%d.json' % k)}))
        steps.append(('cmd', '%s-pin%d' % (t, k), {
            'cmd': pyb + [str(SCRIPTS / 'run-sampler-pin-95.py'), '%s-pin%d' % (t, k), str(k),
                          '--graph', str(P / 'graphs/sampler-pin.json'), '--server-run', str(run)],
            'timeout': 120}))
        arm('%s-cap%d' % (t, k), CAP_ARM, 1, idx_k, W93C, 'cycle', no_oracle=True)
        steps.append(('done-marker', 'sample job %d' % idx_k, {'path': run / ('pipeline-done-sample-%d.json' % idx_k),
                                                               'tries': 180, 'every': 5}))
        steps.append(('rest', 'sleep 5 after worker %d' % k, {'seconds': 5}))
    steps.append(('queue-empty', 'after the capture pass', {}))
    cover = run / ('sampler-capture-coverage-%s-cover.json' % t)
    steps.append(('cmd', t + '-cover', {'cmd': pyb + [str(SCRIPTS / 'run-capture-freeze-94.py'), t + '-cover',
                                                        '--graph', str(P / 'graphs/sampler-capture-coverage.json'),
                                                        '--server-run', str(run)],
                                        'timeout': 360, 'copy': [cover]}))
    last = WORKERS - 1
    steps.append(('cmd', 'pool calibration', {
        'cmd': pyb + [str(SCRIPTS / 'worker-headroom-97.py'), 'calibrate',
                      str(out / ('sampler-capture-coverage-%s-room%d.json' % (t, last))),
                      str(out / ('sampler-capture-coverage-%s-cover.json' % t)), LAYOUT, str(BATCH), str(last)]
               + m + ['--out', str(out / 'pool-calibration.json')],
        'timeout': 120, 'ignore_rc': True}))
    steps.append(('rest', 'settle 30 s', {'seconds': 30}))
    steps.append(('queue-empty', 'before the decode probe', {}))
    steps.append(('cmd', t + '-dprobe', {'cmd': pyb + [str(SCRIPTS / 'run-decode-probe-97.py'), t + '-dprobe',
                                                         '--graph', str(P / 'graphs/decode-replica-probe.json'),
                                                         '--server-run', str(run), '--expect-replicas', SPEC],
                                         'timeout': 1500, 'copy': [run / ('decode-probe-%s-dprobe.json' % t)]}))
    steps.append(('queue-empty', 'before the freeze', {}))
    steps.append(('cmd', t + '-freeze', {'cmd': pyb + [str(SCRIPTS / 'run-capture-freeze-94.py'), t + '-freeze',
                                                         '--graph', str(P / 'graphs/sampler-capture-freeze.json'),
                                                         '--server-run', str(run)],
                                         'timeout': 360,
                                         'copy': [run / ('sampler-capture-freeze-%s-freeze.json' % t)]}))
    steps.append(('rest', 'settle 15 s', {'seconds': 15}))
    steps.append(('mark', 'self-check start time', {'key': 'self_t0'}))
    arm(t + '-wself', TIMED_ARM, self_n, self_base, W93C, 'shift', no_oracle=True)
    steps.append(('selfcheck', t + '-wself', {'cmd': pyb + [str(SCRIPTS / 'selfcheck-94f.py'), '--root', str(a.root),
                                                             '--run', str(run), '--prefix', t + '-wself', '--since'],
                                              'timeout': 120, 'stdout_to': out / 'selfcheck.json'}))
    steps.append(('rest', 'settle 30 s', {'seconds': 30}))
    steps.append(('refs', 'batch-2 references present', {}))
    steps.append(('rest', 'settle 30 s', {'seconds': 30}))
    arm(t + '-proofn', REF_ARM, ref_n, proofn_base, BPREREG, 'proof-neighbours')
    steps.append(('cmd', 'proof check neighbours', {
        'cmd': pyb + [str(SCRIPTS / 'check-batch-proof-96.py'), '--prereg', str(BPREREG), '--arm',
                      str(out / ('%s-proofn-throughput.json' % t)), '--kind', 'neighbours', '--expect-clips',
                      str(ref_k), '--out', str(out / 'proof-neighbours.json')], 'timeout': 120, 'quiet': True}))
    arm(t + '-proofs', REF_ARM, ref_n, proofs_base, BPREREG, 'proof-slots')
    steps.append(('cmd', 'proof check slots', {
        'cmd': pyb + [str(SCRIPTS / 'check-batch-proof-96.py'), '--prereg', str(BPREREG), '--arm',
                      str(out / ('%s-proofs-throughput.json' % t)), '--kind', 'slots', '--expect-clips',
                      str(ref_k), '--out', str(out / 'proof-slots.json')], 'timeout': 120, 'quiet': True}))
    steps.append(('cmd', 'decode placement (warm-up arms)', {
        'cmd': pyb + [str(SCRIPTS / 'check-decode-placement-97.py'), '--root', str(a.root), '--run', str(run),
                      '--replicas', SPEC, t + '-wself', t + '-proofn', t + '-proofs'],
        'timeout': 120, 'stdout_to': out / 'decode-placement-warmup.json'}))
    steps.append(('rest', 'settle 60 s before the stream (runner: before the timed arm)', {'seconds': 60}))
    return steps


def failed_jobs_module():
    return load_module('check_failed_jobs_97', SCRIPTS / 'check-failed-jobs-97.py')


def run_warmup(a, api, run, out, ident_sha, state, save_state):
    out.mkdir(parents=True, exist_ok=True)
    fj = failed_jobs_module()
    t = a.prefix
    if any((a.root / 'requests').glob(t + '-w*')) or any(run.glob('*%s-freeze*' % t)):
        raise Stop(8, 'warm-up requests/receipts for prefix %s already exist; Phase A runs once per server '
                      '(use --skip-warmup if this server is already frozen by it)' % t)
    marks = {}
    steps = warmup_plan(a, run, out)
    log('Phase A: %d steps' % len(steps))

    def failed_now():
        found = fj.find(str(run))
        for path, rec in found:
            log(fj.describe(path, rec))
        return found

    for i, (kind, label, d) in enumerate(steps, 1):
        log('A%02d %s: %s' % (i, kind, label))
        if kind == 'rest':
            time.sleep(d['seconds'])
        elif kind == 'mark':
            marks[d['key']] = int(time.time())
        elif kind == 'queue-empty':
            q = api.get('/queue')
            if q is None or q.get('queue_running') != [] or q.get('queue_pending') != []:
                raise Stop(13, 'queue not provably empty %s' % label)
        elif kind == 'done-marker':
            for _ in range(d['tries']):
                if d['path'].is_file():
                    break
                if failed_now():
                    raise Stop(6, '%s: a pipeline job failed (receipt above)' % label)
                time.sleep(d['every'])
            if not d['path'].is_file():
                if failed_now():
                    raise Stop(6, '%s: a pipeline job failed' % label)
                raise Stop(13, '%s never finished (%s missing)' % (label, d['path']))
        elif kind == 'refs':
            pre = json.loads(BPREREG.read_text())
            assert pre['batch'] == BATCH and len(pre['fixtures']) == 10
            for f in pre['fixtures']:
                if not (a.root / 'output/validation' / f['reference'] / 'tensors.safetensors').is_file() or \
                   not (a.root / 'requests' / f['reference'] / 'history.json').is_file():
                    raise Stop(13, 'batch-2 reference %s incomplete' % f['reference'])
        elif kind in ('cmd', 'arm', 'selfcheck'):
            cmd = list(d['cmd'])
            if kind == 'selfcheck':
                cmd.append(str(marks['self_t0']))
            stdout = subprocess.PIPE if d.get('stdout_to') or d.get('quiet') else None
            try:
                cp = subprocess.run(cmd, timeout=d['timeout'], stdout=stdout, text=True)
                rc = cp.returncode
            except subprocess.TimeoutExpired:
                rc, cp = 124, None
            if d.get('stdout_to') and cp is not None:
                Path(d['stdout_to']).write_text(cp.stdout or '')
                print((cp.stdout or '').strip()[:3000], flush=True)
            for src in d.get('copy', []):
                if Path(src).is_file():
                    shutil.copy2(src, out / Path(src).name)
            log('A%02d %s rc=%d' % (i, label, rc))
            if rc != 0 and not d.get('ignore_rc'):
                if kind == 'arm':
                    failed_now()
                raise Stop(13, 'Phase A step %s failed rc=%d' % (label, rc))
    state['warmup'] = {'server_identity_sha256': ident_sha, 'passed': True, 'finished_utc': utc(), 'out': str(out)}
    save_state()
    log('Phase A passed: window qualified, captures covered and frozen, replica exact, self-check clean, '
        'proof arms byte-identical to stability-01-b2')


# ----------------------------------------------------------------------------------------------
# Phase B
# ----------------------------------------------------------------------------------------------
def frozen_receipts_ok(run, ident_sha):
    """The timed path is admitted only on a server that passed the window probe, the decode probe and
    the freeze (otherwise prompts are refused). Read from this server's own receipts."""
    need = {'text-window-probe-*.json': ('window-qualified', 'passed'),
            'decode-probe-*.json': ('replica-exact', 'passed'),
            'sampler-capture-freeze-*.json': ('frozen', 'frozen')}
    missing = []
    for pat, (outcome, flag) in need.items():
        ok = False
        for p in run.glob(pat):
            try:
                d = json.loads(p.read_text())
            except (OSError, ValueError):
                continue
            if d.get('outcome') == outcome and d.get(flag) is True and d.get('server_identity_sha256') == ident_sha:
                ok = True
                break
        if not ok:
            missing.append(pat + ' (' + outcome + ')')
    return missing


class Driver:
    def __init__(self, a, api, run, ident, ident_sha, state, save_state):
        self.a, self.api, self.run, self.ident, self.ident_sha = a, api, run, ident, ident_sha
        self.state, self.save_state = state, save_state
        self.fixtures = json.loads(Path(a.fixtures).read_text())['fixtures']
        assert len(self.fixtures) == 10 and len({f['seed'] for f in self.fixtures}) == 10
        self.graph = json.loads(Path(a.graph).read_text())
        g = self.graph
        assert g['364']['class_type'] == 'LTXPipelineTextEncode'
        assert g['339']['class_type'] == 'RandomNoise' and g['338']['class_type'] == 'RandomNoise'
        assert g['428']['inputs'].get('batch') == BATCH and 'stream_last' in g['428']['inputs']
        self.batch = g['428']['inputs']['batch']
        self.depth = g['428']['inputs']['depth'] + g['426']['inputs']['depth']
        args = json.loads((run / 'server-args.json').read_text())
        self.output_dir = Path(args[args.index('--output-directory') + 1])
        self.mv_sha = sha256(a.root / 'model-verification.json')
        self.args_sha = sha256(run / 'server-args.json')
        self.fj = failed_jobs_module()
        self.stopping = False
        self.signals = 0
        self.ready = []            # emitted clips waiting for MP4 / check, in clip order
        self.next_failed_check = 0.0
        self.last_success_ts = None
        self.sink_cache = (0.0, None)
        self.started_unix = time.time()
        self.throttled_since = None

    # ---- schedule ------------------------------------------------------------------------
    def schedule(self, pos):
        cycle, k = divmod(pos, len(self.fixtures))
        fx = self.fixtures[k]
        return fx, fx['seed'] + 1000 * cycle, cycle

    def name_for(self, index):
        return '%s-%07d' % (self.a.prefix, index - STREAM_BASE)

    # ---- state ---------------------------------------------------------------------------
    def reconcile(self):
        st = self.state
        st.setdefault('next_index', STREAM_BASE)
        st.setdefault('next_pos', 0)
        st.setdefault('next_seq', 0)
        st.setdefault('outstanding', [])      # prompts in the server: {name,index,pos,prompt_id}
        st.setdefault('clips', {})            # submitted, not yet emitted: str(index) -> {pos,name,prompt_id}
        st.setdefault('group_fill', 0)        # clips in the server's open batch group (0..batch-1)
        st.setdefault('last_emitted', None)
        st['next_index'] = max(st['next_index'], STREAM_BASE)
        same = st.get('server_identity_sha256') == self.ident_sha
        if not same and (st['outstanding'] or st['clips'] or st.get('pending_submit')):
            lost = sorted(int(c['pos']) for c in st['clips'].values())
            if st.get('pending_submit'):
                lost.append(int(st['pending_submit']['pos']))
            rewind = min(lost) if lost else st['next_pos']
            log('state belongs to another server: %d submitted clips were never emitted there and are lost; '
                'their schedule positions are re-submitted from position %d (indices stay fresh)'
                % (len(st['clips']), rewind))
            st['next_pos'] = rewind
            st['outstanding'], st['clips'], st['pending_submit'] = [], {}, None
            st['group_fill'] = 0
            st['last_emitted'] = None
        if not same:
            st['stream_started_unix'] = time.time()
        st['server_identity_sha256'] = self.ident_sha
        st['server_run'] = self.run.name
        ps = st.get('pending_submit')
        if ps:
            self.resolve_pending(ps)
        self.save_state()

    def resolve_pending(self, ps):
        """A POST whose outcome is unknown (crash between reserve and record). Found in /queue or as an
        executed sampler receipt -> submitted; else it never reached the server and its index is free."""
        st = self.state
        name, pid = ps['name'], None
        q = self.api.get('/queue')
        if q is None:
            raise Stop(5, 'cannot read /queue to resolve the unknown submission of %s' % name)
        for item in (q.get('queue_running') or []) + (q.get('queue_pending') or []):
            try:
                if item[2]['428']['inputs']['run_name'] == name:
                    pid = item[1]
            except (KeyError, IndexError, TypeError):
                continue
        receipt = self.run / ('pipeline-sampler-%s.json' % name)
        sub = self.a.root / 'requests' / name / 'submission.json'
        if pid is None and sub.is_file():
            pid = json.loads(sub.read_text()).get('prompt_id')
        if pid is None and receipt.is_file():
            raise Stop(8, '%s executed on the server but its prompt id is unknown; resolve by hand' % name)
        if pid is not None:
            log('unknown submission %s resolved: it is in the server (prompt %s)' % (name, pid))
            self.record_submitted(ps, pid)
        else:
            log('unknown submission %s resolved: it never reached the server; index %d is reused'
                % (name, ps['index']))
            st['next_index'], st['next_pos'] = ps['index'], ps['pos']
            req = self.a.root / 'requests' / name
            if req.is_dir() and not (req / 'submission.json').exists():
                st.setdefault('orphan_request_dirs', []).append(str(req))
        st['pending_submit'] = None

    def record_submitted(self, ps, prompt_id):
        st = self.state
        st['outstanding'].append({'name': ps['name'], 'index': ps['index'], 'pos': ps['pos'],
                                  'prompt_id': prompt_id, 'submitted_unix': time.time(),
                                  'stream_last': ps.get('stream_last', 0)})
        st['clips'][str(ps['index'])] = {'pos': ps['pos'], 'name': ps['name'], 'prompt_id': prompt_id}
        st['next_index'], st['next_pos'] = ps['index'] + 1, ps['pos'] + 1
        st['group_fill'] = 0 if ps.get('stream_last') else (st['group_fill'] + 1) % self.batch
        st['submitted_total'] = st.get('submitted_total', 0) + 1

    # ---- submit ---------------------------------------------------------------------------
    def build(self, index, name, fx, seed, stream_last):
        """Exactly run-throughput-fixtures-96.py lines 186-198 for one prompt."""
        g = json.loads(json.dumps(self.graph))
        for node in g.values():
            if 'run_name' in node.get('inputs', {}):
                node['inputs']['run_name'] = name
            if 'clip_index' in node.get('inputs', {}) and not isinstance(node['inputs']['clip_index'], list):
                node['inputs']['clip_index'] = index
        g['428']['inputs']['stream_last'] = 1 if stream_last else 0
        g['364']['inputs']['text'] = fx['prompt']
        g['339']['inputs']['noise_seed'] = seed
        g['338']['inputs']['noise_seed'] = seed
        if '75' in g:
            g['75']['inputs']['filename_prefix'] = name + '/preview'
        return g

    def submit_one(self, stream_last=False):
        st = self.state
        index, pos = st['next_index'], st['next_pos']
        if index > CLIP_INDEX_MAX:
            raise Stop(8, 'clip index %d would exceed the nodes\' ceiling %d' % (index, CLIP_INDEX_MAX))
        fx, seed, cycle = self.schedule(pos)
        name = self.name_for(index)
        g = self.build(index, name, fx, seed, stream_last)
        req = self.a.root / 'requests' / name
        if (req / 'submission.json').exists():
            raise Stop(12, 'request %s was already submitted; refusing to reuse its index' % name)
        req.mkdir(parents=True, exist_ok=True)
        (req / 'prompt.json').write_text(json.dumps(g, indent=2) + '\n')
        identity = dict(self.ident)
        ticks = proc_ticks(self.ident['pid'])
        if ticks is None:
            raise Stop(5, 'server pid %s is gone' % self.ident['pid'])
        identity['proc_start_ticks'] = ticks
        identity['model_verification_sha256'] = self.mv_sha
        identity['server_args_sha256'] = self.args_sha
        (req / 'identity.json').write_text(json.dumps(identity, indent=2) + '\n')
        ps = {'name': name, 'index': index, 'pos': pos, 'stream_last': 1 if stream_last else 0}
        st['pending_submit'] = ps
        self.save_state()
        r = self.api.post_prompt({'prompt': g, 'client_id': 'stream-' + self.a.prefix})
        if r is None:                                  # connection refused: provably not queued
            st['pending_submit'] = None
            self.save_state()
            return False
        self.api.first_failure = None
        if r.get('node_errors'):
            raise Stop(2, 'prompt %s refused: %s' % (name, json.dumps(r)[:1500]))
        (req / 'submission.json').write_text(json.dumps(r, indent=2) + '\n')
        self.record_submitted(ps, r['prompt_id'])
        st['pending_submit'] = None
        self.save_state()
        return True

    # ---- throttle -------------------------------------------------------------------------
    def sink_last_played(self):
        if not self.a.sink_stats:
            return None
        now = time.monotonic()
        if now - self.sink_cache[0] < 1.0:
            return self.sink_cache[1]
        val = None
        try:
            d = json.loads(Path(self.a.sink_stats).read_text())
            val = int(d.get('last_played_seq', -1))
        except (OSError, ValueError, TypeError):
            val = None
        self.sink_cache = (now, val)
        return val

    def ahead_seconds(self):
        played = self.sink_last_played()
        if played is None:
            return None
        produced = self.state['next_seq'] - 1           # last manifest seq written
        clips = (produced - played) + len(self.state['clips']) + len(self.ready)
        return max(0, clips) * CLIP_SECONDS

    def may_submit(self):
        if len(self.state['outstanding']) >= self.a.in_flight:
            return False
        ahead = self.ahead_seconds()
        if ahead is not None and ahead + CLIP_SECONDS > self.a.max_ahead_seconds:
            if self.throttled_since is None:
                self.throttled_since = time.monotonic()
                log('throttle: %.0f s of video ahead of the sink (limit %.0f s); holding submissions'
                    % (ahead, self.a.max_ahead_seconds))
            return False
        if self.throttled_since is not None:
            log('throttle released after %.1f s' % (time.monotonic() - self.throttled_since))
            self.throttled_since = None
        free = shutil.disk_usage(self.a.root).free / 2 ** 30
        if free < self.a.min_free_gib:
            raise Stop(9, 'only %.1f GiB free under %s (limit %.1f); stopping submissions'
                       % (free, self.a.root, self.a.min_free_gib))
        return True

    # ---- completion ----------------------------------------------------------------------
    def poll_oldest(self):
        """GET /history for the oldest outstanding prompt only. True if it completed."""
        st = self.state
        if not st['outstanding']:
            return False
        p = st['outstanding'][0]
        h = self.api.get('/history/' + p['prompt_id'])
        if not h:
            return False
        entry = h.get(p['prompt_id'])
        if not entry:
            return False
        req = self.a.root / 'requests' / p['name']
        status = entry.get('status', {})
        for m in status.get('messages', []):
            if m[0] == 'execution_error':
                d = m[1] or {}
                (req / 'history.json').write_text(json.dumps(entry, indent=2) + '\n')
                raise Stop(2, 'EXECUTION ERROR in %s: %s | %s' % (p['name'], d.get('exception_type'),
                                                                  str(d.get('exception_message'))[:600]))
        if not status.get('completed'):
            if status.get('status_str') == 'error':
                raise Stop(2, '%s ended with status error' % p['name'])
            return False
        (req / 'history.json').write_text(json.dumps(entry, indent=2) + '\n')
        ts = {m[0]: m[1]['timestamp'] for m in status['messages'] if isinstance(m[1], dict) and 'timestamp' in m[1]}
        t_start, t_done = ts.get('execution_start', ts['execution_success']) / 1000, ts['execution_success'] / 1000
        (req / 'result.json').write_text(json.dumps({'name': p['name'], 'prompt_id': p['prompt_id'],
                                                     'seconds': t_done - t_start, 'status': status}, indent=2) + '\n')
        st['outstanding'].pop(0)
        self.on_completed(p, t_start, t_done)
        self.save_state()
        return True

    def on_completed(self, p, t_start, t_done):
        st = self.state
        dec = self.run / ('pipeline-decode-%s.json' % p['name'])
        if not dec.is_file():
            raise Stop(12, 'no decode receipt %s for a completed prompt' % dec.name)
        drec = json.loads(dec.read_text())
        emitted = drec['detail']['emitted_index']
        if emitted < 0:
            log('%s (clip %d) completed in %.3f s: pipeline fill, emits nothing'
                % (p['name'], p['index'], t_done - t_start))
            self.prune(p['name'])
            return
        clip = st['clips'].get(str(emitted))
        lowest = min((int(k) for k in st['clips']), default=None)
        if clip is None or emitted != lowest:
            raise Stop(12, 'EMISSION SEQUENCE WRONG: %s emitted clip %d; the lowest unemitted clip is %s, last '
                           'emitted %s' % (p['name'], emitted, lowest, st['last_emitted']))
        del st['clips'][str(emitted)]
        st['last_emitted'] = emitted
        save = self.run / ('pipeline-save-%s.json' % p['name'])
        prefix = None
        if save.is_file():
            prefix = json.loads(save.read_text()).get('prefix')
        fx, seed, cycle = self.schedule(int(clip['pos']))
        item = {'index': emitted, 'pos': int(clip['pos']), 'fixture': fx, 'seed': seed, 'cycle': cycle,
                'emit_name': p['name'], 'emit_prompt_id': p['prompt_id'], 'prompt_id': clip['prompt_id'],
                'clip_name': clip['name'], 'prefix': prefix, 't_done': t_done, 't_start': t_start,
                'marker': self.run / ('pipeline-done-save-%d.json' % emitted), 'since': time.monotonic(),
                'check': None, 'decode_split': drec['detail'].get('decode_split')}
        if cycle == 0:
            item['check'] = self.start_check(item)
        self.ready.append(item)

    def start_check(self, item):
        fx = item['fixture']
        ref = fx.get('reference')
        out = Path(self.a.work_dir) / 'parity'
        out.mkdir(parents=True, exist_ok=True)
        parity = out / ('%s-parity.json' % item['emit_name'])
        if self.a.comparator:
            comp = Path(self.a.comparator)
        else:
            raw = (self.a.root / 'output/validation' / ref / 'tensors.safetensors').is_file()
            comp = SCRIPTS / ('compare-clip.py' if raw else 'compare-clip-hash.py')
        cmd = [PY, '-B', str(comp), ref, item['emit_name'], '--output', str(parity)]
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        return {'proc': proc, 'parity': parity, 'reference': ref, 'comparator': str(comp), 'started': time.monotonic()}

    def finish_ready(self):
        """Append finished clips to the manifest, strictly in clip order."""
        while self.ready:
            it = self.ready[0]
            if not it['marker'].is_file():
                if time.monotonic() - it['since'] > self.a.save_wait:
                    raise Stop(7, 'preview of clip %d not written after %d s (%s missing)'
                               % (it['index'], self.a.save_wait, it['marker'].name))
                return
            try:
                saved = json.loads(it['marker'].read_text()).get('saved')
            except ValueError:
                return                                    # being written
            if not saved or str(saved).startswith('save-failed'):
                raise Stop(7, 'preview of clip %d failed: %r' % (it['index'], saved))
            path = self.output_dir / saved
            if it['prefix'] and not str(saved).startswith(it['prefix']):
                raise Stop(7, 'clip %d saved as %s, the save receipt said prefix %s' % (it['index'], saved, it['prefix']))
            if not path.is_file() or path.stat().st_size == 0:
                if time.monotonic() - it['since'] > self.a.save_wait:
                    raise Stop(7, 'preview %s missing or empty' % path)
                return
            summ = self.a.root / 'output/validation' / it['emit_name'] / 'summary.json'
            try:
                meta = json.loads(summ.read_text())
                if not all(v.get('finite') is True for v in meta['tensors'].values()):
                    raise Stop(3, 'clip %d (%s) has non-finite outputs: %s' % (it['index'], it['emit_name'], summ))
            except (OSError, ValueError, KeyError) as e:
                raise Stop(3, 'clip %d: validation summary unreadable (%s)' % (it['index'], e))
            verdict = ''
            if it['check'] is not None:
                c = it['check']
                rc = c['proc'].poll()
                if rc is None:
                    if time.monotonic() - c['started'] > 300:
                        c['proc'].kill()
                        raise Stop(3, 'reference comparison of clip %d timed out' % it['index'])
                    return
                parity = json.loads(c['parity'].read_text()) if c['parity'].is_file() else \
                    {'status': 'missing', 'stderr': (c['proc'].stderr.read() or '')[-800:]}
                exact = parity.get('status') == 'passed' and all(
                    v.get('bitwise_equal') is True for v in parity.get('comparisons', {}).values())
                if not exact:
                    raise Stop(3, 'clip %d (%s seed %d) is NOT byte-identical to %s: %s'
                               % (it['index'], it['fixture']['id'], it['seed'], c['reference'],
                                  json.dumps(parity)[:800]))
                verdict = ' EXACT vs %s' % c['reference']
                self.state['checked_exact'] = self.state.get('checked_exact', 0) + 1
            self.prune(it['emit_name'])
            seq = self.state['next_seq']
            gen = json.loads(it['marker'].read_text()).get('finished_unix') or time.time()
            line = {'seq': seq, 'path': str(path), 'generated_utc': utc(gen),
                    'label': '%s seed %d cycle %d' % (it['fixture']['id'], it['seed'], it['cycle']),
                    'index': it['index'], 'prompt_id': it['prompt_id'],
                    'emitted_by_prompt_id': it['emit_prompt_id']}
            with open(self.a.manifest, 'a') as f:
                f.write(json.dumps(line) + '\n')
                f.flush()
                os.fsync(f.fileno())
            self.state['next_seq'] = seq + 1
            self.state['emitted_total'] = self.state.get('emitted_total', 0) + 1
            iv = '' if self.last_success_ts is None else ' interval %.3f s' % (it['t_done'] - self.last_success_ts)
            self.last_success_ts = it['t_done']
            split = it.get('decode_split') if isinstance(it.get('decode_split'), dict) else {}
            log('seq %d clip %d %s%s prompt %.3f s%s%s path %s' % (
                seq, it['index'], line['label'], iv, it['t_done'] - it['t_start'],
                (' decode %s s on %s' % (split.get('decode_s', split.get('vae_s')), split.get('device'))) if split else '',
                verdict, path))
            self.ready.pop(0)
            self.save_state()

    def prune(self, name):
        if self.a.keep_validation_tensors or not name.startswith(self.a.prefix + '-'):
            return
        t = self.a.root / 'output/validation' / name / 'tensors.safetensors'
        try:
            t.unlink()
        except FileNotFoundError:
            pass

    # ---- guards ---------------------------------------------------------------------------
    def check_failed_jobs(self):
        now = time.monotonic()
        if now < self.next_failed_check:
            return
        self.next_failed_check = now + 5.0
        found = self.fj.find(str(self.run), since=self.state.get('stream_started_unix', self.started_unix))
        if found:
            for path, rec in found:
                log(self.fj.describe(path, rec))
            raise Stop(6, '%d failed pipeline job receipt(s) (pipeline-failed-*.json) in %s' % (len(found), self.run))

    # ---- main loop ------------------------------------------------------------------------
    def on_signal(self, signum, _frame):
        self.signals += 1
        if self.signals == 1:
            log('signal %d: stopping submissions; draining in-flight prompts (up to %d s)' % (signum, self.a.timeout))
            self.stopping = True
        else:
            raise Stop(130, 'second signal: abandoning the drain (state written)')

    def loop(self):
        a, st = self.a, self.state
        drain_deadline = None
        flushed = False
        last_beat = time.monotonic()
        while True:
            self.check_failed_jobs()
            if (a.root / 'FAULT.json').exists():
                raise Stop(4, 'FAULT.json present: device fault latched; halting requests')
            progressed = False
            while self.poll_oldest():
                progressed = True
            self.finish_ready()
            if a.max_clips and st.get('emitted_total', 0) - self.emitted_at_start >= a.max_clips and not self.stopping:
                log('--max-clips %d reached; stopping' % a.max_clips)
                self.stopping = True
            if not self.stopping:
                while self.may_submit():
                    if not self.submit_one():
                        break
                    progressed = True
            else:
                if drain_deadline is None:
                    drain_deadline = time.monotonic() + a.timeout
                if not flushed and st['group_fill'] and len(st['outstanding']) < a.in_flight:
                    # The server's batch grouper holds an incomplete group. Every runner arm ends with a
                    # stream_last prompt; without it any later stream that does not continue this index
                    # sequence is refused AND latches the sampler. One closing prompt, nothing more.
                    log('closing the open batch group with one stream_last prompt')
                    self.submit_one(stream_last=True)
                    flushed = True
                if not st['outstanding'] and not self.ready:
                    log('drained: every submitted prompt completed')
                    return 0
                if time.monotonic() > drain_deadline:
                    log('drain timeout: %d prompts still in the server, %d clips pending; state written'
                        % (len(st['outstanding']), len(self.ready)))
                    return 0
            if time.monotonic() - last_beat > 60:
                last_beat = time.monotonic()
                ahead = self.ahead_seconds()
                log('status: %d emitted, %d in flight, %d in pipeline, ahead %s' % (
                    st.get('emitted_total', 0), len(st['outstanding']), len(st['clips']),
                    'n/a' if ahead is None else '%.0f s' % ahead))
            if not progressed:
                time.sleep(a.poll)

    def run_stream(self):
        self.reconcile()
        self.emitted_at_start = self.state.get('emitted_total', 0)
        log('Phase B: server %s, index %d, schedule position %d, seq %d, %d prompts already in flight, %d clips '
            'in the pipeline' % (self.run.name, self.state['next_index'], self.state['next_pos'],
                                 self.state['next_seq'], len(self.state['outstanding']), len(self.state['clips'])))
        return self.loop()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--server-run', default=DEFAULT_RUN, help='server run name (run dir under --root)')
    ap.add_argument('--prefix', default=DEFAULT_PREFIX, help='request/output name prefix')
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=8188)
    ap.add_argument('--root', type=Path, default=R, help='results root (tests only; Phase A needs the default)')
    ap.add_argument('--work-dir', type=Path, help='driver outputs (default stream/runs/<prefix>)')
    ap.add_argument('--manifest', type=Path)
    ap.add_argument('--state', type=Path)
    ap.add_argument('--fixtures', default=str(BPREREG))
    ap.add_argument('--graph', default=str(P / 'graphs' / ('graph-capture-all48-%s.json' % TIMED_ARM)))
    ap.add_argument('--in-flight', type=int, default=4)
    ap.add_argument('--max-ahead-seconds', type=float, default=300.0)
    ap.add_argument('--sink-stats', help="the sink's --stats JSON (last_played_seq)")
    ap.add_argument('--timeout', type=int, default=600, help='drain bound on SIGINT/SIGTERM, seconds')
    ap.add_argument('--http-fail-seconds', type=int, default=120)
    ap.add_argument('--save-wait', type=int, default=120, help='seconds to wait for an emitted clip\'s MP4')
    ap.add_argument('--min-free-gib', type=float, default=30.0)
    ap.add_argument('--keep-validation-tensors', action='store_true',
                    help='do not delete each stream clip\'s 20 MB oracle tensors after it is checked/emitted')
    ap.add_argument('--comparator', help='reference comparator script (tests); default compare-clip.py')
    ap.add_argument('--poll', type=float, default=0.25)
    ap.add_argument('--max-clips', type=int, default=0, help='clean stop after N emitted clips (0 = forever)')
    ap.add_argument('--skip-warmup', action='store_true')
    ap.add_argument('--warmup-only', action='store_true')
    ap.add_argument('--print-warmup-plan', action='store_true', help='print Phase A commands; contacts nothing')
    ap.add_argument('--test-server', action='store_true', help='fake server: relaxed preflight, no Phase A')
    a = ap.parse_args(argv)
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,80}', a.prefix):
        raise SystemExit('prefix must be lowercase [a-z0-9-], at most 81 characters')
    if a.skip_warmup and a.warmup_only:
        raise SystemExit('--skip-warmup and --warmup-only exclude each other')
    a.work_dir = a.work_dir or (Path(__file__).resolve().parent / 'runs' / a.prefix)
    a.work_dir.mkdir(parents=True, exist_ok=True)
    a.manifest = a.manifest or a.work_dir / 'manifest.jsonl'
    a.state = a.state or a.work_dir / 'state.json'
    run = a.root / a.server_run
    out = a.work_dir / 'warmup'

    if a.print_warmup_plan:
        for i, (kind, label, d) in enumerate(warmup_plan(a, run, out), 1):
            extra = ' '.join(d['cmd'][1:]) if 'cmd' in d else json.dumps({k: str(v) for k, v in d.items()})
            print('A%02d %-12s %-40s %s' % (i, kind, label, extra))
        return 0

    state = json.loads(a.state.read_text()) if a.state.is_file() else {}

    def save_state():
        state['updated_utc'] = utc()
        atomic_write(a.state, json.dumps(state, indent=1, sort_keys=True) + '\n')

    api = Api('http://%s:%d' % (a.host, a.port), a.root, a.http_fail_seconds)
    try:
        if not a.test_server:
            q = None
            for _ in range(360):                          # runner lines 347-353: health wait, 360 x 5 s
                if (a.root / 'FAULT.json').exists():
                    raise Stop(4, 'FAULT.json present')
                q = api.get('/queue')
                if q is not None:
                    break
                time.sleep(5)
            if q is None:
                raise Stop(8, 'server never answered /queue')
        ident, ident_sha = preflight(a, run, strict=not a.test_server)
        log('server %s pid %s identity %s' % (run.name, ident.get('pid'), ident_sha[:12]))
        if not a.skip_warmup and not a.test_server:
            if a.root != R or a.port != 8188:
                raise Stop(8, 'Phase A helpers are pinned to %s and 127.0.0.1:8188' % R)
            w = state.get('warmup') or {}
            if w.get('passed') and w.get('server_identity_sha256') == ident_sha:
                log('Phase A already passed on this server (%s); not repeated' % w.get('finished_utc'))
            else:
                run_warmup(a, api, run, out, ident_sha, state, save_state)
        if a.warmup_only:
            log('--warmup-only: Phase A done; no stream submitted')
            return 0
        if not a.test_server:
            missing = frozen_receipts_ok(run, ident_sha)
            if missing:
                raise Stop(8, 'this server has not passed the preparation the timed path needs: missing %s'
                           % ', '.join(missing))
        drv = Driver(a, api, run, ident, ident_sha, state, save_state)
        signal.signal(signal.SIGINT, drv.on_signal)
        signal.signal(signal.SIGTERM, drv.on_signal)
        rc = drv.run_stream()
        save_state()
        log('clean stop: %d clips emitted in total, next index %d, next seq %d'
            % (state.get('emitted_total', 0), state['next_index'], state['next_seq']))
        return rc
    except Stop as s:
        try:
            save_state()
        except Exception as e:                       # noqa: BLE001
            log('could not write state: %r' % e)
        log('STOPPED (exit %d): %s' % (s.code, s))
        if s.code not in (130,):
            log('no retry, no restart: inspect the evidence above before running again')
        return s.code


if __name__ == '__main__':
    sys.exit(main())
