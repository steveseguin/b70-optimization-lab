#!/usr/bin/env python3
"""Tests of ltx_continuation_client.py --packet 114 against fake_comfy114.py (CPU only, port 18189; never 8188).

    /home/steve/.venvs/ltx25-baseline/bin/python -B tests/run_tests_114.py [--tmp DIR] [--port 18189] [--only NAME]

Covers what packet 114 changes for the client: the anchor mode (latent / frame) and chunk length
(49 / 97) in every request, text reuse on by default, the decode record that follows the receipt
(GET /ltx-stream/decode/<run>, bounded by --save-wait, default 30 s on 114), the 114 qualification
re-derivation over receipts + decode records + captures, the 114 manifest labels, resets, and that
a 113 client and a 114 client each refuse the other packet's server at preflight.
"""
import argparse, hashlib, json, signal, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
CLIENT = HERE.parent / 'ltx_continuation_client.py'
CONTRACT = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation114-stream')
CONTRACT113 = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation113-stream')
FAKE_SHA = hashlib.sha256(b'fake-packet-114-manifest').hexdigest()     # fake_comfy114 default
FAKE113_SHA = 'a23dbc946d156df70c3e61134dc3231b147817c5cb110a015f84c8f020f7f28b'   # fake_comfy113 default
PY = sys.executable

ap = argparse.ArgumentParser()
ap.add_argument('--tmp', type=Path)
ap.add_argument('--port', type=int, default=18189)
ap.add_argument('--only')
args = ap.parse_args()
assert args.port != 8188, 'never the live port'
TMP = Path(tempfile.mkdtemp(prefix='ltx-c114-test-', dir=str(args.tmp) if args.tmp else None))
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
        self.packet = '114'

    def start_fake(self, *extra, fake='fake_comfy114.py', contract=CONTRACT):
        ready = self.root / ('fake113-ready' if '113' in fake else 'fake114-ready')
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

    def client(self, *extra, packet='114', contract=CONTRACT, manifest=FAKE_SHA, timeout=300):
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
        return json.loads((self.root / 'fake114-stats.json').read_text())

    def run_dir(self):
        return next(p for p in self.root.glob('encoder-server-continuation-stream-114-*') if '.old' not in p.name)

    def receipt(self, seq):
        return json.loads((self.run_dir() / 'receipts' / ('receipt-stream114-s%08d.json' % seq)).read_text())

    def decode(self, seq):
        return json.loads((self.run_dir() / 'receipts' / ('decode-stream114-s%08d.json' % seq)).read_text())


def manifest_problems(rows, frames, anchor):
    probs = []
    for k, r in enumerate(rows):
        p = Path(r['path'])
        first = k == 0 or r.get('reset')
        new = frames if first else frames - 1
        if not p.is_file() or p.stat().st_size == 0 or not r.get('preview_sha256'):
            probs.append('mp4 %d' % k)
        if '/stream114-s%08d/' % r['stream_seq'] not in r['path']:
            probs.append('dir %d' % k)
        if first:
            if 'skip_first_frames' in r:
                probs.append('skip on unanchored %d' % k)
        elif r.get('skip_first_frames') != 1 or r['predecessor_anchor_sha256'] != rows[k - 1]['anchor_sha256']:
            probs.append('chain %d' % k)
        if (r.get('frames'), r.get('new_frames'), r.get('seconds'), r.get('anchor')) != \
                (frames, new, round(new / 24, 6), anchor):
            probs.append('labels %d %r' % (k, (r.get('frames'), r.get('new_frames'), r.get('seconds'), r.get('anchor'))))
        if 'border_to_centre_chroma_ratio' not in r or r.get('border_mean_chroma') is None or \
                not r.get('last_frame_sha256') or r.get('submit_to_anchor_ready') is None:
            probs.append('diag/timing %d' % k)
    return probs


def test_latent49():
    e = Env('latent49')
    e.start_fake('--decode-delay', '0.3', '--preview-delay', '0.2')
    cp = e.client('--max-chunks', '8')
    rows, st = e.manifest(), e.stats()
    probs = manifest_problems(rows, 49, 'latent')
    out = cp.stdout + cp.stderr
    check('L1 114 latent/49: client qualification (11 requests + verdict re-derived with decode records), 8 chunks, '
          'exit 0, manifest labels and chain intact',
          cp.returncode == 0 and len(rows) == 8 and not probs and st['stream_order'] == list(range(8)) and
          not st['refusals'] and 'client re-derivation passed' in out and st['qual_posts'] == 11,
          'rc=%d rows=%d probs=%s refusals=%s' % (cp.returncode, len(rows), probs[:4], st['refusals']))
    reuse = [st['reuse_text'][str(k)] for k in range(8)]
    check('L2 text reuse on by default: reuse_text=1 exactly on same-prompt anchored chunks, accepted by the server',
          reuse == expected_reuse(8) and [r['reuse_text'] for r in rows] == expected_reuse(8),
          'reuse=%s want=%s' % (reuse, expected_reuse(8)))
    check('L3 the next chunk is submitted before the previous decode record and preview exist (off the chain)',
          st['submitted_before_prev_decode'] >= 6 and st['submitted_before_prev_preview'] >= 6,
          'before_decode=%d before_preview=%d' % (st['submitted_before_prev_decode'], st['submitted_before_prev_preview']))
    rec = e.receipt(3)
    check('L4 receipts carry the three latents and a 40,960-byte latent anchor; decode records arrive in order',
          set(rec['tensors']) == {'video_latent', 'audio_latent', 'stage_a_latent'} and
          rec['anchor_out']['bytes'] == 40960 and rec['anchor_out']['kind'] == 'latent' and
          rec['decode']['state'] == 'queued' and
          [e.decode(k)['sequence'] for k in range(8)] == sorted(e.decode(k)['sequence'] for k in range(8)) and
          st['drained_before_gated'] == 6, 'anchor_out=%s' % rec['anchor_out'].get('bytes'))
    cp2 = e.client('--max-chunks', '2', '--skip-qualification')
    rows = e.manifest()
    check('L5 resume on the same 114 server continues the chain (decode records of the new chunks verified)',
          cp2.returncode == 0 and len(rows) == 10 and e.stats()['stream_order'] == list(range(10)) and
          not manifest_problems(rows, 49, 'latent'), 'rc=%d rows=%d' % (cp2.returncode, len(rows)))
    e.stop_fake()


def test_latent97():
    e = Env('latent97')
    e.start_fake('--frames', '97', '--phase', 'stream', '--decode-delay', '0.1', '--preview-delay', '0.1')
    cp = e.client('--skip-qualification', '--max-chunks', '4', '--expect-frames', '97', '--expect-anchor', 'latent')
    rows = e.manifest()
    probs = manifest_problems(rows, 97, 'latent')
    check('L6 97 frames: chunk 0 delivers 97 frames (97/24 s), later chunks 96 new frames, 4.0 s, skip_first_frames 1',
          cp.returncode == 0 and len(rows) == 4 and not probs and [r['new_frames'] for r in rows] == [97, 96, 96, 96] and
          [r['seconds'] for r in rows] == [round(97 / 24, 6), 4.0, 4.0, 4.0] and
          e.decode(1)['tensors']['images']['shape'] == [97, 256, 256, 3],
          'rc=%d rows=%d probs=%s' % (cp.returncode, len(rows), probs[:4]))
    e.stop_fake()


def test_frame_anchor():
    e = Env('frame')
    e.start_fake('--anchor', 'frame', '--decode-delay', '0.1', '--preview-delay', '0.1')
    cp = e.client('--max-chunks', '5', '--expect-anchor', 'frame')
    rows = e.manifest()
    probs = manifest_problems(rows, 49, 'frame')
    recs = [e.receipt(k) for k in range(5)]
    ok = all(r['anchor_out']['kind'] == 'frame' and r['anchor_out']['bytes'] == 786432 and
             r['decode']['state'] == 'done' and r['anchor_out']['sha256'] == e.decode(k)['last_frame_sha256']
             for k, r in enumerate(recs))
    check('F1 frame anchor: qualification + 5 chunks, 786,432-byte anchors equal to the decoded last frame, exit 0',
          cp.returncode == 0 and len(rows) == 5 and not probs and ok,
          'rc=%d rows=%d probs=%s ok=%s' % (cp.returncode, len(rows), probs[:4], ok))
    cp = e.client('--skip-qualification', '--max-chunks', '1', '--expect-anchor', 'latent')
    check('F2 --expect-anchor latent against a frame-anchor server refuses at preflight (exit 8)',
          cp.returncode == 8 and 'anchor' in cp.stdout, 'rc=%d' % cp.returncode)
    e.stop_fake()


def test_text_reuse_off():
    e = Env('reuse-off')
    e.start_fake('--text-reuse', '0', '--phase', 'stream', '--decode-delay', '0.05', '--preview-delay', '0.05')
    cp = e.client('--skip-qualification', '--max-chunks', '5')
    st = e.stats()
    check('T1 a text_reuse=0 server: every chunk sends reuse_text=0 and is admitted',
          cp.returncode == 0 and [st['reuse_text'][str(k)] for k in range(5)] == [0] * 5 and not st['refusals'],
          'rc=%d refusals=%s' % (cp.returncode, st['refusals']))
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
    wall = time.time() - t0
    check('D1 a decode record that never appears -> exit 7 within the --save-wait bound; chunk 2 not manifested',
          cp.returncode == 7 and len(e.manifest()) == 2 and wall < 30 and 'decode record' in cp.stdout,
          'rc=%d rows=%d %.1fs' % (cp.returncode, len(e.manifest()), wall))
    e.stop_fake()
    e = Env('decodefail')
    e.start_fake('--phase', 'stream', '--decode-delay', '0.05', '--preview-delay', '0.05', '--decode-fail-at', '3')
    cp = e.client('--skip-qualification', '--max-chunks', '8', '--save-wait', '5')
    rows = e.manifest()
    check('D2 decode thread failure (chunk 3) latches the server -> client exit 2 (halted), chunk 3 never manifested',
          cp.returncode == 2 and len(rows) in (2, 3) and [r['stream_seq'] for r in rows] == list(range(len(rows))) and
          'DECODE FAILED' in cp.stdout, 'rc=%d rows=%d' % (cp.returncode, len(rows)))
    e.stop_fake()
    e = Env('nopreview')
    e.start_fake('--phase', 'stream', '--decode-delay', '0.05', '--preview-delay', '0.05', '--no-preview-at', '2')
    t0 = time.time()
    cp = e.client('--skip-qualification', '--max-chunks', '6', '--save-wait', '2')
    check('P1 a preview record that never appears -> exit 7 within the bound; chunk 2 not manifested',
          cp.returncode == 7 and len(e.manifest()) == 2 and time.time() - t0 < 30,
          'rc=%d rows=%d' % (cp.returncode, len(e.manifest())))
    e.stop_fake()
    e = Env('previewfail')
    e.start_fake('--phase', 'stream', '--decode-delay', '0.05', '--preview-delay', '0.05', '--preview-fail-at', '3')
    cp = e.client('--skip-qualification', '--max-chunks', '8', '--save-wait', '5')
    check('P2 a preview write failure latches the server -> client exit 6 or 2, rows stop at 3',
          cp.returncode in (2, 6) and len(e.manifest()) == 3, 'rc=%d rows=%d' % (cp.returncode, len(e.manifest())))
    e.stop_fake()


def test_default_save_wait():
    e = Env('savewait')
    e.start_fake('--phase', 'stream', '--decode-delay', '6', '--preview-delay', '5.5')
    t0 = time.time()
    cp = e.client('--skip-qualification', '--max-chunks', '1')
    check('S1 default 114 --save-wait (30 s) covers a decode + preview lag of 11.5 s (beyond the 10 s 113 default)',
          cp.returncode == 0 and len(e.manifest()) == 1, 'rc=%d rows=%d %.1fs' % (cp.returncode, len(e.manifest()),
                                                                                 time.time() - t0))
    e.stop_fake()


def test_resets():
    e = Env('reset-every')
    e.start_fake('--phase', 'stream', '--decode-delay', '0.02', '--preview-delay', '0.02')
    cp = e.client('--skip-qualification', '--max-chunks', '10', '--reset-every-chunks', '3')
    rows, st = e.manifest(), e.stats()
    recs = [e.receipt(k) for k in range(10)]
    resets = [r['stream_seq'] for r in recs if r['reset']]
    ok = all((r['anchor_in'] is None) == (r['stream_seq'] == 0 or r['reset']) for r in recs)
    skips = [row.get('skip_first_frames', 0) for row in rows]
    reuse = [st['reuse_text'][str(k)] for k in range(10)]
    check('R1 --reset-every-chunks 3 on 114: resets at 3, 6, 9; unanchored, reuse_text 0, 49 new frames, no skip',
          cp.returncode == 0 and resets == [3, 6, 9] and st['resets'] == [3, 6, 9] and ok and
          skips == [0, 1, 1, 0, 1, 1, 0, 1, 1, 0] and reuse == expected_reuse(10, resets=(3, 6, 9)) and
          [row['new_frames'] for row in rows] == [49, 48, 48, 49, 48, 48, 49, 48, 48, 49] and
          not manifest_problems(rows, 49, 'latent'),
          'rc=%d resets=%s skips=%s reuse=%s' % (cp.returncode, resets, skips, reuse))
    check('R2 after a reset the chain continues from the reset chunk\'s anchor',
          all(recs[k]['anchor_in']['sha256'] == recs[k - 1]['anchor_out']['sha256'] for k in (4, 5, 7, 8)))
    e.stop_fake()
    e = Env('reset-scene')
    e.start_fake('--phase', 'stream', '--decode-delay', '0.02', '--preview-delay', '0.02')
    cp = e.client('--skip-qualification', '--max-chunks', '11', '--reset-on-scene-change')
    recs = [e.receipt(k) for k in range(11)]
    resets = [r['stream_seq'] for r in recs if r['reset']]
    check('R3 --reset-on-scene-change on 114: resets exactly at the scene boundaries 3, 8, 10',
          cp.returncode == 0 and resets == [3, 8, 10], 'rc=%d resets=%s' % (cp.returncode, resets))
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
    e = Env('corrupt-receipt')
    e.start_fake('--phase', 'stream', '--decode-delay', '0.02', '--preview-delay', '0.02', '--corrupt-receipt-at', '2')
    cp = e.client('--skip-qualification', '--max-chunks', '6')
    check('A2 a receipt whose anchor differs from the status chain -> exit 12 before any further submit',
          cp.returncode == 12 and e.stats()['stream_order'] == [0, 1, 2], 'rc=%d' % cp.returncode)
    e.stop_fake()


def test_cross_packet():
    e = Env('c113-vs-114')
    e.start_fake('--phase', 'stream')
    cp = e.client('--skip-qualification', '--max-chunks', '1', packet='113', contract=CONTRACT113, manifest=None)
    check('X1 a 113 client against a 114 server refuses at preflight (manifest identity), exit 8',
          cp.returncode == 8 and e.stats()['posts'] == 0, 'rc=%d' % cp.returncode)
    cp = e.client('--skip-qualification', '--max-chunks', '1', packet='113', contract=CONTRACT113, manifest=FAKE_SHA)
    check('X2 a 113 client with the 114 manifest sha still refuses (packet / qualification_id), exit 8',
          cp.returncode == 8 and 'packet 113' in cp.stdout and e.stats()['posts'] == 0, 'rc=%d' % cp.returncode)
    e.stop_fake()
    e = Env('c114-vs-113')
    e.start_fake('--phase', 'stream', fake='fake_comfy113.py', contract=CONTRACT113)
    cp = e.client('--skip-qualification', '--max-chunks', '1')
    check('X3 a 114 client against a 113 server refuses at preflight (manifest identity), exit 8',
          cp.returncode == 8, 'rc=%d' % cp.returncode)
    cp = e.client('--skip-qualification', '--max-chunks', '1', manifest=FAKE113_SHA)
    check('X4 a 114 client with the 113 manifest sha still refuses (needs a packet 114 server), exit 8',
          cp.returncode == 8 and 'needs a packet 114 server' in cp.stdout, 'rc=%d' % cp.returncode)
    e.stop_fake()
    e = Env('sealed-default')
    e.start_fake('--phase', 'stream')
    cp = e.client('--max-chunks', '1', manifest=None)
    check('X5 sealed packet 114 default manifest refuses a fake manifest (exit 8, nothing posted)',
          cp.returncode == 8 and 'runtime_manifest_sha256' in cp.stdout and e.stats()['posts'] == 0,
          'rc=%d' % cp.returncode)
    e.stop_fake()


for t in (test_latent49, test_latent97, test_frame_anchor, test_text_reuse_off, test_qualification,
          test_decode_faults, test_default_save_wait, test_resets, test_anchor_faults, test_cross_packet):
    if args.only and args.only not in t.__name__:
        continue
    t()
bad = [r for r in RESULTS if not r[1]]
print('\n%d/%d passed; work in %s' % (len(RESULTS) - len(bad), len(RESULTS), TMP))
sys.exit(1 if bad else 0)
