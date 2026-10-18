#!/usr/bin/env python3
"""CPU-only conditional dual-guess cost model. Writes only this packet."""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
STAGE = HERE.parent
PINS = {}


def read(path):
    path = Path(path)
    raw = path.read_bytes()
    PINS[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
    return raw


def js(path):
    return json.loads(read(path))


def paths(c):
    # Exact packet85 depth-one equations; one token per emission interval.
    return (c['D'] + max(c['Bh'], c['A'] + c['spec_offset']) + c['Gh'],
            max(c['D'], c['R'] + c['C']) + max(c['Bm'], c['A'] + c['spec_offset']) + c['Gm'])


def policies():
    return ([('never', 0.0)] + [('margin', x / 8) for x in range(129)]
            + [('margin', 32.0), ('margin', 64.0)]
            + [('top4_probability', x / 100) for x in range(25, 102)]
            + [('always', 0.0)])


def flag(row, policy):
    feature, theta = policy
    return feature == 'always' or (feature != 'never' and row[feature] < theta)


def counts(rows, policy):
    marked = [r for r in rows if flag(r, policy)]
    misses = sum(not r['hit'] for r in marked)
    rescues = sum(r['rescuable'] for r in marked)
    return dict(positions=len(rows), flagged=len(marked), flagged_fraction=len(marked)/len(rows),
                top1_hits=sum(r['hit'] for r in rows), top1_misses=sum(not r['hit'] for r in rows),
                flagged_misses=misses, flagged_rescues=rescues,
                flagged_miss_fraction=misses/len(marked) if marked else None,
                rescue_fraction_of_flagged=rescues/len(marked) if marked else None,
                rescue_fraction_of_flagged_misses=rescues/misses if misses else None)


def edges(rows):
    by_prompt = defaultdict(dict)
    for r in rows:
        by_prompt[r['prompt']][r['index']] = r
    return [(by_prompt[p][i], by_prompt[p][i+1]) for p in sorted(by_prompt)
            for i in sorted(by_prompt[p]) if i+1 in by_prompt[p]]


def evaluate(rows, policy, c, cost):
    intervals = edges(rows)
    baseline = []
    candidate = []
    groups = defaultdict(list)
    for current, following in intervals:
        rescued = flag(current, policy) and current['rescuable']
        kind = 'rescued_miss' if rescued else 'hit' if current['hit'] else 'unrescued_miss'
        successful = current['hit'] or rescued
        d = c['D'] + (cost['top2_ms'] if policy[0] != 'never' else 0)
        ready = d if successful else max(d, c['R'] + c['C'])
        # Conservatively expose selection rather than assuming a free bank swap
        # or hiding it behind D. Already-captured row0 is the existing hit path.
        if rescued:
            ready += cost['select_ms']
        b = c['Bh'] if successful else c['Bm']
        a = c['A'] + cost['extra_half_ms'] * flag(following, policy)
        gap = c['Gh'] if successful else c['Gm']
        elapsed = ready + max(b, a + c['spec_offset']) + gap
        candidate.append(elapsed)
        baseline.append(paths(c)[0 if current['hit'] else 1])
        groups[kind + ('_next_dual' if flag(following, policy) else '_next_single')].append(elapsed)
    base = statistics.mean(baseline)
    value = statistics.mean(candidate)
    delta = value-base
    anchor_ms = 1000/55.69
    return dict(**counts(rows, policy), intervals=len(intervals),
                charged_dual_intervals=sum(flag(b, policy) for _, b in intervals),
                credited_rescues=sum(flag(a, policy) and a['rescuable'] for a, _ in intervals),
                baseline_ms=base, candidate_ms=value, delta_ms=delta,
                baseline_raw_tok_s=1000/base, candidate_raw_tok_s=1000/value,
                raw_gain_percent=100*(base/value-1),
                anchor_additive_tok_s=1000/(anchor_ms+delta),
                anchor_additive_gain_percent=100*(anchor_ms/(anchor_ms+delta)-1),
                anchor_multiplicative_tok_s=55.69*base/value,
                conditional_cycles={k:dict(count=len(v),mean_ms=statistics.mean(v)) for k,v in sorted(groups.items())})


def fit(rows, c, cost, require_active=False):
    scored = [(evaluate(rows, p, c, cost), p) for p in policies()
              if not require_active or any(flag(r, p) for r in rows)]
    result, policy = min(scored, key=lambda pair:(pair[0]['candidate_ms'], pair[0]['flagged'],
                        {'never':0,'margin':1,'top4_probability':2,'always':3}[pair[1][0]], pair[1][1]))
    return dict(feature=policy[0], theta=policy[1], train=result), policy


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    acceptance = js(STAGE/'packet31-mtp-acceptance/acceptance.json')
    p85 = js(STAGE/'packet85-critical-path/model.json')
    c = p85['baseline']['components_ms']
    assert math.isclose(paths(c)[0], p85['baseline']['predicted_hit_ms'], abs_tol=1e-12)
    assert math.isclose(paths(c)[1], p85['baseline']['predicted_miss_ms'], abs_tol=1e-12)
    attr = js(STAGE/'screen/v4-lanes/evidence/packet77-attribution-B-a/run/attribution-summary.json')
    rollback = js(STAGE/'packet88-miss-path/attribution.json')['rollback']
    header = js(STAGE/'packet72-occupancy/header-census.json')['tensors']
    memory = js(STAGE/'packet84-record-bundle/memory-plan.json')
    full_shape = js(STAGE/'packet84-record-bundle/evidence/full-shape.json')
    record_view = 'production--hc-wide--wide64--ordered--production--production--rec-parallel--production'
    record_r0 = [r for r in full_shape['runs'] if r['view']==record_view
                 and r['placement']=='1' and r['rank']==0]
    assert len(record_r0)==1 and record_r0[0]['passed']
    census_path = STAGE/'packet84-record-bundle/evidence/census.json-1d302e63c78658adcc04bb091964842539f48cb93a56d5bb72a1a71978547b83.gz'
    census = json.loads(gzip.decompress(read(census_path)))
    assert record_r0[0]['census']==str(census_path.relative_to(ROOT))
    assert record_r0[0]['census_sha256']==PINS[str(census_path.relative_to(ROOT))]
    # Pin supporting identities and negative history without importing runtime code.
    for name in ('packet85-critical-path/model.py', 'packet85-critical-path/MODEL.md',
                 'packet31-mtp-acceptance/README.md', 'packet31-mtp-acceptance/analyze.py',
                 'packet71c-depth2-engine/DO-NOT-REPEAT.md', 'packet79-draft-rank0/DO-NOT-REPEAT.md',
                 'packet87-slack-model/DECISION.md', 'packet88-miss-path/MISS.md',
                 'packet68c-m2-from-production/README.md', 'packet68c-m2-from-production/production_rows.hpp',
                 'packet68c-m2-from-production/production_expert_chains.hpp',
                 'packet84-record-bundle/rank.hpp', 'packet84-record-bundle/mtp.hpp',
                 'packet84-record-bundle/native_controller.hpp', 'packet84-record-bundle/strict_snapshot.hpp',
                 'packet77-attribution/report.py', 'packet77-attribution/byte_formulas.py'):
        read(STAGE/name)
    read(ROOT/'notes/2026-10-17-own-runtime-packet77.md')
    read(HERE/'PLAN.md')
    read(HERE/'model.py')

    rows = []
    for item in acceptance['positions']:
        source = item['sources']['mtp_fp8_iq3']
        logits = source['top4_logits']
        margin = logits[0]-logits[1]
        assert margin == source['draft_margin'] and margin >= 0
        assert source['draft_token'] == source['top4'][0]
        hit = item['target_token'] == source['top4'][0]
        assert hit == source['hit']
        rows.append(dict(prompt=item['prompt'],index=item['generated_index'],
                         margin=margin,top4_probability=1/sum(math.exp(x-logits[0]) for x in logits),
                         hit=hit,rescuable=item['target_token']==source['top4'][1],
                         top4_hit=item['target_token'] in source['top4']))
    assert len(rows)==len({(r['prompt'],r['index']) for r in rows})==256
    assert sum(r['hit'] for r in rows)==198
    assert sum(r['rescuable'] for r in rows)==28
    assert sum(r['top4_hit'] for r in rows)==245

    classes = defaultdict(lambda:dict(m1_ms=0.0,weight_bytes=0.0,other_read_bytes=0.0))
    for site in attr['sites']:
        if site['rank'] != 0:
            continue
        row = classes[site['site']]
        row['m1_ms'] += site['estimated_us_per_half']/1000
        row['weight_bytes'] += site['runtime_weight_read_bytes']*site['occurrences_per_half']
        row['other_read_bytes'] += site['activation_state_read_bytes']*site['occurrences_per_half']
    k,n = 10,512
    overlap = k*k/n
    union = 2*k-overlap
    expert_sites = {'expsgate','expsdown'}
    extras = dict(favorable=0.0, partial_sharing=0.0, conservative=0.0)
    for site,row in sorted(classes.items()):
        t,w = row['m1_ms'],row['weight_bytes']
        if site in expert_sites:
            # Favorable union scaling gives full latency credit for shared routes.
            low = t*(union/k-1)
            mid = low
            high = t  # independent FP32 chains still double, even on shared weights
            mode = 'random expert union; conservative doubles arithmetic'
        elif site == 'gdn.recurrence' or w == 0:
            low = mid = high = t
            mode = 'independent state/activation row work doubles'
        else:
            low = 0.0
            mid = max(0.0,t-w/(555*1e6))
            high = t
            mode = 'weights read once ideally; partial residual or conservative doubled work'
        row.update(favorable_extra_ms=low,partial_sharing_extra_ms=mid,
                   conservative_extra_ms=high,assumption=mode)
        for key,amount in zip(extras,(low,mid,high)):
            extras[key]+=amount
    capture = rollback['capture_payload_bytes']
    restore = rollback['restore_payload_bytes']
    # 555 GB/s read+write floor is optimistic; R/bytes is an explicitly pessimistic
    # whole-command proxy, not an independently measured memcpy bandwidth.
    copy_floor = 2*capture/(555*1e6)
    copy_proxy = c['R']*capture/restore
    costs = {
        'favorable':dict(extra_half_ms=extras['favorable']+copy_floor,copy_ms=copy_floor,
                        top2_ms=0.0,select_ms=0.0),
        'partial_sharing':dict(extra_half_ms=extras['partial_sharing']+copy_proxy,copy_ms=copy_proxy,
                              top2_ms=0.023,select_ms=c['R']),
        'conservative':dict(extra_half_ms=extras['conservative']+copy_proxy+0.1,copy_ms=copy_proxy,
                           top2_ms=0.05,select_ms=copy_proxy),
        'serial_m1':dict(extra_half_ms=c['A']+copy_proxy,copy_ms=copy_proxy,
                         top2_ms=0.05,select_ms=copy_proxy)}
    # Current hit costs can be kept exactly by taking never: no top2 work is enabled.
    for cost in costs.values():
        cost['m2_half_ms']=c['A']+cost['extra_half_ms']
        assert evaluate(rows,('never',0),c,cost)['delta_ms']==0

    actual_expert_bytes = sum(t['bytes']*k/n for name,t in header.items()
        if name.startswith('blk.') and int(name.split('.')[1])<24
        and name.endswith(('ffn_gate_exps.weight','ffn_up_exps.weight','ffn_down_exps.weight')))
    assert actual_expert_bytes>0
    r0 = memory['placements']['1']['capacities']['4096']['ranks'][0]
    categories = Counter()
    for allocation in census['allocations']:
        if allocation['live'] and allocation['memory']=='device':
            categories[allocation['category']]+=allocation['bytes']
    assert sum(categories.values()) == r0['arena_device_bytes']
    # Upper reservation: duplicate all nonweights, including full KV capacity,
    # both GDN banks, workspace and private snapshot+descriptors. Share weights.
    extra_allocation = sum(v for k,v in categories.items() if k!='weights')
    memory_result = dict(context_capacity=4096,record_view=record_view,record_rank0_full_shape=record_r0[0],
        rank0_baseline=r0,census_categories=dict(categories),
        additional_all_nonweight_bytes=extra_allocation,
        additional_single_recurrence_bank_bytes=rollback['omitted_spare_bank_bytes'],
        additional_capture_payload_bytes=capture,
        new_arena_bytes=r0['arena_device_bytes']+extra_allocation,
        remaining_arena_bytes=r0['arena_headroom_bytes']-extra_allocation,
        remaining_physical_free_bytes=r0['free_with_mtp_bytes']-extra_allocation,
        arena_limit_bytes=memory['arena_limit_bytes'],minimum_free_bytes=memory['minimum_free_bytes'],
        reservation_fits=(extra_allocation<=r0['arena_headroom_bytes'] and
                          r0['free_with_mtp_bytes']-extra_allocation>=memory['minimum_free_bytes']),
        is_candidate_startup_or_device_test=False)

    train_names = {'incident-retrospective','code-review'}
    train = [r for r in rows if r['prompt'] in train_names]
    test = [r for r in rows if r['prompt'] not in train_names]
    scenarios = {}
    for name,cost in costs.items():
        trained,policy = fit(train,c,cost)
        active,active_policy = fit(train,c,cost,require_active=True)
        folds = []
        for prompt in sorted({r['prompt'] for r in rows}):
            fitted,p = fit([r for r in rows if r['prompt']!=prompt],c,cost)
            folds.append(dict(test_prompt=prompt,selection=fitted,
                              test=evaluate([r for r in rows if r['prompt']==prompt],p,c,cost)))
        temporal,p = fit([r for r in rows if r['index']<32],c,cost)
        best_all,all_policy = fit(rows,c,cost)
        scenarios[name] = dict(cost=cost,selection=trained,test=evaluate(test,policy,c,cost),
            best_active_train_selection=active,best_active_test=evaluate(test,active_policy,c,cost),
            leave_one_prompt_out=folds,temporal_selection=temporal,
            temporal_test=evaluate([r for r in rows if r['index']>=32],p,c,cost),
            optimistic_in_sample_best=best_all,always=evaluate(rows,('always',0),c,cost),
            cycle_table={kind+('_next_dual' if dual else '_next_single'):
                ((c['D']+cost['top2_ms']+(cost['select_ms'] if kind=='rescued_miss' else 0))
                 if kind!='unrescued_miss' else max(c['D']+cost['top2_ms'],c['R']+c['C']))
                +max(c['Bm'] if kind=='unrescued_miss' else c['Bh'],
                     c['A']+cost['extra_half_ms']*dual+c['spec_offset'])
                +(c['Gm'] if kind=='unrescued_miss' else c['Gh'])
                for kind in ('hit','rescued_miss','unrescued_miss') for dual in (False,True)})

    # Full fixed-grid counts and matched train/test predictions for every theta.
    sweep = []
    def compact(value):
        return {k:value[k] for k in ('intervals','charged_dual_intervals','credited_rescues',
            'candidate_ms','delta_ms','candidate_raw_tok_s','anchor_additive_tok_s',
            'anchor_additive_gain_percent','anchor_multiplicative_tok_s')}
    for policy in policies():
        sweep.append(dict(feature=policy[0],theta=policy[1],all=counts(rows,policy),
            train=counts(train,policy),test=counts(test,policy),
            predictions={name:dict(train=compact(evaluate(train,policy,c,cost)),test=compact(evaluate(test,policy,c,cost)))
                         for name,cost in costs.items()}))
    sensitivity = []
    for extra in (0,1,2,3,4,5,6,7,8,10,12,14):
        cost=dict(extra_half_ms=extra,top2_ms=0.05,select_ms=copy_proxy)
        selected,policy=fit(train,c,cost)
        sensitivity.append(dict(extra_half_ms=extra,selection=selected,test=evaluate(test,policy,c,cost)))
    chosen=scenarios['conservative']
    speed_pass=chosen['test']['anchor_additive_gain_percent']>=1.5
    # Tiny dependency checks expose the easy off-by-one error: a flag costs in
    # the preceding interval; its rescue changes readiness in the following one.
    synthetic = [dict(prompt='check',index=i,margin=1.0,top4_probability=0.7,
                      hit=True,rescuable=False) for i in range(3)]
    synthetic[1].update(margin=0.0,hit=False,rescuable=True)
    probe_cost=dict(extra_half_ms=4.0,top2_ms=0.0,select_ms=0.0)
    probe=evaluate(synthetic,('margin',0.125),c,probe_cost)
    h,m=paths(c)
    expected=(h+max(0,c['A']+4+c['spec_offset']-c['Bh'])+h)/2
    assert math.isclose(probe['candidate_ms'],expected,abs_tol=1e-12)
    assert probe['charged_dual_intervals']==probe['credited_rescues']==1
    assert len(edges(rows))==252 and len(edges(train))==len(edges(test))==126
    result=dict(schema='own-runtime.packet96.dual-guess-model.v1',device_executed=False,
        submission_eligible=False,seal_ready=False,decision='close',
        conservative_speed_gate_passed=speed_pass,required_gain_percent=1.5,
        target_anchor_tok_s=55.69,required_anchor_tok_s=55.69*1.015,
        data=dict(unique_positions=len(rows),prompts=4,top1_hits=198,top2_hits=226,top4_hits=245,
                  top1_rate=198/256,top2_rate=226/256,top4_rate=245/256,
                  primary_train_prompts=sorted(train_names),primary_test_prompts=sorted({r['prompt'] for r in test}),
                  target_arithmetic='packet31 iq3-p17-detmath-v2; packet84 iq3-p49-split32-v1',
                  full_vocabulary_probability_available=False,production_draft_equivalence_proved=False),
        baseline_components_ms=c,baseline_hit_miss_ms=paths(c),
        costs=dict(classes=dict(sorted(classes.items())),class_sum_ms=sum(r['m1_ms'] for r in classes.values()),
                   capture_payload_bytes=capture,restore_payload_bytes=restore,copy_floor_ms=copy_floor,
                   copy_whole_command_proxy_ms=copy_proxy,independent_copy_device_timing_available=False),
        experts=dict(choices_per_row=k,total_experts=n,expected_overlap=overlap,expected_union=union,
                     union_ratio=union/k,actual_rank0_single_route_packed_bytes=actual_expert_bytes,
                     expected_union_packed_bytes=actual_expert_bytes*union/k,
                     no_overlap_packed_bytes=2*actual_expert_bytes,
                     independence_assumption_measured=False),
        memory=memory_result,scenarios=scenarios,cost_sensitivity=sensitivity,
        validation=dict(packet85_equations_reproduced=True,unique_counts_verified=True,
                        no_flag_recovers_baseline=True,contiguous_edges_only=True,
                        next_flag_current_rescue_dependency_checked=True,
                        per_row_arithmetic_for_new_branch_controller_proved=False),
        limitations=[
            '256 development positions, not 512; four correlated prompts, no representative speed claim.',
            'Top-four softmax is an upper bound on true top-one probability, not calibrated confidence.',
            'Packet31 CPU draft and older target arithmetic differ from packet84; acceptance transfer is unproved.',
            'Packet77 sampled class estimates are not whole-half or packet84 class measurements.',
            'Byte sharing, 555 GB/s and R-per-byte copy costs are explicit assumptions, not latency guarantees.',
            'Costs paid for flag at i+1; rescue credited for verified flag at i; each finite window excludes its entering cost and departing benefit, as packet85 intervals do.',
            'Anchor transfer applies a modeled mean-cycle delta to a class-balanced record; both additive and multiplicative shown.',
            'No second-row controller, new M2 kernels, device test, quality gate, startup test or seal was built.'
        ],source_sha256=dict(sorted(PINS.items())))
    assert not speed_pass, 'Conservative gate passed: decision text must be revisited'
    output=json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n'
    sweep_output=json.dumps(dict(schema='packet96.threshold-sweep.v1',rows=sweep),indent=1,sort_keys=True,allow_nan=False)+'\n'
    for path,content in ((HERE/'DECISION.json',output),(HERE/'thresholds.json',sweep_output)):
        if args.check:
            assert path.read_text()==content, f'{path.name} differs from recomputation'
        else:
            path.write_text(content)
    print(json.dumps(dict(decision=result['decision'],memory=memory_result,
        cost_summary={k:v for k,v in costs.items()},
        primary={k:dict(feature=v['selection']['feature'],theta=v['selection']['theta'],
                       train_gain=v['selection']['train']['anchor_additive_gain_percent'],
                       test_gain=v['test']['anchor_additive_gain_percent'],
                       test_tps=v['test']['anchor_additive_tok_s']) for k,v in scenarios.items()}),indent=2))
    print('PASS: CPU model invariants and '+('byte-identical JSON recomputation' if args.check else 'JSON generation'))


if __name__=='__main__':
    main()
