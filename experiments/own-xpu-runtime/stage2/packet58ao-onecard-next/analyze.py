#!/usr/bin/env python3
"""Read small saved receipts only; stdout is the complete reproducible report."""
import hashlib
import json
import math
import resource
import statistics as st
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
S = HERE.parent
INPUTS = {}


def read(path):
    raw = path.read_bytes()
    INPUTS[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
    return raw


def js(path):
    return json.loads(read(path))


def balanced(rows, cut=0):
    classes = defaultdict(list)
    for cls, ms in rows:
        assert ms > cut
        classes[cls].append(1000 / (ms - cut))
    assert {k: len(v) for k, v in classes.items()} == {
        'operations': 3, 'analysis': 3, 'code': 2, 'prose': 2,
        'documentation': 1, 'structured-writing': 1}
    return st.median(st.median(v) for v in classes.values())


def replay(packet, chain):
    base = S / packet / 'evidence' / chain / 'WS128'
    summary = js(base / 'summary.json')
    window = js(base / 'window.json')
    assert window['passed'] and window['device_executed']
    assert window['teardown_confirmed_before_reporting']
    assert summary['passed'] and summary['arithmetic'] == 'iq3-p49-split32-v1'
    assert summary['gpu_count'] == 1 and summary['decode_mode'] == 'plain'
    assert summary['kv_dtype'] == 'BF16' and summary['context'] == 4096
    assert summary['cache_bytes'] == 21552729600
    assert len(summary['requests']) == 12
    means, timings, requests, request_hashes = [], [], [], {}
    for req in summary['requests']:
        assert req['passed'] and req['exact_oracle'] and req['cached_tokens'] == 0
        ts = req['token_timestamps']
        assert len(ts) == req['output_tokens'] == 128
        assert all(math.isfinite(t) for t in ts)
        assert all(b > a for a, b in zip(ts, ts[1:]))
        ms = 1000 * (ts[99] - ts[0]) / 99
        means.append((req['prompt_class'], ms))
        q = base / 'run/run' / req['prompt_id']
        path = q / 'timings.jsonl'
        raw = read(path)
        assert hashlib.sha256(raw).hexdigest() == window['native_files'][str(path.relative_to(base))]
        rows = [json.loads(line) for line in raw.splitlines()]
        assert len(rows) == 128
        assert [r['generated_index'] for r in rows] == list(range(1, 129))
        assert all(r['kind'] == 'generated_token' for r in rows)
        assert [r['token_id'] for r in rows] == req['tokens']
        receipt_path = q / 'receipt.json'
        receipt = js(receipt_path)
        assert INPUTS[str(receipt_path.relative_to(ROOT))] == window['native_files'][str(receipt_path.relative_to(base))]
        assert receipt['passed'] and receipt['cached_tokens'] == 0
        assert receipt['tokens'] == req['tokens']
        assert receipt['arithmetic'] == summary['arithmetic']
        assert all(r['gemv_device_ms'] == r['non_gemv_device_ms'] == 0 for r in rows)
        assert all(r['enqueue_family_ms'] is None for r in rows)
        if packet.startswith('packet58aj'):
            assert all(r['resident_lookups'] for r in rows)
        timings.extend(rows[1:100])
        requests.append({'prompt_id': req['prompt_id'], 'class': req['prompt_class'],
                         'mean_interval_ms': ms, 'first_timestamp': ts[0],
                         'last_timestamp': ts[99], 'events': 100, 'intervals': 99,
                         'numerator': 99, 'output_hash': req['output_token_sha256'],
                         'prompt_hash': req['prompt_token_sha256']})
        request_hashes[req['prompt_id']] = (req['prompt_token_sha256'], req['output_token_sha256'])
    rate = balanced(means)
    assert abs(rate - summary['class_balanced_tok_s_1_100_intervals_after_ttft']['median']) < 1e-8
    assert len(timings) == 1188
    lo, hi = 0, min(ms for _, ms in means) / 2
    for _ in range(70):
        mid = (lo + hi) / 2
        if balanced(means, mid) / rate < 1.02:
            lo = mid
        else:
            hi = mid
    keys = ['wall_ms', 'prepare_ms', 'enqueue_loop_ms', 'wait_ms',
            'transfer_wall_ms', 'kernel_submissions', 'host_waits', 'process_major_faults']
    out = {'rate_tok_s': rate, 'reciprocal_rate_ms': 1000 / rate,
           'uniform_saving_for_2pct_ms': hi, 'requests': requests,
           'timing_means': {k: st.mean(r[k] for r in timings) for k in keys},
           'intervals': len(timings), 'device_class_times_available': False,
           'strict512': summary['realistic_final_gate']['passed'],
           'timing_scope': 'generated events 2..100; mean over 1188 rows; spans overlap'}
    return out, means, request_hashes


def main():
    ah, _, ah_hashes = replay('packet58ah-onecard-record', 'card0-58ah-b')
    aj, means, aj_hashes = replay('packet58aj-onecard-resident', 'card0-58aj-a')
    assert ah_hashes == aj_hashes
    old = js(S / 'packet58y-onecard-attribution/analysis/report.json')
    proxy = js(S / 'packet140-body-lever/analysis.json')
    assert not old['independent_miss_cost_known']
    assert not proxy['packet128b_overhead_passed']
    classes = sorted(({'class': k, 'diagnostic_two_card_half_ms': v['diagnostic_half_ms'],
                       'one_card_ms': None}
                      for k, v in proxy['scenarios'].items()),
                     key=lambda row: -row['diagnostic_two_card_half_ms'])
    def sensitivity(saving):
        return {'uniform_saving_ms': saving,
                'gain_pct': 100 * (balanced(means, saving) / aj['rate_tok_s'] - 1),
                'measured': False, 'supported_forecast': False}
    raw = 2 * proxy['n1_whole_eligible_path']['central_20pct_transfer']['raw_half_saving_ms']
    scenarios = {'scale_multicast_20pct': sensitivity(raw * .2),
                 'scale_multicast_80pct': sensitivity(raw * .8),
                 'scale_multicast_required_transfer': aj['uniform_saving_for_2pct_ms'] / raw}
    for name in ['dense_attention', 'gate_up', 'hc_norm']:
        v = proxy['scenarios'][name]['central_20pct_transfer']['raw_half_saving_ms']
        scenarios[name + '_20pct'] = sensitivity(2 * v * .2)
        scenarios[name + '_80pct'] = sensitivity(2 * v * .8)
    # All requested negative indexes, including inherited/private copies. Do not follow symlinks.
    negatives = []
    for pattern in ['packet58*', 'packet140*', 'packet147*']:
        for packet in sorted(S.glob(pattern)):
            if packet == HERE:
                continue
            for path in sorted(packet.rglob('DO-NOT-REPEAT*')):
                if path.is_file():
                    read(path)
                    negatives.append(str(path.relative_to(ROOT)))
    for rel in ['packet147-lever-synthesis/PLAN.md',
                'packet58aj-onecard-resident/runtime-selection.json',
                'packet58aj-onecard-resident/selection.json',
                'packet58aj-onecard-resident/native/engine_bracket.hpp',
                'packet58aj-onecard-resident/native/generated/main.cpp',
                'packet58ag-onecard-ports/AUDIT.md',
                'packet97-record-bundle/bundle-selection.json',
                'packet103-record-bundle/bundle-selection.json',
                'packet124c-record-bundle/bundle-selection.json',
                'packet136-record-bundle/bundle-selection.json']:
        read(S / rel)
    for tag in ['58j', '58p', '58v', '58w', '58x', '58z', '58ab', '58ag', '58ah', '58aj',
                '97', '100', '101', '103', '105b', '109', '124c', '131b', '136']:
        for directory in sorted(S.glob('packet' + tag + '-*')):
            read(directory / 'README.md')
    for name in ['2026-10-18-own-runtime-packet58r-result.md',
                 '2026-10-19-own-runtime-packet58aj-result.md',
                 '2026-10-19-own-runtime-packet58ah-chain-a-result.md',
                 '2026-10-18-own-runtime-packet97.md']:
        read(ROOT / 'notes' / name)
    print(json.dumps({'schema': 'own-runtime.packet58ao.audit.v1',
                      'decision': 'CLOSED_NO_SUPPORTED_2_PERCENT_FOLLOW_ON',
                      'device_executed': False, 'build_created': False,
                      'record': aj, 'predecessor': ah,
                      'packet58y': {k: old[k] for k in ['primary_metric', 'cache_bytes', 'ranking', 'caveats']},
                      'class_ranking_proxy_only': classes,
                      'sensitivity_only': scenarios,
                      'top_unported_exact_target_lever': 'rec-both-plus; closed by 58r, no new >=2% support',
                      'negative_indexes': negatives,
                      'packet147_has_negative_index': bool(list((S / 'packet147-lever-synthesis').glob('DO-NOT-REPEAT*'))),
                      'inputs_sha256': INPUTS}, indent=2, sort_keys=True))


if __name__ == '__main__':
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    main()
