#!/usr/bin/env python3
"""CPU-only packet57 analysis of existing native controller receipts.

Use nice -n 19 taskset -c 4-15,20-31 python3 -B. No imports of runtime code,
weights or device libraries. Raw token IDs/guesses never appear in output.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import statistics as st

DEFAULT_ROOT = Path('/home/steve/own-xpu-runtime-results')
PACKETS = ('packet49c-round2', 'packet49d-round3', 'packet56-draft-prefix')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stats(xs):
    xs = [x for x in xs if x is not None]
    return dict(count=len(xs), mean_ms=st.mean(xs), median_ms=st.median(xs),
                min_ms=min(xs), max_ms=max(xs)) if xs else None


def duration(row):
    return 1000 * (row['rank_completed'] - row['rank_received'])


def union_ms(intervals, start, end):
    """Union clipped intervals, never double-count overlapping command envelopes."""
    spans = sorted((max(a, start), min(b, end)) for a, b in intervals
                   if b > start and a < end)
    total, right = 0.0, start
    for left, stop in spans:
        total += max(0.0, stop - max(left, right))
        right = max(right, stop)
    return total * 1000


def command(rows, rank, op, position, speculative=None):
    found = [r for r in rows if r['rank'] == rank and r['op'] == op
             and r['position'] == position
             and (speculative is None or r['speculative'] == speculative)]
    if len(found) > 1:
        raise ValueError('ambiguous command identity')
    return found[0] if found else None


def extract(receipt):
    """Cycle belongs to preceding guess: hit at t_i determines t_(i+1)-t_i.

    draft_rows[position=p] proposes token p and completes target p-1. Its
    cycle_ms is the FOLLOWING inter-token interval, whose commands work p.
    The final interval lacks another speculative HALF; retain measured cycle
    but exclude it from full S/B projections.
    """
    trace = receipt['rank_trace']
    generated = receipt['generated_token_completion_timestamps']
    labels = {r['target_completed_monotonic']: r for r in receipt['draft_rows']
              if r.get('hit') is not None}
    draft_by_position = {r['position']: r for r in receipt['draft_rows']}
    cycles = []
    for start, end in zip(generated, generated[1:]):
        row = labels.get(start)
        if row is None:
            raise ValueError('generated interval has no preceding hit/miss label')
        p = row['position']
        d = command(trace, 1, 9, p)
        s = command(trace, 0, 1, p + 1, True)
        b = command(trace, 1, 1, p)
        r = command(trace, 0, 3, p, True)
        a = command(trace, 0, 1, p, False)
        publication = draft_by_position.get(p + 1)
        if not d or not b or not publication:
            raise ValueError('missing draft/target command or publication')
        if row['hit'] and (r or a):
            raise ValueError('hit has unexpected redo')
        if not row['hit'] and (not r or not a):
            raise ValueError('miss lacks rollback/redo')
        cycle = dict(position=p, hit=row['hit'], cycle_ms=1000*(end-start),
                     D_wall_ms=publication['draft_wall_ms'], D_command_ms=duration(d),
                     S_ms=duration(s) if s else None, B_ms=duration(b),
                     R_ms=duration(r) if r else 0.0, A_ms=duration(a) if a else 0.0,
                     draft_observation_wait_ms=publication['rank0_idle_waiting_for_guess_ms'],
                     rank1_mailbox_ms=1000*(b['rank_received']-b['sent']),
                     observation_to_draft_send_ms=1000*(d['sent']-start),
                     draft_command_to_B_start_ms=1000*(b['rank_received']-d['rank_completed']),
                     target_finish_to_observation_ms=1000*(end-b['rank_completed']))
        # The async publication lacks an absolute GPU endpoint. Do not label
        # no-command spans as GPU idle, or treat gpu_ms=0 as a measured zero.
        for rank in (0, 1):
            busy = union_ms([(t['rank_received'], t['rank_completed'])
                             for t in trace if t['rank'] == rank], start, end)
            cycle[f'rank{rank}_host_occupied_ms'] = busy
            cycle[f'rank{rank}_host_uncovered_ms'] = max(0.0, cycle['cycle_ms']-busy)
        if s:
            cycle['S_minus_B_ms'] = duration(s)-duration(b)
            cycle['rank0_finishes_last'] = s['rank_completed'] > b['rank_completed']
            cycle['rank0_finish_slack_ms'] = max(0.0, (b['rank_completed']-s['rank_completed'])*1000)
            cycle['rank1_finish_slack_ms'] = max(0.0, (s['rank_completed']-b['rank_completed'])*1000)
            cycle['B_to_S_start_ms'] = 1000*(s['rank_received']-b['rank_received'])
            cycle['model_ms'] = model(cycle)
            cycle['model_residual_ms'] = cycle['cycle_ms']-cycle['model_ms']
        cycles.append(cycle)
    return cycles


def model(c, delta0=0.0, delta1=0.0, draft=None):
    d = c['D_wall_ms'] if draft is None else draft
    prefix = d if c['hit'] else max(d, c['R_ms']+c['A_ms']+delta0)
    return prefix + max(c['S_ms']+delta0, c['B_ms']+delta1)


def summarize(cycles):
    numeric = sorted({k for c in cycles for k, v in c.items()
                      if k.endswith('_ms') and isinstance(v, (int, float))})
    result = {label: {k: stats([c.get(k) for c in part]) for k in numeric}
              for label, part in [('all', cycles), ('hit', [c for c in cycles if c['hit']]),
                                  ('miss', [c for c in cycles if not c['hit']])]}
    full = [c for c in cycles if c.get('S_ms') is not None]
    result['counts'] = dict(intervals=len(cycles), hits=sum(c['hit'] for c in cycles),
                           misses=sum(not c['hit'] for c in cycles), full_model_cycles=len(full),
                           rank0_finishes_last=sum(c['rank0_finishes_last'] for c in full))
    result['acceptance'] = sum(c['hit'] for c in cycles)/len(cycles)
    return result


def projections(cycles):
    full = [c for c in cycles if c.get('S_ms') is not None]
    # Explicitly average-half sensitivities, NOT measured migrating layer cost.
    # S includes speculation/snapshot; B includes target head. A avoids the
    # snapshot but is only present on misses. Actual layers 22/23 are unmeasured.
    s = st.median(c['S_ms'] for c in full)
    b = st.median(c['B_ms'] for c in full)
    a = st.median(c['A_ms'] for c in full if not c['hit'])
    baseline = st.mean(c['cycle_ms'] for c in full)
    result = {'measured': False, 'basis': 'paired cycle delta applied to observed full-cycle mean',
              'not_class_balanced_submission_metric': True,
              'per_layer_measured': False,
              'average_half_proxy_ms': {'rank0_S_over23': s/23, 'rank0_A_over23': a/23,
                                        'rank1_B_over25_including_head': b/25},
              'baseline_mean_cycle_ms': baseline, 'cases': {}}
    for label, shift in [('22_26', -1), ('24_24', 1)]:
        deltas, prefix_deltas, half_deltas = [], [], []
        for c in full:
            # Preserve baseline formula residual; moving one layer changes both
            # half terms, and corrected A only on misses.
            prefix = c['D_wall_ms'] if c['hit'] else max(c['D_wall_ms'], c['R_ms']+c['A_ms']+shift*a/23)
            after = prefix+max(c['S_ms']+shift*s/23, c['B_ms']-shift*b/25)
            deltas.append(after-model(c))
            baseprefix = c['D_wall_ms'] if c['hit'] else max(c['D_wall_ms'],c['R_ms']+c['A_ms'])
            prefix_deltas.append(prefix-baseprefix)
            half_deltas.append(max(c['S_ms']+shift*s/23,c['B_ms']-shift*b/25)-max(c['S_ms'],c['B_ms']))
        delta = st.mean(deltas)
        result['cases'][label] = dict(mean_cycle_delta_ms=delta,
            mean_recovery_prefix_delta_ms=st.mean(prefix_deltas),
            mean_parallel_half_delta_ms=st.mean(half_deltas),
            projected_mean_cycle_ms=baseline+delta,
            projected_relative_rate_change_percent=100*(baseline/(baseline+delta)-1))
    # Break-even destination-layer cost for 22/26 with the same rank0 average
    # removal. This is a sensitivity threshold, not an operator measurement.
    def move_delta(destination):
        return st.mean((c['D_wall_ms'] if c['hit'] else max(c['D_wall_ms'],c['R_ms']+c['A_ms']-a/23))
                       +max(c['S_ms']-s/23,c['B_ms']+destination)-model(c) for c in full)
    lo, hi = 0.0, 2.0
    for _ in range(36):
        mid = (lo+hi)/2
        if move_delta(mid) < 0: lo=mid
        else: hi=mid
    result['22_26_break_even_destination_layer_ms'] = (lo+hi)/2
    for label, saving in [('remove_0p5ms_D', .5), ('remove_1ms_D', 1.0), ('remove_all_D_ideal_bound', None)]:
        delta = st.mean(model(c, draft=0 if saving is None else max(0,c['D_wall_ms']-saving))-model(c) for c in full)
        result['cases'][label] = dict(mean_cycle_delta_ms=delta,
            projected_relative_rate_change_percent=100*(baseline/(baseline+delta)-1))
    # With today's controller draft-on-rank0 begins only after the preceding
    # speculative half is accepted. On a miss it shares the device with redo,
    # replacing max(D,R+A) by D+R+A. Ignore new reverse-transfer cost (optimistic).
    delta = st.mean(0.0 if c['hit'] else min(c['D_wall_ms'], c['R_ms']+c['A_ms']) for c in full)
    result['cases']['draft_rank0_same_D_optimistic'] = dict(mean_cycle_delta_ms=delta,
        projected_relative_rate_change_percent=100*(baseline/(baseline+delta)-1),
        excludes='reverse hidden transfer, weight placement/capacity, rank-dependent D speed')
    return result


def analyze(path):
    sources, requests, all_cycles, acceptances, published = [], {}, [], [], {'hit': [], 'miss': []}
    files = sorted((path/'run/repeat-1').glob('*/receipt.json'))
    if len(files) != 12:
        raise ValueError(f'expected twelve prompts: {path}, found {len(files)}')
    for source in files:
        j = json.loads(source.read_bytes())
        if not j['passed'] or not j['oracle_check']['passed']:
            raise ValueError('input request failed')
        cycles = extract(j)
        sources.append({'path':str(source), 'sha256':sha(source)})
        summary = summarize(cycles)
        requests[j['prompt_id']] = dict(counts=summary['counts'], acceptance=summary['acceptance'],
            output_token_sha256=j['output_token_sha256'],
            medians_ms={branch:{key: value['median_ms'] for key,value in summary[branch].items() if value}
                        for branch in ('all','hit','miss')})
        acceptances.append(j['acceptance'])
        all_cycles.extend(cycles)
        for branch in published:
            published[branch].append(j['hit_miss_cycles'][branch]['mean_ms'])
    return dict(sources=sources, summary=summarize(all_cycles), requests=requests,
                receipt_acceptance_median=st.median(acceptances),
                receipt_cycle_median_of_request_means_ms={k:st.median(v) for k,v in published.items()},
                projections=projections(all_cycles))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--receipts-root', type=Path, default=DEFAULT_ROOT)
    ap.add_argument('--output', type=Path)
    args = ap.parse_args()
    out = dict(schema='lab.packet57.timeline.v1', device_executed=False,
               scope='repeat-1 full 128-token generated spans, after TTFT; no warmup/prefill; host monotonic command envelopes',
               units='milliseconds except fractions/counts/percent',
               measured_gpu_idle=False, measured_per_layer=False,
               packets={name:analyze(args.receipts_root/name/'build/device-cards01-a/WS128') for name in PACKETS})
    base = out['packets']['packet56-draft-prefix']['requests']
    out['target_output_hash_comparison'] = {name:all(
        request['output_token_sha256']==base[prompt]['output_token_sha256']
        for prompt,request in data['requests'].items()) for name,data in out['packets'].items()}
    chain = args.receipts_root/'packet56-draft-prefix/build/device-cards01-a'
    out['site_availability'] = {}
    for window in ('KD','WS','WS128x','WS128'):
        sites = sorted((chain/window).rglob('sites.jsonl*'))
        sizes = [(len(gzip.decompress(p.read_bytes())) if p.suffix=='.gz' else p.stat().st_size) for p in sites]
        out['site_availability'][window] = dict(files=len(sites), nonempty_files=sum(n>0 for n in sizes), uncompressed_bytes=sum(sizes))
    encoded = json.dumps(out, indent=2, sort_keys=True)+'\n'
    if args.output:
        args.output.write_text(encoded)
    else:
        print(encoded, end='')


if __name__ == '__main__':
    main()
