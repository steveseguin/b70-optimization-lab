#!/usr/bin/env python3
"""Fixed106 posthoc counter subset. Default is read-only; never repairs validity."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat

BASE = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
RUN = BASE / 'encoder-server-sampler-accounting-106-two-way-w2-b1-p1-dxpu2-s640x384'
PACKET = BASE / 'prepared-sampler-accounting-106'
PLAN_SHA = 'eb8f71c3f6073c654abb6eed215aa877f2256b35e75cf595ea598c83352b31af'
PINS = {
    'raw': (RUN / 'driver-accounting.jsonl', '44ff8217b2ef13d2e9ba2851a5db93641139ba0282e9619a75a9a782f1d41d17'),
    'fast': (RUN / 'same-size-timed-fast.json', '9371b161bc6a6daa304679edf1dc92347c17e134727a31a7ca1550f1375483e8'),
    'campaign': (RUN / 'resolution-campaign-result.json', '91023e9100605a252e1ae24aa4798cf46b643a35e6f0bf98dcb17b2930a83e06'),
    'contract': (RUN / 'driver-accounting-contract.json', '7d4f3bcfb78afa3d6c266d6a57d9c6fb5c2249be910892acd02a3b919c8e231f'),
    'mapping': (RUN / 'driver-accounting-mapping.json', 'f2ce8c645f0023589ab6355d9d0b2f376d07b54f418d55318ea3032679c52ed7'),
    'manifest': (PACKET / 'manifest.json', '59765f873aa553104691053c43f0964725353ddb25df471f806b039e1aa4c6e2'),
    'identity': (RUN / 'server-identity.json', 'e292b16b347bf2673e3c7657aa17f85ebac70d58c00560c1c6d18ce1b53e9dda'),
    'plan': (PACKET / 'resolution/candidate-plan.json', 'af7bcc04e1e56f07eb2212dd0c4dc747defdbf58a4994956eefa8c26565f3add'),
}
QUALITY_PIN = (Path('/home/steve/llm-optimizations/experiments/ltx25-b70/data/resume-20261007/sampler106-post-completion-proof.json'),
               '8ac2b3c101d052c9cf648255bd556b83ace92bfabc6e84e79c04230b3ef94add')
MAX_READ = 2 * 1024**2
ENGINES = ('ccs', 'bcs')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def strict(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, 'Duplicate JSON key')
            out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: require(False, 'Nonfinite JSON'))


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def bound_read(path, expected):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts and
            not any(p.is_symlink() for p in (path, *path.parents)), 'Unsafe source path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        require(stat.S_ISREG(os.fstat(fd).st_mode), 'Nonregular source')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(MAX_READ + 1)
        require(len(raw) <= MAX_READ and digest(raw) == expected, 'Source hash/size differs')
        return raw
    finally:
        os.close(fd)


def integer(value):
    return type(value) is int


def counter_pair(a, b):
    """Return per-client deltas, or a reason to exclude this adjacent pair."""
    if not a['complete'] or not b['complete'] or a['issues'] or b['issues']:
        return None, 'incomplete-snapshot'
    if a['render_descriptors'] != a['render_descriptors_after'] or \
            b['render_descriptors'] != b['render_descriptors_after'] or \
            a['render_descriptors'] != b['render_descriptors']:
        return None, 'render-ownership-changed'
    if set(a['clients']) != set(b['clients']) or not a['clients']:
        return None, 'client-set-changed'
    for sample in (a, b):
        if {d['client_key'] for d in sample['render_descriptors'].values()} != set(sample['clients']):
            return None, 'client-render-coverage-differs'
    output = {}
    for key in sorted(a['clients']):
        old, new = a['clients'][key], b['clients'][key]
        if any(old[k] != new[k] for k in ('pci', 'client', 'selected_fd')) or \
                key != old['pci'] + '/' + old['client']:
            return None, 'client-identity-changed'
        if old['duplicate_observations'] or new['duplicate_observations']:
            return None, 'duplicate-client-observations-not-admitted'
        if set(old['engines']) != set(ENGINES) or set(new['engines']) != set(ENGINES):
            return None, 'engine-coverage-changed'
        output[key] = {}
        for engine in ENGINES:
            x, y = old['engines'][engine], new['engines'][engine]
            fields = ('busy', 'total', 'busy_watermark', 'total_watermark', 'capacity')
            if not all(integer(z.get(f)) and z[f] >= 0 for z in (x, y) for f in fields):
                return None, 'missing-or-invalid-counter'
            if not all(type(z.get('capacity_defaulted')) is bool and z['capacity'] > 0 for z in (x, y)):
                return None, 'invalid-capacity'
            if (x['capacity'], x['capacity_defaulted']) != (y['capacity'], y['capacity_defaulted']):
                return None, 'capacity-changed'
            if any(z[f] != z[f + '_watermark'] for z in (x, y) for f in ('busy', 'total')):
                return None, 'counter-below-watermark'
            busy, total = y['busy'] - x['busy'], y['total'] - x['total']
            if busy < 0 or total <= 0:
                return None, 'counter-regression-or-nonpositive-total'
            output[key][engine] = {'busy_cycles_delta': busy, 'own_total_cycles_delta': total,
                                   'capacity': x['capacity'], 'capacity_defaulted': x['capacity_defaulted']}
    return output, None


def analyze_records(records, start_ms, end_ms):
    require(integer(start_ms) and integer(end_ms) and start_ms < end_ms, 'Bad server boundaries')
    require(len(records) >= 4 and records[0].get('schema') == 'ltx.raw-drm-snapshots.v1', 'Bad raw header')
    terminal = records[-1]
    require(terminal.get('terminal') in ('output-cap', 'duration-cap', 'sample-cap'), 'Missing successful terminal')
    rows = records[1:-1]
    require(records[0].get('limits') == {'bytes': 131072, 'interval': 2, 'samples': 64, 'seconds': 120},
            'Unexpected collection bounds')
    admitted_pci = {x['pci'] for x in records[0]['ordered_xpu_mapping']}
    require(len(admitted_pci) == 4 and len(records[0]['ordered_xpu_mapping']) == 4, 'Mapping coverage differs')
    samples = []
    missed = 0
    previous_end = -1
    for raw_index, row in enumerate(rows, 1):
        require('terminal' not in row, 'Duplicate/interior terminal')
        if row.get('incomplete') == 'missed-cadence':
            missed += 1
            continue
        require(type(row.get('complete')) is bool and isinstance(row.get('issues'), list) and
                row['complete'] == (not row['issues']), 'Inconsistent completeness')
        m, u, n = (row.get(k) for k in ('monotonic_start_ns', 'unix_start_ns', 'monotonic_end_ns'))
        require(all(integer(x) for x in (m, u, n)) and 0 <= m <= n and previous_end < m and u > 0,
                'Malformed or unordered clock samples')
        previous_end = n
        if row['complete']:
            require({c['pci'] for c in row['clients'].values()} == admitted_pci and
                    not row['child_pids'], 'Complete sample lacks process/render coverage')
        samples.append((raw_index, row))
    require(2 <= len(samples) <= 64 and terminal.get('samples_recorded') == len(samples) and
            terminal.get('missed_slots') == missed, 'Terminal count mismatch')
    lows = [r['unix_start_ns'] - r['monotonic_end_ns'] for _, r in samples]
    highs = [r['unix_start_ns'] - r['monotonic_start_ns'] for _, r in samples]
    require(max(lows) <= min(highs), 'Observed clock brackets have no common intersection')
    low, high = min(lows), max(highs)
    # int(time.time()*1000) truncates: the true start may be almost 1ms later.
    # Use the latest possible start and earliest possible end, then whole scans.
    inner_start = start_ms * 1_000_000 + 1_000_000 - low
    inner_end = end_ms * 1_000_000 - high
    require(inner_start < inner_end, 'Clock uncertainty consumes entire window')
    accepted, excluded = [], []
    for i, ((ia, a), (ib, b)) in enumerate(zip(samples, samples[1:])):
        reasons = []
        if ib != ia + 1:
            reasons.append('intervening-record-gap')
        if b['monotonic_start_ns'] - a['monotonic_start_ns'] >= 4_000_000_000:
            reasons.append('cadence-gap')
        if a['monotonic_start_ns'] <= inner_start or b['monotonic_end_ns'] >= inner_end:
            reasons.append('outside-conservative-interior')
        deltas, reason = counter_pair(a, b)
        if reason:
            reasons.append(reason)
        pair = {'sample_indexes': [i, i+1], 'jsonl_indexes': [ia, ib]}
        if reasons:
            excluded.append({**pair, 'reasons': reasons})
            continue
        accepted.append({**pair, 'client_engines': deltas,
            'endpoint_scan_ns': [[a['monotonic_start_ns'], a['monotonic_end_ns']],
                                 [b['monotonic_start_ns'], b['monotonic_end_ns']]],
            'counter_read_elapsed_bounds_ns': [b['monotonic_start_ns'] - a['monotonic_end_ns'],
                                               b['monotonic_end_ns'] - a['monotonic_start_ns']]})
    require(accepted, 'No defensible complete interior pairs')
    return {'schema': 'ltx.accounting106-posthoc.v1', 'diagnostic_valid': False,
            'subset_scope': 'posthoc exploratory complete adjacent pairs only',
            'claim': 'Raw per-client engine cycle deltas; no utilization, busy seconds, cross-client totals, speed record or per-clip GPU attribution.',
            'clock_assumption': 'Local wall/monotonic offset stays within the observed envelope; unobserved wall-clock steps cannot be ruled out.',
            'unix_window_ms': [start_ms, end_ms], 'server_boundary_quantization_ns': 1_000_000,
            'clock_offset_envelope_ns': [low, high], 'clock_offset_intersection_ns': [max(lows), min(highs)],
            'conservative_monotonic_inner_ns': [inner_start, inner_end],
            'scan_width_bounds_ns': [min(r['monotonic_end_ns']-r['monotonic_start_ns'] for _,r in samples),
                                    max(r['monotonic_end_ns']-r['monotonic_start_ns'] for _,r in samples)],
            'accepted_pairs': accepted, 'excluded_pairs': excluded,
            'edge_exclusions_ns': {'start_to_first_scan_min': accepted[0]['endpoint_scan_ns'][0][0]-inner_start,
                                   'last_scan_to_end_min': inner_end-accepted[-1]['endpoint_scan_ns'][1][1]},
            'notes': 'Scored delivery window includes overlapping lookahead/tails; counter reads within each scan are not simultaneous. Invalid global diagnostic is unchanged.'}


def load_fixed():
    require(QUALITY_PIN is not None, 'Coordinator post-completion proof pin required')
    pins = {**PINS, 'quality': QUALITY_PIN}
    raw = {key: bound_read(*binding) for key, binding in pins.items()}
    require(raw['raw'].endswith(b'\n'), 'Truncated JSONL')
    records = [strict(line) for line in raw['raw'].splitlines()]
    values = {key: strict(value) for key, value in raw.items() if key != 'raw'}
    h, c, f, campaign = records[0], values['contract'], values['fast'], values['campaign']
    require(campaign['diagnostic_valid'] is False and campaign['driver_accounting']['valid'] is False and
            campaign['passed'] is True, 'Global invalid diagnostic and quality outcome must be retained')
    require(h['contract_sha256'] == PINS['contract'][1] and h['bindings'] == c['bindings'] and
            h['ordered_xpu_mapping'] == c['ordered_xpu_mapping'] == values['mapping']['ordered_xpu_mapping'],
            'Accounting contract/header/map differs')
    for role, key in [('mapping_evidence','mapping'), ('plan','plan'), ('runtime_manifest','manifest'), ('server_identity','identity')]:
        require(h['bindings'][role] == {'path': str(PINS[key][0]), 'sha256': PINS[key][1]}, 'Foreign source binding')
    require(all(h[k] == c[k] for k in ('pid', 'start_ticks', 'boot_id', 'collector_sha256')), 'Collector identity differs')
    identity = values['identity']
    require(h['pid'] == identity['pid'] and str(h['start_ticks']) == str(identity['proc_start_ticks']) and
            h['boot_id'] == identity['boot_id'] and identity['source_packet_manifest_sha256'] == PINS['manifest'][1],
            'Recorded server process identity differs')
    require(f['runtime_manifest_sha256'] == PINS['manifest'][1] and f['server_identity_sha256'] == PINS['identity'][1]
            and f['plan_sha256'] == c['plan_sha256'] == PLAN_SHA and f['status'] == 'timed_fast_verified', 'Proof identity differs')
    require(f['four_tensor_exact_clips'] == f['distinct_fixtures'] == 10 and f['fills_not_scored'] == 4, 'Quality scope differs')
    executions = f['executions']
    require(len(executions) == 14 and all(x['fill'] is True for x in executions[:4]), 'Fill scope differs')
    scored = executions[4:]
    require([x['emitted_index'] for x in scored] == list(range(10)) and
            all(x['fill'] is False and x['timing_scope'] == 'sampler-driver-accounting' and
                x['parity_status'] == 'four-tensors-exact' for x in scored), 'Scored scope differs')
    quality = values['quality']
    verifier_path = PACKET / 'resolution/components/candidate_gate.py'
    require(quality.get('schema') == 'ltx.sampler106.post-completion-proof.v1' and quality.get('passed') is True and
            quality['runtime_manifest_sha256'] == PINS['manifest'][1] and
            quality['fast_receipt_sha256'] == PINS['fast'][1] and quality['verifier'] == str(verifier_path) and
            quality['verifier_sha256'] == values['manifest']['files']['resolution/components/candidate_gate.py'],
            'Post-completion quality proof refused')
    pins['quality_verifier'] = (verifier_path, quality['verifier_sha256'])
    collector_path = PACKET / 'resolution/components/driver_accounting.py'
    require(h['collector_sha256'] == values['manifest']['files']['resolution/components/driver_accounting.py'],
            'Collector source differs')
    pins['collector'] = (collector_path, h['collector_sha256'])
    result = analyze_records(records, scored[0]['success_ms'], scored[-1]['success_ms'])
    result['ordered_xpu_mapping'] = h['ordered_xpu_mapping']
    for i, binding in enumerate(values['mapping']['evidence_sources']):
        pins['mapping_evidence_%d' % i] = (Path(binding['path']), binding['sha256'])
    for key, (path, sha) in pins.items():
        bound_read(path, sha)
    result['inputs'] = {key: {'path': str(path), 'sha256': sha} for key,(path,sha) in pins.items()}
    result['analyzer'] = {'path': str(Path(__file__).resolve()), 'sha256': digest(Path(__file__).read_bytes())}
    return result


def write_exclusive(path, raw):
    path = Path(path)
    require(path.parent.is_dir() and not any(p.is_symlink() for p in (path, *path.parents)), 'Unsafe output')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    raw = json.dumps(load_fixed(), sort_keys=True, indent=2, allow_nan=False).encode() + b'\n'
    if args.out:
        write_exclusive(args.out, raw)
    else:
        print(raw.decode(), end='')


if __name__ == '__main__':
    main()
