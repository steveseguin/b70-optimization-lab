#!/usr/bin/env python3
"""Stream hash-bound packet55 routes through fixed-quota expert caches. No devices."""
import argparse
from collections import Counter, OrderedDict
import copy
import gzip
import hashlib
import heapq
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKET = HERE.parent
ROOT = HERE.parents[4]
LAYERS, EXPERTS, TOPK = 48, 512, 10
SIZES = (8, 12, 18, 24)
POLICIES = ('lru', 'lfu', 'static')


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def align(n):
    return (n + 4095) // 4096 * 4096


def packed(layer):
    return 2_329_600 if layer == 2 else 1_971_200


def allocation(quotas):
    slots = sum(quotas)
    slab = sum(q * align(packed(l)) for l, q in enumerate(quotas))
    metadata = align(LAYERS * EXPERTS * 4 + LAYERS * 64) + align(slots * 64)
    return dict(aligned_slot_bytes=slab, metadata_bytes=metadata,
                owned_bytes=slab + metadata, slots=slots,
                payload_bytes=sum(q * packed(l) for l, q in enumerate(quotas)))


def placement(limit):
    """Equal expert counts per layer, then ascending ordinary layers, then layer2."""
    q = [0] * LAYERS
    for count in range(1, EXPERTS + 1):
        candidate = [count] * LAYERS
        if allocation(candidate)['owned_bytes'] > limit:
            break
        q = candidate
    for l in [x for x in range(LAYERS) if x != 2] + [2]:
        if q[l] == EXPERTS:
            continue
        q[l] += 1
        if allocation(q)['owned_bytes'] > limit:
            q[l] -= 1
    return dict(limit_bytes=limit, quotas=q, **allocation(q))


class LayerCache:
    """LFU counts reset on admission; ties evict least recently used resident."""
    def __init__(self, policy, quota):
        self.policy, self.quota = policy, quota
        self.entries = OrderedDict()
        self.clock = 0
        self.heap = []

    def access(self, expert, protected=frozenset()):
        if self.policy == 'static':
            return expert in self.entries
        self.clock += 1
        hit = expert in self.entries
        if hit:
            count, _ = self.entries.pop(expert)
        else:
            count = 0
            if not self.quota:
                return False
            if len(self.entries) == self.quota:
                if self.policy == 'lru':
                    victim = next(e for e in self.entries if e not in protected)
                    del self.entries[victim]
                else:
                    deferred = []
                    while True:
                        n, t, victim = heapq.heappop(self.heap)
                        if self.entries.get(victim) == (n, t):
                            if victim in protected:
                                deferred.append((n, t, victim))
                                continue
                            del self.entries[victim]
                            break
                    for item in deferred:
                        heapq.heappush(self.heap, item)
        self.entries[expert] = (count + 1, self.clock)
        if self.policy == 'lfu':
            heapq.heappush(self.heap, (count + 1, self.clock, expert))
            if len(self.heap) > max(16, self.quota * 4):
                self.heap = [(n, t, e) for e, (n, t) in self.entries.items()]
                heapq.heapify(self.heap)
        return hit

    def route(self, experts):
        # Router exposes the complete selection at once. Resident selected slots
        # stay pinned through expert combine; earlier misses cannot evict them.
        protected = frozenset(experts)
        if self.policy != 'static':
            require(len(protected) <= self.quota, 'quota cannot hold a complete route')
        missing = sum(e not in self.entries for e in experts)
        for expert in experts:
            self.access(expert, protected)
        return missing


def new_cache(policy, quotas):
    return [LayerCache(policy, q) for q in quotas]


def no_benchmark_overlap(manifest, forbidden):
    banned_ids = {p['prompt_id'] for p in forbidden}
    for prompt in manifest['prompts']:
        require(prompt['prompt_id'] not in banned_ids, 'benchmark prompt ID in calibration')
        tokens = tuple(prompt['tokens'])
        for ref in forbidden:
            other = tuple(ref['tokens'])
            shorter, longer = sorted((tokens, other), key=len)
            require(not any(longer[i:i+len(shorter)] == shorter
                            for i in range(len(longer)-len(shorter)+1)),
                    'benchmark prompt token overlap in calibration')


def inputs(window, trace):
    manifest_path = window / 'calibration-manifest.json'
    summary_path = trace.with_suffix(trace.suffix + '.json')
    manifest = json.loads(manifest_path.read_text())
    summary = json.loads(summary_path.read_text())
    status = json.loads((window / 'window.json').read_text())
    require(status.get('passed') is True and status.get('device_executed') is True,
            'passed completed device window required')
    require(summary.get('schema') == 'packet55.route-conversion.v1' and summary.get('passed') is True,
            'passed converter receipt required')
    for field, path in [('manifest_sha256', manifest_path), ('output_sha256', trace),
                        ('window_sha256', window / 'window.json')]:
        require(summary.get(field) == sha(path), 'converter binding mismatch: ' + field)
    source = PACKET / 'route/calibration-prompts.json'
    require(manifest.get('source_sha256') == sha(source), 'calibration source binding mismatch')
    canonical = json.loads(source.read_text())
    require(manifest.get('benchmark_prompt_overlap') is False and manifest.get('benchmark_training') is False,
            'calibration overlap exclusion missing')
    require(manifest.get('token_cap') == 256, 'calibration cap must be 256')
    prompts = manifest['prompts']
    require(len(prompts) == 24 and len({p['prompt_id'] for p in prompts}) == 24,
            'all 24 unique calibration prompts required')
    require(Counter(p['split'] for p in prompts) == {'train': 12, 'test': 12}, '12/12 split required')
    require([p['prompt_id'] for p in prompts] == [p['prompt_id'] for p in canonical['prompts']],
            'calibration prompt order mismatch')
    for p, original in zip(prompts, canonical['prompts']):
        require(all(p.get(k) == v for k, v in original.items()), 'calibration source content mismatch')
        require(p['prompt_sha256'] == hashlib.sha256(p['text'].encode()).hexdigest(), 'prompt text hash')
        require(0 < p['prompt_tokens'] < 1024 and len(p['tokens']) == p['prompt_tokens'], 'prompt token count')
    suite_path = PACKET.parent / 'packet49c-round2/oracle/results/suite-manifest.json'
    suite = json.loads(suite_path.read_text())
    forbidden = []
    for p in suite['prompts']:
        path = ROOT / p['input_bundle'] / 'tokens.txt'
        require(sha(path) == p['input_bundle_hashes']['tokens.txt'], 'benchmark input binding')
        forbidden.append(dict(prompt_id=p['prompt_id'], tokens=list(map(int, path.read_text().split()))))
    no_benchmark_overlap(manifest, forbidden)
    requests = summary['requests']
    require([r['prompt_id'] for r in requests] == [p['prompt_id'] for p in prompts], 'request coverage/order')
    for p, r in zip(prompts, requests):
        result_path = window / 'requests' / p['prompt_id'] / 'result.json'
        require(sha(result_path) == r['result_sha256'], 'request result binding')
        result = json.loads(result_path.read_text())
        require(result.get('passed') is True and result.get('completed') is True, 'incomplete request')
        require(result['prompt_id'] == p['prompt_id'] and r['split'] == p['split'], 'request identity')
        require(result['generated_tokens'] == r['generated_tokens'] and 1 <= r['generated_tokens'] <= 256,
                'generated-token binding')
        for rank in (0, 1):
            path = result_path.parent / f'rank{rank}/routes.p55bin'
            require(sha(path) == r['binary_sha256'][str(rank)], 'native route binding')
    require(summary['records'] == sum(r['records'] for r in requests), 'record-count receipt')
    return manifest, summary, dict(calibration_manifest_sha256=sha(manifest_path),
        trace_sha256=sha(trace), conversion_receipt_sha256=sha(summary_path),
        benchmark_manifest_sha256=sha(suite_path), calibration_source_sha256=sha(source))


def records(trace, manifest, summary):
    """Validate incrementally; at most one prompt's coverage sets in memory."""
    with gzip.open(trace, 'rt', encoding='utf-8') as f:
        for p, receipt in zip(manifest['prompts'], summary['requests']):
            coverage = [set() for _ in range(LAYERS)]
            draft = set()
            previous = (-1, -1, -1)
            sequences = [-1, -1]
            for _ in range(receipt['records']):
                raw = f.readline()
                require(bool(raw), 'truncated converted routes')
                row = json.loads(raw)
                require(row['prompt_id'] == p['prompt_id'] and row['split'] == p['split'], 'route prompt/split')
                rank, role, layer, pos = row['rank'], row['role'], row['layer'], row['position']
                require(rank in (0, 1) and role in ('target', 'draft'), 'route role/rank')
                require(isinstance(pos, int) and 0 <= pos < 4096, 'route position')
                if role == 'target':
                    require(0 <= layer < LAYERS and rank == (0 if layer < 23 else 1), 'target owner/layer')
                    coverage[layer].add(pos)
                else:
                    require(layer == 0 and rank == 1, 'draft owner/layer')
                    draft.add(pos)
                expected_phase = 'decode' if pos + (role == 'draft') >= p['prompt_tokens'] - 1 else 'prefill'
                require(row['phase'] == expected_phase, 'route phase')
                require(len(row['ids']) == TOPK and len(set(row['ids'])) == TOPK
                        and all(type(e) is int and 0 <= e < EXPERTS for e in row['ids']), 'route IDs')
                require(len(row['weights']) == TOPK and all(math.isfinite(w) and w >= 0 for w in row['weights'])
                        and math.isclose(sum(row['weights']), 1, abs_tol=2e-5), 'route weights')
                key = (row['monotonic_ns'], rank, row['sequence'])
                require(key >= previous and row['sequence'] > sequences[rank], 'route observation order')
                previous, sequences[rank] = key, row['sequence']
                yield row
            expected = set(range(p['prompt_tokens'] + receipt['generated_tokens'] - 1))
            require(all(expected <= observed for observed in coverage), 'incomplete target coverage')
            require(set(range(max(0, len(expected)-1))) <= draft, 'incomplete draft coverage')
        require(not f.readline(), 'unreceipted trailing records')


def quantiles(values):
    values = sorted(values)
    if not values:
        return dict(count=0, mean=None, p50=None, p95=None, maximum=None)
    return dict(count=len(values), mean=sum(values)/len(values),
                p50=values[math.ceil(.5*len(values))-1],
                p95=values[math.ceil(.95*len(values))-1], maximum=values[-1])


def stat():
    return dict(route_visits=0, requested_bytes=0, hit_bytes=0, miss_bytes=0,
                missing_experts=0, miss_count_histogram=Counter())


def update(s, miss, layer):
    s['route_visits'] += 1
    s['requested_bytes'] += TOPK * packed(layer)
    s['hit_bytes'] += (TOPK-miss) * packed(layer)
    s['miss_bytes'] += miss * packed(layer)
    s['missing_experts'] += miss
    s['miss_count_histogram'][miss] += 1


def finish(s):
    return dict(**s, byte_hit_rate=s['hit_bytes']/s['requested_bytes'] if s['requested_bytes'] else None,
                miss_bytes_per_layer_visit=s['miss_bytes']/s['route_visits'] if s['route_visits'] else None)


def analyze(trace, manifest, summary, details_path):
    layouts = {size: placement(size * 1_000_000_000) for size in SIZES}
    caches = {(size, policy): new_cache(policy, layouts[size]['quotas'])
              for size in SIZES for policy in POLICIES}
    counts = [Counter() for _ in range(LAYERS)]
    # A first streaming pass trains only. No held-out record updates these counts.
    for row in records(trace, manifest, summary):
        if row['split'] != 'train' or row['role'] != 'target':
            continue
        counts[row['layer']].update(row['ids'])
        for (size, policy), cache in caches.items():
            if policy != 'static':
                cache[row['layer']].route(row['ids'])
    for (size, policy), cache in caches.items():
        if policy == 'static':
            for layer, q in enumerate(layouts[size]['quotas']):
                experts = sorted(range(EXPERTS), key=lambda e: (-counts[layer][e], e))[:q]
                cache[layer].entries = OrderedDict((e, (counts[layer][e], 0)) for e in experts)
    trained = caches
    initial = {key: sum(len(c.entries) * packed(l) for l, c in enumerate(cache))
               for key, cache in trained.items()}
    totals = {key: {phase: [stat() for _ in range(LAYERS)] for phase in ('prefill', 'decode')}
              for key in trained}
    positions = {key: {} for key in trained}
    draft_counts = Counter()
    prompt = None
    test_tokens = sum(r['generated_tokens'] for r in summary['requests'] if r['split'] == 'test')
    for row in records(trace, manifest, summary):
        if row['split'] != 'test':
            continue
        if prompt != row['prompt_id']:
            prompt = row['prompt_id']
            caches = copy.deepcopy(trained)
        phase, layer = row['phase'], row['layer']
        if row['role'] == 'draft':
            draft_counts[phase] += 1
            continue
        for key, cache in caches.items():
            misses = cache[layer].route(row['ids'])
            update(totals[key][phase][layer], misses, layer)
            poskey = (prompt, phase, row['position'])
            dest = positions[key].setdefault(poskey, dict(route_visits=0, miss_bytes=0, missing_experts=0))
            dest['route_visits'] += 1
            dest['miss_bytes'] += misses * packed(layer)
            dest['missing_experts'] += misses
    reports = []
    with gzip.open(details_path, 'wt', encoding='utf-8', compresslevel=6) as detail:
        for key, byphase in totals.items():
            size, policy = key
            phases = {}
            for phase, layers in byphase.items():
                overall = stat()
                for s in layers:
                    for k, v in s.items():
                        if k == 'miss_count_histogram':
                            overall[k].update(v)
                        else:
                            overall[k] += v
                posvalues = [p['miss_bytes'] for (_, ph, _), p in positions[key].items() if ph == phase]
                phases[phase] = dict(overall=finish(overall), layers=[dict(layer=l, **finish(s)) for l, s in enumerate(layers)],
                    miss_bytes_per_observed_position=quantiles(posvalues),
                    miss_bytes_per_generated_token=overall['miss_bytes']/test_tokens if phase == 'decode' else None)
            startup = initial[key] * sum(r['split'] == 'test' for r in summary['requests'])
            demand = sum(p['overall']['miss_bytes'] for p in phases.values())
            reports.append(dict(cache_GB=size, policy=policy, layout=layouts[size], phases=phases,
                initial_cache_load_packed_bytes_per_prompt=initial[key],
                initial_cache_load_packed_bytes_all_test_prompts=startup,
                prefill_plus_decode_miss_bytes=demand,
                cold_start_transfer_demand_bytes_including_initial_load=startup+demand,
                cold_start_transfer_bytes_per_generated_token=(startup+demand)/test_tokens,
                trained_resident_counts_by_layer=[len(c.entries) for c in trained[key]]))
            detail.write(json.dumps(dict(record_type='trained_cache', cache_GB=size, policy=policy,
                residents_by_layer=[list(c.entries) for c in trained[key]]), separators=(',', ':')) + '\n')
            for (pid, phase, pos), value in positions[key].items():
                detail.write(json.dumps(dict(record_type='observed_position', cache_GB=size, policy=policy, prompt_id=pid, phase=phase,
                    position=pos, **value), separators=(',', ':')) + '\n')
    return dict(schema='packet55.route-locality.v1', passed=True, device_executed=False,
        measured_token_speed=False, policy_scope='fixed per-layer quota; no cross-layer eviction',
        replay_order='converter host monotonic timestamp; per-layer observed rank order',
        training='all target prefill and decode records of 12 train prompts; no test updates to initial state',
        evaluation='reset trained cache at each test prompt; charge preload, process prefill then decode; all speculative visits charged',
        percentile_definition='nearest-rank actual observation; no interpolation',
        draft=dict(residency='complete draft resident outside target cache', target_cache_demand_bytes=0,
                   route_visits_by_phase=dict(draft_counts), selected_expert_evaluations=sum(draft_counts.values())*TOPK),
        generated_tokens_test=test_tokens,
        requested_scope_complete=all(r['generated_tokens'] == 256 for r in summary['requests']),
        requested_scope='24 prompts each generating 256 tokens; early EOS remains partial evidence',
        ended_early_test_prompts=[r['prompt_id'] for r in summary['requests'] if r['split']=='test' and r['generated_tokens']<256],
        position_definition='observed target position ID per prompt/phase; repeated speculative visits add demand, never disappear',
        per_position_detail_sha256=sha(details_path), per_position_detail=str(details_path), results=reports)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--window', type=Path, required=True)
    p.add_argument('--trace', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--positions', type=Path, required=True)
    args = p.parse_args()
    require(not args.output.exists() and not args.positions.exists(), 'new output paths required')
    manifest, summary, bindings = inputs(args.window, args.trace)
    result = analyze(args.trace, manifest, summary, args.positions)
    result['bindings'] = bindings
    result['analyzer_sha256'] = sha(Path(__file__))
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=True, output=str(args.output), output_sha256=sha(args.output),
                         configurations=len(result['results']), test_generated_tokens=result['generated_tokens_test'])))


if __name__ == '__main__':
    main()
