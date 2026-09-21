#!/usr/bin/env python3
"""Offline replay of one fixture prompt against a quiesced pipeline server.

Purpose: root-cause a campaign's wrong clip WITHOUT the campaign's concurrent
load. All three 2026-09-20 freezes hit under full-depth pipelined traffic, so
the heavy instrumentation path (packet 87's latent fingerprints) may only run
when the server is idle except for this one prompt.

  python scripts/replay-clip.py REPLAY-NAME \
      --graph <arm graph.json> --fixture bird \
      --server-run <run dir> \
      [--bad-output <validation dir of the failing clip>] \
      [--index-base N --index I] [--out <dir>]

--index selects the clip index (fixture slot = index % 10, so e.g. bird is
any index == 2 mod 10). Clip content is text+seed only; the index is pure
pipeline bookkeeping. A server keeps un-collected pipeline jobs forever, so
EACH replay on one server needs an index never submitted to it before --
pick the next free slot in the same fixture class (e.g. 112, then 122).
A collision latches the server ('sample job already exists'), after which
every later prompt fails closed and the server must be relaunched.
Exit 0 and prints a verdict:
  MATCHES_REFERENCE   replay is bitwise the fixture reference: the wrongness
                      needs campaign concurrency (race/timing/pool alias)
  MATCHES_BAD         replay is bitwise the failing clip: deterministic wrong
                      output reproducible in isolation -> safe to fingerprint
                      this replay with the heavy (packet-87) instrumentation
  MATCHES_NEITHER     replay is a third output: nondeterministic even alone
The replay's own validation dir is left in output/validation/<name>.
"""
import argparse, json, hashlib, subprocess, sys, time, urllib.request, urllib.error
from pathlib import Path

LANE = Path(__file__).resolve().parent.parent
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
API = 'http://127.0.0.1:8188'
PY = sys.executable

ap = argparse.ArgumentParser()
ap.add_argument('name')
ap.add_argument('--graph', required=True)
ap.add_argument('--fixture', required=True)
ap.add_argument('--fixtures', default=str(LANE / 'data/stability-01-prereg.json'))
ap.add_argument('--server-run', required=True)
ap.add_argument('--bad-output', default=None, help='validation dir name of the failing clip')
ap.add_argument('--index-base', type=int, default=201088)
ap.add_argument('--index', type=int, default=0)
ap.add_argument('--out', required=True)
ap.add_argument('--timeout', type=int, default=1500)
a = ap.parse_args()

server_run = Path(a.server_run)
out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)


def call(path, payload=None, retries=30):
    assert not (ROOT / 'FAULT.json').exists(), 'device fault; halt requests'
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(API + path, data=data, headers={'Content-Type': 'application/json'})
    attempt = 0
    while True:
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.loads(r.read() or b'{}')
        except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError):
            attempt += 1
            if payload is not None or attempt > retries:
                raise
            time.sleep(10)


fixture_list = json.loads(Path(a.fixtures).read_text())['fixtures']
ORDER = [f['id'] for f in fixture_list]
fixtures = {f['id']: f for f in fixture_list}
for f in fixture_list:
    f.setdefault('reference', 'stability-01-r01-' + f['id'])


def build(name, idx):
    """The runner's graph patch, verbatim: per-fixture text and constant seed,
    clip_index from the campaign's index base."""
    fx = fixtures[ORDER[idx % len(ORDER)]]
    g = json.loads(Path(a.graph).read_text())
    for node in g.values():
        if 'run_name' in node.get('inputs', {}):
            node['inputs']['run_name'] = name
        if 'clip_index' in node.get('inputs', {}) and not isinstance(node['inputs']['clip_index'], list):
            node['inputs']['clip_index'] = a.index_base + idx
    g['364']['inputs']['text'] = fx['prompt']
    g['339']['inputs']['noise_seed'] = fx['seed']
    g['338']['inputs']['noise_seed'] = fx['seed']
    if '75' in g:
        g['75']['inputs']['filename_prefix'] = name + '/preview'
    return g, fx


queue = call('/queue')
assert not queue['queue_running'] and not queue['queue_pending'], 'server busy; replay needs a quiesced server'
assert json.loads((ROOT / 'model-verification.json').read_text())['status'] == 'passed'

# The pipelined sampler emits nothing for its first two prompts (fill), and a
# prompt's saved clip is the one DECODED one prompt earlier (decode depth 1
# behind the sampler's depth 2). To capture the target's full bundle the
# replay therefore submits the target plus THREE fillers from the campaign's
# own fixture cycle; the target's clip is captured under the third filler's
# run name.
target_fx = fixtures[a.fixture]
assert ORDER[a.index % len(ORDER)] == a.fixture, \
    f'fixture cycle mismatch: index {a.index} maps to {ORDER[a.index % len(ORDER)]}, not {a.fixture}'
submissions = [(a.name, a.index)] + [(a.name + f'-f{i}', a.index + i) for i in (1, 2, 3)]
last_id = None
for name, idx in submissions:
    g, fx = build(name, idx)
    req = ROOT / 'requests' / name
    req.mkdir(parents=True, exist_ok=False)
    (req / 'prompt.json').write_text(json.dumps(g, indent=2) + '\n')
    r = call('/prompt', {'prompt': g, 'client_id': 'replay-' + name})
    assert not r.get('node_errors'), r
    (req / 'submission.json').write_text(json.dumps(r, indent=2) + '\n')
    print('submitted %s (fixture %s, seed %d, clip %d)' % (name, fx['id'], fx['seed'], a.index_base + idx), flush=True)
    last_id = r['prompt_id']

deadline = time.time() + a.timeout
while time.time() < deadline:
    h = call('/history/' + last_id)
    entry = h.get(last_id)
    if entry:
        status = entry.get('status', {})
        for m in status.get('messages', []):
            if m[0] == 'execution_error':
                (ROOT / 'requests' / submissions[-1][0] / 'history.json').write_text(json.dumps(entry, indent=2) + '\n')
                raise SystemExit('EXECUTION ERROR: ' + str(m[1])[:400])
        if status.get('completed'):
            (ROOT / 'requests' / submissions[-1][0] / 'history.json').write_text(json.dumps(entry, indent=2) + '\n')
            break
    time.sleep(0.5)
else:
    raise SystemExit('TIMED OUT')


def summary_sha(name):
    s = json.loads((ROOT / 'output/validation' / name / 'summary.json').read_text())
    return {k: {'sha256': v['sha256'], 'finite': v['finite']} for k, v in s['tensors'].items()}


def compare(ref_name, cand_name, tag):
    """Summary-level sha256 comparison (the r01 references carry no tensors)."""
    try:
        ref, cand = summary_sha(ref_name), summary_sha(cand_name)
    except Exception as error:
        return {'status': 'compare-failed: ' + repr(error), 'bitwise_equal': False}
    per = {k: {'bitwise_equal': ref[k]['sha256'] == cand[k]['sha256'],
               'candidate_finite': cand[k]['finite']} for k in ref}
    exact = all(v['bitwise_equal'] for v in per.values())
    result = {'status': 'passed', 'bitwise_equal': exact, 'comparisons': per}
    (out / (a.name + '-' + tag + '.json')).write_text(json.dumps(result, indent=2) + '\n')
    return result


time.sleep(2)  # let the validation writer finish flushing
emitted_name = a.name + '-f3'
# Guard: the emitted clip must be the target's, not a fill or a filler clip.
decode_receipt = json.loads((server_run / ('pipeline-decode-' + emitted_name + '.json')).read_text())
emitted_index = decode_receipt.get('detail', {}).get('emitted_index')
assert emitted_index == a.index_base + a.index, \
    f'expected emitted clip {a.index_base + a.index} under {emitted_name}, got {emitted_index}'
vs_ref = compare(target_fx['reference'], emitted_name, 'vs-reference')
verdict = {'name': a.name, 'fixture': target_fx['id'], 'emitted_clip': emitted_index,
           'captured_under': emitted_name, 'vs_reference': vs_ref}
if vs_ref['bitwise_equal']:
    verdict['verdict'] = 'MATCHES_REFERENCE'
else:
    if a.bad_output:
        vs_bad = compare(a.bad_output, emitted_name, 'vs-bad')
        verdict['vs_bad'] = vs_bad
        verdict['verdict'] = 'MATCHES_BAD' if vs_bad['bitwise_equal'] else 'MATCHES_NEITHER'
    else:
        verdict['verdict'] = 'NOT_REFERENCE_NO_BAD_GIVEN'
(out / (a.name + '-verdict.json')).write_text(json.dumps(verdict, indent=2) + '\n')
print(json.dumps(verdict, indent=2))
