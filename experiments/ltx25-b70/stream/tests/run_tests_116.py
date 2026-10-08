#!/usr/bin/env python3
"""Tests of ltx_continuation_client.py --packet 116 against fake_comfy116.py (CPU only, port 18190; never 8188).

    /home/steve/.venvs/ltx25-baseline/bin/python -B tests/run_tests_116.py [--tmp DIR] [--port 18190] [--only NAME]

Covers what packet 116 changes for the client: the frame anchor by default with the 116a hand-off (the
receipt commits before the decode record; the client waits for the record, then the preview), the decoder
graph (status decoder_graph 0/1, --expect-decoder-graph, decoder_graph/decoder_mode in manifest lines), the
116 qualification re-derivation (decoder-graph rows, the cross-packet reference: the sealed reference refuses
the fake's outputs), the other anchor modes, resets, decode faults, and that 115 and 116 clients each refuse
the other packet's server at preflight.
"""
import argparse, hashlib, json, signal, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
CLIENT = HERE.parent / 'ltx_continuation_client.py'
CONTRACT = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation116-stream')
CONTRACT115 = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation115-stream')
CONTRACT114 = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation114-stream')
CONTRACT113 = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation113-stream')
FAKE_SHA = hashlib.sha256(b'fake-packet-116-manifest').hexdigest()     # fake_comfy116 default
FAKE115_SHA = hashlib.sha256(b'fake-packet-115-manifest').hexdigest()  # fake_comfy115 default
FAKE114_SHA = hashlib.sha256(b'fake-packet-114-manifest').hexdigest()  # fake_comfy114 default
FAKE113_SHA = 'a23dbc946d156df70c3e61134dc3231b147817c5cb110a015f84c8f020f7f28b'   # fake_comfy113 default
PY = sys.executable

ap = argparse.ArgumentParser()
ap.add_argument('--tmp', type=Path)
ap.add_argument('--port', type=int, default=18190)
ap.add_argument('--only')
args = ap.parse_args()
assert args.port != 8188, 'never the live port'
TMP = Path(tempfile.mkdtemp(prefix='ltx-c116-test-', dir=str(args.tmp) if args.tmp else None))
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
        self.packet = '116'
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

    def client(self, *extra, packet='116', contract=CONTRACT, manifest=FAKE_SHA, timeout=300, refs=True):
        cmd = [PY, '-B', str(CLIENT), '--work-dir', str(self.work), '--root', str(self.root),
               '--port', str(args.port), '--contract-dir', str(contract), '--poll', '0.05',
               '--min-free-gib', '1', '--scenes', str(self.scenes_file), '--base-seed', str(BASE_SEED),
               '--packet', packet]
        if manifest:
            cmd += ['--manifest-sha256', manifest]
        if refs and packet == '116':
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
        return next(p for p in self.root.glob('encoder-server-continuation-stream-116-*') if '.old' not in p.name)

    def receipt(self, seq):
        return json.loads((self.run_dir() / 'receipts' / ('receipt-stream116-s%08d.json' % seq)).read_text())

    def qdecode(self, name):
        return json.loads((self.run_dir() / 'receipts' / ('decode-%s.json' % name)).read_text())

    def decode(self, seq):
        return json.loads((self.run_dir() / 'receipts' / ('decode-stream116-s%08d.json' % seq)).read_text())


def manifest_problems(rows, frames, anchor, dg=1):
    probs = []
    for k, r in enumerate(rows):
        p = Path(r['path'])
        first = k == 0 or r.get('reset')
        new = frames if (first or anchor == 'guide') else frames - 1
        if not p.is_file() or p.stat().st_size == 0 or not r.get('preview_sha256'):
            probs.append('mp4 %d' % k)
        if '/stream116-s%08d/' % r['stream_seq'] not in r['path']:
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


def test_frame49():
    for dg in (1, 0):
        e = Env('frame49-dg%d' % dg)
        e.start_fake('--decoder-graph', str(dg), '--decode-delay', '0.15', '--audio-delay', '0.3',
                     '--preview-delay', '0.1')
        cp = e.client('--max-chunks', '8', '--expect-anchor', 'frame', '--expect-decoder-graph', str(dg))
        rows, st = e.manifest(), e.stats()
        probs = manifest_problems(rows, 49, 'frame', dg)
        out = cp.stdout + cp.stderr
        check('F%d 116 frame/49 dg%d (default anchor): qualification re-derived with the 116 gate, 8 chunks, exit 0, '
              'manifest labels, chain, sharpness and decoder fields intact' % (1 + 2 * (1 - dg), dg),
              cp.returncode == 0 and len(rows) == 8 and not probs and st['stream_order'] == list(range(8)) and
              not st['refusals'] and 'client re-derivation passed' in out and st['qual_posts'] == 11,
              'rc=%d rows=%d probs=%s refusals=%s last=%s' % (cp.returncode, len(rows), probs[:4], st['refusals'],
                                                             out.strip().splitlines()[-1:]))
        recs = [e.receipt(k) for k in range(8)]
        lines = [ln for ln in out.splitlines() if ' stream_seq ' in ln and 'submit->preview' in ln]
        check('F%d log stage buckets (116a): video-decode(chain), anchor-handoff, receipt, decode-tail(off-chain); '
              'no decode(in-chain)' % (5 + (1 - dg)),
              len(lines) == 8 and all('video-decode(chain)' in ln and 'decode(in-chain)' not in ln and
                                      'anchor-handoff' in ln and 'decode-tail(off-chain)' in ln and ' receipt ' in ln
                                      for ln in lines), lines[:1])
        q0 = e.qdecode('stream116-qgraph-c000000')
        check('F%d 116a: frame stream receipts commit before their decode records (state video_done); the gated '
              'qualification chunks waited for their whole decode; dg%d decoder rows' % (2 + 2 * (1 - dg), dg),
              st['receipt_before_record'] >= 6 and st['gated_waited_full'] == 6 and
              all(r['decode']['state'] == 'video_done' and r['timing_ns']['video_done'] <= r['timing_ns']['anchor_ready']
                  for r in recs) and q0['decoder']['new_captures'] == (2 if dg else 0) and
              (q0['decoder']['reference'] is not None) == bool(dg) and
              [st['reuse_text'][str(k)] for k in range(8)] == expected_reuse(8),
              'before_record=%d gated=%d q0=%r' % (st['receipt_before_record'], st['gated_waited_full'],
                                                 q0['decoder']))
        e.stop_fake()


def test_frame97_and_ab_modes():
    e = Env('frame97')
    e.start_fake('--frames', '97', '--phase', 'stream', '--decode-delay', '0.1', '--preview-delay', '0.1')
    cp = e.client('--skip-qualification', '--max-chunks', '4', '--expect-frames', '97')
    rows = e.manifest()
    probs = manifest_problems(rows, 97, 'frame')
    check('N1 frame/97: 97 then 96 new frames, skip_first_frames 1, sharpness of 8 frames',
          cp.returncode == 0 and len(rows) == 4 and not probs and [r['new_frames'] for r in rows] == [97, 96, 96, 96] and
          len(rows[1]['sharpness_relative']) == 8, 'rc=%d rows=%d probs=%s' % (cp.returncode, len(rows), probs[:4]))
    e.stop_fake()
    for anchor in ('mixed', 'latent', 'guide'):
        e = Env('ab-' + anchor)
        e.start_fake('--anchor', anchor, '--phase', 'stream', '--decode-delay', '0.05', '--preview-delay', '0.05')
        cp = e.client('--skip-qualification', '--max-chunks', '4', '--expect-anchor', anchor)
        rows = e.manifest()
        out = cp.stdout + cp.stderr
        check('N4 %s log buckets: video-decode(off-chain) and decode-tail(off-chain), no decode(in-chain)' % anchor,
              'video-decode(off-chain)' in out and 'decode-tail(off-chain)' in out and 'decode(in-chain)' not in out,
              '')
        check('N2 A/B anchor %s on a 116 server streams 4 chunks with 116 manifest labels' % anchor,
              cp.returncode == 0 and len(rows) == 4 and not manifest_problems(rows, 49, anchor),
              'rc=%d rows=%d probs=%s' % (cp.returncode, len(rows), manifest_problems(rows, 49, anchor)[:3]))
        cp = e.client('--skip-qualification', '--max-chunks', '1', '--expect-anchor', 'frame')
        check('N3 --expect-anchor frame against a %s server refuses at preflight (exit 8)' % anchor,
              cp.returncode == 8 and 'anchor' in cp.stdout, 'rc=%d' % cp.returncode)
        e.stop_fake()


def test_decoder_graph_expectations():
    e = Env('expect-dg')
    e.start_fake('--phase', 'stream', '--decoder-graph', '1', '--decode-delay', '0.02', '--preview-delay', '0.02')
    cp = e.client('--skip-qualification', '--max-chunks', '1', '--expect-decoder-graph', '0')
    check('E1 --expect-decoder-graph 0 against a decoder_graph 1 server refuses at preflight (exit 8), nothing posted',
          cp.returncode == 8 and 'decoder_graph' in cp.stdout and e.stats()['posts'] == 0, 'rc=%d' % cp.returncode)
    cp = e.client('--skip-qualification', '--max-chunks', '2', '--expect-decoder-graph', '1')
    check('E2 --expect-decoder-graph 1 matches and streams', cp.returncode == 0 and len(e.manifest()) == 2,
          'rc=%d' % cp.returncode)
    e.stop_fake()
    cp = Env('expect-dg-115').client('--max-chunks', '1', '--expect-decoder-graph', '1', packet='115',
                                     contract=CONTRACT115, manifest=FAKE115_SHA)
    check('E3 --packet 115 --expect-decoder-graph is refused before contacting a server',
          cp.returncode != 0 and 'need --packet 116' in (cp.stdout + cp.stderr), 'rc=%d' % cp.returncode)


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
    e = Env('qual-sealed-ref')
    e.start_fake('--decode-delay', '0.05', '--preview-delay', '0.05')
    cp = e.client('--max-chunks', '1', refs=False)          # the sealed packet-113 reference for 49/two-way20-28/frame
    out = cp.stdout + cp.stderr
    check('Q3 with the sealed cross-packet reference the fake frame/49 outputs fail the client re-derivation (exit 13)',
          cp.returncode == 13 and 'packet-113 reference' in out and not e.manifest(),
          'rc=%d last=%s' % (cp.returncode, out.strip().splitlines()[-1:]))
    e.stop_fake()


def test_decode_faults():
    e = Env('nodecode')
    e.start_fake('--phase', 'stream', '--decode-delay', '0.05', '--preview-delay', '0.05', '--no-decode-at', '2')
    t0 = time.time()
    cp = e.client('--skip-qualification', '--max-chunks', '6', '--save-wait', '2')
    check('D1 frame: a decode record that never appears (its receipt committed at the hand-off) -> client exit 7 '
          'within the --save-wait bound; chunk 2 not manifested',
          cp.returncode == 7 and len(e.manifest()) == 2 and time.time() - t0 < 90,
          'rc=%d rows=%d' % (cp.returncode, len(e.manifest())))
    e.stop_fake()
    e = Env('decodefail')
    e.start_fake('--phase', 'stream', '--decode-delay', '0.05', '--preview-delay', '0.05', '--decode-fail-at', '3')
    cp = e.client('--skip-qualification', '--max-chunks', '8', '--save-wait', '5')
    rows = e.manifest()
    check('D2 decode thread failure (chunk 3, before the hand-off) latches the server -> client exit 2 or 6, '
          'chunk 3 never manifested',
          cp.returncode in (2, 6) and len(rows) in (2, 3) and [r['stream_seq'] for r in rows] == list(range(len(rows))),
          'rc=%d rows=%d' % (cp.returncode, len(rows)))
    e.stop_fake()


def test_resets():
    e = Env('reset-every')
    e.start_fake('--phase', 'stream', '--decode-delay', '0.02', '--preview-delay', '0.02')
    cp = e.client('--skip-qualification', '--max-chunks', '10', '--reset-every-chunks', '3')
    rows = e.manifest()
    recs = [e.receipt(k) for k in range(10)]
    resets = [r['stream_seq'] for r in recs if r['reset']]
    skips = [row.get('skip_first_frames', 0) for row in rows]
    check('R1 --reset-every-chunks 3 on 116 frame: resets at 3, 6, 9 (no skip), chain continues',
          cp.returncode == 0 and resets == [3, 6, 9] and skips == [0, 1, 1, 0, 1, 1, 0, 1, 1, 0] and
          all(recs[k]['anchor_in'] is None for k in (0, 3, 6, 9)) and
          all(recs[k]['anchor_in']['source_run_name'] == recs[k - 1]['run_name'] for k in (4, 5, 7, 8)) and
          not manifest_problems(rows, 49, 'frame'), 'rc=%d resets=%s skips=%s' % (cp.returncode, resets, skips))
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
    e = Env('c115-vs-116')
    e.start_fake('--phase', 'stream')
    cp = e.client('--skip-qualification', '--max-chunks', '1', packet='115', contract=CONTRACT115, manifest=FAKE_SHA)
    check('X1 a 115 client with the 116 manifest sha refuses a 116 server at preflight, exit 8',
          cp.returncode == 8 and e.stats()['posts'] == 0, 'rc=%d' % cp.returncode)
    e.stop_fake()
    e = Env('c116-vs-115')
    e.start_fake('--phase', 'stream', fake='fake_comfy115.py', contract=CONTRACT115)
    cp = e.client('--skip-qualification', '--max-chunks', '1')
    check('X2 a 116 client against a 115 server refuses at preflight (manifest identity), exit 8',
          cp.returncode == 8, 'rc=%d' % cp.returncode)
    cp = e.client('--skip-qualification', '--max-chunks', '1', manifest=FAKE115_SHA)
    check('X3 a 116 client with the 115 manifest sha still refuses (needs a packet 116 server), exit 8',
          cp.returncode == 8 and 'needs a packet 116 server' in cp.stdout, 'rc=%d' % cp.returncode)
    e.stop_fake()
    cp = Env('live-refs').client('--max-chunks', '1', '--port', '8188')
    check('X4 --reference-hashes on the live port is refused before contacting a server',
          cp.returncode != 0 and 'fake servers' in (cp.stdout + cp.stderr), 'rc=%d' % cp.returncode)


for t in (test_frame49, test_frame97_and_ab_modes, test_decoder_graph_expectations, test_qualification,
          test_decode_faults, test_resets, test_anchor_faults, test_cross_packet):
    if args.only and args.only not in t.__name__:
        continue
    t()
bad = [r for r in RESULTS if not r[1]]
print('\n%d/%d passed; work in %s' % (len(RESULTS) - len(bad), len(RESULTS), TMP))
sys.exit(1 if bad else 0)
