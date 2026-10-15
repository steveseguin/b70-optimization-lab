"""Read retained metadata only; python3 -B; no model bytes or device execution.

Print reproducible byte floors and explicitly hypothetical structural forecasts.
No output file is opened by this helper. All throughput projections are planning
numbers, never replacement benchmark results.
"""
import collections
import hashlib
import json
import math
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / 'experiments/own-xpu-runtime/stage2/packet45-merged3'
RUN = P / 'build/speed6-c4096-dr1-s23-cards01-gpu/WS128'
INPUTS = {}


def readonly(event, args):
    if event in ('os.remove', 'os.rename', 'os.mkdir', 'os.rmdir', 'subprocess.Popen'):
        raise RuntimeError('read-only analysis')
    if event == 'open':
        _, mode, flags = args
        if (mode and any(c in mode for c in 'wax+')) or flags & (1 | 2 | 64 | 512 | 1024):
            raise RuntimeError('read-only analysis')


sys.addaudithook(readonly)


def read(path):
    raw = path.read_bytes()
    INPUTS[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
    return raw


def load(path):
    return json.loads(read(path))


def weights():
    meta = {}
    for line in read(P/'build/input/plan.tsv').decode().splitlines():
        x = line.split()
        if len(x) >= 10:
            meta[x[1]] = (int(x[3]), list(map(int, x[9:])))
    result = []
    for rank in (0, 1):
        plan = load(RUN/f'run/ranks/rank{rank}/plan.json')
        groups = collections.defaultdict(lambda: dict(bytes=0, dot_flops=0))
        for tensor in plan['tensor_owners']:
            category = tensor['component']
            if category in ('embedding', 'ple_lookup'):
                continue  # host row lookups, not whole-table device reads
            typ, dims = meta[tensor['name']]
            elements = math.prod(dims)
            numerator, denominator = (10, 512) if category == 'routed_experts' else (1, 1)
            size = tensor['stored_bytes']
            if tensor.get('variant', '').startswith('expanded'):
                group = 16 if typ in (22, 11, 14) else 32
                size = elements + elements // group * 4
            assert size * numerator % denominator == 0
            groups[category]['bytes'] += size * numerator // denominator
            groups[category]['dot_flops'] += (2 * elements * numerator // denominator
                                               if len(dims) >= 2 else 0)
        result.append(dict(classes=dict(sorted(groups.items())),
                           bytes=sum(v['bytes'] for v in groups.values()),
                           dot_flops=sum(v['dot_flops'] for v in groups.values())))
    assert [r['bytes'] for r in result] == [2740419328, 3730572032]
    # Private MTP weights are BF16/F32, except its unchanged INT8 experts.
    census = load(RUN/'run/ranks/rank1/census.json')
    draft = 0
    for a in census['allocations']:
        if a['live'] and a['label'].startswith('card0:draft:weight:'):
            draft += a['bytes'] * 10 // 512 if '_exps.weight' in a['label'] else a['bytes']
    draft += result[1]['classes']['target_head']['bytes']  # alias, another read
    assert draft == 1037289472
    return result, draft


def bandwidth():
    source = ROOT/'experiments/own-xpu-runtime/stage2/packet7-kopt2/receipts-card3-20261011/ceiling/native.json'
    x = load(source)
    rows = []
    for r in x['results']:
        assert r['exact']
        ns = st.median(e['end_ns']-e['start_ns'] for e in r['events'])
        rows.append(dict(variant=r['variant'], bytes=r['bytes'], salt=r['salt'],
                         median_ns=ns, payload_GBs=r['bytes']/ns))
    return rows


def kv(n):
    selected = 4 * min(n//4, 512) + n%4
    return 2048*selected + 256*(n//4)


def class_rate(rows):
    classes = sorted({r['cls'] for r in rows})
    return st.median(st.median(r['rate'] for r in rows if r['cls'] == c) for c in classes)


def receipts(target, draft_bytes):
    window = load(RUN/'window.json')
    assert window['passed'] and window['qualifying'] and not window.get('diagnostic_unsealed')
    requests = []
    full = collections.Counter()
    primary = collections.Counter()
    transitions = collections.Counter()
    transitions99 = collections.Counter()
    run_lengths = collections.Counter()
    sequences = {}
    modeled = collections.defaultdict(list)
    for f in sorted((RUN/'run/repeat-1').glob('*/receipt.json')):
        r = load(f)
        assert r['passed'] and r['oracle_check']['passed'] and len(r['tokens']) == 128
        guesses = [bool(g['hit']) for g in r['guess_rows']]
        sequences[r['prompt_id']] = [(g['position'], g['guess'], g['actual'], g['hit'])
                                      for g in r['guess_rows']]
        assert len(guesses) == 127
        full.update(guesses)
        transitions.update('HM'[not a]+'HM'[not b] for a, b in zip(guesses, guesses[1:]))
        streak = 0
        for hit in guesses + [False]:
            if hit:
                streak += 1
            elif streak:
                run_lengths[streak] += 1
                streak = 0
        stamps = r['generated_token_completion_timestamps']
        rows = [d for d in r['draft_rows'] if d.get('hit') is not None and 'cycle_ms' in d
                and stamps[0] <= d['target_completed_monotonic'] < stamps[99]]
        assert len(rows) == 99
        primary.update(bool(d['hit']) for d in rows)
        hs = [bool(d['hit']) for d in rows]
        transitions99.update('HM'[not a]+'HM'[not b] for a, b in zip(hs, hs[1:]))
        requests.append(dict(prompt=r['prompt_id'], cls=r['prompt_class'],
                             rate=99/(stamps[99]-stamps[0]), hits=sum(hs)))
        # A read/write lower bound, NOT a complete instruction/launch roofline.
        # Actual indexed history length, not the allocated 4096-row capacity.
        for gb in (590, 600):
            durations = []
            for d in rows:
                n = d['position']+1
                state_rw = 2*18*(1572864+61440)
                a = (target[0]['bytes']+state_rw+5*kv(n))/(gb*1e6)
                b = (target[1]['bytes']+state_rw+7*kv(n))/(gb*1e6)
                draft = (draft_bytes+kv(n))/(gb*1e6)
                # Real payload, not masked padded-grid slots. Copy payload GB/s.
                capture = 48332354/(270*1e6)
                restore = 18730562/(270*1e6)
                front = draft if d['hit'] else max(draft, a+restore)
                durations.append(front+max(a+capture, b))
            modeled[f'memory_floor_{gb}'].append(dict(cls=r['prompt_class'], rate=99000/sum(durations)))
    assert len(requests) == 12
    for repeat in (P/'build/speed6-c4096-dr1-s23-cards01-gpu/WS128-r2',
                   P/'build/speed6-c4096-dr1-s23-cards23-gpu/WS128'):
        window = load(repeat/'window.json')
        assert window['passed'] and window['qualifying'] and not window.get('diagnostic_unsealed')
        fs = sorted((repeat/'run/repeat-1').glob('*/receipt.json'))
        assert len(fs) == 12
        for f in fs:
            r = load(f)
            assert r['passed'] and r['oracle_check']['passed']
            assert sequences[r['prompt_id']] == [(g['position'], g['guess'], g['actual'], g['hit'])
                                                  for g in r['guess_rows']]
    p = full[True]/sum(full.values())
    q = transitions['HH']/(transitions['HH']+transitions['HM'])
    baseline = class_rate(requests)
    d = 2.8
    return dict(requests=requests, measured_class_balanced=baseline,
                full=dict(hits=full[True], misses=full[False], p=p),
                primary99=dict(hits=primary[True], misses=primary[False]),
                transitions=dict(transitions), transitions99=dict(transitions99),
                conditional_one_step_proxy=q, maximal_hit_runs=dict(sorted(run_lengths.items())),
                repeat_guess_sequence_checks=24,
                optimistic_memory_only_ceiling={k:class_rate(v) for k,v in modeled.items()},
                block_model=dict(D_ms=d, E_two_positions=1+p, E_three_positions_proxy=1+p+p*q,
                    max_T2_ms=(1+p)*1000/baseline-d,
                    max_T3_ms_proxy=(1+p+p*q)*1000/baseline-2*d,
                    two_position_scenarios=[dict(T2_ms=t, rate=1000*(1+p)/(t+d)) for t in (35, 38, 40, 42, 45, 50)],
                    three_position_scenarios=[dict(T3_ms=t,
                        q_required=((t+2*d)*baseline/1000-1-p)/p,
                        rate_at_proxy=1000*(1+p+p*q)/(t+2*d)) for t in (45, 50, 55, 60)]))


if __name__ == '__main__':
    targets, draft = weights()
    output = dict(target_weights=targets, draft_weight_bytes=draft, bandwidth=bandwidth(),
                  qsa_unique_bytes={n:kv(n) for n in (122, 4096)},
                  analysis=receipts(targets, draft))
    # T=37.1*(1-f/2)+L is an Amdahl sensitivity, not a TP measurement.
    output['tp_target_only_sensitivity'] = [dict(parallel_fraction=f, overhead_ms=l,
        token_ms=37.1*(1-f/2)+l, rate=1000/(37.1*(1-f/2)+l))
        for f in (.7, .8, .85, .9) for l in (2, 3, 5)]
    output['half_byte_floors_ms_at_600'] = dict(
        rank0=(targets[0]['bytes']+2*18*(1572864+61440)+5*kv(122))/600e6,
        rank1=(targets[1]['bytes']+2*18*(1572864+61440)+7*kv(122))/600e6,
        draft=(draft+kv(122))/600e6,
        capture=48332354/270e6, restore=18730562/270e6)
    output['input_sha256'] = INPUTS
    print(json.dumps(output, indent=2, sort_keys=True))
