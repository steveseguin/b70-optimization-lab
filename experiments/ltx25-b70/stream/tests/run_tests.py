#!/usr/bin/env python3
"""Phase B tests of ltx_stream_driver.py against fake_comfy.py (CPU only, port 18188 by default).

    /home/steve/.venvs/ltx25-baseline/bin/python -B tests/run_tests.py [--tmp DIR] [--port 18188]

Every test gets a fresh fake root (and a fresh fake server unless it tests a resume on the same one).
"""
import argparse, hashlib, json, os, signal, subprocess, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DRIVER = HERE.parent / 'ltx_stream_driver.py'
FIXTURES = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/data/stability-01-batch2-prereg.json')
CLIP = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/output/f97-twowayw2b2p1dxpu2r2-timed-100/preview_00001_.mp4')
RUN = 'encoder-server-place-97-two-way-w2-b2-p1-dxpu2-stream01'
PY = sys.executable

ap = argparse.ArgumentParser()
ap.add_argument('--tmp', type=Path)
ap.add_argument('--port', type=int, default=18188)
ap.add_argument('--only')
args = ap.parse_args()
TMP = Path(tempfile.mkdtemp(prefix='ltx-stream-test-', dir=str(args.tmp) if args.tmp else None))
RESULTS = []


def sha(*parts):
    return hashlib.sha256('|'.join(str(p) for p in parts).encode()).hexdigest()


class Env:
    def __init__(self, name, bad_reference=None):
        self.root = TMP / name / 'root'
        self.work = TMP / name / 'work'
        self.root.mkdir(parents=True)
        self.work.mkdir(parents=True)
        for f in json.loads(FIXTURES.read_text())['fixtures']:
            d = self.root / 'output/validation' / f['reference']
            d.mkdir(parents=True)
            seed = f['seed'] + (1 if f['id'] == bad_reference else 0)
            (d / 'summary.json').write_text(json.dumps({'tensors': {k: {'sha256': sha(f['prompt'], seed, k), 'finite': True}
                                                                    for k in ('images', 'video_latent', 'audio_latent', 'waveform')}}))
        self.fake = None

    def start_fake(self, *extra):
        self.fake_log = open(self.root.parent / ('fake-%d.log' % time.time_ns()), 'w')
        self.fake = subprocess.Popen([PY, '-B', str(HERE / 'fake_comfy.py'), '--root', str(self.root), '--run-name', RUN,
                                      '--port', str(args.port), '--clip', str(CLIP)] + list(extra),
                                     stdout=self.fake_log, stderr=subprocess.STDOUT)
        for _ in range(100):
            if (self.root / RUN / 'server-identity.json').is_file():
                try:
                    import urllib.request
                    urllib.request.urlopen('http://127.0.0.1:%d/queue' % args.port, timeout=2).read()
                    return
                except OSError:
                    pass
            time.sleep(0.1)
        raise RuntimeError('fake did not start')

    def stop_fake(self):
        if self.fake:
            self.fake.send_signal(signal.SIGINT)
            try:
                self.fake.wait(10)
            except subprocess.TimeoutExpired:
                self.fake.kill()
            self.fake = None
            (self.root / RUN / 'server-identity.json').unlink()

    def driver_cmd(self, *extra):
        return [PY, '-B', str(DRIVER), '--test-server', '--root', str(self.root), '--port', str(args.port),
                '--work-dir', str(self.work), '--comparator', str(HERE / 'fake_compare.py'),
                '--poll', '0.05', '--min-free-gib', '1'] + list(extra)

    def driver(self, *extra, timeout=300):
        env = dict(os.environ, FAKE_ROOT=str(self.root))
        cp = subprocess.run(self.driver_cmd(*extra), capture_output=True, text=True, timeout=timeout, env=env)
        (self.work / ('driver-%d.log' % time.time_ns())).write_text(cp.stdout + cp.stderr)
        return cp

    def driver_bg(self, *extra):
        env = dict(os.environ, FAKE_ROOT=str(self.root))
        log = open(self.work / ('driver-bg-%d.log' % time.time_ns()), 'w')
        return subprocess.Popen(self.driver_cmd(*extra), stdout=log, stderr=subprocess.STDOUT, env=env), log

    def manifest(self):
        p = self.work / 'manifest.jsonl'
        return [json.loads(x) for x in p.read_text().splitlines()] if p.is_file() else []

    def state(self):
        return json.loads((self.work / 'state.json').read_text())

    def stats(self):
        return json.loads((self.root / 'fake-stats.json').read_text())


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok), detail))
    print('%s %s %s' % ('PASS' if ok else 'FAIL', name, detail), flush=True)


def manifest_ok(e, rows, first_seq=0):
    fx = json.loads(FIXTURES.read_text())['fixtures']
    problems = []
    for k, r in enumerate(rows):
        if r['seq'] != first_seq + k:
            problems.append('seq %s at row %d' % (r['seq'], k))
        p = Path(r['path'])
        if not p.is_file() or p.stat().st_size == 0:
            problems.append('missing ' + r['path'])
        if k and r['index'] != rows[k - 1]['index'] + 1:
            problems.append('index gap %s -> %s' % (rows[k - 1]['index'], r['index']))
    return problems


def label_for(pos):
    fx = json.loads(FIXTURES.read_text())['fixtures']
    c, k = divmod(pos, 10)
    return '%s seed %d cycle %d' % (fx[k]['id'], fx[k]['seed'] + 1000 * c, c)


def test_basic_resume_and_identity():
    e = Env('basic')
    e.start_fake('--delay', '0.03')
    cp = e.driver('--max-clips', '40', '--in-flight', '4')
    rows = e.manifest()
    check('A1 >=40 clips (drain emits the in-flight tail), exit 0', cp.returncode == 0 and 40 <= len(rows) <= 40 + 4, 'rc=%d rows=%d' % (cp.returncode, len(rows)))
    check('A2 manifest seq/index/path', not manifest_ok(e, rows), str(manifest_ok(e, rows)[:3]))
    check('A3 labels follow seed + 1000 x cycle', [r['label'] for r in rows] == [label_for(i) for i in range(len(rows))],
          rows[10]['label'] + ' | ' + rows[-1]['label'])
    exact = cp.stdout.count('EXACT vs stability-01-b2-')
    check('A4 first ten clips checked EXACT against stability-01-b2', exact == 10, 'EXACT lines %d' % exact)
    st = e.stats()
    check('A5 in-flight cap (<=4 prompts in the server)', st['max_in_server'] <= 4, 'max %d' % st['max_in_server'])
    check('A6 /history polled only for the oldest outstanding prompt', st['non_oldest_polls'] == 0,
          '%d non-oldest of %d gets' % (st['non_oldest_polls'], st['history_gets']))
    check('A7 first stream index is 50,001,000; MP4 dirs carry the stream prefix',
          rows[0]['index'] == 50001000 and '/s97-twowayw2b2p1dxpu2-stream01-' in rows[0]['path'], rows[0]['path'])
    tens = list((e.root / 'output/validation').glob('s97-*/tensors.safetensors'))
    check('A8 oracle tensors pruned after check/emission', len(tens) <= 12, '%d left (in pipeline)' % len(tens))
    s1 = e.state()
    check('A9 state: nothing outstanding after clean stop, group closed', not s1['outstanding'] and s1['group_fill'] == 0,
          'outstanding %d clips-in-pipeline %d group_fill %d' % (len(s1['outstanding']), len(s1['clips']), s1['group_fill']))
    # resume on the SAME server: the pipeline tail of run 1 is emitted first, no index reused, no gap
    cp2 = e.driver('--max-clips', '15')
    rows2 = e.manifest()
    check('B1 resume (same server) continues seq and indices', cp2.returncode == 0 and len(rows) + 15 <= len(rows2) <= len(rows) + 19 and
          not manifest_ok(e, rows2), 'rc=%d rows=%d %s' % (cp2.returncode, len(rows2), manifest_ok(e, rows2)[:2]))
    check('B2 resumed labels continue the schedule', [r['label'] for r in rows2] == [label_for(i) for i in range(len(rows2))])
    check('B3 fake grouper never refused (no latch)', e.stats()['latched'] is None, str(e.stats()['latched']))
    # resume on a NEW server: lost pipeline clips re-submitted at fresh indices, schedule continuous
    used = e.state()['next_index']
    e.stop_fake()
    e.start_fake('--delay', '0.03')
    cp3 = e.driver('--max-clips', '12')
    rows3 = e.manifest()
    labels_ok = [r['label'] for r in rows3] == [label_for(i) for i in range(len(rows3))]
    n2 = len(rows2)
    idx_fresh = len(rows3) > n2 and rows3[n2]['index'] >= used
    check('C1 resume (new server) rewinds lost positions, fresh indices', cp3.returncode == 0 and len(rows3) >= n2 + 12 and
          labels_ok and idx_fresh, 'rc=%d rows=%d labels_ok=%s first new index %s (first unused %d)' % (
              cp3.returncode, len(rows3), labels_ok, rows3[n2]['index'] if len(rows3) > n2 else None, used))
    e.stop_fake()


def test_throttle():
    e = Env('throttle')
    e.start_fake('--delay', '0.02')
    stats = e.work / 'sink-stats.json'
    stats.write_text(json.dumps({'last_played_seq': -1}))
    p, log = e.driver_bg('--sink-stats', str(stats), '--max-ahead-seconds', '20')
    time.sleep(6)
    n1 = len(e.manifest())
    st = e.state()
    ahead = (len(e.manifest()) + len(st['clips'])) * 25 / 24
    check('D1 throttle holds with the sink at seq -1 (limit 20 s)', n1 > 0 and ahead <= 20 + 1e-6,
          'emitted %d, in pipeline %d, ahead %.1f s' % (n1, len(st['clips']), ahead))
    time.sleep(2)
    check('D2 no progress while held', len(e.manifest()) == n1, '%d -> %d' % (n1, len(e.manifest())))
    stats.write_text(json.dumps({'last_played_seq': n1 - 1 + 5}))   # sink played everything + pretend 5 more
    time.sleep(4)
    n2 = len(e.manifest())
    check('D3 throttle releases as the sink advances', n2 > n1, '%d -> %d' % (n1, n2))
    p.send_signal(signal.SIGINT)
    rc = p.wait(60)
    log.close()
    st = e.state()
    check('D4 SIGINT while throttled: exit 0, drained', rc == 0 and not st['outstanding'], 'rc=%d' % rc)
    e.stop_fake()


def test_sigint_and_flush():
    e = Env('sigint')
    e.start_fake('--delay', '0.1')
    p, log = e.driver_bg()
    time.sleep(3.3)
    p.send_signal(signal.SIGINT)
    rc = p.wait(60)
    log.close()
    st = e.state()
    txt = Path(log.name).read_text()
    flush = 'closing the open batch group' in txt
    check('E1 SIGINT: exit 0, in-flight drained, state written', rc == 0 and not st['outstanding'] and st['group_fill'] == 0,
          'rc=%d outstanding=%d flush_prompt=%s' % (rc, len(st['outstanding']), flush))
    check('E2 the server-side group was closed (stream_last count matches)', e.stats()['stream_last_prompts'] == (1 if flush else 0),
          'stream_last prompts %d' % e.stats()['stream_last_prompts'])
    n = len(e.manifest())
    cp = e.driver('--max-clips', '5')
    rows = e.manifest()
    check('E3 resume after SIGINT', cp.returncode == 0 and n + 5 <= len(rows) <= n + 10 and not manifest_ok(e, rows),
          'rc=%d %d -> %d' % (cp.returncode, n, len(rows)))
    e.stop_fake()


def test_failures():
    e = Env('error')
    e.start_fake('--error-at-index', str(50001000 + 17))
    cp = e.driver()
    check('F1 execution error -> exit 2, no retry', cp.returncode == 2 and 'EXECUTION ERROR' in cp.stdout,
          'rc=%d' % cp.returncode)
    e.stop_fake()
    e = Env('failedjob')
    e.start_fake('--failed-receipt-at-index', str(50001000 + 9), '--delay', '0.05')
    cp = e.driver()
    check('F2 pipeline-failed receipt -> exit 6', cp.returncode == 6 and 'FAILED JOB' in cp.stdout, 'rc=%d' % cp.returncode)
    e.stop_fake()
    e = Env('fault')
    e.start_fake('--delay', '0.05')
    p, log = e.driver_bg()
    time.sleep(2)
    (e.root / 'FAULT.json').write_text('{}')
    rc = p.wait(30)
    check('F3 FAULT.json -> exit 4', rc == 4, 'rc=%d' % rc)
    (e.root / 'FAULT.json').unlink()
    e.stop_fake()
    e = Env('http')
    e.start_fake('--delay', '0.05')
    p, log = e.driver_bg('--http-fail-seconds', '4')
    time.sleep(2)
    e.fake.kill()
    e.fake.wait()
    e.fake = None
    t0 = time.time()
    rc = p.wait(60)
    check('F4a server process gone -> exit 5 at once (no restart)', rc == 5 and time.time() - t0 < 10,
          'rc=%d after %.1f s' % (rc, time.time() - t0))
    e = Env('http-stall')
    e.start_fake('--delay', '0.05')
    p, log = e.driver_bg('--http-fail-seconds', '6')
    time.sleep(2)
    e.fake.send_signal(signal.SIGSTOP)
    t0 = time.time()
    rc = p.wait(120)
    e.fake.send_signal(signal.SIGCONT)
    check('F4b server alive but not answering > --http-fail-seconds -> exit 5', rc == 5 and 5 < time.time() - t0 < 60,
          'rc=%d after %.1f s' % (rc, time.time() - t0))
    e.stop_fake()
    e = Env('mismatch', bad_reference='bird')
    e.start_fake('--delay', '0.03')
    cp = e.driver('--max-clips', '20')
    rows = e.manifest()
    check('F5 cycle-0 reference mismatch -> exit 3, clip not published', cp.returncode == 3 and len(rows) == 2 and
          'NOT byte-identical' in cp.stdout, 'rc=%d rows=%d' % (cp.returncode, len(rows)))
    e.stop_fake()


def test_sustained():
    e = Env('sustained')
    e.start_fake('--delay', '0.01')
    t0 = time.time()
    cp = e.driver('--max-clips', '200')
    rows = e.manifest()
    st = e.stats()
    check('G1 200 clips sustained, ordered, cap and polling held', cp.returncode == 0 and 200 <= len(rows) <= 204 and
          not manifest_ok(e, rows) and st['max_in_server'] <= 4 and st['non_oldest_polls'] == 0,
          '%.1f s, max in server %d, gets %d' % (time.time() - t0, st['max_in_server'], st['history_gets']))
    e.stop_fake()


for t in (test_basic_resume_and_identity, test_throttle, test_sigint_and_flush, test_failures, test_sustained):
    if args.only and args.only not in t.__name__:
        continue
    t()
bad = [r for r in RESULTS if not r[1]]
print('\n%d/%d passed; work in %s' % (len(RESULTS) - len(bad), len(RESULTS), TMP))
sys.exit(1 if bad else 0)
