#!/usr/bin/env python3
"""Fail-closed summary of bounded same-server prefill A/B/A screening.

Never promotes an image: independent-process qualification is outside this
campaign. Completed negative results exit zero; missing/invalid evidence exits 3.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics

PROFILES = ('4b', '9b', '27b-int4', '27b-fp8')
ARMS = ('baseline', 'candidate', 'final-control')
LENGTHS = (128, 256, 512)
KEYS = {f'{kind}-{length}' for kind in ('prose', 'code', 'docs') for length in LENGTHS}
FIELDS = ('ttft_s', 'http_prompt_tokens_per_ttft_s', 'server_prefill_s',
          'server_prefill_tokens_per_s', 'decode_token_1_to_100_tps', 'decode_after_ttft_tps')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def positive(value):
    return isinstance(value, (int, float)) and math.isfinite(value) and value > 0


def median(values):
    return statistics.median(values)


class Reader:
    def __init__(self, root):
        self.root = root
        self.sources = {}

    def read(self, relative, decode=True):
        path = self.root / relative
        data = path.read_bytes()
        self.sources[str(relative)] = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
        return json.loads(data) if decode else data.decode()


def load_arm(reader, profile, arm):
    d = reader.read(Path(profile) / arm / 'summary.json')
    require(d.get('passed') is True, f'{arm}: client did not finish successfully')
    require(set(d['prompts']) == KEYS, f'{arm}: wrong prompt coverage')
    require(d['args']['repeats'] == 3 and d['args']['max_tokens'] == 128,
            f'{arm}: wrong repetition/output contract')
    require(d['args']['max_model_len'] == 1024, f'{arm}: wrong context capacity')
    require(len(d['rows']) == 27, f'{arm}: expected 27 measured rows')
    seen = set()
    expected = {}
    by_key = {}
    for row in d['rows']:
        key = row['key']
        require(key in KEYS and row['phase'] == 'measure', f'{arm}: invalid row key or phase')
        pair = (key, row['repeat'])
        require(row['repeat'] in (0, 1, 2) and pair not in seen, f'{arm}: duplicate/invalid repeat')
        seen.add(pair)
        length = int(key.rsplit('-', 1)[1])
        prompt = d['prompts'][key]
        ids = row['token_ids']
        require(len(prompt) == length and all(type(x) is int for x in prompt), f'{arm}: invalid prompt IDs')
        require(len(ids) == 128 and all(type(x) is int for x in ids), f'{arm}: incomplete output IDs')
        require(key not in expected or expected[key] == ids, f'{arm}: repeated output divergence: {key}')
        expected[key] = ids
        usage = row['usage']
        require(usage['prompt_tokens'] == length and usage['completion_tokens'] == 128,
                f'{arm}: usage mismatch')
        require((usage.get('prompt_tokens_details') or {}).get('cached_tokens') == 0,
                f'{arm}: missing/nonzero cache count')
        offsets = row['token_offsets_s']
        require(len(offsets) == 128 and all(positive(t) for t in offsets)
                and all(a <= b for a, b in zip(offsets, offsets[1:])), f'{arm}: invalid token timing')
        recomputed = {'ttft_s': offsets[0], 'http_prompt_tokens_per_ttft_s': length / offsets[0],
                      'decode_token_1_to_100_tps': 99 / (offsets[99] - offsets[0]),
                      'decode_after_ttft_tps': 127 / (offsets[-1] - offsets[0])}
        for field, value in recomputed.items():
            require(positive(row[field]) and math.isclose(value, row[field], rel_tol=1e-9),
                    f'{arm}: invalid {field}')
        server = row.get('server_prefill_s')
        if server is not None:
            require(positive(server) and math.isclose(length / server, row['server_prefill_tokens_per_s'], rel_tol=1e-9),
                    f'{arm}: invalid server prefill metric')
            deltas = row['raw_delta']
            counts = [v for k, v in deltas.items() if k.endswith('request_prefill_time_seconds_count')]
            sums = [v for k, v in deltas.items() if k.endswith('request_prefill_time_seconds_sum')]
            require(len(counts) == 1 and counts[0] == 1 and len(sums) == 1
                    and math.isclose(server, sums[0], rel_tol=1e-9), f'{arm}: invalid serial histogram delta')
        by_key.setdefault(key, []).append(row)
    medians = {key: {field: median([r[field] for r in rows])
                    if all(r.get(field) is not None for r in rows) else None
                    for field in FIELDS} for key, rows in by_key.items()}
    return d, expected, medians


def strict(reader, profile):
    data = {}
    for arm in ('baseline', 'candidate'):
        prefix = Path(profile) / (arm + '-strict')
        d = reader.read(prefix / 'performance.json')
        canaries = reader.read(prefix / 'canaries.json')
        identity = reader.read(prefix / 'campaign-identity.json')
        contract = identity['performance_contract']
        require(contract['max_tokens'] == 512 and contract['ignore_eos'] is False
                and contract['complete_fixed_suite'] is True, f'{arm}: wrong strict natural-completion contract')
        require(bool(identity.get('suite_sha256')), f'{arm}: missing strict suite identity')
        require(d['realistic_final_gate']['passed'] is True and d['fresh_response_validity']['valid'] is True
                and d['fresh_response_validity']['cached_tokens_all_zero'] is True
                and canaries['pass_all'] is True, f'{arm}: strict workload/canary gate failed')
        rows = d['rows']
        require(len(rows) == 12 and len({r['prompt_id'] for r in rows}) == 12, f'{arm}: strict coverage')
        classes = {}
        for row in rows:
            require(row['cached_tokens'] == 0 and len(row['token_ids']) == row['completion_tokens']
                    and len(row['token_ids']) >= 100, f'{arm}: strict IDs/cache incomplete')
            rate = row['tok_s_1_100_intervals_after_ttft']
            require(positive(rate), f'{arm}: strict decode metric invalid')
            classes.setdefault(row['prompt_class'], []).append(rate)
        require(len(classes) == 6, f'{arm}: strict classes incomplete')
        data[arm] = {'rows': {r['prompt_id']: r for r in rows},
                     'decode': median([median(v) for v in classes.values()]), 'identity': identity}
    a, b = data['baseline'], data['candidate']
    require(a['identity']['suite_sha256'] == b['identity']['suite_sha256'], 'strict suites differ')
    require(set(a['rows']) == set(b['rows']), 'strict prompt sets differ')
    for key in a['rows']:
        require(a['rows'][key]['prompt_sha256'] == b['rows'][key]['prompt_sha256'], 'strict input hashes differ')
        require(a['rows'][key]['token_ids'] == b['rows'][key]['token_ids'], f'strict output divergence: {key}')
    comparison = reader.read(Path(profile) / 'strict-comparison.json')
    require(comparison['comparison']['exact_prompts'] == 12 and comparison['comparison']['total_prompts'] == 12
            and comparison['qualification']['strict_pair_qualified'] is True, 'stored strict comparison failed')
    return {'exact_prompts': 12, 'total_prompts': 12, 'baseline_decode_tps': a['decode'],
            'candidate_decode_tps': b['decode'], 'candidate_vs_baseline_ratio': b['decode'] / a['decode'],
            'independent_process_repeat': False}


def profile_summary(reader, profile):
    root = reader.root / profile
    require(not (root / 'ABORTED').exists(), 'stage ABORTED')
    require(bool(reader.read(Path(profile) / 'DONE', False).strip()), 'stage not DONE')
    identity = reader.read(Path(profile) / 'identity.json')
    reader.read(Path(profile) / 'container-inspect.json')
    runtime = reader.read(Path(profile) / 'runtime-sha256.txt', False)
    require(runtime.split()[0] == identity['runtime_sha256'], 'runtime hash mismatch')
    for path in ('postflight-discovery.txt', 'postflight-health.log', 'postflight-final-journal.txt', 'stop.log'):
        reader.read(Path(profile) / path, False)
    arms = {arm: load_arm(reader, profile, arm) for arm in ARMS}
    for arm in ARMS[1:]:
        require(arms[arm][0]['prompts'] == arms['baseline'][0]['prompts'], 'A/B/A prompt IDs differ')
        require(arms[arm][1] == arms['baseline'][1], 'A/B/A full output IDs differ')
    points = []
    for length in LENGTHS:
        keys = sorted(k for k in KEYS if k.endswith(f'-{length}'))
        measurements = {arm: {field: median([arms[arm][2][k][field] for k in keys])
                            if all(arms[arm][2][k][field] is not None for k in keys) else None
                            for field in FIELDS} for arm in ARMS}
        ratios = {}
        drifts = {}
        for field in FIELDS:
            ratios[field] = None
            drifts[field] = None
            if all(arms[arm][2][k][field] is not None for arm in ARMS for k in keys):
                ratios[field] = median([arms['candidate'][2][k][field] /
                    ((arms['baseline'][2][k][field] + arms['final-control'][2][k][field]) / 2) for k in keys])
                drifts[field] = median([arms['final-control'][2][k][field] /
                    arms['baseline'][2][k][field] for k in keys]) - 1
        points.append({'prompt_tokens': length, 'classes': 3, 'repeats_per_class_per_arm': 3,
                       'arms': measurements, 'candidate_vs_mean_controls_per_key_median_ratio': ratios,
                       'final_vs_initial_control_fractional_drift': drifts})
    strict_result = strict(reader, profile)
    prefill = [p['candidate_vs_mean_controls_per_key_median_ratio']['server_prefill_tokens_per_s'] for p in points]
    gains = median(prefill) - 1 if all(x is not None for x in prefill) else None
    drift = max(abs(p['final_vs_initial_control_fractional_drift']['server_prefill_tokens_per_s'])
                for p in points) if gains is not None else None
    decode_ok = strict_result['candidate_vs_baseline_ratio'] >= .97 and all(
        p['candidate_vs_mean_controls_per_key_median_ratio']['decode_token_1_to_100_tps'] >= .97 for p in points)
    speed_ok = gains is not None and gains >= .03 and gains > drift
    reasons = ['No independent-process candidate repeat: same-server A/B/A only.']
    if not speed_ok:
        reasons.append('Server-prefill gain absent, below 3%, or not larger than observed control drift.')
    if not decode_ok:
        reasons.append('At least one matched decode screen regressed more than 3%.')
    return {'complete': True, 'quality_exact': True, 'points': points, 'strict': strict_result,
            'median_server_prefill_fractional_gain': gains, 'max_observed_control_fractional_drift': drift,
            'screen_speed_gate_passed': speed_ok, 'screen_decode_gate_passed': decode_ok,
            'promotion_qualified': False, 'decision': 'retain original runtime', 'reasons': reasons,
            'identity': identity}


def summarize(root):
    reader = Reader(root)
    result = {'schema': 'neural.download.short-prefill-aba-screen.v1', 'raw_root': str(root),
              'complete': False, 'promotion_qualified': False,
              'metric_scope': 'Server prefill histogram elapsed time; HTTP tokens/TTFT proxy includes first-token and transport. Neither is isolated GPU kernel time.',
              'workload_scope': 'Repeated synthetic continuation shapes, c1, context capacity 1024; no new performance headline.',
              'profiles': {}}
    for profile in PROFILES:
        try:
            result['profiles'][profile] = profile_summary(reader, profile)
        except (OSError, ValueError, KeyError, TypeError, ZeroDivisionError) as exc:
            result['profiles'][profile] = {'complete': False, 'promotion_qualified': False,
                                          'error': f'{type(exc).__name__}: {exc}'}
    try:
        op = reader.read('rowchunk-direct-output.json')
        rows = op['rows']
        exact = len(rows) == 72 and op.get('passed') is True and all(r['bit_differences'] == 0
            and set(r['repeat_bit_differences']) == {'baseline', 'direct_out'}
            and all(v == 0 for v in r['repeat_bit_differences'].values()) for r in rows)
        result['operator_screen'] = {'complete': exact, 'exact_rows': len(rows) if exact else None,
            'median_speedup': median([r['speedup'] for r in rows]) if exact else None,
            'scope': 'Separate operator screen; cannot establish endpoint benefit or model quality.'}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result['operator_screen'] = {'complete': False, 'error': f'{type(exc).__name__}: {exc}'}
    result['complete'] = all(p['complete'] for p in result['profiles'].values()) and result['operator_screen']['complete']
    result['sources'] = reader.sources
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--raw-root', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    result = summarize(a.raw_root.resolve())
    with a.out.open('x') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
        f.write('\n')
    print(json.dumps({'complete': result['complete'], 'promotion_qualified': False,
                      'profiles': {k: v.get('error', v.get('decision')) for k, v in result['profiles'].items()}}))
    return 0 if result['complete'] else 3


if __name__ == '__main__':
    raise SystemExit(main())
