"""CPU-only saved-evidence recheck; no runtime, model, or orchestration imports."""
import gzip
import hashlib
import importlib.util
import json
import resource
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
P = Path(__file__).resolve().parent
S = P.parent
ROOT = P.parents[3]
PINS = {}


def pin(path):
    with path.open('rb') as f:
        digest = hashlib.file_digest(f, 'sha256').hexdigest()
    PINS[str(path.relative_to(ROOT))] = digest
    return path


def read(path):
    pin(path)
    with (gzip.open(path, 'rt') if path.suffix == '.gz' else path.open()) as f:
        return json.load(f)


def union_summary(rows):
    out = []
    for layer in range(48):
        values = rows[layer]
        out.append(dict(layer=layer, pairs=len(values), mean_union=st.mean(values),
                        min_union=min(values), max_union=max(values)))
    return dict(per_layer=out, mean_union=st.mean(v for r in rows.values() for v in r),
                pairs=sum(len(r) for r in rows.values()))


def main():
    h = read(S/'packet58h-onecard-mtp/feasibility.json')
    x = read(S/'packet58x-cache-capacity/admission.json')['admission']
    u = read(S/'packet58u-host-admission/measured-peaks.json')
    y = read(S/'packet58y-onecard-attribution/analysis/report.json')
    timing = read(S/'packet138-xlayer-prefetch/evidence/timing-inputs.json')
    zpath = S/'packet58z-onecard-record/evidence/card0-58z-a/WS128'
    z = read(zpath/'summary.json'); zw = read(zpath/'window.json')
    census = read(zpath/'run/run/census.json')[0]
    assert next(r['bytes'] for r in census['allocations'] if r['label']=='card0:weight:output.weight') == 839321600
    pin(S/'packet68c-m2-from-production/README.md')
    pin(S/'packet85-critical-path/MODEL.md')
    assert z['passed'] and zw['passed'] and z['arithmetic'] == 'iq3-p49-split32-v1'
    assert z['cache_bytes'] == x['cache_bytes'] and z['kv_dtype'] == 'BF16'
    m = h['memory']; a = .787; anchor = 29.260; threshold = anchor * 1.05
    resident_cost = m['options']['resident_draft_experts']['proposed_device_bound_bytes'] - m['base_plan_device_bound_bytes']
    shared_cost = m['options']['shared_cache_draft_experts']['proposed_device_bound_bytes'] - m['base_plan_device_bound_bytes']
    resident_cap = (x['cache_bytes'] - resident_cost)//256*256
    shared_cap = (x['cache_bytes'] - shared_cost)//256*256
    # Deliberately retain the entire 58x backing charge even after shrinking the
    # target cache. Add full new draft/state backing, not just its observed shadow.
    memory = dict(resident_draft_device_cost=resident_cost, shared_draft_device_cost=shared_cost,
        resident_target_cache_bytes=resident_cap, shared_total_cache_bytes=shared_cap,
        shared_target_capacity_if_all_draft_experts_cached=shared_cap-m['draft_weights_by_group']['experts'],
        host_resident_conservative_bytes=x['host_required_available_bytes']+m['options']['resident_draft_experts']['extra_device_payload_bytes']+m['draft_pinned_bytes'],
        host_shared_conservative_bytes=x['host_required_available_bytes']+m['options']['shared_cache_draft_experts']['extra_device_payload_bytes']+m['options']['shared_cache_draft_experts']['extra_direct_host_payload_bytes'],
        historical_available_floor=x['historical_available_floor_bytes'], z_available=zw['memory_admission']['available_bytes'],
        z_shadow_peak=zw['postload_memory']['peak_shadow_bytes'], device_reserve_bytes=x['device_reserve_bytes'],
        driver_allowance_bytes=x['driver_allowance_bytes'], host_margin_bytes=x['host_margin_bytes'], host_reserve_bytes=x['host_reserve_bytes'])
    assert sum(r['bytes'] for r in m['draft_weight_rows']) == 3_326_953_472
    assert resident_cost == 3_326_953_472 + m['draft_kv_bytes']
    memory['current_actual_device_bytes'] = census['totals']['device']
    memory['resident_proposed_actual_device_bytes'] = census['totals']['device'] - (x['cache_bytes']-resident_cap) + m['options']['resident_draft_experts']['extra_device_payload_bytes']
    memory['shared_proposed_actual_device_bytes'] = census['totals']['device'] - (x['cache_bytes']-shared_cap) + m['options']['shared_cache_draft_experts']['extra_device_payload_bytes']
    for cap,cost in ((resident_cap,resident_cost),(shared_cap,shared_cost)):
        assert x['device_owned_bound_bytes']-x['cache_bytes']+cap+cost+x['driver_allowance_bytes']+x['device_reserve_bytes'] <= 32_000_000_000
    assert max(memory['host_resident_conservative_bytes'],memory['host_shared_conservative_bytes']) < memory['historical_available_floor']

    pred = read(S/'packet138-xlayer-prefetch/evidence/predictions.json.gz')
    capture = read(S/'packet138-xlayer-prefetch/evidence/capture-inputs.json')
    pre = read(S/'packet138-xlayer-prefetch/evidence/prefill-inputs.json.gz')
    assert pred['passed'] and pre['passed']
    assert pred['capture_manifest_sha256'] == PINS[str((S/'packet138-xlayer-prefetch/evidence/capture-inputs.json').relative_to(ROOT))]
    truth = pred['truth']; del pred
    rows = defaultdict(list)
    for tokens in truth.values():
        assert len(tokens)==48
        for first,second in zip(tokens,tokens[1:]):
            assert len(first)==len(second)==48
            for layer,(i,j) in enumerate(zip(first,second)):
                assert len(set(i))==len(set(j))==10
                rows[layer].append(len(set(i)|set(j)))
    union138 = union_summary(rows)

    # Check actual speculative/rejected target visits too. Keep observation order,
    # only adjacent positions within the same prompt/layer; exclude rewinds/gaps.
    raw55 = pin(S/'packet55-feasibility/route/evidence/cards23-a/routes.jsonl.gz')
    binding55 = read(S/'packet58i-onecard-attribution/route-inputs/binding.json')
    assert PINS[str(raw55.relative_to(ROOT))] == binding55['source_bindings']['trace_sha256']
    rows55=defaultdict(list); previous={}; counts=defaultdict(int)
    with gzip.open(raw55,'rt') as f:
        for line in f:
            r=json.loads(line)
            if r['split']!='test' or r['role']!='target' or r['phase']!='decode': continue
            k=(r['prompt_id'],r['layer']); old=previous.get(k)
            if old and r['position']==old['position']+1:
                rows55[r['layer']].append(len(set(old['ids'])|set(r['ids'])))
                counts['second_row_speculative']+=bool(r['speculative'])
            elif old: counts['excluded_nonadjacent_or_rewind']+=1
            previous[k]=r
    union55=union_summary(rows55);union55['selection_counts']=dict(counts)
    union138['extra_logical_target_bytes_per_pair'] = sum((r['mean_union']-10)*(2329600 if r['layer']==2 else 1971200) for r in union138['per_layer'])
    union55['extra_logical_target_bytes_per_pair'] = sum((r['mean_union']-10)*(2329600 if r['layer']==2 else 1971200) for r in union55['per_layer'])

    # This saved CPU simulator has no model/runtime imports. It reproduces the
    # byte allocator and lagged publication; grouping pairs is an explicit model.
    sim_path=pin(S/'packet138-xlayer-prefetch/cache_sim.py')
    spec=importlib.util.spec_from_file_location('cache_model58aa',sim_path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    sizes=[1_971_200]*48;sizes[2]=2_329_600
    def replay(cap, pair=False, unique=True):
        scenario=module.Scenario('58aa', (55 if pair else 1000/anchor)/48, .5,
            25_000_000,0,0,0,.003,1,1000/anchor,0)
        sim=module.Simulator(sizes,scenario,capacity=cap)
        for name,tokens in truth.items():
            sim.reset_request()
            for token in pre['prompts'][name]: sim.token(token,record=False)
            if pair:
                for index in range(0,len(tokens),2):
                    both=[list(dict.fromkeys(i+j)) if unique else i+j
                          for i,j in zip(tokens[index],tokens[index+1])]
                    sim.token(both)
            else:
                for token in tokens: sim.token(token)
        return sim.summary()
    replays={}
    for label,cap in [('current',x['cache_bytes']),('resident',resident_cap),('shared_no_draft_pollution',shared_cap)]:
        replays[label+'_M1']=replay(cap)
        for unique in (True,False):
            if label=='current':continue
            replays[label+('_M2_union' if unique else '_M2_two_reads')]=replay(cap,True,unique)
        print('replayed',label,flush=True)
    base=replays['current_M1']['per_token']; d=h['timing']['draft_ms']; restore=(1-a)*h['timing']['restore68_ms']
    def remote(row,kind):
        penalties=timing['k1_remote_penalty_ms_per_missing_expert'][kind]
        special=row.get('zero_copy_bytes_layer2',0)
        return (row['zero_copy_bytes']-special)/sizes[0]*penalties['0']+special/sizes[2]*penalties['2']
    ratio=h['timing']['combined_M2_M1_ratio']
    delta=sum(r['H2_device_sum_ms']-r['H1_device_sum_ms'] for r in h['timing']['proxies'])
    def rate(verify,draft,extra):
        # Recompute class statistic from each retained prompt, with an affine
        # verify transform supplied below. Aggregate reciprocal also retained.
        byclass=defaultdict(list)
        for r in z['requests']:
            period=1000/r['tok_s_1_100_intervals_after_ttft']
            byclass[r['prompt_class']].append(1000*(1+a)/(verify(period)+draft+extra))
        return st.median(st.median(v) for v in byclass.values())
    scenarios=[]
    for layout in ('resident','shared_no_draft_pollution'):
        for reuse in ('union','two_reads'):
            row=replays[layout+'_M2_'+reuse]['per_token']
            for penalty in timing['k1_remote_penalty_ms_per_missing_expert']:
                base_remote=remote(base,penalty); pair_remote=remote(row,penalty)
                for name in ('ratio_nonremote','constant_overhead'):
                    def verify(t):
                        return ratio*(t-base_remote)+pair_remote if name=='ratio_nonremote' else t+delta+pair_remote-base_remote
                    for draft in (d,2*d):
                        # 1x is the resident two-card command transferred to one
                        # card; 2x allows one repair/feedback pass, not measured.
                        for charge_fill in (False,True):
                            fill=max(0,row.get('demand_bytes',0)-base.get('demand_bytes',0))/25_000_000 if charge_fill else 0
                            extra=restore+fill
                            value=rate(verify,draft,extra)
                            scenarios.append(dict(layout=layout,reuse=reuse,remote_penalty=penalty,model=name,
                                draft_ms=draft,fill_exposed_ms=fill,restore_expectation_ms=restore,
                                verify_ms_at_anchor=verify(1000/anchor),projected_tok_s=value,
                                gain_percent=100*(value/anchor-1),passes=value>=threshold))
    out=dict(schema='packet58aa.cpu-feasibility.v1',measured_speed=False,device_executed=False,
        anchor_tok_s=anchor,receipt_tok_s=z['class_balanced_tok_s_1_100_intervals_after_ttft']['median'],
        threshold_tok_s=threshold,acceptance_assumption=a,memory=memory,
        union138=union138,union55=union55,replays=replays,scenarios=scenarios,
        naive_ratio_no_extra_cost_tok_s=rate(lambda t:ratio*t,d,0),
        max_cycle_ms=1000*(1+a)/threshold,max_verify_ms_after_draft_restore=1000*(1+a)/threshold-d-restore,
        diagnostic58y=y['measured_split'], sources=PINS,
        decision='do-not-build', build_gate_passed=False,
        decision_reason='Memory fits the reviewed hypothetical layout, but no charged scenario reaches 30.723 tok/s; shared-cache sensitivity omits draft pollution and remote draft reads.',
        limitations=['Projection, not a measured one-card MTP result or a confidence interval.',
            'Independent 48-token accepted-route capture; rejected MTP paths are not replayed. Packet55 observed speculative visits separately check union growth.',
            'M2 groups two accepted positions per cycle and transfers M1 lag per group. Future causal verifier scheduling may differ.',
            'The 55 ms M2 copy window is assumed; fills can spill and wait. It is not measured layer timing.',
            'Shared-cache model leaves all target capacity available while charging resident draft time: deliberately favorable, not an implementable complete layout.',
            'Zero-copy penalties and fill bandwidth are historical transfer sensitivities, not physical traffic measurements.',
            '29.260 is the brief anchor; per-prompt predictions recompute median of class medians from exact 58z rates.'])
    assert not any(r['passes'] for r in scenarios)
    (P/'analysis.json').write_text(json.dumps(out,indent=2)+'\n')
    csv=['layer,packet138_pairs,packet138_mean_union,packet55_pairs,packet55_mean_union']
    for r,q in zip(union138['per_layer'],union55['per_layer']):
        csv.append(f"{r['layer']},{r['pairs']},{r['mean_union']:.9f},{q['pairs']},{q['mean_union']:.9f}")
    (P/'route-union-by-layer.csv').write_text('\n'.join(csv)+'\n')
    print(json.dumps({k:v for k,v in out.items() if k in ('memory','naive_ratio_no_extra_cost_tok_s','max_cycle_ms','max_verify_ms_after_draft_restore')},indent=2))
    print('union138',union138['mean_union'],'union55',union55['mean_union'])
    for name in ('ratio_nonremote','constant_overhead'):
        values=[r['projected_tok_s'] for r in scenarios if r['model']==name and r['layout']=='resident']
        print(name,min(values),max(values))
    print('peak RSS KiB',resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def check():
    result=json.loads((P/'analysis.json').read_text())
    for name,digest in result['sources'].items():
        assert hashlib.file_digest((ROOT/name).open('rb'),'sha256').hexdigest()==digest,name
    assert result['threshold_tok_s']==29.260*1.05
    assert result['union138']['pairs']==12*47*48
    assert len(result['union55']['per_layer'])==48
    assert len(result['scenarios'])==64
    assert all(not r['passes'] and r['projected_tok_s']<result['threshold_tok_s'] for r in result['scenarios'])
    assert result['memory']['device_reserve_bytes']==1_500_000_000
    assert len((P/'route-union-by-layer.csv').read_text().splitlines())==49
    print('PASS: all source hashes, route counts, 64 timing scenarios and retained reserve; no device execution.')


if __name__=='__main__':
    if sys.argv[1:]==['--check']:check()
    else:main()
