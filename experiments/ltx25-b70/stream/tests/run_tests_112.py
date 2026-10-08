#!/usr/bin/env python3
"""Tests of ltx_continuation_client.py against fake_comfy112.py (CPU only, port 18189 by default; never 8188).

    /home/steve/.venvs/ltx25-baseline/bin/python -B tests/run_tests_112.py [--tmp DIR] [--port 18189] [--only NAME]
"""
import argparse, hashlib, importlib.util, json, os, signal, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
CLIENT = HERE.parent / 'ltx_continuation_client.py'
CONTRACT = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation112-stream')
PY = sys.executable

ap = argparse.ArgumentParser()
ap.add_argument('--tmp', type=Path)
ap.add_argument('--port', type=int, default=18189)
ap.add_argument('--only')
args = ap.parse_args()
assert args.port != 8188, 'never the live port'
TMP = Path(tempfile.mkdtemp(prefix='ltx-c112-test-', dir=str(args.tmp) if args.tmp else None))
RESULTS = []
BASE_SEED = 11200000

SCENES3 = [{'id': 'boat-a', 'prompt': 'A small red wooden toy boat floats on calm clear water at sunset, gentle ripples.',
            'chunks': 3},
           {'id': 'boat-b', 'prompt': 'The red toy boat drifts slowly left as a soft breeze ripples the water.',
            'chunks': 5},
           {'id': 'boat-c', 'prompt': 'Close-up of the toy boat bobbing as warm light glitters on the water.',
            'chunks': 2}]


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok), detail))
    print('%s %s %s' % ('PASS' if ok else 'FAIL', name, detail), flush=True)


def sched(scenes, pos):
    cyc = sum(s['chunks'] for s in scenes)
    r = pos % cyc
    for s in scenes:
        if r < s['chunks']:
            return s
        r -= s['chunks']


class Env:
    def __init__(self, name, scenes=SCENES3):
        self.dir = TMP / name
        self.root = self.dir / 'root'
        self.work = self.dir / 'work'
        self.root.mkdir(parents=True)
        self.work.mkdir(parents=True)
        self.scenes_file = self.dir / 'scenes.json'
        self.scenes = scenes
        self.scenes_file.write_text(json.dumps(scenes) if not isinstance(scenes, dict) else json.dumps(scenes))
        self.fake = None

    def start_fake(self, *extra):
        ready = self.root / 'fake112-ready'
        if ready.exists():
            ready.unlink()
        self.fake_log = open(self.dir / ('fake-%d.log' % time.time_ns()), 'w')
        self.fake = subprocess.Popen([PY, '-B', str(HERE / 'fake_comfy112.py'), '--root', str(self.root),
                                      '--port', str(args.port), '--contract-dir', str(CONTRACT)] + list(extra),
                                     stdout=self.fake_log, stderr=subprocess.STDOUT)
        for _ in range(200):
            if ready.is_file():
                try:
                    urllib.request.urlopen('http://127.0.0.1:%d/ltx-stream/status' % args.port, timeout=2).read()
                    return
                except OSError:
                    pass
            if self.fake.poll() is not None:
                raise RuntimeError('fake exited: ' + Path(self.fake_log.name).read_text()[-2000:])
            time.sleep(0.05)
        raise RuntimeError('fake did not start')

    def stop_fake(self):
        if self.fake:
            try:
                self.fake.send_signal(signal.SIGCONT)
            except ProcessLookupError:
                pass
            self.fake.send_signal(signal.SIGINT)
            try:
                self.fake.wait(10)
            except subprocess.TimeoutExpired:
                self.fake.kill()
                self.fake.wait()
            self.fake = None

    def cmd(self, *extra):
        base = [PY, '-B', str(CLIENT), '--work-dir', str(self.work), '--root', str(self.root),
                '--port', str(args.port), '--contract-dir', str(CONTRACT), '--poll', '0.05',
                '--min-free-gib', '1', '--scenes', str(self.scenes_file), '--base-seed', str(BASE_SEED)]
        return base + list(extra)

    def client(self, *extra, timeout=300):
        cp = subprocess.run(self.cmd(*extra), capture_output=True, text=True, timeout=timeout)
        (self.work / ('client-%d.log' % time.time_ns())).write_text(cp.stdout + cp.stderr)
        return cp

    def client_bg(self, *extra):
        log = open(self.work / ('client-bg-%d.log' % time.time_ns()), 'w')
        return subprocess.Popen(self.cmd(*extra), stdout=log, stderr=subprocess.STDOUT), log

    def manifest(self):
        p = self.work / 'manifest.jsonl'
        return [json.loads(x) for x in p.read_text().splitlines()] if p.is_file() else []

    def state(self):
        return json.loads((self.work / 'client-state.json').read_text())

    def stats(self):
        return json.loads((self.root / 'fake112-stats.json').read_text())

    def receipt(self, seq):
        run = next(p for p in self.root.glob('encoder-server-continuation-stream-112-*') if '.old' not in p.name)
        return json.loads((run / 'receipts' / ('receipt-stream112-s%08d.json' % seq)).read_text())


def chain_problems(rows, scenes, first_seq=0, pos_offset=0):
    """Manifest rows of one server chain: seq/stream_seq order, anchors, skip field, schedule, seeds."""
    probs = []
    for k, r in enumerate(rows):
        if r['seq'] != first_seq + k:
            probs.append('seq %s at %d' % (r['seq'], k))
        if r['stream_seq'] != k:
            probs.append('stream_seq %s at %d' % (r['stream_seq'], k))
        if r['seed'] != BASE_SEED + r['stream_seq']:
            probs.append('seed %s' % r['seed'])
        want = sched(scenes, pos_offset + k)
        if r['scene'] != want['id'].replace('-', ''):
            probs.append('scene %s != %s at %d' % (r['scene'], want['id'], k))
        if k == 0:
            if 'skip_first_frames' in r or r['predecessor_anchor_sha256'] != '':
                probs.append('chunk 0 carries skip/predecessor')
        else:
            if r.get('skip_first_frames') != 1:
                probs.append('no skip_first_frames at %d' % k)
            if r['predecessor_anchor_sha256'] != rows[k - 1]['anchor_sha256']:
                probs.append('anchor chain broken at %d' % k)
        p = Path(r['path'])
        if not p.is_file() or p.stat().st_size == 0:
            probs.append('missing mp4 %s' % p)
    return probs


# ------------------------------------------------------------------------------------------------
def test_qualification():
    e = Env('qual-pass')
    e.start_fake('--delay', '0.03')
    cp = e.client('--max-chunks', '5')
    st = e.stats()
    rows = e.manifest()
    check('Q1 qualification pass -> streams (11 serial requests, verdict, 5 chunks)',
          cp.returncode == 0 and st['qual_posts'] == 11 and st['stream_order'] == [0, 1, 2, 3, 4] and len(rows) == 5
          and 'client re-derivation passed' in cp.stdout and not st['refusals'],
          'rc=%d qual_posts=%d order=%s refusals=%s' % (cp.returncode, st['qual_posts'], st['stream_order'], st['refusals']))
    q = [json.loads(x) for x in (e.work / 'qualification.jsonl').read_text().splitlines()]
    check('Q2 qualification log has the LAUNCH.md order and a passed verdict',
          [x['name'] for x in q[:11]] == ['stream112-window-probe', 'stream112-prepare'] +
          ['stream112-%s-c%06d' % (k, i) for k in ('qeager', 'qgraph', 'qrepeat') for i in range(3)] and
          q[11]['verdict']['passed'] is True and st['max_in_server'] == 1)
    cp2 = e.client('--max-chunks', '2')
    st = e.stats()
    check('Q3 second run on a qualified server verifies, does not re-qualify',
          cp2.returncode == 0 and st['qual_posts'] == 11 and 'already passed qualification' in cp2.stdout and
          st['stream_order'] == list(range(7)), 'rc=%d' % cp2.returncode)
    e.stop_fake()
    for mode in ('fail', 'lie'):
        e = Env('qual-' + mode)
        e.start_fake('--qualification', mode)
        cp = e.client('--max-chunks', '3')
        st = e.stats()
        check('Q4 qualification %s -> exit 13, nothing streamed' % mode,
              cp.returncode == 13 and st['stream_order'] == [] and not e.manifest(),
              'rc=%d order=%s last=%s' % (cp.returncode, st['stream_order'], cp.stdout.strip().splitlines()[-2][:160]))
        e.stop_fake()
    e = Env('qual-skip')
    e.start_fake()
    cp = e.client('--skip-qualification')
    check('Q5 --skip-qualification on an unqualified server -> exit 13, no request',
          cp.returncode == 13 and e.stats()['posts'] == 0, 'rc=%d' % cp.returncode)
    cp = e.client('--qualification-only')
    st = e.stats()
    check('Q6 --qualification-only -> exit 0, qualified, no stream chunk',
          cp.returncode == 0 and st['qual_posts'] == 11 and st['stream_order'] == [], 'rc=%d' % cp.returncode)
    e.stop_fake()


def test_serial_40():
    e = Env('serial40')
    e.start_fake('--phase', 'stream', '--delay', '0.03')
    cp = e.client('--max-chunks', '40', '--skip-qualification')
    rows = e.manifest()
    st = e.stats()
    probs = chain_problems(rows, SCENES3)
    check('S1 40 chunks, exit 0, server order 0..39, never >1 in server, no refusals',
          cp.returncode == 0 and st['stream_order'] == list(range(40)) and st['max_in_server'] == 1 and not st['refusals'],
          'rc=%d n=%d max=%d refusals=%s' % (cp.returncode, len(st['stream_order']), st['max_in_server'], st['refusals']))
    check('S2 manifest: seq, anchor chain, skip_first_frames, scene schedule, seeds', len(rows) == 40 and not probs,
          str(probs[:3]))
    recs = [e.receipt(k) for k in range(40)]
    cuts = [k for k in range(1, 40) if recs[k]['prompt_changed']]
    want_cuts = [k for k in range(1, 40) if sched(SCENES3, k)['prompt'] != sched(SCENES3, k - 1)['prompt']]
    prompts_ok = all(recs[k]['prompt_sha256'] == hashlib.sha256(sched(SCENES3, k)['prompt'].encode()).hexdigest()
                     for k in range(40))
    check('S3 prompts follow the schedule; cuts exactly at scene boundaries (anchor chain continues through)',
          prompts_ok and cuts == want_cuts and all(recs[k]['anchor_in']['sha256'] == recs[k - 1]['anchor_out']['sha256']
                                                    for k in range(1, 40)), 'cuts %s' % cuts[:8])
    gaps = st['submit_after_commit_s']
    check('S4 next chunk submitted within one poll of the previous receipt (poll 0.05 s)',
          len(gaps) == 39 and max(gaps) < 0.05 + 0.2, 'max %.3f s median %.3f s' % (max(gaps), sorted(gaps)[19]))
    s = e.state()
    check('S5 state: no pending, last stream_seq 39, next manifest seq 40',
          s.get('pending') is None and s['last_manifested_stream_seq'] == 39 and s['next_manifest_seq'] == 40)
    e.stop_fake()


def test_restart_same_and_new_server():
    e = Env('restart')
    e.start_fake('--phase', 'stream', '--delay', '0.03')
    cp1 = e.client('--max-chunks', '7', '--skip-qualification')
    cp2 = e.client('--max-chunks', '6', '--skip-qualification')
    rows = e.manifest()
    probs = chain_problems(rows, SCENES3)
    check('R1 restart on the same server continues the chain (13 chunks, one chain, seq 0..12)',
          cp1.returncode == 0 and cp2.returncode == 0 and len(rows) == 13 and not probs and
          'resuming this server\'s chain at stream_seq 7' in cp2.stdout and e.stats()['stream_order'] == list(range(13)),
          'rc=%d/%d %s' % (cp1.returncode, cp2.returncode, probs[:3]))
    # crash (SIGKILL) while a chunk is in flight, then restart: adopt, no gap, no duplicate
    e.stop_fake()
    e2 = Env('crash')
    e2.start_fake('--phase', 'stream', '--delay', '0.6')
    p, log = e2.client_bg('--skip-qualification')
    deadline = time.time() + 30
    while time.time() < deadline and len(e2.manifest()) < 3:
        time.sleep(0.05)
    time.sleep(0.2)
    p.kill()
    p.wait()
    log.close()
    n_before = len(e2.manifest())
    in_server = e2.stats()['stream_order']
    cp = e2.client('--max-chunks', '2', '--skip-qualification')
    rows = e2.manifest()
    probs = chain_problems(rows, SCENES3)
    check('R2 crash with a chunk in flight: restart adopts/recovers it, then continues without gap or duplicate',
          cp.returncode == 0 and not probs and len(rows) == len(e2.stats()['stream_order']) and
          ('adopting the in-flight chunk' in cp.stdout or len(in_server) == n_before),
          'rc=%d before=%d submitted_before=%d after=%d %s' % (cp.returncode, n_before, len(in_server), len(rows), probs[:2]))
    e2.stop_fake()
    # new server: the chain restarts at stream_seq 0, manifest seq keeps increasing, next scene starts
    n_old = len(e.manifest())
    last_pos = e.manifest()[-1]['schedule_pos']
    e.start_fake('--phase', 'stream', '--delay', '0.03')
    cp3 = e.client('--max-chunks', '5', '--skip-qualification')
    rows = e.manifest()
    new = rows[n_old:]
    cyc = sum(s['chunks'] for s in SCENES3)
    r = last_pos % cyc
    acc = 0
    for s in SCENES3:
        if r < acc + s['chunks']:
            start = last_pos - r + acc + s['chunks']
            break
        acc += s['chunks']
    probs = chain_problems(new, SCENES3, first_seq=n_old, pos_offset=start)
    check('R3 new server: stream_seq restarts at 0, manifest seq continues, next scene starts, fresh preview path',
          cp3.returncode == 0 and len(new) == 5 and not probs and new[0]['schedule_pos'] == start and
          new[0]['server_identity_sha256'] != rows[0]['server_identity_sha256'] and
          new[0]['path'].endswith('preview_00002_.mp4'),
          'rc=%d %s first path %s' % (cp3.returncode, probs[:3], new[0]['path'] if new else None))
    e.stop_fake()


def test_throttle():
    e = Env('throttle')
    e.start_fake('--phase', 'stream', '--delay', '0.02')
    stats = e.work / 'sink-stats.json'
    stats.write_text(json.dumps({'last_played_seq': -1}))
    p, log = e.client_bg('--skip-qualification', '--sink-stats', str(stats), '--max-ahead-seconds', '9')
    time.sleep(4)
    n1 = len(e.manifest())
    time.sleep(1.5)
    n1b = len(e.manifest())
    check('T1 throttle holds with the sink at seq -1 (limit 9 s at 2 s per chunk)', 1 <= n1 <= 5 and n1b == n1,
          'chunks %d then %d' % (n1, n1b))
    stats.write_text(json.dumps({'last_played_seq': n1 - 1}))
    time.sleep(3)
    n2 = len(e.manifest())
    check('T2 throttle releases as the sink advances', n2 > n1, '%d -> %d' % (n1, n2))
    p.send_signal(signal.SIGINT)
    rc = p.wait(60)
    log.close()
    check('T3 SIGINT while throttled: exit 0', rc == 0 and e.state().get('pending') is None, 'rc=%d' % rc)
    e.stop_fake()


def test_disposal():
    spec = importlib.util.spec_from_file_location('c112', str(CLIENT))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = TMP / 'unit' / 'output'
    (out / 'stream112-s00000007').mkdir(parents=True)
    (out / 'other').mkdir()
    (out / 'stream112-s00000007' / 'preview_00001_.mp4').write_bytes(b'x')
    os.symlink(out / 'stream112-s00000007', out / 'stream112-s00000008')

    class Fake:
        output_dir = out
    dz = lambda p: mod.Client.disposable(Fake, p)
    cases = [(out / 'stream112-s00000007/preview_00001_.mp4', True),
             (out / 'stream112-s0000007/preview_00001_.mp4', False),
             (out / 'stream112-s000000077/preview_00001_.mp4', False),
             (out / 'stream112-qeager-c000000/preview_00001_.mp4', False),
             (out / 's97-twowayw2b2p1dxpu2-stream01-0000001/preview_00001_.mp4', False),
             (out / 'stream112-s00000007/receipt.json', False),
             (out / 'stream112-s00000007/preview_00001_.mp4.tmp', False),
             (out / 'other/preview_00001_.mp4', False),
             (out.parent / 'stream112-s00000007/preview_00001_.mp4', False),
             (out / 'stream112-s00000008/preview_00001_.mp4', False)]
    bad = [str(p) for p, want in cases if dz(p) != want]
    check('D1 disposal regex: only <output>/stream112-sNNNNNNNN/preview_NNNNN_.mp4, no symlinked dirs', not bad, str(bad))
    e = Env('dispose')
    e.start_fake('--phase', 'stream', '--delay', '0.02')
    stats = e.work / 'sink-stats.json'
    stats.write_text(json.dumps({'last_played_seq': -1}))
    cp = e.client('--skip-qualification', '--max-chunks', '12', '--sink-stats', str(stats), '--delete-consumed-previews',
                  '--dispose-margin', '3', '--max-ahead-seconds', '1000')
    rows = e.manifest()
    decoy = Path(rows[2]['path']).parent / 'notes.txt'
    decoy.write_text('not a preview')
    stats.write_text(json.dumps({'last_played_seq': 8}))
    cp = e.client('--skip-qualification', '--max-chunks', '1', '--sink-stats', str(stats), '--delete-consumed-previews',
                  '--dispose-margin', '3', '--max-ahead-seconds', '1000')
    rows = e.manifest()
    gone = [r['seq'] for r in rows if not Path(r['path']).exists()]
    check('D2 consumed previews deleted only past last_played_seq - margin (seq <= 5)', gone == [0, 1, 2, 3, 4, 5],
          'deleted seqs %s' % gone)
    check('D3 a preview dir with other content keeps that content (only the MP4 goes)',
          decoy.is_file() and not Path(rows[2]['path']).exists() and not Path(rows[1]['path']).parent.exists())
    e.stop_fake()
    e = Env('dispose-off')
    e.start_fake('--phase', 'stream', '--delay', '0.02')
    stats = e.work / 'sink-stats.json'
    stats.write_text(json.dumps({'last_played_seq': 100}))
    e.client('--skip-qualification', '--max-chunks', '6', '--sink-stats', str(stats), '--dispose-margin', '0',
             '--max-ahead-seconds', '1000')
    check('D4 disposal is off by default', all(Path(r['path']).exists() for r in e.manifest()))
    e.stop_fake()


def test_sigint():
    e = Env('sigint')
    e.start_fake('--phase', 'stream', '--delay', '0.8')
    p, log = e.client_bg('--skip-qualification')
    time.sleep(2.6)
    p.send_signal(signal.SIGINT)
    t0 = time.time()
    rc = p.wait(60)
    log.close()
    txt = Path(log.name).read_text()
    rows = e.manifest()
    st = e.stats()
    check('G1 SIGINT: exit 0 after the in-flight chunk completes and is recorded; state written',
          rc == 0 and len(rows) == len(st['stream_order']) and e.state().get('pending') is None and
          'waiting for the in-flight request' in txt, 'rc=%d rows=%d submitted=%d after %.1f s' % (
              rc, len(rows), len(st['stream_order']), time.time() - t0))
    cp = e.client('--skip-qualification', '--max-chunks', '2')
    rows = e.manifest()
    check('G2 resume after SIGINT: no gap', cp.returncode == 0 and not chain_problems(rows, SCENES3), 'rc=%d' % cp.returncode)
    e.stop_fake()


def halt_case(label, code, fake_extra, client_extra=(), scenes=SCENES3, expect_text=None, max_rows=None):
    e = Env('halt-' + label, scenes)
    e.start_fake('--phase', 'stream', '--delay', '0.03', *fake_extra)
    cp = e.client('--skip-qualification', '--max-chunks', '10', *client_extra, timeout=120)
    rows = e.manifest()
    last = (cp.stdout.strip().splitlines() or [''])[-2:]
    ok = cp.returncode == code and (expect_text is None or expect_text in cp.stdout) and \
        (max_rows is None or len(rows) <= max_rows)
    check('H %-28s -> exit %d' % (label, code), ok, 'rc=%d rows=%d %s' % (cp.returncode, len(rows), last[0][:170]))
    e.stop_fake()
    return e, cp


def test_halts():
    halt_case('server halt', 2, ['--halt-at', '3'], expect_text='server halted', max_rows=3)
    halt_case('failed-job receipt', 6, ['--fail-at', '3'], expect_text='FAILED JOB', max_rows=3)
    halt_case('FAULT.json', 4, ['--fault-at', '3'], max_rows=3)
    halt_case('preview missing', 7, ['--no-preview-at', '2'], max_rows=2)
    halt_case('chunk stalls', 16, ['--stall-at', '2'], ['--chunk-timeout', '3'], max_rows=2)
    halt_case('stale anchor (409)', 10, ['--corrupt-anchor-at', '2'], expect_text='stale-anchor', max_rows=3)
    halt_case('order (409)', 10, ['--refuse-at', '4', '--refuse-code', 'order'], max_rows=4)
    halt_case('receipt anchor mismatch', 12, ['--corrupt-receipt-at', '2'], max_rows=2)
    halt_case('another client advanced', 12, ['--advance-at', '2'], expect_text='another client', max_rows=3)
    halt_case('contract (400)', 11, ['--refuse-at', '1', '--refuse-code', 'contract', '--refuse-status', '400'],
              max_rows=1)
    halt_case('text-reuse-rule (409)', 14, ['--refuse-at', '1', '--refuse-code', 'text-reuse-rule'], max_rows=1)
    halt_case('busy (409)', 15, ['--refuse-at', '2', '--refuse-code', 'busy'], max_rows=2)
    halt_case('halted (503 on POST)', 2, ['--refuse-at', '2', '--refuse-code', 'halted', '--refuse-status', '503'],
              max_rows=2)
    long_scenes = [dict(SCENES3[0]), {'id': 'long', 'chunks': 2, 'prompt': 'A small red toy boat ' * 8 +
                                      'drifts slowly across calm clear water as warm daylight glitters.'}]
    halt_case('over-long prompt (server)', 14, ['--max-prompt-chars', '120'], ['--token-check', 'off'], scenes=long_scenes,
              expect_text='window-not-qualified', max_rows=3)
    too_long = [dict(SCENES3[0]), {'id': 'toolong', 'chunks': 1, 'prompt': ' '.join(
        ['the small red wooden toy boat drifts gently across the calm clear water'] * 6) + '.'}]
    e, cp = halt_case('over-long prompt (client)', 8, [], scenes=too_long, expect_text='scene schedule refused',
                      max_rows=0)
    check('H   over-long prompt refused before any request', json.loads((e.root / 'fake112-stats.json').read_text())['posts'] == 0)
    halt_case('disk below --min-free-gib', 9, [], ['--min-free-gib', '1000000'], max_rows=0)
    halt_case('wrong runtime manifest', 8, ['--manifest-sha256', 'f' * 64], max_rows=0)
    # HTTP: server stops answering (SIGSTOP) / goes away
    for label, action in (('server not answering', 'stop'), ('server gone', 'kill')):
        e = Env('http-' + action)
        e.start_fake('--phase', 'stream', '--delay', '0.1')
        p, log = e.client_bg('--skip-qualification', '--http-fail-seconds', '4')
        time.sleep(1.5)
        if action == 'stop':
            e.fake.send_signal(signal.SIGSTOP)
        else:
            e.fake.kill()
            e.fake.wait()
            e.fake = None
        t0 = time.time()
        rc = p.wait(90)
        log.close()
        lo = 3.5 if action == 'stop' else 0.0   # a kill mid-POST is an unknown outcome: exit 5 at once
        check('H %-28s -> exit 5' % ('HTTP: ' + label), rc == 5 and lo < time.time() - t0 < 30,
              'rc=%d after %.1f s' % (rc, time.time() - t0))
        e.stop_fake()


def test_text_reuse_and_fixtures():
    e = Env('reuse')
    e.start_fake('--phase', 'stream', '--delay', '0.02', '--text-reuse', '1')
    cp = e.client('--skip-qualification', '--max-chunks', '12')
    recs = [e.receipt(k) for k in range(12)]
    want = [int(k > 0 and sched(SCENES3, k)['prompt'] == sched(SCENES3, k - 1)['prompt']) for k in range(12)]
    check('X1 text_reuse=1 server: reuse_text 1 on continuous chunks, 0 at cuts and chunk 0',
          cp.returncode == 0 and [r['reuse_text'] for r in recs] == want and not e.stats()['refusals'],
          'rc=%d %s' % (cp.returncode, [r['reuse_text'] for r in recs]))
    e.stop_fake()
    kittens = json.loads(Path('/home/steve/llm-optimizations/experiments/ltx25-b70/data/stream/kittens-01.json').read_text())
    e = Env('kittens', kittens)
    e.start_fake('--phase', 'stream', '--delay', '0.02')
    cp = e.client('--skip-qualification', '--max-chunks', '9')
    rows = e.manifest()
    ids = [scene for scene in (r['scene'] for r in rows)]
    check('X2 kittens-01 fixtures format: each fixture a scene of --default-chunks 4, ids sanitised to [a-z0-9]',
          cp.returncode == 0 and ids == ['kittenyawn'] * 4 + ['kittenbox'] * 4 + ['kittenyarn'] and
          'kittenyawn=49' in cp.stdout, 'rc=%d %s' % (cp.returncode, ids))
    e.stop_fake()


for t in (test_qualification, test_serial_40, test_restart_same_and_new_server, test_throttle, test_disposal,
          test_sigint, test_halts, test_text_reuse_and_fixtures):
    if args.only and args.only not in t.__name__:
        continue
    t()
bad = [r for r in RESULTS if not r[1]]
print('\n%d/%d passed; work in %s' % (len(RESULTS) - len(bad), len(RESULTS), TMP))
sys.exit(1 if bad else 0)
