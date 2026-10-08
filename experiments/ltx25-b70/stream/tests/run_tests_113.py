#!/usr/bin/env python3
"""Tests of ltx_continuation_client.py --packet 113 against fake_comfy113.py (CPU only, port 18189; never 8188).

    /home/steve/.venvs/ltx25-baseline/bin/python -B tests/run_tests_113.py [--tmp DIR] [--port 18189] [--only NAME]

Covers what packet 113 changes for the client: the receipt arrives before the MP4 (the client
submits the next chunk first, then waits for the preview record within --save-wait), chain
resets (--reset-every-chunks, --reset-on-scene-change), the preview failure latch, and that
the 112 defaults refuse the 113-only flags.
"""
import argparse, json, signal, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
CLIENT = HERE.parent / 'ltx_continuation_client.py'
CONTRACT = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation113-stream')
PY = sys.executable

ap = argparse.ArgumentParser()
ap.add_argument('--tmp', type=Path)
ap.add_argument('--port', type=int, default=18189)
ap.add_argument('--only')
args = ap.parse_args()
assert args.port != 8188, 'never the live port'
TMP = Path(tempfile.mkdtemp(prefix='ltx-c113-test-', dir=str(args.tmp) if args.tmp else None))
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


class Env:
    def __init__(self, name):
        self.dir = TMP / name
        self.root, self.work = self.dir / 'root', self.dir / 'work'
        self.root.mkdir(parents=True)
        self.work.mkdir(parents=True)
        self.scenes_file = self.dir / 'scenes.json'
        self.scenes_file.write_text(json.dumps(SCENES3))
        self.fake = None

    def start_fake(self, *extra):
        ready = self.root / 'fake113-ready'
        self.fake_log = open(self.dir / ('fake-%d.log' % time.time_ns()), 'w')
        self.fake = subprocess.Popen([PY, '-B', str(HERE / 'fake_comfy113.py'), '--root', str(self.root),
                                      '--port', str(args.port), '--contract-dir', str(CONTRACT)] + list(extra),
                                     stdout=self.fake_log, stderr=subprocess.STDOUT)
        for _ in range(400):
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
            self.fake.send_signal(signal.SIGINT)
            try:
                self.fake.wait(10)
            except subprocess.TimeoutExpired:
                self.fake.kill()
                self.fake.wait()
            self.fake = None

    def client(self, *extra, packet='113', timeout=300):
        cmd = [PY, '-B', str(CLIENT), '--work-dir', str(self.work), '--root', str(self.root),
               '--port', str(args.port), '--contract-dir', str(CONTRACT), '--poll', '0.05',
               '--min-free-gib', '1', '--scenes', str(self.scenes_file), '--base-seed', str(BASE_SEED),
               '--packet', packet] + list(extra)
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        (self.work / ('client-%d.log' % time.time_ns())).write_text(cp.stdout + cp.stderr)
        return cp

    def manifest(self):
        p = self.work / 'manifest.jsonl'
        return [json.loads(x) for x in p.read_text().splitlines()] if p.is_file() else []

    def stats(self):
        return json.loads((self.root / 'fake113-stats.json').read_text())

    def receipt(self, seq):
        run = next(p for p in self.root.glob('encoder-server-continuation-stream-113-*') if '.old' not in p.name)
        return json.loads((run / 'receipts' / ('receipt-stream112-s%08d.json' % seq)).read_text())


def test_async_preview():
    e = Env('async')
    e.start_fake('--delay', '0.05', '--preview-delay', '0.4')
    cp = e.client('--max-chunks', '8')
    rows, st = e.manifest(), e.stats()
    probs = []
    for k, r in enumerate(rows):
        p = Path(r['path'])
        if not p.is_file() or p.stat().st_size == 0 or 'preview_sha256' not in r:
            probs.append('mp4 %d' % k)
        if k and (r.get('skip_first_frames') != 1 or r['predecessor_anchor_sha256'] != rows[k - 1]['anchor_sha256']):
            probs.append('chain %d' % k)
        if r.get('submit_to_anchor_ready') is None or r.get('border_mean_chroma') is None or 'border_to_centre_chroma_ratio' not in r:
            probs.append('timing/diag %d' % k)
    check('A1 113 qualification + 8 chunks: exit 0, previews verified against their records, chain intact',
          cp.returncode == 0 and len(rows) == 8 and not probs and st['stream_order'] == list(range(8)) and
          not st['refusals'], 'rc=%d rows=%d probs=%s' % (cp.returncode, len(rows), probs[:4]))
    check('A2 the next chunk is submitted before the previous preview is written (preview off the chain)',
          st['submitted_before_prev_preview'] >= 6, 'submitted_before_prev_preview=%d' % st['submitted_before_prev_preview'])
    check('A3 previews written in order', st['preview_order'][-8:] == ['stream112-s%08d' % k for k in range(8)],
          str(st['preview_order'][-8:]))
    cp2 = e.client('--max-chunks', '2', '--skip-qualification')
    check('A4 resume on the same 113 server continues the chain', cp2.returncode == 0 and len(e.manifest()) == 10 and
          e.stats()['stream_order'] == list(range(10)), 'rc=%d' % cp2.returncode)
    e.stop_fake()


def test_resets():
    e = Env('reset-every')
    e.start_fake('--phase', 'stream', '--delay', '0.02', '--preview-delay', '0.05')
    cp = e.client('--skip-qualification', '--max-chunks', '10', '--reset-every-chunks', '3')
    rows, st = e.manifest(), e.stats()
    recs = [e.receipt(k) for k in range(10)]
    resets = [r['stream_seq'] for r in recs if r['reset']]
    ok = all((r['anchor_in'] is None) == (r['stream_seq'] == 0 or r['reset']) for r in recs)
    skips = [row.get('skip_first_frames', 0) for row in rows]
    check('R1 --reset-every-chunks 3: resets at 3, 6, 9; unanchored; no skip_first_frames on resets',
          cp.returncode == 0 and resets == [3, 6, 9] and st['resets'] == [3, 6, 9] and ok and
          skips == [0, 1, 1, 0, 1, 1, 0, 1, 1, 0] and [row['reset'] for row in rows] == [k in (3, 6, 9) for k in range(10)],
          'rc=%d resets=%s skips=%s' % (cp.returncode, resets, skips))
    check('R2 after a reset the chain continues from the reset chunk\'s anchor',
          all(recs[k]['anchor_in']['sha256'] == recs[k - 1]['anchor_out']['sha256'] for k in (4, 5, 7, 8)))
    e.stop_fake()
    e = Env('reset-scene')
    e.start_fake('--phase', 'stream', '--delay', '0.02', '--preview-delay', '0.05')
    cp = e.client('--skip-qualification', '--max-chunks', '11', '--reset-on-scene-change')
    recs = [e.receipt(k) for k in range(11)]
    resets = [r['stream_seq'] for r in recs if r['reset']]
    check('R3 --reset-on-scene-change: resets exactly at the scene boundaries 3, 8, 10',
          cp.returncode == 0 and resets == [3, 8, 10], 'rc=%d resets=%s' % (cp.returncode, resets))
    e.stop_fake()
    e = Env('reset-112')
    cp = e.client('--reset-every-chunks', '2', packet='112')
    check('R4 reset flags with --packet 112 are refused before any request', cp.returncode != 0 and
          'need --packet 113' in (cp.stdout + cp.stderr), 'rc=%d' % cp.returncode)


def test_preview_faults():
    e = Env('nopreview')
    e.start_fake('--phase', 'stream', '--delay', '0.02', '--preview-delay', '0.05', '--no-preview-at', '2')
    t0 = time.time()
    cp = e.client('--skip-qualification', '--max-chunks', '6', '--save-wait', '2')
    check('P1 a preview record that never appears -> exit 7 within the --save-wait bound; chunk 2 not manifested',
          cp.returncode == 7 and len(e.manifest()) == 2 and time.time() - t0 < 30,
          'rc=%d rows=%d %.1fs' % (cp.returncode, len(e.manifest()), time.time() - t0))
    e.stop_fake()
    e = Env('previewfail')
    e.start_fake('--phase', 'stream', '--delay', '0.02', '--preview-delay', '0.05', '--preview-fail-at', '3')
    cp = e.client('--skip-qualification', '--max-chunks', '8', '--save-wait', '5')
    check('P2 a preview write failure latches the server -> client exit 6 (failure file) or 2, rows stop at 3',
          cp.returncode in (2, 6) and len(e.manifest()) == 3, 'rc=%d rows=%d' % (cp.returncode, len(e.manifest())))
    e.stop_fake()
    e = Env('wrongpacket')
    e.start_fake('--phase', 'stream')
    cp = e.client('--skip-qualification', '--max-chunks', '1', packet='112')
    check('P3 a 112 client against a 113 server refuses at preflight (manifest identity)', cp.returncode == 8,
          'rc=%d' % cp.returncode)
    e.stop_fake()


for t in (test_async_preview, test_resets, test_preview_faults):
    if args.only and args.only not in t.__name__:
        continue
    t()
bad = [r for r in RESULTS if not r[1]]
print('\n%d/%d passed; work in %s' % (len(RESULTS) - len(bad), len(RESULTS), TMP))
sys.exit(1 if bad else 0)
