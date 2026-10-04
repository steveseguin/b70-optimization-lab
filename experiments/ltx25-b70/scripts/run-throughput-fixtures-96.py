#!/usr/bin/env python3
"""Packet 96 copy of run-throughput-fixtures.py (that file is left untouched; a live
packet 95b run uses it). Same evidence per prompt, same oracle, same interval
definition. Differences:

- `--order`: which fixture each prompt carries. 'cycle' (prompt i -> fixture i mod 10,
  the packet 95 order), 'shift' (cycle k rotated by k, so batch composition changes
  every cycle), or a named arrangement from ltx_sampler_batch.ORDERS ('ref',
  'proof-neighbours', 'proof-slots'), continued by the cycle for drain prompts.
  The emitted clip is mapped to its fixture through this order, never through
  (index mod 10).
- Batch arms (the sampler node carries 'stream_last'): the last prompt sets
  stream_last = 1, so the server flushes the open batch group with fill rows.
- Each row records the emitted clip's batch job (slot, rows, fill slots) and its
  neighbour fixtures. Decode trails the sampler, so the prompt that emits a clip from
  decode is NOT the prompt whose sampler receipt released it: the job is found by the
  clip's absolute index among all the arm's sampler receipts (detail.emitted_index),
  and batch.rows[slot] must equal that index (packet 96 review, finding 1).
- The emitted clip sequence must be exactly clips 0..K-1 in prompt order, K = count -
  sampler depth - decode depth (both read from the graph); a duplicate or a gap fails
  the arm (exit 12) instead of being excluded as a fill (review finding 4).
- `--no-oracle`: no comparison (the reference arm, whose references do not exist yet);
  rows carry exact = null and the summary all_exact = null. Exit 0 if every prompt ran.
- Decode queue depth per prompt (decode receipt pending_after) is recorded.

No retries, no restarts. An execution error stops the driver (exit 2).
"""
import argparse, json, hashlib, subprocess, sys, time, urllib.request, urllib.error
from pathlib import Path

LANE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LANE / 'scripts'))
import ltx_sampler_batch as batching  # noqa: E402

ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
API = 'http://127.0.0.1:8188'
PY = sys.executable
VIDEO_SECONDS = 25 / 24
ORDER_NAMES = ('cycle', 'shift', 'ref', 'proof-neighbours', 'proof-slots')


def parse(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('prefix')
    ap.add_argument('--graph', required=True)
    ap.add_argument('--arm', required=True, help='arm name, recorded only')
    ap.add_argument('--server-run', required=True)
    ap.add_argument('--count', type=int, default=20)
    ap.add_argument('--fixtures', default=str(LANE / 'data/stability-01-prereg.json'))
    ap.add_argument('--out', required=True)
    ap.add_argument('--timeout', type=int, default=1500)
    ap.add_argument('--order', default='cycle', choices=ORDER_NAMES)
    ap.add_argument('--batch', type=int, default=1, choices=batching.BATCH_CHOICES,
                    help='the server batch; named orders are defined per batch')
    ap.add_argument('--no-oracle', action='store_true')
    ap.add_argument('--index-base', type=int, required=True)
    return ap.parse_args(argv)


def expected_clip_count(count, sampler_depth, decode_depth):
    """Clips a stream of `count` prompts emits: prompt i emits clip i - sampler_depth -
    decode_depth (the sampler releases clip i - Ds, decode emits what it was handed Dd
    prompts earlier). Every stage is fed in clip order."""
    return max(0, count - sampler_depth - decode_depth)


class SequenceError(Exception):
    """An emission-sequence fault found before the per-row checks (fails the arm with exit 12)."""


def provenance_map(sampler_receipts):
    """{absolute clip index: emitted_batch_job} from every sampler receipt of the arm,
    keyed by the clip that receipt's prompt released (detail.emitted_index)."""
    out = {}
    for rec in sampler_receipts:
        det = (rec or {}).get('detail') or {}
        e = det.get('emitted_index')
        if isinstance(e, int) and e >= 0 and isinstance(det.get('emitted_batch_job'), dict):
            if e in out:
                raise SequenceError('two sampler receipts released clip %d' % e)
            out[e] = det['emitted_batch_job']
    return out


def batch_info_for(absolute, pmap, order, fixtures, index_base):
    """Batch provenance of the clip with this absolute index, or None (batch-1 arm)."""
    bjob = pmap.get(absolute)
    if bjob is None:
        return None
    slot = bjob.get('slot')
    rows = bjob.get('rows') or []
    if not (isinstance(slot, int) and 0 <= slot < len(rows) and rows[slot] == absolute):
        raise AssertionError('batch provenance of clip %d names row %r at slot %r' % (
            absolute, rows[slot] if isinstance(slot, int) and 0 <= slot < len(rows) else None, slot))
    fill_of = bjob.get('fill_of')
    members = [(fill_of if c is None else c) for c in rows]
    neigh = []
    for k, c in enumerate(members):
        if k == slot:
            continue
        m = None if c is None else c - index_base
        neigh.append(fixtures[order[m]]['id'] if m is not None and 0 <= m < len(order) else None)
    return {'job': bjob.get('job'), 'slot': slot, 'rows': rows, 'fill_slots': bjob.get('fill_slots'),
            'batch': bjob.get('batch'), 'neighbour_fixtures': sorted(n for n in neigh if n is not None),
            'neighbour_unknown': sum(1 for n in neigh if n is None)}


def emission_problems(emitted_in_prompt_order, expected):
    """The non-fill emitted clip indices (relative), in prompt order, must be exactly
    0..expected-1."""
    seq = [e for e in emitted_in_prompt_order if e >= 0]
    problems = []
    dups = sorted({e for e in seq if seq.count(e) > 1})
    if dups:
        problems.append('clips emitted more than once: %s' % dups)
    if seq != list(range(expected)):
        problems.append('emitted %s, expected clips 0..%d in order' % (seq[:40], expected - 1))
    return problems


def build_order(a, nfix):
    if a.order in ('cycle', 'shift'):
        return batching.order_for(a.order, a.batch, a.count, nfix)
    if a.batch == 1:
        raise SystemExit('named orders need --batch 2 or 4')
    return batching.order_for(a.order, a.batch, a.count, nfix)


def main(argv=None):
    import re
    a = parse(argv)
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,100}', a.prefix):
        raise SystemExit('prefix must be lowercase [a-z0-9-]: ' + a.prefix)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    server_run = Path(a.server_run)

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

    fixtures = json.loads(Path(a.fixtures).read_text())['fixtures']
    assert len(fixtures) == 10 and len({f['seed'] for f in fixtures}) == 10
    if not a.no_oracle:
        for f in fixtures:
            f.setdefault('reference', 'stability-01-r01-' + f['id'])
            assert (ROOT / 'output/validation' / f['reference'] / 'summary.json').is_file(), f['reference']
            assert (ROOT / 'requests' / f['reference'] / 'history.json').is_file(), f['reference']
    order = build_order(a, len(fixtures))

    base = json.loads(Path(a.graph).read_text())
    assert base['364']['class_type'] == 'LTXPipelineTextEncode'
    assert base['339']['class_type'] == 'RandomNoise' and base['338']['class_type'] == 'RandomNoise'
    batch_arm = '428' in base and 'stream_last' in base['428'].get('inputs', {})
    s_depth = base['428']['inputs']['depth'] if '428' in base else 0
    d_depth = base['426']['inputs']['depth'] if '426' in base else 0
    expected = expected_clip_count(a.count, s_depth, d_depth)
    if batch_arm:
        assert base['428']['inputs'].get('batch') == a.batch, 'graph batch %r, --batch %d' % (
            base['428']['inputs'].get('batch'), a.batch)
    else:
        assert a.batch == 1 or a.order in ('cycle', 'shift'), 'named batch orders need a batch arm'
    identity_base = json.loads((server_run / 'server-identity.json').read_text())
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip() == identity_base['boot_id']
    assert json.loads((ROOT / 'model-verification.json').read_text())['status'] == 'passed'
    queue = call('/queue')
    assert not queue['queue_running'] and not queue['queue_pending'], 'server busy'

    prompts = []
    for i in range(a.count):
        fx = fixtures[order[i]]
        name = f'{a.prefix}-{i:02d}'
        g = json.loads(json.dumps(base))
        for node in g.values():
            if 'run_name' in node.get('inputs', {}):
                node['inputs']['run_name'] = name
            if 'clip_index' in node.get('inputs', {}) and not isinstance(node['inputs']['clip_index'], list):
                node['inputs']['clip_index'] = a.index_base + i
        if batch_arm:
            g['428']['inputs']['stream_last'] = 1 if i == a.count - 1 else 0
        g['364']['inputs']['text'] = fx['prompt']
        g['339']['inputs']['noise_seed'] = fx['seed']
        g['338']['inputs']['noise_seed'] = fx['seed']
        if '75' in g:
            g['75']['inputs']['filename_prefix'] = name + '/preview'
        req = ROOT / 'requests' / name
        req.mkdir(parents=True, exist_ok=False)
        (req / 'prompt.json').write_text(json.dumps(g, indent=2) + '\n')
        identity = dict(identity_base)
        identity['proc_start_ticks'] = Path(f"/proc/{identity['pid']}/stat").read_text().split(') ')[1].split()[19]
        for key, path in [('model_verification', ROOT / 'model-verification.json'),
                          ('server_args', server_run / 'server-args.json')]:
            identity[key + '_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        (req / 'identity.json').write_text(json.dumps(identity, indent=2) + '\n')
        prompts.append({'index': i, 'name': name, 'fixture': fx['id'], 'seed': fx['seed'], 'graph': g, 'req': req})

    t_submit = time.time()
    for p in prompts:
        r = call('/prompt', {'prompt': p['graph'], 'client_id': 'fixtures-' + a.prefix})
        assert not r.get('node_errors'), r
        p['prompt_id'] = r['prompt_id']
        (p['req'] / 'submission.json').write_text(json.dumps(r, indent=2) + '\n')
    print('queued %d prompts (order %s, batch %d) in %.2f s' % (len(prompts), a.order, a.batch,
                                                              time.time() - t_submit), flush=True)

    done = 0
    deadline = time.time() + a.timeout
    while done < len(prompts) and time.time() < deadline:
        for p in prompts:
            if 'history' in p:
                continue
            h = call('/history/' + p['prompt_id'])
            entry = h.get(p['prompt_id'])
            if not entry:
                continue
            status = entry.get('status', {})
            for m in status.get('messages', []):
                if m[0] == 'execution_error':
                    d = m[1] or {}
                    print('EXECUTION ERROR in %s: %s | %s' % (p['name'], d.get('exception_type'),
                          str(d.get('exception_message'))[:400]), flush=True)
                    (p['req'] / 'history.json').write_text(json.dumps(entry, indent=2) + '\n')
                    raise SystemExit(2)
            if status.get('completed'):
                p['history'] = entry
                (p['req'] / 'history.json').write_text(json.dumps(entry, indent=2) + '\n')
                ts = {m[0]: m[1]['timestamp'] for m in status['messages'] if isinstance(m[1], dict) and 'timestamp' in m[1]}
                p['t_start'] = ts.get('execution_start') / 1000
                p['t_done'] = ts['execution_success'] / 1000
                (p['req'] / 'result.json').write_text(json.dumps(
                    {'name': p['name'], 'prompt_id': p['prompt_id'], 'seconds': p['t_done'] - p['t_start'],
                     'status': status}, indent=2) + '\n')
                done += 1
                print('  done %s (%s) at +%.3f s' % (p['name'], p['fixture'], p['t_done'] - prompts[0]['t_start']),
                      flush=True)
        time.sleep(0.2)
    if done < len(prompts):
        print('TIMED OUT: %d/%d' % (done, len(prompts)))
        raise SystemExit(1)

    try:
        pmap = provenance_map([json.loads((server_run / ('pipeline-sampler-' + p['name'] + '.json')).read_text())
                               for p in prompts if (server_run / ('pipeline-sampler-' + p['name'] + '.json')).is_file()])
    except SequenceError as exc:
        # Third review: a clip released by two sampler receipts must fail the arm as a recorded sequence fault.
        fault = {'schema': 'ltx.throughput-fixtures-96.v1', 'prefix': a.prefix, 'arm': a.arm, 'index_base': a.index_base,
                 'server_run': str(server_run), 'count': a.count, 'emission_sequence_ok': False,
                 'emission_problems': [str(exc)], 'all_exact': False, 'rows': []}
        (out / (a.prefix + '-throughput.json')).write_text(json.dumps(fault, indent=2) + '\n')
        print('EMISSION SEQUENCE WRONG: %s' % exc, flush=True)
        return 12
    seen = set()
    rows = []
    for p in prompts:
        dec = server_run / ('pipeline-decode-' + p['name'] + '.json')
        decode_pending = None
        if dec.is_file():
            drec = json.loads(dec.read_text())
            raw = drec['detail']['emitted_index']
            emitted = -1 if raw < 0 else raw - a.index_base
            assert emitted >= -1, (p['name'], emitted)
            pend = drec['detail'].get('pending_after')
            decode_pending = len(pend) if isinstance(pend, list) else None
        else:
            emitted = p['index']
        if emitted < 0:
            rows.append({'prompt': p['name'], 'index': p['index'], 'prompt_fixture': p['fixture'],
                         'emitted_index': -1, 'emitted_fixture': None, 'reference': None, 'fill': True,
                         't_done': p['t_done'], 'exact': True, 'parity_status': 'fill', 'comparator': None,
                         'decode_pending': decode_pending})
            print('  %s emitted nothing (pipeline fill)' % p['name'], flush=True)
            continue
        fx = fixtures[order[emitted]]
        duplicate = emitted in seen          # never a fill: a pipelined stream emits each clip once
        seen.add(emitted)
        batch_info = batch_info_for(a.index_base + emitted, pmap, order, fixtures, a.index_base)
        if batch_arm and batch_info is None:
            raise AssertionError('no batch provenance for emitted clip %d' % (a.index_base + emitted))
        row = {'prompt': p['name'], 'index': p['index'], 'prompt_fixture': p['fixture'],
               'emitted_index': emitted, 'emitted_fixture': fx['id'], 'fill': False, 'duplicate': duplicate,
               't_done': p['t_done'], 'batch': batch_info, 'decode_pending': decode_pending}
        if a.no_oracle:
            row.update({'reference': None, 'exact': None, 'parity_status': 'not-compared', 'comparator': None})
            rows.append(row)
            print('  %s emitted clip %d (%s), slot %s, not compared' % (
                p['name'], emitted, fx['id'], (batch_info or {}).get('slot')), flush=True)
            continue
        parity_path = out / (p['name'] + '-parity.json')
        raw = (ROOT / 'output/validation' / fx['reference'] / 'tensors.safetensors').is_file()
        comparator = 'scripts/compare-clip.py' if raw else 'scripts/compare-clip-hash.py'
        cp = subprocess.run([PY, '-B', str(LANE / comparator), fx['reference'], p['name'],
                             '--output', str(parity_path)], capture_output=True, text=True, timeout=300)
        parity = json.loads(parity_path.read_text()) if parity_path.exists() else {'status': 'missing', 'stderr': cp.stderr[-800:]}
        exact = (parity.get('status') == 'passed' and not duplicate and
                 all(v.get('bitwise_equal') is True for v in parity.get('comparisons', {}).values()))
        row.update({'reference': fx['reference'], 'exact': exact, 'parity_status': parity.get('status'),
                    'comparator': comparator})
        rows.append(row)
        print('  %s emitted clip %d (%s) vs %s: %s%s' % (p['name'], emitted, fx['id'], fx['reference'],
              'EXACT' if exact else 'MISMATCH ' + str(parity.get('status')), ' [duplicate]' if duplicate else ''), flush=True)

    seq_problems = emission_problems([r['emitted_index'] for r in rows], expected)
    distinct = [r for r in rows if not r['fill'] and not r.get('duplicate')]
    distinct.sort(key=lambda r: r['t_done'])
    ivs = [round(b['t_done'] - a_['t_done'], 3) for a_, b in zip(distinct, distinct[1:])]
    steady = ivs[1:] if len(ivs) > 1 else ivs
    mean = sum(steady) / len(steady) if steady else None
    p95 = sorted(steady)[int(round(0.95 * (len(steady) - 1)))] if steady else None
    summary = {'schema': 'ltx.throughput-fixtures-96.v1', 'prefix': a.prefix, 'arm': a.arm, 'index_base': a.index_base,
               'graph': str(a.graph), 'server_run': str(server_run), 'count': a.count, 'order': a.order,
               'fixture_order': [fixtures[k]['id'] for k in order], 'batch': a.batch,
               'references_from': None if a.no_oracle else str(a.fixtures),
               'fixture_count': len(fixtures), 'distinct_clips_emitted': len(distinct),
               'sampler_depth': s_depth, 'decode_depth': d_depth, 'expected_clips': expected,
               'emission_sequence_ok': not seq_problems, 'emission_problems': seq_problems,
               'fills_excluded': [r['prompt'] for r in rows if r['fill']],
               'all_exact': None if a.no_oracle else all(r['exact'] for r in rows),
               'intervals_between_distinct_clips_s': ivs,
               'steady_mean_s': mean, 'steady_p95_s': p95, 'steady_min_s': min(steady) if steady else None,
               'steady_max_s': max(steady) if steady else None,
               'seconds_of_wall_per_second_of_video': (mean / VIDEO_SECONDS) if mean else None,
               'effective_fps': (25 / mean) if mean else None,
               'definition': 'interval between server execution_success timestamps of consecutive distinct emitted '
                             'clips; the first such interval is excluded from the mean; fills are prompts that emit '
                             'nothing (pipeline fill); a re-emitted clip fails the arm',
               'rows': rows}
    (out / (a.prefix + '-throughput.json')).write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({k: v for k, v in summary.items() if k != 'rows'}, indent=2))
    if seq_problems:
        print('EMISSION SEQUENCE WRONG: ' + '; '.join(seq_problems), flush=True)
        return 12
    if summary['all_exact'] is False:
        return 3
    return 0


if __name__ == '__main__':
    sys.exit(main())
