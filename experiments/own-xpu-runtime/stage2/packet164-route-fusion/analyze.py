"""Bounded CPU analysis of saved event clocks; never assign time to unobserved phases."""
from collections import defaultdict
import csv
import gzip
import hashlib
import io
import json
from statistics import median
from capture import P, guard


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def read(name):
    pin = json.loads((P/'evidence/input-pins.json').read_text())[name]
    packed = (P/'evidence'/pin['retained']).read_bytes()
    require(hashlib.sha256(packed).hexdigest() == pin['retained_sha256'], 'compressed input hash')
    raw = gzip.decompress(packed)
    require(len(raw) == pin['bytes'] and hashlib.sha256(raw).hexdigest() == pin['sha256'], 'input hash')
    return raw


def jsonl(name):
    return [json.loads(line) for line in read(name).splitlines()]


def events_report(events, plan, halves, actual_plan):
    sites = {r['site']: r for r in plan['sites']}
    require(len(sites) == len(plan['sites']), 'duplicate site')
    actual = {r['site']: r for r in actual_plan}
    require(set(actual) == set(sites) and len(actual) == len(actual_plan), 'actual plan coverage')
    mismatches = [dict(site=i, label=s['label'], declared=s['kernel_count'], actual=actual[i]['kernel_count'])
                  for i, s in sites.items() if s['kernel_count'] != actual[i]['kernel_count']]
    grouped = defaultdict(list)
    for row in events:
        require(row['arm'] in ('a', 'b', 'c', 'natural') and row['block'] in range(4), 'arm/block')
        require(row['site'] in sites, 'unknown site')
        site = sites[row['site']]
        require((row['class'], row['label']) == (site['class'], site['label']), 'site label')
        require(type(row['start_ns']) is int and type(row['end_ns']) is int
                and 0 < row['start_ns'] < row['end_ns'], 'event clocks')
        grouped[row['block'], row['arm']].append(row)
    require(set(grouped) == {(b, a) for b in range(4) for a in ('a', 'b', 'c', 'natural')}, 'half coverage')
    require(len(halves) == 16 and all(h['routes_equal'] and h['state_equal'] for h in halves), 'half equality')
    samples, site_samples = [], defaultdict(list)
    for (block, arm), rows in sorted(grouped.items()):
        # Arm c contains touch events whose declared counts caused p141's
        # original analyzer refusal. It is retained but cannot qualify this analysis.
        require(all(a['end_ns'] <= b['start_ns'] for a, b in zip(rows, rows[1:])), 'serial ordering')
        if arm == 'c':
            continue
        for rep in (range(6) if arm == 'b' else (0,)):
            rr = [r for r in rows if r['repeat'] == rep]
            expected = [(site, n) for site, item in sorted(actual.items()) for n in range(item['kernel_count'])]
            require([r['site'] for r in rr] == [site for site, _ in expected], 'complete event sequence')
            require(all(not r['pretouch'] and r['warmup'] == (arm == 'b' and rep < 2) for r in rr), 'flags')
            if arm == 'b' and rep < 2:
                continue
            row = dict(block=block, arm=arm, repeat=rep)
            for cls in ('route', 'router'):
                selected = [r for r in rr if r['class'] == cls]
                require(len(selected) == 24 and len({r['label'] for r in selected}) == 24, '24 layer calls')
                require(all(sites[r['site']]['kernel_count'] == 1 for r in selected), 'single kernel site')
                row[cls+'_ms'] = sum(r['end_ns']-r['start_ns'] for r in selected)/1e6
                row[cls+'_launches'] = len(selected)
                for r in selected:
                    site_samples[arm, r['label']].append((r['end_ns']-r['start_ns'])/1e3)
            if arm != 'b':
                row['gap_before_route_ms'] = sum(r['start_ns']-rr[i-1]['end_ns'] for i, r in enumerate(rr) if i and r['class'] == 'route')/1e6
                row['gap_after_route_ms'] = sum(rr[i+1]['start_ns']-r['end_ns'] for i, r in enumerate(rr[:-1]) if r['class'] == 'route')/1e6
                row['all_between_event_ms'] = sum(b['start_ns']-a['end_ns'] for a, b in zip(rr, rr[1:]))/1e6
            samples.append(row)
    aggregate = {}
    for arm in ('a', 'b', 'natural'):
        rows = [r for r in samples if r['arm'] == arm]
        aggregate[arm] = {key: median(r[key] for r in rows) for key in rows[0] if key not in ('arm', 'block', 'repeat')}
    return dict(samples=samples, aggregate=aggregate,
                per_kernel_us=[dict(arm=a, label=l, samples=len(v), median_us=median(v), min_us=min(v), max_us=max(v)) for (a, l), v in sorted(site_samples.items())],
                phase_ms=dict(top_k=None, normalization=None, publication=None, shared_activation=None,
                              internal_dependency_wait=None, host_launch_overhead=None),
                latency_threshold_met=False, latency_threshold_status='not identifiable, not a measured failure',
                latency_ms_lower_bound=0.0, latency_ms_upper_bound=aggregate['a']['route_ms'],
                diagnostic_only=True, original_p141_analyzer_passed=False,
                declared_actual_plan_mismatches=mismatches)


def balanced(pairs):
    groups = defaultdict(list)
    for cls, value in pairs:
        groups[cls].append(value)
    return median(median(v) for v in groups.values())


def price(route_ms, router_ms):
    one = json.loads(read('onecard-result.json'))
    requests = one['rows']
    require(len(requests) == 12 and all(r['passed'] and r['cached_tokens'] == 0 and r['exact_oracle'] for r in requests), 'onecard evidence')
    prompt_ms = [(r['prompt_class'], 1000*(r['token_timestamps'][99]-r['token_timestamps'][0])/99) for r in requests]
    one_rate = balanced((cls, 1000/ms) for cls, ms in prompt_ms)
    require(abs(one_rate-one['primary_metric']['value_tok_s']) < 1e-8, 'onecard replay')
    two = json.loads(read('twocard-result.json'))
    rows = list(csv.DictReader(io.StringIO(read('record-intervals.csv').decode())))
    require(len(rows) == 1188, 'record intervals')
    groups = defaultdict(list)
    for r in rows:
        for k in ('D', 'R', 'C', 'A', 'B', 'spec_start_offset_ms', 'unresolved_control_gaps_ms', 'elapsed_ms'):
            r[k] = float(r[k])
        groups[r['prompt_class'], r['prompt_id']].append(r)
    require(len(groups) == 12 and all(len(v) == 99 for v in groups.values()), '12 x 99')
    def model(r, cut, correction, both):
        return (max(r['D'], r['R']+max(0, r['C']-(cut if correction and r['C'] else 0)))
                + max(r['B']-cut, r['A']-(cut if both else 0)+r['spec_start_offset_ms'])
                + r['unresolved_control_gaps_ms'])
    require(max(abs(model(r, 0, False, False)-r['elapsed_ms']) for r in rows) < 1e-7, 'record reconstruction')
    def two_rate(cut=0, correction=False, both=False):
        return balanced((cls, 99000/sum(model(r, cut, correction, both) for r in rr)) for (cls, _), rr in groups.items())
    baseline = two_rate()
    require(abs(baseline-two['primary_metric']['value_tok_s']) < 1e-8, 'two-card rate')
    scenarios = []
    for label, half in [('all_route_vanishes', route_ms), ('all_route_and_fused_router_vanish', route_ms+router_ms),
                        ('latency_trigger_0.4', .4)]:
        for transfer in (1., .2):
            cut = half*transfer
            one_new = balanced((cls, 1000/(ms-2*cut)) for cls, ms in prompt_ms)
            scenarios.append(dict(assumption=label, transfer=transfer, saving_per_half_ms=cut,
                                  onecard_48_layer_proxy_ms=2*cut, onecard_gain_percent=100*(one_new/one_rate-1),
                                  twocard_B_only_percent=100*(two_rate(cut)/baseline-1),
                                  twocard_B_and_C_percent=100*(two_rate(cut, True)/baseline-1),
                                  twocard_A_B_C_percent=100*(two_rate(cut, True, True)/baseline-1)))
    def threshold():
        lo, hi = 0., 2.
        for _ in range(70):
            mid = (lo+hi)/2
            if balanced((cls, 1000/(ms-mid)) for cls, ms in prompt_ms)/one_rate < 1.02:
                lo = mid
            else:
                hi = mid
        return hi
    need = threshold()
    return dict(onecard_baseline_tok_s=one_rate, twocard_baseline_tok_s=baseline,
                onecard_2percent_net_ms=need, route_recovery_fraction_for_2percent=need/(2*route_ms),
                route_plus_router_recovery_fraction_for_2percent=need/(2*(route_ms+router_ms)),
                scenarios=scenarios, measured_speed_claim=False,
                layer_scaling_is_unmeasured=True, route_and_router_are_not_free_to_remove=True)


def main():
    guard()
    report = events_report(jsonl('p141-events.jsonl'), json.loads(read('probe-plan.json')), jsonl('p141-halves.jsonl'), jsonl('p141-touch-plan.jsonl'))
    states = jsonl('p141-state-hashes.jsonl')
    require(len(states) == 16 and all(r['sha256_by_allocation'] == states[0]['sha256_by_allocation'] for r in states), 'whole-state agreement')
    report['pricing'] = price(report['aggregate']['a']['route_ms'], report['aggregate']['a']['router_ms'])
    report['decision'] = 'Close latency-fusion build: latency trigger unproven; even free route+router is below +2% at 20% transfer.'
    (P/'evidence/analysis.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(aggregate=report['aggregate'], pricing=report['pricing'], decision=report['decision']), indent=2))


if __name__ == '__main__':
    main()
