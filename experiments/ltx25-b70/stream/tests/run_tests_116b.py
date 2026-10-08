#!/usr/bin/env python3
"""Tests of ltx_continuation_client.py --packet 116b against fake_comfy116.py in 116b mode (--contract-dir of
recovery/20261008-continuation116b-stream). CPU only, port 18191; never 8188.

    /home/steve/.venvs/ltx25-baseline/bin/python -B tests/run_tests_116b.py [--tmp DIR] [--port 18191] [--only NAME]

Packet 116b is packet 116 for the client except the string packet id '116b', the stream116b- names and its
own sealed contract module: qualification re-derivation (frame, decoder graph 1), streaming lines with
stream116b names, --expect-decoder-graph, and 116 / 116b clients refusing each other's servers.
"""
import argparse, hashlib, json, signal, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
CLIENT = HERE.parent / 'ltx_continuation_client.py'
CONTRACT = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation116b-stream')
CONTRACT116 = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation116-stream')
CONTRACT115 = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation115-stream')
CONTRACT114 = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation114-stream')
CONTRACT113 = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation113-stream')
FAKE_SHA = hashlib.sha256(b'fake-packet-116b-manifest').hexdigest()    # fake_comfy116 116b default
FAKE116_SHA = hashlib.sha256(b'fake-packet-116-manifest').hexdigest()  # fake_comfy116 116 default
FAKE115_SHA = hashlib.sha256(b'fake-packet-115-manifest').hexdigest()  # fake_comfy115 default
FAKE114_SHA = hashlib.sha256(b'fake-packet-114-manifest').hexdigest()  # fake_comfy114 default
FAKE113_SHA = 'a23dbc946d156df70c3e61134dc3231b147817c5cb110a015f84c8f020f7f28b'   # fake_comfy113 default
PY = sys.executable

ap = argparse.ArgumentParser()
ap.add_argument('--tmp', type=Path)
ap.add_argument('--port', type=int, default=18191)
ap.add_argument('--only')
args = ap.parse_args()
assert args.port != 8188, 'never the live port'
TMP = Path(tempfile.mkdtemp(prefix='ltx-c116b-test-', dir=str(args.tmp) if args.tmp else None))
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
        self.packet = '116b'
        self.refs = self.dir / 'refs-empty.json'          # no variant: the fake's outputs match no real run
        self.refs.write_text(json.dumps({'schema': 'ltx.stream116.reference-frame-hashes.v1', 'variants': {}}))

    def start_fake(self, *extra, fake='fake_comfy116.py', contract=CONTRACT):
        ready = self.root / ('fake115-ready' if '115' in fake else 'fake116-ready')
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

    def client(self, *extra, packet='116b', contract=CONTRACT, manifest=FAKE_SHA, timeout=300, refs=True):
        cmd = [PY, '-B', str(CLIENT), '--work-dir', str(self.work), '--root', str(self.root),
               '--port', str(args.port), '--contract-dir', str(contract), '--poll', '0.05',
               '--min-free-gib', '1', '--scenes', str(self.scenes_file), '--base-seed', str(BASE_SEED),
               '--packet', packet]
        if manifest:
            cmd += ['--manifest-sha256', manifest]
        if refs and packet in ('116', '116b'):
            cmd += ['--reference-hashes', str(self.refs)]
        cp = subprocess.run(cmd + list(extra), capture_output=True, text=True, timeout=timeout)
        (self.work / ('client-%d.log' % time.time_ns())).write_text(cp.stdout + cp.stderr)
        return cp

    def manifest(self):
        p = self.work / 'manifest.jsonl'
        return [json.loads(x) for x in p.read_text().splitlines()] if p.is_file() else []

    def stats(self):
        return json.loads((self.root / 'fake116-stats.json').read_text())

    def run_dir(self):
        return next(p for p in self.root.glob('encoder-server-continuation-stream-116b-*') if '.old' not in p.name)

    def receipt(self, seq):
        return json.loads((self.run_dir() / 'receipts' / ('receipt-stream116b-s%08d.json' % seq)).read_text())

    def qdecode(self, name):
        return json.loads((self.run_dir() / 'receipts' / ('decode-%s.json' % name)).read_text())

    def decode(self, seq):
        return json.loads((self.run_dir() / 'receipts' / ('decode-stream116b-s%08d.json' % seq)).read_text())


def manifest_problems(rows, frames, anchor, dg=1):
    probs = []
    for k, r in enumerate(rows):
        p = Path(r['path'])
        first = k == 0 or r.get('reset')
        new = frames if (first or anchor == 'guide') else frames - 1
        if not p.is_file() or p.stat().st_size == 0 or not r.get('preview_sha256'):
            probs.append('mp4 %d' % k)
        if '/stream116b-s%08d/' % r['stream_seq'] not in r['path']:
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
            probs.append('labels %d' % k)
        if 'border_to_centre_chroma_ratio' not in r or not r.get('last_frame_sha256') or \
                r.get('submit_to_anchor_ready') is None or type(r.get('sharpness_relative')) is not dict or \
                r.get('sharpness_first_frames_min') is None:
            probs.append('diag/timing/sharpness %d' % k)
        if (r.get('decoder_graph'), r.get('decoder_mode')) != (dg, 'graph' if dg else 'eager') or \
                r.get('video_decode_s') is None:
            probs.append('decoder %d %r' % (k, (r.get('decoder_graph'), r.get('decoder_mode'))))
        if anchor == 'frame' and r.get('decode_in_chain') is None:
            probs.append('decode_in_chain %d' % k)
        if anchor == 'mixed' and not first and r.get('frame_wait_s') is None:
            probs.append('frame wait %d' % k)
    return probs


def test_frame_dg1():
    e = Env('b-frame49-dg1')
    e.start_fake('--decode-delay', '0.1', '--audio-delay', '0.2', '--preview-delay', '0.05')
    cp = e.client('--max-chunks', '6', '--expect-anchor', 'frame', '--expect-decoder-graph', '1')
    rows, st = e.manifest(), e.stats()
    probs = manifest_problems(rows, 49, 'frame', 1)
    out = cp.stdout + cp.stderr
    check('B1 116b frame/49 dg1: qualification re-derived with the 116 gate, 6 chunks with stream116b names, exit 0',
          cp.returncode == 0 and len(rows) == 6 and not probs and 'client re-derivation passed' in out and
          st['qual_posts'] == 11 and all('/stream116b-s' in r['path'] and r['run_name'].startswith('stream116b-s')
                                         for r in rows),
          'rc=%d rows=%d probs=%s last=%s' % (cp.returncode, len(rows), probs[:4], out.strip().splitlines()[-1:]))
    recs = [e.receipt(k) for k in range(6)]
    check('B2 116a hand-off on 116b: frame receipts commit before their decode records; status packet 116b',
          st['receipt_before_record'] >= 4 and all(r['decode']['state'] == 'video_done' for r in recs) and
          json.loads(urllib.request.urlopen('http://127.0.0.1:%d/ltx-stream/status' % args.port).read())['packet']
          == '116b', 'before_record=%d' % st['receipt_before_record'])
    e.stop_fake()


def test_dg0_and_expectations():
    e = Env('b-dg0')
    e.start_fake('--phase', 'stream', '--decoder-graph', '0', '--decode-delay', '0.02', '--preview-delay', '0.02')
    cp = e.client('--skip-qualification', '--max-chunks', '1', '--expect-decoder-graph', '1')
    check('B3 --expect-decoder-graph 1 against a 116b decoder_graph 0 server refuses at preflight (exit 8)',
          cp.returncode == 8 and e.stats()['posts'] == 0, 'rc=%d' % cp.returncode)
    cp = e.client('--skip-qualification', '--max-chunks', '3', '--expect-decoder-graph', '0')
    rows = e.manifest()
    check('B4 116b decoder_graph 0 streams 3 chunks with eager decoder lines',
          cp.returncode == 0 and len(rows) == 3 and not manifest_problems(rows, 49, 'frame', 0),
          'rc=%d probs=%s' % (cp.returncode, manifest_problems(rows, 49, 'frame', 0)[:3]))
    e.stop_fake()


def test_cross_packet():
    e = Env('b-c116-vs-116b')
    e.start_fake('--phase', 'stream')
    cp = e.client('--skip-qualification', '--max-chunks', '1', packet='116', contract=CONTRACT116, manifest=FAKE_SHA)
    check('B5 a 116 client (116b manifest sha) refuses a 116b server at preflight, exit 8, nothing posted',
          cp.returncode == 8 and e.stats()['posts'] == 0 and 'needs a packet 116 server' in cp.stdout,
          'rc=%d' % cp.returncode)
    e.stop_fake()
    e = Env('b-c116b-vs-116')
    e.start_fake('--phase', 'stream', contract=CONTRACT116)
    cp = e.client('--skip-qualification', '--max-chunks', '1')
    check('B6 a 116b client against a 116 server refuses at preflight (manifest identity), exit 8',
          cp.returncode == 8 and e.stats()['posts'] == 0, 'rc=%d' % cp.returncode)
    cp = e.client('--skip-qualification', '--max-chunks', '1', manifest=FAKE116_SHA)
    check('B7 a 116b client with the 116 manifest sha still refuses (needs a packet 116b server), exit 8',
          cp.returncode == 8 and 'needs a packet 116b server' in cp.stdout, 'rc=%d' % cp.returncode)
    e.stop_fake()
    cp = Env('b-pins').client('--max-chunks', '1', contract=CONTRACT116)
    check('B8 --packet 116b with the 116 contract module is refused (module pin), exit 8',
          cp.returncode == 8 and 'differs from the sealed packet module' in cp.stdout, 'rc=%d' % cp.returncode)


for t in (test_frame_dg1, test_dg0_and_expectations, test_cross_packet):
    if args.only and args.only not in t.__name__:
        continue
    t()
bad = [r for r in RESULTS if not r[1]]
print('\n%d/%d passed; work in %s' % (len(RESULTS) - len(bad), len(RESULTS), TMP))
sys.exit(1 if bad else 0)
