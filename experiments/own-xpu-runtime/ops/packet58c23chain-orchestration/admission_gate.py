#!/usr/bin/env python3
"""Admission gate: recompute the packet58-onecard-cache23 screen's five views from raw device data (CPU, read in place).

Reads, never copies, the screen packet's WSCREEN evidence (card0-58c23-v5-a/resident/WSCREEN): every request's
result.json (tokens + token timestamps), timings/prefill-timings streams, cache.jsonl, the DRM samples, the
suite order and the packet49 oracle results; recomputes per request 99/(t100 - t1), the six prompt-class medians,
each view's class-balanced median, the warm-control drift, the minimum gain of both max23 views over every warm
max view, exactness against the oracle, fills per decode token per view and the lifetime DRM peak; compares
every number with the screen's summary.json / s58c23_decision and applies the chain admission:

  screen winner   both max23 >= 1.005 x every warm max, 60/60 exact, drift <= 3 %, fills/token >= 8 % below max;
  chain bar       +2 % over every max view and >= 36.6452544 tok/s: NOT met (by design the ruling admits the chain
                  under the idle-lanes rule; recorded, never recomputed into a pass);
  record bar      fresh WS128 must exceed 35.92672010504166 (cmvjejvoi03qcrf0138emu5a6): pending the device chain.

Every file read is pinned by sha256 as a provenance record {name, parent_relpath, parent_digest} (not a pin-guard
pin: the screen evidence sits under screen/evidence, which the guard does not treat as immutable chain evidence).
--verify re-reads and re-hashes every pinned file and recomputes the numbers again.
"""
import argparse, hashlib, json, statistics, sys
from decimal import Decimal
from pathlib import Path

ROOT = Path('/home/steve/llm-optimizations')
X = ROOT / 'experiments/own-xpu-runtime'
P = X / 'stage2/packet58-onecard-cache23-chain'
SCREEN = X / 'stage2/packet58-onecard-cache23/screen/evidence/card0-58c23-v5-a/resident/WSCREEN'
ORACLE = Path('/home/steve/own-xpu-runtime-results/packet49-integrate/oracle/results')
LABELS = ('A0', 'B0', 'A1', 'B1', 'A2')
VIEW_OF = dict(A0='max', B0='max23', A1='max', B1='max23', A2='max')
RECORD = 35.92672010504166
RECORD_ID = 'cmvjejvoi03qcrf0138emu5a6'
CHAIN_BAR = 36.6452544
DRM_GUARD = 30_500_000_000
sys.path.insert(0, str(P))
import suite_metrics as M  # noqa: E402  (PROMPT_CLASSES, the sealed class map of this packet)

READ = {}


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def pinned(path):
    path = Path(path)
    key = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    if key not in READ:
        READ[key] = dict(name=path.name, parent_relpath=key, parent_digest=sha(path))
    return path


def read_json(path):
    return json.loads(pinned(path).read_text())


def read_lines(path):
    return [json.loads(s) for s in pinned(path).read_text().splitlines() if s.strip()]


def require(ok, why):
    if not ok:
        raise ValueError(why)


def rate_1_100(stamps):
    require(len(stamps) >= 100, 'fewer than 100 generated events')
    return 99 / (stamps[99] - stamps[0])


def drm_bytes(path):
    text = pinned(path).read_text()
    for line in text.splitlines():
        if line.startswith('drm-total-vram0:'):
            value, unit = line.split(':', 1)[1].split()
            return int(value) * {'KiB': 1024, 'MiB': 1024 ** 2, 'B': 1}[unit] if unit in ('KiB', 'MiB', 'B') else int(value) * 1024
    return None   # before_load samples carry no vram0 line (the card is not yet touched)


def compute():
    run = SCREEN / 'run'
    order = [line.split()[0] for line in pinned(run / 'suite-inputs.tsv').read_text().splitlines() if line.strip()]
    require(order == list(M.PROMPT_CLASSES), 'suite order differs from the sealed prompt classes')
    oracle = {pid: read_json(ORACLE / pid / 'result.json')['tokens'] for pid in order}
    require(all(len(t) == 128 for t in oracle.values()), 'oracle tokens are not 128 per prompt')
    cache = read_lines(run / 'run/cache.jsonl')
    views, timing_rows = {}, []
    for label in LABELS:
        rates, classes, exact = {}, {}, 0
        for pid in order:
            d = run / 'run' / label / pid
            r = read_json(d / 'result.json')
            stamps = [x['completed_monotonic'] for x in r['timing_rows']]
            require(len(r['tokens']) == len(stamps) == 128 and r['cached_tokens'] == 0 and r['requested_max_new'] == 128 and r['passed'] is True
                    and r['arithmetic'] == 'iq3-p49-split32-v1' and r['gpu_count'] == 1 and r['context'] == 4096, f'{label}/{pid}: request identity')
            require(all(b > a for a, b in zip(stamps, stamps[1:])) and r['request_start_monotonic'] <= stamps[0], f'{label}/{pid}: timestamps')
            require(r['tokens'] == oracle[pid], f'{label}/{pid}: INEXACT against the packet49 oracle')
            exact += 1
            rates[pid] = rate_1_100(stamps)
            classes.setdefault(M.PROMPT_CLASSES[pid], []).append(rates[pid])
            for name in ('prefill-timings.jsonl', 'timings.jsonl'):
                for row in read_lines(d / name):
                    row['_view'] = label
                    timing_rows.append(row)
        medians = {k: statistics.median(v) for k, v in sorted(classes.items())}
        require(len(medians) == 6, f'{label}: six prompt classes required')
        views[label] = dict(view=VIEW_OF[label], exact_requests=exact, class_medians=medians, rate=statistics.median(medians.values()), request_rates=rates)
    # fills per decode token: cache.jsonl is one row per position in run order (views, requests, prefill rows then generated rows)
    require(len(timing_rows) == len(cache), f'cache/timing join mismatch: {len(cache)} cache rows, {len(timing_rows)} timing rows')
    for i in range(1, len(cache)):
        require(cache[i]['position'] == cache[i - 1]['position'] + 1, 'non-contiguous cache positions')
    fills = {label: [0, 0] for label in LABELS}
    for i, (row, c) in enumerate(zip(timing_rows, cache)):
        same = i > 0 and timing_rows[i - 1]['_view'] == row['_view']
        if row.get('kind') == 'generated_token' and row['generated_index'] >= 2:
            fills[row['_view']][0] += (c.get('fills_total', 0) - cache[i - 1].get('fills_total', 0)) if same else 0
            fills[row['_view']][1] += 1
    for label in LABELS:
        views[label]['decode_tokens'] = fills[label][1]
        views[label]['fills_per_token'] = round(fills[label][0] / fills[label][1], 3)
    drm = {str(p.relative_to(run / 'run')): drm_bytes(p) for p in sorted((run / 'run').rglob('drm-memory-*.txt'))}
    loaded = {k: v for k, v in drm.items() if v is not None and not k.endswith(('before_load.txt', 'end.txt'))}
    require(len(loaded) >= 130, f'expected the loaded DRM samples of 5 views x 12 requests x 2 resets plus the view resets; found {len(loaded)}')
    rates = [Decimal(str(views[l]['rate'])) for l in LABELS]
    warm = rates[2::2]; max23 = rates[1::2]; maxes = rates[0::2]
    drift = float(max(warm) / min(warm) - 1)
    min_gain = float(min(max23) / max(warm) - 1)
    fills_ok = all(views[b]['fills_per_token'] <= 0.92 * views[a]['fills_per_token'] for b in ('B0', 'B1') for a in ('A1', 'A2'))
    screen_winner = all(c >= a * Decimal('1.005') for a in warm for c in max23) and drift <= 0.03 and fills_ok and all(v['exact_requests'] == 12 for v in views.values())
    chain_rule = screen_winner and all(b >= a * Decimal('1.02') for a in maxes for b in max23) and all(b >= Decimal(str(CHAIN_BAR)) for b in max23)
    return dict(views=views, rates=[float(r) for r in rates], control_drift_fraction=drift, minimum_gain_vs_best_warm_control=min_gain,
                minimum_gain_vs_every_max_view=float(min(max23) / max(maxes) - 1), exact_requests=sum(v['exact_requests'] for v in views.values()),
                fills_reduced_8pct=fills_ok, fills_reduction_fraction=round(1 - views['B0']['fills_per_token'] / views['A1']['fills_per_token'], 4),
                drm_peak_loaded_bytes=max(loaded.values()), drm_samples=len(drm), drm_loaded_samples=len(loaded), drm_guard_bytes=DRM_GUARD,
                drm_under_guard=max(loaded.values()) < DRM_GUARD, screen_winner=screen_winner, chain_rule=chain_rule)


def compare(computed):
    s = read_json(SCREEN / 'summary.json')
    w = read_json(SCREEN / 'window.json')
    d = s['s58c23_decision']
    require(s['passed'] is True and s['device_executed'] is True and s['candidate_beats_all_controls'] is True and s['control_drift_passed'] is True, 'screen summary did not pass')
    require(w['passed'] is True and w['returncode'] == 0 and w['stop_reasons'] == [] and w['device_executed'] is True, 'screen window receipt incomplete')
    require(w['boot_id'] == Path('/proc/sys/kernel/random/boot_id').read_text().strip(), 'screen boot differs from the current boot')
    require([v['label'] for v in s['views']] == list(LABELS) and [v['view'] for v in s['views']] == [VIEW_OF[l] for l in LABELS], 'view order')
    for i, label in enumerate(LABELS):
        sv = s['views'][i]
        require(abs(sv['class_balanced_tok_s_1_100_intervals_after_ttft']['median'] - computed['views'][label]['rate']) < 1e-9, f'{label}: view rate differs from summary')
        require(abs(s['rates'][i] - computed['views'][label]['rate']) < 1e-9, f'{label}: summary rates differ')
        for req in sv['requests']:
            require(req['exact_oracle'] is True and req['passed'] is True and abs(req['tok_s_1_100_intervals_after_ttft'] - computed['views'][label]['request_rates'][req['prompt_id']]) < 1e-9,
                    f'{label}/{req["prompt_id"]}: request rate or exactness differs')
        require(abs(d['per_view'][label]['fills_per_token'] - computed['views'][label]['fills_per_token']) < 1e-9, f'{label}: fills/token differs from the decision ({d["per_view"][label]["fills_per_token"]} vs {computed["views"][label]["fills_per_token"]})')
    require(abs(s['control_drift_fraction'] - computed['control_drift_fraction']) < 1e-9 and abs(s['minimum_gain_vs_best_control'] - computed['minimum_gain_vs_best_warm_control']) < 1e-9, 'drift/gain differ')
    require(d['screen_winner'] is True and d['chain_rule'] is False and d['kill_rules_fired'] == [] and d['fills_reduced_8pct'] is True
            and d['record_tok_s'] == 35.926720 and d['chain_bar_tok_s'] == CHAIN_BAR, 'decision fields')
    require(computed['screen_winner'] is True and computed['chain_rule'] is False and computed['drm_under_guard'], 'recomputed decision differs')
    require(w['postload_memory']['full_cache_bytes'] == 23049601024 and w['memory_admission']['required_bytes'] == 100487123456
            and w['memory_admission']['passed'] is True, 'screen window memory identity')
    return dict(summary=READ[str((SCREEN / 'summary.json').relative_to(ROOT))], window=READ[str((SCREEN / 'window.json').relative_to(ROOT))],
                boot_id=w['boot_id'], unit=w['systemd_cgroup'].strip().rsplit('/', 1)[-1], started_utc_ns=w['started_utc_ns'], finished_utc_ns=w['finished_utc_ns'])


def evaluate():
    READ.clear()
    computed = compute()
    identity = compare(computed)
    ledger = read_json(ROOT / 'scripts/packet58_onecard_record_threshold.json')['records'][-1]
    require(ledger['reference_submission'] == RECORD_ID and ledger['threshold_tok_s'] == RECORD, 'live ledger record differs from the bars')
    row = dict(schema='packet58cache23chain.admission-gate.v1', passed=True, device_executed=False, model_reads=False, copies_made=False,
               screen_packet='packet58-onecard-cache23', screen_evidence=str(SCREEN.relative_to(ROOT)), screen_identity=identity,
               recomputed={k: v for k, v in computed.items() if k != 'views'},
               views={l: {k: v for k, v in computed['views'][l].items() if k != 'request_rates'} for l in LABELS},
               admission=dict(screen_bar_gain=0.005, screen_winner=True, chain_bar_tok_s=CHAIN_BAR, chain_bar_met=False,
                              chain_admitted_by='coordinator ruling 2026-10-23: lanes idle (the chain policy allows a chain below +2 % on idle lanes); '
                                                'derive the one-card record chain with the max23 selection',
                              record_bar=dict(tok_s=RECORD, reference_submission=RECORD_ID, rule='fresh exact WS128 must exceed it and the live ledger; every exactness gate'),
                              expected_ws128_tok_s='36.5-36.6 (the max23 views) against 35.926720; +1.7 % expected, not measured'),
               files_read=len(READ), files_read_digest=hashlib.sha256(json.dumps(READ, sort_keys=True).encode()).hexdigest(), files=READ)
    return row


def verify(path):
    stored = json.loads(Path(path).read_text())
    fresh = evaluate()
    for key in ('recomputed', 'views', 'screen_identity', 'files_read_digest'):
        require(stored[key] == fresh[key], 'admission gate changed: ' + key)
    for key, rec in stored['files'].items():
        require(sha(ROOT / key if not key.startswith('/') else key) == rec['parent_digest'], 'pinned screen file changed: ' + key)
    return fresh


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path, default=P / 'evidence/admission-gate.json')
    ap.add_argument('--verify', action='store_true')
    a = ap.parse_args()
    if a.verify:
        row = verify(a.output)
    else:
        row = evaluate()
        a.output.write_text(json.dumps(row, indent=2) + '\n')
    r = row['recomputed']
    print(json.dumps(dict(passed=True, rates=r['rates'], minimum_gain=r['minimum_gain_vs_best_warm_control'], drift=r['control_drift_fraction'],
                          fills=[row['views'][l]['fills_per_token'] for l in LABELS], drm_peak=r['drm_peak_loaded_bytes'], files=row['files_read'])))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except ValueError as e:
        print('admission_gate: REFUSED ' + str(e), file=sys.stderr)
        raise SystemExit(2)
