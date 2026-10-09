#!/usr/bin/env python3
"""Tests of ltx_continuation_client.py --packet 118 against fake_comfy118.py (--contract-dir of
recovery/20261009-continuation118-stream). CPU only, port 18193; never 8188.

    /home/steve/.venvs/ltx25-baseline/bin/python -B tests/run_tests_118.py [--tmp DIR] [--port 18193] [--only NAME]

Packet 118 is packet 117 for requests plus two server-side options (status snapshot_mode and
decoder_graph_pool_cap_bytes, receipts server_options) and the timing split in every receipt: qualification
re-derivation with the 118 gate (snapshot rows, decoder pool), streaming lines with stream118 names and the split,
the snapshot summary, the server turnaround and the client's own turnaround, the --expect-snapshot-mode /
--expect-pool-cap-gb flags, 117 / 118 clients refusing each other's servers, and a verdict whose snapshot rows fail.
"""
import argparse, hashlib, json, signal, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
CLIENT = HERE.parent / 'ltx_continuation_client.py'
CONTRACT = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261009-continuation118-stream')
CONTRACT117 = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261008-continuation117-stream')
FAKE_SHA = hashlib.sha256(b'fake-packet-118-manifest').hexdigest()     # fake_comfy118 default
FAKE117_SHA = hashlib.sha256(b'fake-packet-117-manifest').hexdigest()  # fake_comfy117 default
PY = sys.executable

ap = argparse.ArgumentParser()
ap.add_argument('--tmp', type=Path)
ap.add_argument('--port', type=int, default=18193)
ap.add_argument('--only')
args = ap.parse_args()
assert args.port != 8188, 'never the live port'
TMP = Path(tempfile.mkdtemp(prefix='ltx-c118-test-', dir=str(args.tmp) if args.tmp else None))
RESULTS = []
BASE_SEED = 11800000
SCENES3 = [{'id': 'boat-a', 'prompt': 'A small red wooden toy boat floats on calm clear water at sunset, gentle ripples.',
            'chunks': 3},
           {'id': 'boat-b', 'prompt': 'The red toy boat drifts slowly left as a soft breeze ripples the water.',
            'chunks': 5}]
SPLIT_KEYS = {'precheck', 'comfy_validate_queue', 'queue_to_executor', 'authority_begin', 'before_request_checks',
              'request_before_snapshot', 'before_request_tail', 'executor_to_first_node', 'first_node_to_condition_a',
              'condition_a_lookup', 'stage_a_before_snapshot', 'stage_a_consume', 'stage_a_after_snapshot',
              'condition_a_tail', 'dispatch_to_sampler_a', 'other', 'total'}


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
        self.refs = self.dir / 'refs-empty.json'
        self.refs.write_text(json.dumps({'schema': 'ltx.stream116.reference-frame-hashes.v1', 'variants': {}}))

    def start_fake(self, *extra, fake='fake_comfy118.py', contract=CONTRACT):
        tag = '118' if '118' in fake else '117'
        ready = self.root / ('fake%s-ready' % tag)
        self.stats_name = 'fake%s-stats.json' % tag
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

    def client(self, *extra, packet='118', contract=CONTRACT, manifest=FAKE_SHA, timeout=300):
        cmd = [PY, '-B', str(CLIENT), '--work-dir', str(self.work), '--root', str(self.root),
               '--port', str(args.port), '--contract-dir', str(contract), '--poll', '0.05',
               '--min-free-gib', '1', '--scenes', str(self.scenes_file), '--base-seed', str(BASE_SEED),
               '--packet', packet, '--reference-hashes', str(self.refs)]
        if manifest:
            cmd += ['--manifest-sha256', manifest]
        cp = subprocess.run(cmd + list(extra), capture_output=True, text=True, timeout=timeout)
        (self.work / ('client-%d.log' % time.time_ns())).write_text(cp.stdout + cp.stderr)
        return cp

    def manifest(self):
        p = self.work / 'manifest.jsonl'
        return [json.loads(x) for x in p.read_text().splitlines()] if p.is_file() else []

    def stats(self):
        return json.loads((self.root / self.stats_name).read_text())


def line_problems(rows, frames, mode, cap=None):
    probs = []
    for k, r in enumerate(rows):
        if not r['run_name'].startswith('stream118-s') or '/stream118-s%08d/' % r['stream_seq'] not in r['path']:
            probs.append('name %d' % k)
        if r.get('server_options') != {'snapshot_mode': mode, 'decoder_graph_pool_cap_bytes': cap}:
            probs.append('options %d %r' % (k, r.get('server_options')))
        if set(r.get('submit_split') or {}) != SPLIT_KEYS:
            probs.append('split %d' % k)
        snaps = r.get('snapshots') or {}
        first = k == 0
        want = ['request-before'] + ([] if first else ['A-before', 'A-after', 'B-before', 'B-after']) + ['request-after']
        if snaps.get('labels') != want or len(snaps.get('seconds') or []) != len(want):
            probs.append('snapshots %d %r' % (k, snaps.get('labels')))
        dual = mode == 'fingerprint' and r['stream_seq'] % 20 == 0
        if snaps.get('dual') != (len(want) if dual else 0):
            probs.append('dual %d %r' % (k, snaps.get('dual')))
        if not isinstance(r.get('authority_checks'), dict) or 'healthy_calls' not in r['authority_checks']:
            probs.append('checks %d' % k)
        if (r.get('turnaround') is None) != first:
            probs.append('turnaround %d' % k)
        if r.get('frames') != frames:
            probs.append('frames %d' % k)
    return probs


def last_log(cp):
    return (cp.stdout + cp.stderr).strip().splitlines()[-1:]


def test_fingerprint_97():
    e = Env('d-fp-97')
    e.start_fake('--frames', '97', '--decode-delay', '0.05', '--audio-delay', '0.1', '--preview-delay', '0.05')
    cp = e.client('--max-chunks', '5', '--expect-frames', '97', '--expect-anchor', 'frame', '--expect-decoder-graph', '1',
                  '--expect-anchor-decode', 'cone', '--expect-bencode-overlap', '1', '--expect-prep-ahead', '1',
                  '--expect-snapshot-mode', 'fingerprint', '--expect-pool-cap-gb', 'none')
    rows, st = e.manifest(), e.stats()
    probs = line_problems(rows, 97, 'fingerprint')
    out = cp.stdout + cp.stderr
    check('D1 118 frame/97 fingerprint: qualification re-derived with the 118 gate (snapshot rows), 5 stream118 '
          'chunks with the split, the snapshots and the turnaround, exit 0',
          cp.returncode == 0 and len(rows) == 5 and not probs and 'client re-derivation passed' in out and
          st['qual_posts'] == 11, 'rc=%d rows=%d probs=%s last=%s' % (cp.returncode, len(rows), probs[:4], last_log(cp)))
    turn = [r.get('client_turnaround_s') for r in rows]
    check('D2 every line but the last carries the client turnaround (receipt verified -> next POST) and POST time',
          all(type(v) is float and v >= 0 for v in turn[:-1]) and all(type(r.get('client_post_s')) is float
                                                                       for r in rows[:-1]), str(turn))
    status = json.loads(urllib.request.urlopen('http://127.0.0.1:%d/ltx-stream/status' % args.port).read())
    check('D3 status packet 118 with the server options and features',
          status['packet'] == 118 and status['snapshot_mode'] == 'fingerprint' and
          status['decoder_graph_pool_cap_bytes'] is None and status['features']['timing_split'] is True and
          status['features']['snapshot_fingerprint'] is True and status['features']['decoder_graph_pool_cap'] is False,
          str(status.get('features')))
    e.stop_fake()


def test_walk_and_pool_cap():
    e = Env('d-walk')
    e.start_fake('--snapshot-mode', 'walk', '--decode-delay', '0.02', '--audio-delay', '0.03', '--preview-delay', '0.02')
    cp = e.client('--max-chunks', '3', '--expect-snapshot-mode', 'walk')
    rows = e.manifest()
    probs = line_problems(rows, 49, 'walk')
    check('D4 a walk-mode server: the gate passes with no dual snapshots; 3 chunks, exit 0',
          cp.returncode == 0 and len(rows) == 3 and not probs, 'rc=%d probs=%s last=%s' % (cp.returncode, probs[:3],
                                                                                         last_log(cp)))
    e.stop_fake()
    e = Env('d-cap')
    e.start_fake('--frames', '121', '--pool-cap', '1.0', '--decode-delay', '0.02', '--audio-delay', '0.03',
                 '--preview-delay', '0.02')
    cp = e.client('--max-chunks', '3', '--expect-frames', '121', '--expect-pool-cap-gb', '1.0')
    rows = e.manifest()
    probs = line_problems(rows, 121, 'fingerprint', 10 ** 9)
    check('D5 a 121-frame dg1 server with a 1.0 GB pool cap: the gate accepts one capture; 3 chunks, exit 0',
          cp.returncode == 0 and len(rows) == 3 and not probs, 'rc=%d probs=%s last=%s' % (cp.returncode, probs[:3],
                                                                                         last_log(cp)))
    for flag, val in (('--expect-pool-cap-gb', 'none'), ('--expect-pool-cap-gb', '2.0'),
                      ('--expect-snapshot-mode', 'walk')):
        cp = e.client('--skip-qualification', '--max-chunks', '1', flag, val)
        check('D6 %s %s against a fingerprint/1.0 GB server refuses at preflight (exit 8), nothing new posted'
              % (flag, val), cp.returncode == 8, 'rc=%d' % cp.returncode)
    e.stop_fake()


def test_snapshot_failure_refused():
    e = Env('d-snap-fail')
    e.start_fake('--snapshot-fail', '--decode-delay', '0.02', '--audio-delay', '0.02', '--preview-delay', '0.02')
    cp = e.client('--max-chunks', '1')
    check('D7 qualification snapshots without the dual walk fail the 118 gate; client exit 13',
          cp.returncode == 13 and e.manifest() == [], 'rc=%d last=%s' % (cp.returncode, last_log(cp)))
    e.stop_fake()
    e = Env('d-snap-lie')
    e.start_fake('--snapshot-fail', '--qualification', 'lie', '--decode-delay', '0.02', '--audio-delay', '0.02',
                 '--preview-delay', '0.02')
    cp = e.client('--max-chunks', '1')
    check('D8 a server that claims a pass over those snapshot rows is refused by the re-derivation (exit 13)',
          cp.returncode == 13 and e.manifest() == [] and 'did not run (or agree with) the walk' in cp.stdout,
          'rc=%d last=%s' % (cp.returncode, last_log(cp)))
    e.stop_fake()


def test_cross_packet_and_flags():
    e = Env('d-117-vs-118')
    e.start_fake('--phase', 'stream')
    cp = e.client('--skip-qualification', '--max-chunks', '1', packet='117', contract=CONTRACT117, manifest=FAKE_SHA)
    check('D9 a 117 client (118 manifest sha) refuses a 118 server at preflight, exit 8, nothing posted',
          cp.returncode == 8 and e.stats()['posts'] == 0, 'rc=%d last=%s' % (cp.returncode, last_log(cp)))
    e.stop_fake()
    e = Env('d-118-vs-117')
    e.start_fake('--phase', 'stream', fake='fake_comfy117.py', contract=CONTRACT117)
    cp = e.client('--skip-qualification', '--max-chunks', '1', manifest=FAKE117_SHA)
    check('D10 a 118 client against a 117 server refuses at preflight (no server options / packet), exit 8',
          cp.returncode == 8 and e.stats()['posts'] == 0, 'rc=%d last=%s' % (cp.returncode, last_log(cp)))
    e.stop_fake()
    cp = Env('d-flags-117').client('--max-chunks', '1', '--expect-snapshot-mode', 'walk', packet='117',
                                   contract=CONTRACT117, manifest=FAKE117_SHA)
    check('D11 --expect-snapshot-mode is refused for --packet 117 (argument check)',
          cp.returncode not in (0, 8) and 'need --packet 118' in cp.stderr, 'rc=%d' % cp.returncode)
    cp = Env('d-flags-cap').client('--max-chunks', '1', '--expect-pool-cap-gb', '0.1')
    check('D12 --expect-pool-cap-gb outside 0.25..16 is refused (argument check)',
          cp.returncode not in (0, 8) and 'between 0.25 and 16' in cp.stderr, 'rc=%d' % cp.returncode)
    cp = Env('d-pins').client('--max-chunks', '1', contract=CONTRACT117)
    check('D13 --packet 118 with the 117 contract module is refused (module pin), exit 8',
          cp.returncode == 8 and 'differs from the sealed packet module' in cp.stdout, 'rc=%d' % cp.returncode)


for t in (test_fingerprint_97, test_walk_and_pool_cap, test_snapshot_failure_refused, test_cross_packet_and_flags):
    if args.only and args.only not in t.__name__:
        continue
    t()
bad = [r for r in RESULTS if not r[1]]
print('\n%d/%d passed; work in %s' % (len(RESULTS) - len(bad), len(RESULTS), TMP))
sys.exit(1 if bad else 0)
