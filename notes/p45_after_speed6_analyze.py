"""Read-only retained-receipt analysis. Run with python3 -B; JSON to stdout only."""
import collections
import hashlib
import importlib.util
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / 'experiments/own-xpu-runtime/stage2/packet45-merged3'


def read_only(event, args):
    # Includes import caches; this analyzer has no legitimate write or child run.
    if event in ('os.remove', 'os.rename', 'os.mkdir', 'os.rmdir', 'subprocess.Popen'):
        raise RuntimeError('analysis forbids filesystem mutations/child execution')
    if event == 'open':
        _, mode, flags = args
        if (mode and any(c in mode for c in 'wax+')) or flags & (1 | 2 | 64 | 512 | 1024):
            raise RuntimeError('analysis forbids writes')


sys.addaudithook(read_only)
RUNS = {
    'speed6-a': P/'build/speed6-c4096-dr1-s23-cards01-gpu/WS128',
    'speed6-a2': P/'build/speed6-c4096-dr1-s23-cards01-gpu/WS128-r2',
    'speed6-b': P/'build/speed6-c4096-dr1-s23-cards23-gpu/WS128',
    'speed3-dr1': P/'build/speed3-c4096-dr1-gpu/WS128',
    'speed3-dr0': P/'build/speed3-c4096-dr0-s24-gpu/WS128',
}


def load(p):
    return json.loads(p.read_bytes())


def span(t):
    return 1000*(t['rank_completed']-t['rank_received'])


def summary(rows):
    keys = rows[0].keys()
    return {k: {'median': st.median(r[k] for r in rows),
                'mean': st.mean(r[k] for r in rows)} for k in keys}


def snapshot_schedule():
    root=RUNS['speed6-a']/'run/ranks/rank0'
    allocations=load(root/'census.json')['allocations']
    plan=load(root/'launch-plan.json')
    backup=next(x for x in allocations if x['label']=='card0:speculative-private-image')
    represented={'card0:'+x['name'] for x in plan['buffers']} | {x['label'] for x in allocations if x['label'].startswith('card0:alternate:')}
    outputs={'token','position','token_history'}; kv=set()
    for site in plan['launches']:
        outputs.update(site['outputs'])
        if site['op']=='qsa_append_pool': kv.update(site['outputs'])
    sources=[dict(name=x['name'],bytes=x['bytes']) for x in plan['buffers'] if x['name'] in outputs]
    sources += [dict(name=x['label'],bytes=x['bytes']) for x in allocations if x['id']<backup['id'] and x['live'] and x['memory']=='device' and x['category']!='weights' and x['label'] not in represented and x['label']!='card0:mixture-one']
    assert sum(x['bytes'] for x in sources)==backup['bytes']
    categories=collections.Counter(); capture=[]; redo=[]
    for source in sources:
        n=source['bytes']; name=source['name']; category='intermediates'
        if name in kv: n//=1024 if name.endswith('.pooled') else 4096; category='QSA rows'
        elif name=='card0:operator-scratch': n=1597440; category='standalone'
        elif name.startswith('card0:'): category='standalone'
        elif name.endswith('.state') or name.endswith('.history'): category='banked'
        categories[category]+=n; capture.append(n)
        if category!='banked': redo.append(n)
    result={'categories':dict(categories),'capacity_bytes':backup['bytes']}
    for name, sizes in [('capture',capture),('redo',redo)]:
        sizes.sort(); batches=[sizes[i:i+32] for i in range(0,len(sizes),32)]
        assert max(map(sum,batches))<=134217728
        result[name]=dict(components=len(sizes),batches=len(batches),bytes=sum(sizes),
                         work_items=sum(len(b)*((max(b)+15)//16) for b in batches),
                         padded_byte_slots=sum(len(b)*((max(b)+15)//16)*16 for b in batches),
                         packed_work_items=sum((n+15)//16 for n in sizes))
        for ratio in (2,4,8):
            grouped=[]; current=[]
            for n in sizes:
                if current and (len(current)==32 or n>current[0]*ratio or sum(current)+n>134217728):
                    grouped.append(current);current=[]
                current.append(n)
            if current:grouped.append(current)
            assert sum(map(sum,grouped))==sum(sizes)
            result[name][f'ratio{ratio}_hypothesis']=dict(batches=len(grouped),
                padded_byte_slots=sum(len(b)*((max(b)+15)//16)*16 for b in grouped),
                single_descriptor_batches=sum(len(b)==1 for b in grouped))
    final=max((load(f) for f in (RUNS['speed6-a']/'run/repeat-1').glob('*/rank0/speculative-snapshot.json')),key=lambda x:x['captures'])
    assert result['capture']['bytes']*final['captures']==final['snapshot_payload_bytes']
    assert result['redo']['bytes']*final['restores']==final['restored_bytes']
    return result


def memory_projection():
    ledger=load(P/'memory-plan.json')
    base=ledger['placements']['1-split23']['capacities']['4096']['ranks']
    for rank,row in enumerate(base):
        census=load(RUNS['speed6-a']/f'run/ranks/rank{rank}/census.json')
        assert census['totals']['device']==row['arena_device_bytes']
    rows=[]
    # Layer22 is GDN: no new QSA cache when moving 23->22.
    for context in (4096,32768):
        growth=(context-4096)*2368*8  # seven target QSA layers + one draft
        arena=base[1]['arena_device_bytes']+1115963658+growth
        rows.append(dict(split='22/26',draft_rank=1,context=context,
                         hypothetical_8MiB_scratch=True,arena_bytes=arena,
                         arena_headroom_bytes=ledger['arena_limit_bytes']-arena,
                         reserve_headroom_bytes=ledger['capacity_bytes']-ledger['minimum_free_bytes']-base[1]['allocation_reserve_bytes']-arena))
    return rows


def expanded_weight_inventory():
    raw={}
    for line in (P/'build/input/plan.tsv').read_text().splitlines():
        fields=line.split()
        if len(fields)>=6 and fields[5].isdigit(): raw[fields[1]]=int(fields[5])
    ranks={}
    for rank in (0,1):
        census=load(RUNS['speed6-a']/f'run/ranks/rank{rank}/census.json')
        deltas={}
        for row in census['allocations']:
            if row['live'] and row['label'].startswith('card0:weight:'):
                name=row['label'].split('weight:',1)[1]
                if name in raw and row['bytes']!=raw[name]: deltas[name]=row['bytes']-raw[name]
        ranks[rank]=dict(expansion_bytes=sum(deltas.values()),tensors=len(deltas),
                        head_expansion_bytes=deltas.get('output.weight',0),
                        layer22_expansion_bytes=sum(v for k,v in deltas.items() if k.startswith('blk.22.')))
    return ranks


def verify_legacy():
    spec=importlib.util.spec_from_file_location('legacy',P/'evidence/regression-analysis/analyze.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    # SPEED3 introduced null deferred GPU timings. Do not relabel these as zero.
    old=module.stats;module.stats=lambda xs:old(x for x in xs if x is not None)
    classes={r['prompt_id']:r['prompt_class'] for r in load(RUNS['speed6-a']/'run/summary.json')['rows']}
    output={}
    for name in ('speed6-a','speed6-a2','speed6-b'):
        legacy=module.analyze(RUNS[name],classes);current=analyze(RUNS[name])
        assert legacy['reported_cycle_mean_median']==current['reported']
        assert legacy['reported_decode_busy_median']==current['busy']
        assert abs(legacy['class_balanced_rate']-current['forecasts']['unchanged']['rate'])<1e-10
        output[name]=dict(passed=True,class_balanced_rate=legacy['class_balanced_rate'],
                          reported_cycles=current['reported'],input_digest=current['input_digest'])
    return output


def analyze(root):
    window = load(root/'window.json')
    assert window['passed'] and window['qualifying']
    phases = collections.defaultdict(list)
    request_phases = collections.defaultdict(list)
    additive_full = collections.defaultdict(list)
    forwards = collections.defaultdict(list)
    paired = []
    requests = []
    hashes = {}
    forecasts = collections.defaultdict(list)
    # Planning hypotheses in ms, NOT measured kernel speedups. These are
    # independent alternatives, not additive promises.
    scenarios = {
        'unchanged': {},
        'snapshot-low': dict(S=.3,R=.3),
        'snapshot-central': dict(S=.7,R=.7),
        'snapshot-high': dict(S=1.0,R=1.0),
        'moe-low': dict(S=.2,A=.2,T=.217),
        'moe-central': dict(S=.4,A=.4,T=.435),
        'moe-high': dict(S=.6,A=.6,T=.652),
        'head-low': dict(D=.14,T=.14),
        'head-central': dict(D=.28,T=.28),
        'head-high': dict(D=.42,T=.42),
        'split22': dict(S=.836,A=.713,T=-.760),
        'split24': dict(S=-.836,A=-.713,T=.760),
        'early-draft-low': dict(early=.5),
        'early-draft-upper': dict(early=1),
    }
    for f in sorted((root/'run/repeat-1').glob('*/receipt.json')):
        r = load(f)
        assert r['passed'] and r['oracle_check']['passed'] and len(r['tokens']) == 128
        files = [f] + [f.parent/f'rank{rank}/timings.jsonl' for rank in (0, 1)]
        for source in files:
            hashes[str(source.relative_to(root))] = hashlib.sha256(source.read_bytes()).hexdigest()
        trace = r['rank_trace']
        by_position = collections.defaultdict(list)
        for rank in (0, 1):
            ts = [t for t in trace if t['rank'] == rank and t['op'] == 1]
            xs = [json.loads(line) for line in files[rank+1].read_bytes().splitlines()]
            assert len(ts) == len(xs)
            for t, x in zip(ts, xs):
                assert (t['position'],t['fixture'],t['speculative']) == (x['position'],x['fixture'],x['speculative'])
                z = {k: x[k] for k in ('prepare_ms','enqueue_loop_ms','wait_ms','host_waits','launches_issued')}
                z.update(forward_ms=sum(x[k] for k in ('prepare_ms','enqueue_loop_ms','wait_ms')),
                         command_ms=span(t), outside_ms=span(t)-t['busy_ms'], cancelled=x['cancelled'])
                if t['position'] >= 100:
                    forwards[f'r{rank}-'+('spec' if t['speculative'] else 'plain')].append(z)
                    if rank == 0: by_position[t['position']].append(z)
        for zs in by_position.values():
            if len(zs) == 2:
                paired.append({k: zs[0][k]-zs[1][k] for k in ('command_ms','outside_ms','wait_ms','forward_ms')})
        per_request = collections.defaultdict(list)
        additive_request = collections.defaultdict(list)
        changes = {name: [] for name in scenarios}
        for d in r['draft_rows']:
            if d.get('hit') is None or 'cycle_ms' not in d: continue
            left = d['target_completed_monotonic']; right = left + d['cycle_ms']/1000
            # The hit/miss resolves the previous speculative half; the next
            # rank1 HALF is the only one fully within this emitted interval.
            candidates = [t for t in trace if t['rank']==1 and t['op']==1 and t['rank_received']>=left and t['rank_completed']<=right+1e-8]
            assert len(candidates)==1
            t = candidates[0]
            additive_request['hit' if d['hit'] else 'miss'].append(dict(
                cycle=d['cycle_ms'], before=1000*(t['rank_received']-left),
                r1_half=span(t), observation=1000*(right-t['rank_completed'])))
            ds = [q for q in trace if q['op']==9 and q['rank_received']>=left and q['rank_completed']<=right]
            assert len(ds)==1
            draft=ds[0]
            specs=[q for q in trace if q['rank']==0 and q['op']==1 and q['speculative'] and q['position']==t['position']+1]
            if len(specs)!=1: continue  # last emitted token has no next speculation
            s=specs[0]
            redos=[q for q in trace if q['rank']==0 and q['op']==1 and not q['speculative'] and q['rank_received']>=left and q['rank_completed']<=t['rank_received']]
            rollback=[q for q in trace if q['rank']==0 and q['op']==3 and q['rank_received']>=left and q['rank_completed']<=t['rank_received']]
            accepts={rank:sum(span(q) for q in trace if q['rank']==rank and q['op']==2 and q['rank_received']>=left and q['rank_completed']<=t['rank_received']) for rank in (0,1)}
            z=dict(cycle=d['cycle_ms'],before=1000*(t['rank_received']-left),r1_half=span(t),observation=1000*(right-t['rank_completed']),
                   draft_command=span(draft),observation_to_draft_sent=1000*(draft['sent']-left),
                   draft_dispatch=1000*(draft['rank_received']-draft['sent']),draft_complete_to_half_send=1000*(t['sent']-draft['rank_completed']),
                   half_dispatch=1000*(t['rank_received']-t['sent']),r0_spec=span(s),
                   r0_start_after_r1=1000*(s['rank_received']-t['rank_received']),
                   r0_later_than_r1=1000*(s['rank_completed']-t['rank_completed']),
                   rollback=sum(span(q) for q in rollback),redo=sum(span(q) for q in redos),
                   accept0=accepts[0],accept1=accepts[1])
            z['before_residual']=z['before']-max(z['draft_command'],z['rollback']+z['redo'])
            z['critical_max']=max(z['r1_half'],z['r0_start_after_r1']+z['r0_spec'])
            z['post_max']=1000*(right-max(t['rank_completed'],s['rank_completed']))
            assert abs(z['before']+z['r1_half']+z['observation']-z['cycle'])<1e-6
            key='hit' if d['hit'] else 'miss'
            per_request[key].append(z)
            if d['position']>=100: phases[key].append(z)
            if r['generated_token_completion_timestamps'][0] <= left < r['generated_token_completion_timestamps'][99]:
                for name, hypothesis in scenarios.items():
                    q=lambda k:hypothesis.get(k,0)
                    if q('early'):
                        # Generous ceiling: overlap delayed observation with next
                        # draft issuance; no claim that dependencies permit all.
                        saving=q('early')*max(0,z['r0_later_than_r1'])
                    else:
                        before=max(z['draft_command'],z['rollback']+z['redo'])
                        after=max(z['draft_command']-q('D'), max(0,z['rollback']-q('R'))+max(0,z['redo']-q('A')))
                        saving=before-after+z['critical_max']-max(z['r1_half']-q('T'),z['r0_start_after_r1']+z['r0_spec']-q('S'))
                    changes[name].append((key,saving))
        for key,rows in per_request.items():
            request_phases[key].append({k:st.mean(z[k] for z in rows) for k in rows[0]})
        for key,rows in additive_request.items():
            additive_full[key].append({k:st.mean(z[k] for z in rows) for k in rows[0]})
        requests.append(dict(prompt=r['prompt_id'],cls=r['prompt_class'],rate=r['submission100']['tok_s'] if isinstance(r.get('submission100'),dict) and 'tok_s' in r['submission100'] else 99/(r['generated_token_completion_timestamps'][99]-r['generated_token_completion_timestamps'][0]),
                             cycles=r['hit_miss_cycles'],busy=r['decode_rank_metrics'],
                             hit_count99=sum(bool(d['hit']) for d in r['draft_rows'] if d.get('hit') is not None and d.get('cycle_ms') is not None and r['generated_token_completion_timestamps'][0]<=d['target_completed_monotonic']<r['generated_token_completion_timestamps'][99]),
                             snapshot=load(f.parent/'rank0/speculative-snapshot.json')))
        for name, rows in changes.items():
            assert len(rows)==99, 'forecast must cover the exact 99 intervals'
            elapsed=(r['generated_token_completion_timestamps'][99]-r['generated_token_completion_timestamps'][0])*1000
            forecasts[name].append(dict(cls=r['prompt_class'],rate=99000/(elapsed-sum(v for _,v in rows)),
                                        **{h:st.mean(v for k,v in rows if k==h) for h in ('hit','miss')}))
    assert len(requests)==12
    return dict(path=str(root.relative_to(ROOT)),window_sha256=hashlib.sha256((root/'window.json').read_bytes()).hexdigest(),
                input_digest=hashlib.sha256(''.join(f'{p} {h}\n' for p,h in sorted(hashes.items())).encode()).hexdigest(),
                reported={h:st.median(r['cycles'][h]['mean_ms'] for r in requests) for h in ('hit','miss')},
                additive_full={h:{k:st.median(z[k] for z in rows) for k in rows[0]} for h,rows in additive_full.items()},
                busy=[st.median(r['busy'][rank]['busy_ms_per_interval'] for r in requests) for rank in (0,1)],
                full_request_phase_medians={k:{f:st.median(z[f] for z in rows) for f in rows[0]} for k,rows in request_phases.items()},
                steady={k:dict(count=len(rows),r0_finishes_later_fraction=st.mean(z['r0_later_than_r1']>0 for z in rows),**summary(rows)) for k,rows in phases.items()},
                forwards={k:summary(v) for k,v in forwards.items()},paired=summary(paired),requests=requests,
                forecasts={n:dict(rate=st.median(st.median(q['rate'] for q in rs if q['cls']==c) for c in set(q['cls'] for q in rs)),
                                  **{h:st.median(q[h] for q in rs) for h in ('hit','miss')}) for n,rs in forecasts.items()} if window['draft_rank']==1 else {})


if __name__ == '__main__':
    names=sys.argv[1:] or list(RUNS)
    if names==['--verify']:
        print(json.dumps(dict(legacy_crosscheck=verify_legacy(),snapshot_schedule=snapshot_schedule(),memory_projection=memory_projection(),expanded_weight_inventory=expanded_weight_inventory()),indent=2))
        raise SystemExit(0)
    print(json.dumps({'snapshot_schedule':snapshot_schedule()}))
    for name in names:
        print(json.dumps({name:analyze(RUNS[name])}))
