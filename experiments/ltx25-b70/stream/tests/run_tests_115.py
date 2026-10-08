#!/usr/bin/env python3
"""Tests of ltx_continuation_client.py --packet 115 against fake_comfy115.py (CPU only, port 18189; never 8188).

    /home/steve/.venvs/ltx25-baseline/bin/python -B tests/run_tests_115.py [--tmp DIR] [--port 18189] [--only NAME]

Covers what packet 115 changes for the client: four anchor modes (mixed by default; guide delivers every
frame, no skip), the 115 qualification re-derivation (mixed: stage B used the predecessor's decoded frame),
the sharpness profile and the mixed frame wait in manifest lines, resets, decode faults, and that 114 and
115 clients each refuse the other packet's server at preflight.
"""
import argparse, hashlib, json, signal, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
CLIENT = HERE.parent / 'ltx_continuation_client.py'
CONTRACT = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation115-stream')
CONTRACT114 = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation114-stream')
CONTRACT113 = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation113-stream')
FAKE_SHA = hashlib.sha256(b'fake-packet-115-manifest').hexdigest()     # fake_comfy115 default
FAKE114_SHA = hashlib.sha256(b'fake-packet-114-manifest').hexdigest()  # fake_comfy114 default
FAKE113_SHA = 'a23dbc946d156df70c3e61134dc3231b147817c5cb110a015f84c8f020f7f28b'   # fake_comfy113 default
PY = sys.executable

ap = argparse.ArgumentParser()
ap.add_argument('--tmp', type=Path)
ap.add_argument('--port', type=int, default=18189)
ap.add_argument('--only')
args = ap.parse_args()
assert args.port != 8188, 'never the live port'
TMP = Path(tempfile.mkdtemp(prefix='ltx-c115-test-', dir=str(args.tmp) if args.tmp else None))
RESULTS = []
BASE_SEED = 11400000
SCENES3 = [{'id': 'boat-a', 'prompt': 'A small red wooden toy boat floats on calm clear water at sunset, gentle ripples.',
            'chunks': 3},
           {'id': 'boat-b', 'prompt': 'The red toy boat drifts slowly left as a soft breeze ripples the water.',
            'chunks': 5},
           {'id': 'boat-c', 'prompt': 'Close-up of the toy boat bobbing as warm light glitters on the water.',
            'chunks': 2}]
SCENE_STARTS = (0, 3, 8)          # stream_seq where a new scene (prompt) begins, first cycle


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok), detail))
    print('%s %s %s' % ('PASS' if ok else 'FAIL', name, detail), flush=True)


def expected_reuse(n_chunks, resets=()):
    """reuse_text=1 exactly for an anchored, non-reset chunk whose prompt equals its predecessor's."""
    cycle = sum(s['chunks'] for s in SCENES3)
    starts = {k + cycle * j for j in range(4) for k in SCENE_STARTS}
    return [int(n > 0 and n not in resets and n not in starts) for n in range(n_chunks)]


class Env:
    def __init__(self, name):
        self.dir = TMP / name
        self.root, self.work = self.dir / 'root', self.dir / 'work'
        self.root.mkdir(parents=True)
        self.work.mkdir(parents=True)
        self.scenes_file = self.dir / 'scenes.json'
        self.scenes_file.write_text(json.dumps(SCENES3))
        self.fake = None
        self.packet = '115'

    def start_fake(self, *extra, fake='fake_comfy115.py', contract=CONTRACT):
        ready = self.root / ('fake114-ready' if '114' in fake else 'fake115-ready')
        self.fake_log = open(self.dir / ('fake-%d.log' % time.time_ns()), 'w')
        self.fake = subprocess.Popen([PY, '-B', str(HERE / fake), '--root', str(self.root),
                                      '--port', str(args.port), '--contract-dir', str(contract)] + list(extra),
                                     stdout=self.fake_log, stderr=subprocess.STDOUT)
        for _ in range(600):
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

    def client(self, *extra, packet='115', contract=CONTRACT, manifest=FAKE_SHA, timeout=300):
        cmd = [PY, '-B', str(CLIENT), '--work-dir', str(self.work), '--root', str(self.root),
               '--port', str(args.port), '--contract-dir', str(contract), '--poll', '0.05',
               '--min-free-gib', '1', '--scenes', str(self.scenes_file), '--base-seed', str(BASE_SEED),
               '--packet', packet]
        if manifest:
            cmd += ['--manifest-sha256', manifest]
        cp = subprocess.run(cmd + list(extra), capture_output=True, text=True, timeout=timeout)
        (self.work / ('client-%d.log' % time.time_ns())).write_text(cp.stdout + cp.stderr)
        return cp

    def manifest(self):
        p = self.work / 'manifest.jsonl'
        return [json.loads(x) for x in p.read_text().splitlines()] if p.is_file() else []

    def stats(self):
        return json.loads((self.root / 'fake115-stats.json').read_text())

    def run_dir(self):
        return next(p for p in self.root.glob('encoder-server-continuation-stream-115-*') if '.old' not in p.name)

    def receipt(self, seq):
        return json.loads((self.run_dir() / 'receipts' / ('receipt-stream115-s%08d.json' % seq)).read_text())

    def decode(self, seq):
        return json.loads((self.run_dir() / 'receipts' / ('decode-stream115-s%08d.json' % seq)).read_text())


def manifest_problems(rows, frames, anchor):
    probs = []
    for k, r in enumerate(rows):
        p = Path(r['path'])
        first = k == 0 or r.get('reset')
        new = frames if (first or anchor == 'guide') else frames - 1
        if not p.is_file() or p.stat().st_size == 0 or not r.get('preview_sha256'):
            probs.append('mp4 %d' % k)
        if '/stream115-s%08d/' % r['stream_seq'] not in r['path']:
            probs.append('dir %d' % k)
        if not first and r['predecessor_anchor_sha256'] != rows[k - 1]['anchor_sha256']:
            probs.append('chain %d' % k)
        if first or anchor == 'guide':
            if 'skip_first_frames' in r:
                probs.append('skip without an overlap frame %d' % k)
        elif r.get('skip_first_frames') != 1:
            probs.append('skip %d' % k)
        if (r.get('frames'), r.get('new_frames'), r.get('seconds'), r.get('anchor')) != \
                (frames, new, round(new / 24, 6), anchor):
            probs.append('labels %d %r' % (k, (r.get('frames'), r.get('new_frames'), r.get('seconds'), r.get('anchor'))))
        if 'border_to_centre_chroma_ratio' not in r or not r.get('last_frame_sha256') or \
                r.get('submit_to_anchor_ready') is None or type(r.get('sharpness_relative')) is not dict or \
                r.get('sharpness_first_frames_min') is None:
            probs.append('diag/timing/sharpness %d' % k)
        if anchor == 'mixed' and not first and r.get('frame_wait_s') is None:
            probs.append('frame wait %d' % k)
    return probs


def test_mixed49():
    e = Env('mixed49')
    e.start_fake('--decode-delay', '0.3', '--preview-delay', '0.2')
    cp = e.client('--max-chunks', '8', '--expect-anchor', 'mixed')
    rows, st = e.manifest(), e.stats()
    probs = manifest_problems(rows, 49, 'mixed')
    out = cp.stdout + cp.stderr
    check('M1 115 mixed/49 (default anchor): client qualification re-derived with the 115 gate, 8 chunks, exit 0, '
          'manifest labels, chain and sharpness intact',
          cp.returncode == 0 and len(rows) == 8 and not probs and st['stream_order'] == list(range(8)) and
          not st['refusals'] and 'client re-derivation passed' in out and st['qual_posts'] == 11,
          'rc=%d rows=%d probs=%s refusals=%s' % (cp.returncode, len(rows), probs[:4], st['refusals']))
    reuse = [st['reuse_text'][str(k)] for k in range(8)]
    check('M2 text reuse on by default; the next chunk is submitted before the previous decode record exists',
          reuse == expected_reuse(8) and st['submitted_before_prev_decode'] >= 6,
          'reuse=%s before_decode=%d' % (reuse, st['submitted_before_prev_decode']))
    recs = [e.receipt(k) for k in range(8)]
    ok = all(recs[k]['anchor_in']['frame']['sha256'] == e.decode(k - 1)['last_frame_sha256'] and
             recs[k]['anchor_in']['frame']['source_run_name'] == recs[k - 1]['run_name'] for k in range(1, 8))
    check('M3 every anchored mixed chunk used its predecessor\'s decoded frame; stage B waited for it '
          '(the decode overlapped text + stage A)',
          ok and recs[3]['anchor_out']['kind'] == 'mixed' and recs[3]['anchor_out']['bytes'] == 40960 and
          set(recs[3]['slot0_pin']) == {'A'} and any(w > 0.05 for w in st['frame_waits']),
          'ok=%s waits=%s' % (ok, st['frame_waits'][:8]))
    e.stop_fake()


def test_guide():
    for frames in (49, 97):
        e = Env('guide%d' % frames)
        e.start_fake('--anchor', 'guide', '--frames', str(frames), '--decode-delay', '0.1', '--preview-delay', '0.1')
        cp = e.client('--max-chunks', '5', '--expect-anchor', 'guide', '--expect-frames', str(frames))
        rows = e.manifest()
        probs = manifest_problems(rows, frames, 'guide')
        rec = e.receipt(2)
        check('G%d guide/%d: qualification + 5 chunks, every chunk delivers all %d frames with no skip, '
              '81,920-byte guide anchors, guide pins' % (1 if frames == 49 else 2, frames, frames),
              cp.returncode == 0 and len(rows) == 5 and not probs and [r['new_frames'] for r in rows] == [frames] * 5 and
              rec['anchor_out']['bytes'] == 81920 and set(rec['guide_pin']) == {'A', 'B'} and rec['slot0_pin'] is None,
              'rc=%d rows=%d probs=%s' % (cp.returncode, len(rows), probs[:4]))
        e.stop_fake()


def test_mixed97_and_ab_modes():
    e = Env('mixed97')
    e.start_fake('--frames', '97', '--phase', 'stream', '--decode-delay', '0.1', '--preview-delay', '0.1')
    cp = e.client('--skip-qualification', '--max-chunks', '4', '--expect-frames', '97')
    rows = e.manifest()
    probs = manifest_problems(rows, 97, 'mixed')
    check('N1 mixed/97: 97 then 96 new frames, skip_first_frames 1, sharpness of 8 frames',
          cp.returncode == 0 and len(rows) == 4 and not probs and [r['new_frames'] for r in rows] == [97, 96, 96, 96] and
          len(rows[1]['sharpness_relative']) == 8, 'rc=%d rows=%d probs=%s' % (cp.returncode, len(rows), probs[:4]))
    e.stop_fake()
    for anchor in ('latent', 'frame'):
        e = Env('ab-' + anchor)
        e.start_fake('--anchor', anchor, '--phase', 'stream', '--decode-delay', '0.05', '--preview-delay', '0.05')
        cp = e.client('--skip-qualification', '--max-chunks', '4', '--expect-anchor', anchor)
        rows = e.manifest()
        check('N2 A/B anchor %s on a 115 server streams 4 chunks with 115 manifest labels' % anchor,
              cp.returncode == 0 and len(rows) == 4 and not manifest_problems(rows, 49, anchor),
              'rc=%d rows=%d probs=%s' % (cp.returncode, len(rows), manifest_problems(rows, 49, anchor)[:3]))
        cp = e.client('--skip-qualification', '--max-chunks', '1', '--expect-anchor', 'mixed')
        check('N3 --expect-anchor mixed against a %s server refuses at preflight (exit 8)' % anchor,
              cp.returncode == 8 and 'anchor' in cp.stdout, 'rc=%d' % cp.returncode)
        e.stop_fake()


def test_qualification():
    for mode, label in (('fail', 'Q1 qualification fail -> exit 13, nothing streamed'),
                        ('lie', 'Q2 qualification lie (server says passed) -> client re-derivation fails, exit 13')):
        e = Env('qual-' + mode)
        e.start_fake('--qualification', mode, '--decode-delay', '0.05', '--preview-delay', '0.05')
        cp = e.client('--max-chunks', '3')
        out = cp.stdout + cp.stderr
        want = 'DID NOT PASS' if mode == 'fail' else 're-derivation of the verdict FAILED'
        check(label, cp.returncode == 13 and not e.manifest() and e.stats()['stream_order'] == [] and want in out,
              'rc=%d last=%s' % (cp.returncode, out.strip().splitlines()[-2:] if out.strip() else ''))
        e.stop_fake()


def test_decode_faults():
    e = Env('nodecode')
    e.start_fake('--phase', 'stream', '--decode-delay', '0.05', '--preview-delay', '0.05', '--no-decode-at', '2')
    t0 = time.time()
    cp = e.client('--skip-qualification', '--max-chunks', '6', '--save-wait', '2')
    check('D1 mixed: a decode record that never appears -> client exit 7 within the --save-wait bound, or the '
          'server halts the next chunk (its stage B never gets the frame); chunk 2 not manifested',
          cp.returncode in (2, 6, 7) and len(e.manifest()) == 2 and time.time() - t0 < 90,
          'rc=%d rows=%d' % (cp.returncode, len(e.manifest())))
    e.stop_fake()
    e = Env('decodefail')
    e.start_fake('--phase', 'stream', '--decode-delay', '0.05', '--preview-delay', '0.05', '--decode-fail-at', '3')
    cp = e.client('--skip-qualification', '--max-chunks', '8', '--save-wait', '5')
    rows = e.manifest()
    check('D2 decode thread failure (chunk 3) latches the server -> client exit 2 or 6, chunk 3 never manifested',
          cp.returncode in (2, 6) and len(rows) in (2, 3) and [r['stream_seq'] for r in rows] == list(range(len(rows))),
          'rc=%d rows=%d' % (cp.returncode, len(rows)))
    e.stop_fake()


def test_resets():
    e = Env('reset-every')
    e.start_fake('--phase', 'stream', '--decode-delay', '0.02', '--preview-delay', '0.02')
    cp = e.client('--skip-qualification', '--max-chunks', '10', '--reset-every-chunks', '3')
    rows, st = e.manifest(), e.stats()
    recs = [e.receipt(k) for k in range(10)]
    resets = [r['stream_seq'] for r in recs if r['reset']]
    skips = [row.get('skip_first_frames', 0) for row in rows]
    check('R1 --reset-every-chunks 3 on 115 mixed: resets at 3, 6, 9 (no frame wait, no skip), chain continues',
          cp.returncode == 0 and resets == [3, 6, 9] and skips == [0, 1, 1, 0, 1, 1, 0, 1, 1, 0] and
          all(recs[k]['anchor_in'] is None for k in (0, 3, 6, 9)) and
          all(recs[k]['anchor_in']['frame']['source_run_name'] == recs[k - 1]['run_name'] for k in (4, 5, 7, 8)) and
          not manifest_problems(rows, 49, 'mixed'), 'rc=%d resets=%s skips=%s' % (cp.returncode, resets, skips))
    e.stop_fake()


def test_anchor_faults():
    e = Env('corrupt')
    e.start_fake('--phase', 'stream', '--decode-delay', '0.02', '--preview-delay', '0.02', '--corrupt-anchor-at', '2')
    cp = e.client('--skip-qualification', '--max-chunks', '6')
    st = e.stats()
    check('A1 a corrupt (stale) anchor -> the server refuses stale-anchor, client exit 10, no retry',
          cp.returncode == 10 and st['refusals'].get('stale-anchor') == 1 and st['stream_order'] == [0, 1, 2],
          'rc=%d refusals=%s order=%s' % (cp.returncode, st['refusals'], st['stream_order']))
    e.stop_fake()


def test_cross_packet():
    e = Env('c114-vs-115')
    e.start_fake('--phase', 'stream')
    cp = e.client('--skip-qualification', '--max-chunks', '1', packet='114', contract=CONTRACT114, manifest=FAKE_SHA)
    check('X1 a 114 client with the 115 manifest sha refuses a 115 server at preflight, exit 8',
          cp.returncode == 8 and e.stats()['posts'] == 0, 'rc=%d' % cp.returncode)
    e.stop_fake()
    e = Env('c115-vs-114')
    e.start_fake('--phase', 'stream', fake='fake_comfy114.py', contract=CONTRACT114)
    cp = e.client('--skip-qualification', '--max-chunks', '1')
    check('X2 a 115 client against a 114 server refuses at preflight (manifest identity), exit 8',
          cp.returncode == 8, 'rc=%d' % cp.returncode)
    cp = e.client('--skip-qualification', '--max-chunks', '1', manifest=FAKE114_SHA)
    check('X3 a 115 client with the 114 manifest sha still refuses (needs a packet 115 server), exit 8',
          cp.returncode == 8 and 'needs a packet 115 server' in cp.stdout, 'rc=%d' % cp.returncode)
    e.stop_fake()
    cp = Env('expect').client('--max-chunks', '1', '--expect-anchor', 'guide', packet='114', contract=CONTRACT114,
                              manifest=FAKE114_SHA)
    check('X4 --packet 114 --expect-anchor guide is refused before contacting a server',
          cp.returncode != 0 and 'needs --packet 115' in (cp.stdout + cp.stderr), 'rc=%d' % cp.returncode)


for t in (test_mixed49, test_guide, test_mixed97_and_ab_modes, test_qualification, test_decode_faults, test_resets,
          test_anchor_faults, test_cross_packet):
    if args.only and args.only not in t.__name__:
        continue
    t()
bad = [r for r in RESULTS if not r[1]]
print('\n%d/%d passed; work in %s' % (len(RESULTS) - len(bad), len(RESULTS), TMP))
sys.exit(1 if bad else 0)
