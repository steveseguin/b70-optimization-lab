#!/usr/bin/env python3
"""Tests of ltx_continuation_client.py --packet 117 against fake_comfy117.py (--contract-dir of
recovery/20261008-continuation117-stream). CPU only, port 18192; never 8188.

    /home/steve/.venvs/ltx25-baseline/bin/python -B tests/run_tests_117.py [--tmp DIR] [--port 18192] [--only NAME]

Packet 117 is packet 116b for the client plus the three frame-anchor levers (status anchor_decode /
bencode_overlap / prep_ahead, part of every request and of the qualification id) and 121-frame chunks:
qualification re-derivation with every lever combination that changes the request or the gate, streaming
lines with stream117 names at 97 and 121 frames, the --expect-* lever flags, 116b / 117 clients refusing each
other's servers, and a verdict whose lever check fails being refused.
"""
import argparse, hashlib, json, signal, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
CLIENT = HERE.parent / 'ltx_continuation_client.py'
CONTRACT = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation117-stream')
CONTRACT116B = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation116b-stream')
CONTRACT116 = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation116-stream')
CONTRACT115 = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation115-stream')
CONTRACT114 = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation114-stream')
CONTRACT113 = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation113-stream')
FAKE_SHA = hashlib.sha256(b'fake-packet-117-manifest').hexdigest()     # fake_comfy117 default
FAKE116B_SHA = hashlib.sha256(b'fake-packet-116b-manifest').hexdigest()  # fake_comfy116 116b default
FAKE116_SHA = hashlib.sha256(b'fake-packet-116-manifest').hexdigest()  # fake_comfy116 116 default
FAKE115_SHA = hashlib.sha256(b'fake-packet-115-manifest').hexdigest()  # fake_comfy115 default
FAKE114_SHA = hashlib.sha256(b'fake-packet-114-manifest').hexdigest()  # fake_comfy114 default
FAKE113_SHA = 'a23dbc946d156df70c3e61134dc3231b147817c5cb110a015f84c8f020f7f28b'   # fake_comfy113 default
PY = sys.executable

ap = argparse.ArgumentParser()
ap.add_argument('--tmp', type=Path)
ap.add_argument('--port', type=int, default=18192)
ap.add_argument('--only')
args = ap.parse_args()
assert args.port != 8188, 'never the live port'
TMP = Path(tempfile.mkdtemp(prefix='ltx-c117-test-', dir=str(args.tmp) if args.tmp else None))
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
        self.packet = '117'
        self.refs = self.dir / 'refs-empty.json'          # no variant: the fake's outputs match no real run
        self.refs.write_text(json.dumps({'schema': 'ltx.stream116.reference-frame-hashes.v1', 'variants': {}}))

    def start_fake(self, *extra, fake='fake_comfy117.py', contract=CONTRACT):
        ready = self.root / ('fake117-ready' if '117' in fake else 'fake116-ready')
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

    def client(self, *extra, packet='117', contract=CONTRACT, manifest=FAKE_SHA, timeout=300, refs=True):
        cmd = [PY, '-B', str(CLIENT), '--work-dir', str(self.work), '--root', str(self.root),
               '--port', str(args.port), '--contract-dir', str(contract), '--poll', '0.05',
               '--min-free-gib', '1', '--scenes', str(self.scenes_file), '--base-seed', str(BASE_SEED),
               '--packet', packet]
        if manifest:
            cmd += ['--manifest-sha256', manifest]
        if refs and packet in ('116', '116b', '117'):
            cmd += ['--reference-hashes', str(self.refs)]
        cp = subprocess.run(cmd + list(extra), capture_output=True, text=True, timeout=timeout)
        (self.work / ('client-%d.log' % time.time_ns())).write_text(cp.stdout + cp.stderr)
        return cp

    def manifest(self):
        p = self.work / 'manifest.jsonl'
        return [json.loads(x) for x in p.read_text().splitlines()] if p.is_file() else []

    def stats(self):
        name = 'fake117-stats.json' if (self.root / 'fake117-stats.json').is_file() else 'fake116-stats.json'
        return json.loads((self.root / name).read_text())

    def run_dir(self):
        return next(p for p in self.root.glob('encoder-server-continuation-stream-117-*') if '.old' not in p.name)

    def receipt(self, seq):
        return json.loads((self.run_dir() / 'receipts' / ('receipt-stream117-s%08d.json' % seq)).read_text())

    def qdecode(self, name):
        return json.loads((self.run_dir() / 'receipts' / ('decode-%s.json' % name)).read_text())

    def decode(self, seq):
        return json.loads((self.run_dir() / 'receipts' / ('decode-stream117-s%08d.json' % seq)).read_text())



def manifest_problems(rows, frames, levers, dg=1):
    probs = []
    ad, bo, pa = levers
    for k, r in enumerate(rows):
        p = Path(r['path'])
        first = k == 0 or r.get('reset')
        new = frames if first else frames - 1
        if not p.is_file() or p.stat().st_size == 0 or not r.get('preview_sha256'):
            probs.append('mp4 %d' % k)
        if '/stream117-s%08d/' % r['stream_seq'] not in r['path'] or not r['run_name'].startswith('stream117-s'):
            probs.append('dir %d' % k)
        if not first and r['predecessor_anchor_sha256'] != rows[k - 1]['anchor_sha256']:
            probs.append('chain %d' % k)
        if first:
            if 'skip_first_frames' in r:
                probs.append('skip without an overlap frame %d' % k)
        elif r.get('skip_first_frames') != 1:
            probs.append('skip %d' % k)
        if (r.get('frames'), r.get('new_frames'), r.get('seconds'), r.get('anchor')) != \
                (frames, new, round(new / 24, 6), 'frame'):
            probs.append('labels %d %r' % (k, (r.get('frames'), r.get('new_frames'), r.get('seconds'))))
        if (r.get('decoder_graph'), r.get('decoder_mode')) != (dg, 'graph' if dg else 'eager') or \
                r.get('decode_in_chain') is None:
            probs.append('decoder %d' % k)
        if r.get('levers') != {'anchor_decode': ad, 'bencode_overlap': bo, 'prep_ahead': pa} or \
                r.get('anchor_decode_mode') != ad or r.get('anchor_decode_in_chain') is None or \
                r.get('cone_equal') is not (True if ad == 'cone' else None) or \
                (ad == 'cone') != (r.get('display_decode_s') is not None):
            probs.append('levers %d %r' % (k, (r.get('levers'), r.get('anchor_decode_mode'), r.get('cone_equal'))))
        want = None if first else {'A': 'precomputed' if pa else 'native', 'B': 'precomputed' if bo else 'native'}
        if r.get('conditioning_sources') != want:
            probs.append('sources %d %r' % (k, r.get('conditioning_sources')))
    return probs


def last_log(cp):
    return (cp.stdout + cp.stderr).strip().splitlines()[-1:]


def test_all_levers_97():
    e = Env('c-all-97')
    e.start_fake('--frames', '97', '--decode-delay', '0.05', '--audio-delay', '0.1', '--preview-delay', '0.05')
    cp = e.client('--max-chunks', '5', '--expect-frames', '97', '--expect-anchor', 'frame',
                  '--expect-decoder-graph', '1', '--expect-anchor-decode', 'cone', '--expect-bencode-overlap', '1',
                  '--expect-prep-ahead', '1')
    rows, st = e.manifest(), e.stats()
    probs = manifest_problems(rows, 97, ('cone', 1, 1))
    out = cp.stdout + cp.stderr
    check('C1 117 frame/97 cone+overlap+prep: qualification re-derived with the 117 gate, 5 stream117 chunks, exit 0',
          cp.returncode == 0 and len(rows) == 5 and not probs and 'client re-derivation passed' in out and
          st['qual_posts'] == 11, 'rc=%d rows=%d probs=%s last=%s' % (cp.returncode, len(rows), probs[:4], last_log(cp)))
    check('C2 stage buckets show anchor-decode(chain), the off-chain display decode, precompute waits and the go wait',
          all(k in out for k in ('anchor-decode(chain)', 'display-decode(off-chain)', 'precompute-A-wait',
                                 'precompute-B-wait', 'go-wait(off-chain)')) and 'video-decode(chain)' not in out,
          [ln for ln in out.splitlines() if 'anchor-decode' in ln][:1])
    recs = [e.receipt(k) for k in range(5)]
    status = json.loads(urllib.request.urlopen('http://127.0.0.1:%d/ltx-stream/status' % args.port).read())
    check('C3 receipts carry the levers; status packet 117 with the lever features',
          all(r['levers'] == {'anchor_decode': 'cone', 'bencode_overlap': 1, 'prep_ahead': 1} for r in recs) and
          status['packet'] == 117 and status['features']['cone_anchor_decode'] is True and
          status['features']['chunk_121'] is True, str(status.get('features')))
    e.stop_fake()


def test_121():
    e = Env('c-121')
    e.start_fake('--frames', '121', '--decode-delay', '0.03', '--audio-delay', '0.05', '--preview-delay', '0.03')
    cp = e.client('--max-chunks', '4', '--expect-frames', '121')
    rows = e.manifest()
    probs = manifest_problems(rows, 121, ('cone', 1, 1))
    check('C4 117 frame/121: qualification + 4 chunks; anchored lines deliver 120 new frames (5.0 s), exit 0',
          cp.returncode == 0 and len(rows) == 4 and not probs and [r['new_frames'] for r in rows] == [121, 120, 120, 120]
          and rows[1]['seconds'] == 5.0, 'rc=%d probs=%s last=%s' % (cp.returncode, probs[:4], last_log(cp)))
    e.stop_fake()


def test_lever_combinations():
    for i, (ad, bo, pa) in enumerate((('full', 0, 0), ('cone', 0, 0), ('full', 1, 0), ('full', 0, 1),
                                       ('cone', 1, 0))):
        e = Env('c-levers-%d' % i)
        e.start_fake('--anchor-decode', ad, '--bencode-overlap', str(bo), '--prep-ahead', str(pa),
                     '--decode-delay', '0.02', '--audio-delay', '0.03', '--preview-delay', '0.02')
        cp = e.client('--max-chunks', '3', '--expect-anchor-decode', ad, '--expect-bencode-overlap', str(bo),
                      '--expect-prep-ahead', str(pa))
        rows = e.manifest()
        probs = manifest_problems(rows, 49, (ad, bo, pa))
        check('C5.%d levers %s/%d/%d: qualification re-derived with these levers, 3 chunks, exit 0' % (i, ad, bo, pa),
              cp.returncode == 0 and len(rows) == 3 and not probs,
              'rc=%d probs=%s last=%s' % (cp.returncode, probs[:3], last_log(cp)))
        e.stop_fake()


def test_expectations_and_dg0():
    e = Env('c-expect')
    e.start_fake('--phase', 'stream', '--anchor-decode', 'full', '--decoder-graph', '0',
                 '--decode-delay', '0.02', '--preview-delay', '0.02')
    for flag, val in (('--expect-anchor-decode', 'cone'), ('--expect-bencode-overlap', '0'),
                      ('--expect-prep-ahead', '0'), ('--expect-frames', '121')):
        cp = e.client('--skip-qualification', '--max-chunks', '1', flag, val)
        check('C6 %s %s against a full/1/1 f49 server refuses at preflight (exit 8), nothing posted' % (flag, val),
              cp.returncode == 8 and e.stats()['posts'] == 0, 'rc=%d' % cp.returncode)
    cp = e.client('--skip-qualification', '--max-chunks', '2', '--expect-decoder-graph', '0',
                  '--expect-anchor-decode', 'full')
    rows = e.manifest()
    check('C7 decoder_graph 0 / anchor_decode full streams 2 chunks with eager full-decode lines',
          cp.returncode == 0 and len(rows) == 2 and not manifest_problems(rows, 49, ('full', 1, 1), 0),
          'rc=%d probs=%s' % (cp.returncode, manifest_problems(rows, 49, ('full', 1, 1), 0)[:3]))
    e.stop_fake()
    cp = Env('c-flags-116b').client('--max-chunks', '1', '--expect-anchor-decode', 'cone', packet='116b',
                                    contract=CONTRACT116B, manifest=FAKE116B_SHA)
    check('C8 the lever flags are refused for --packet 116b (argument check, exit 1-2)',
          cp.returncode not in (0, 8) and 'need --packet 117' in cp.stderr, 'rc=%d' % cp.returncode)


def test_lever_failure_refused():
    e = Env('c-lever-fail')
    e.start_fake('--lever-fail', 'precompute', '--decode-delay', '0.02', '--audio-delay', '0.02',
                 '--preview-delay', '0.02')
    cp = e.client('--max-chunks', '1')
    check('C9 a verdict whose repeat-chain stage B did not use the precomputed encode fails; client exit 13',
          cp.returncode == 13 and e.manifest() == [], 'rc=%d last=%s' % (cp.returncode, last_log(cp)))
    e.stop_fake()
    e = Env('c-lever-lie')
    e.start_fake('--lever-fail', 'precompute', '--qualification', 'lie', '--decode-delay', '0.02',
                 '--audio-delay', '0.02', '--preview-delay', '0.02')
    cp = e.client('--max-chunks', '1')
    check('C10 a server that claims a pass over that lever failure is refused by the re-derivation (exit 13)',
          cp.returncode == 13 and e.manifest() == [] and 'did not use the precomputed encode' in cp.stdout,
          'rc=%d last=%s' % (cp.returncode, last_log(cp)))
    e.stop_fake()


def test_cross_packet():
    e = Env('c-116b-vs-117')
    e.start_fake('--phase', 'stream')
    cp = e.client('--skip-qualification', '--max-chunks', '1', packet='116b', contract=CONTRACT116B, manifest=FAKE_SHA)
    check('C11 a 116b client (117 manifest sha) refuses a 117 server at preflight, exit 8, nothing posted',
          cp.returncode == 8 and e.stats()['posts'] == 0 and 'needs a packet 116b server' in cp.stdout,
          'rc=%d' % cp.returncode)
    e.stop_fake()
    e = Env('c-117-vs-116b')
    e.start_fake('--phase', 'stream', fake='fake_comfy116.py', contract=CONTRACT116B)
    cp = e.client('--skip-qualification', '--max-chunks', '1')
    check('C12 a 117 client against a 116b server refuses at preflight (manifest identity), exit 8',
          cp.returncode == 8 and e.stats()['posts'] == 0, 'rc=%d' % cp.returncode)
    cp = e.client('--skip-qualification', '--max-chunks', '1', manifest=FAKE116B_SHA)
    check('C13 a 117 client with the 116b manifest sha still refuses (no lever status / needs a packet 117 server), '
          'exit 8', cp.returncode == 8 and e.stats()['posts'] == 0, 'rc=%d' % cp.returncode)
    e.stop_fake()
    cp = Env('c-pins').client('--max-chunks', '1', contract=CONTRACT116B)
    check('C14 --packet 117 with the 116b contract module is refused (module pin), exit 8',
          cp.returncode == 8 and 'differs from the sealed packet module' in cp.stdout, 'rc=%d' % cp.returncode)


for t in (test_all_levers_97, test_121, test_lever_combinations, test_expectations_and_dg0, test_lever_failure_refused,
          test_cross_packet):
    if args.only and args.only not in t.__name__:
        continue
    t()
bad = [r for r in RESULTS if not r[1]]
print('\n%d/%d passed; work in %s' % (len(RESULTS) - len(bad), len(RESULTS), TMP))
sys.exit(1 if bad else 0)
