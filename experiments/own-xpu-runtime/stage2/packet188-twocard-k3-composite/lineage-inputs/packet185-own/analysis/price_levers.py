#!/usr/bin/env python3
"""Lever pricing replay on the 1,188 packet160 record intervals (bundle 8, 58.798109 tok/s).
CPU-only arithmetic. Reads packet160 evidence/record-intervals.csv and retained v4 receipts only.
Every model parameter is labelled measured / transferred / assumed in the printed output."""
import csv, statistics as st, json, itertools
from collections import defaultdict
from pathlib import Path
R=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2')
rows=[]
for r in csv.DictReader(open(R/'packet160-critical-path/evidence/record-intervals.csv')):
    d={k:(float(r[k]) if r[k] not in ('',None) else 0.0) for k in ['elapsed_ms','D','B','A','R','C','spec_start_offset_ms','unresolved_control_gaps_ms']}
    d['hit']=r['hit']=='True'; d['pid']=r['prompt_id']; d['cls']=r['prompt_class']; rows.append(d)
assert len(rows)==1188
def metric(T):
    per=defaultdict(float); cls={}
    for r,t in zip(rows,T): per[r['pid']]+=t; cls[r['pid']]=r['cls']
    bycls=defaultdict(list)
    for p,s in per.items(): bycls[cls[p]].append(99000/s)
    return st.median(st.median(v) for v in bycls.values())
def base(r): return max(r['D'],r['R']+r['C'])+max(r['B'],r['A']+r['spec_start_offset_ms'])+r['unresolved_control_gaps_ms']
T0=[base(r) for r in rows]
assert max(abs(t-r['elapsed_ms']) for t,r in zip(T0,rows))<1e-6
REC=metric(T0); print('replay',REC)
def gain(T): return 100*(metric(T)/REC-1)
hits=[r for r in rows if r['hit']]; miss=[r for r in rows if not r['hit']]
out={'record':REC}
# --- coupling: B-A on hits; sigma measured in coupled split-head arms (p106b split, p120 x2, p127 prod, p131b controls)
ba=[r['B']-r['A'] for r in hits]; q=st.quantiles(ba,n=10)
SIGMA=0.478  # measured: B-A in six coupled split-head arms 0.477-0.483
out['B_minus_A_hit']={'mean':st.mean(ba),'p10':q[0],'p50':st.median(ba),'frac_below_sigma_plus_0.05':sum(x<SIGMA+0.05 for x in ba)/len(ba)}
# rank1-only cut capped by A+sigma (split head kept)
def rank1_only(cut,sigma=SIGMA,dcut=0.0):
    T=[]
    for r in rows:
        b=max(r['B']-cut, r['A']+r['spec_start_offset_ms']+sigma) if r['B']-cut< r['A']+sigma else r['B']-cut
        b=max(r['B']-cut, min(r['B'], r['A']+sigma))
        d=r['D']-dcut if r['hit'] else r['D']
        T.append(max(d,r['R']+r['C'])+max(b,r['A']+r['spec_start_offset_ms'])+r['unresolved_control_gaps_ms'])
    return T
out['rank1_only_capped']={str(c):round(gain(rank1_only(c)),3) for c in (0.1,0.2,0.333,0.5,1.0)}
def rank1_only_uncapped(cut):
    return [max(r['D'],r['R']+r['C'])+max(r['B']-cut,r['A']+r['spec_start_offset_ms'])+r['unresolved_control_gaps_ms'] for r in rows]
out['rank1_only_uncapped_p160_style']={str(c):round(gain(rank1_only_uncapped(c)),3) for c in (0.1,0.2,0.333,0.5)}
# --- two-card kernel foreground I/O analogue (port of packet176): remove synchronous copy round trips
RT=0.023; RT_KIO=0.005  # measured 22.7-25.5 us per synchronous copy+wait (p105-transfers.jsonl, packet165 two-card bundle-8 requal); kernel store/stamp assumed 5 us
def kio(n_d=2,n_b=3,n_sigma=4,n_c=2,async_switch=0.0):
    s=RT-RT_KIO; T=[]
    for r in rows:
        dcut=n_d*s; bcut=n_b*s+async_switch; sig=SIGMA-n_sigma*s
        b=max(r['B']-bcut, min(r['B'], r['A']+sig))
        if r['hit']: ready=r['D']-dcut
        else: ready=max(r['D']-dcut, r['R']+r['C']-n_c*s)
        T.append(ready+max(b,r['A']+r['spec_start_offset_ms'])+r['unresolved_control_gaps_ms'])
    return T
out['kernel_io_two_card']={'central(2D,3B,4sigma,2C RTs)':round(gain(kio()),3),'plus 5 async engine switches x5us':round(gain(kio(async_switch=0.025)),3),'generous(3D,5B,6sigma,4C,+0.05 async)':round(gain(kio(3,5,6,4,0.05)),3)}
# --- V3: un-split target head + k rank1 body layers run on rank0 non-speculatively at the verified boundary
def v3(k,u,s1,c0,exp=0.025,cap=0.08,accept_overlap=True,accept_host=0.743):
    T=[]
    for r in rows:
        own=r['B']+u-k*s1                      # rank1: full head, no merge RTs, k fewer layers
        L=k*c0
        tail=max(0.0, r['A']+r['spec_start_offset_ms']-own)   # previous speculative A still running at emission
        if r['hit']:
            r0=tail+L+exp+cap+(0 if accept_overlap else accept_host)
            ready=max(r['D'],r0)
            t=ready+own+r['unresolved_control_gaps_ms']
            t=max(t, L+r['A']+cap+exp)          # rank0 per-interval work floor
        else:
            t=tail+r['R']+r['C']+L+exp+own+r['unresolved_control_gaps_ms']
            t=max(t, r['D']+own+r['unresolved_control_gaps_ms'])
        T.append(t)
    return T
grid=[]
for k,u,s1,c0 in itertools.product((1,2),(0.15,0.20,0.25),(0.47,0.49,0.55),(0.49,0.55,0.59)):
    grid.append({'k':k,'u':u,'s1':s1,'c0':c0,'gain':round(gain(v3(k,u,s1,c0)),3)})
out['v3_grid']=grid
for k in (1,2):
    g=[x['gain'] for x in grid if x['k']==k]; out[f'v3_k{k}_range']=(min(g),st.median(g),max(g))
out['v3_k2_accept_serialized']=round(gain(v3(2,0.20,0.49,0.55,accept_overlap=False)),3)
# --- V1: un-split + 25/23 speculative placement (p120 layer cost on rank0 measured 0.59 incl. snapshot)
def v1(k,u,s1,c0=0.59,accept_host=0.743):
    T=[]
    for r in rows:
        own=r['B']+u-k*s1; A2=r['A']+k*c0
        tail=max(0.0,A2+r['spec_start_offset_ms']-own)
        if r['hit']: t=max(r['D'],tail+accept_host)+own+r['unresolved_control_gaps_ms']
        else: t=tail+r['R']+r['C']+k*c0+own+r['unresolved_control_gaps_ms']
        T.append(t)
    return T
out['v1_unsplit_speculative']={f'k{k}_u{u}_s{s1}':round(gain(v1(k,u,s1)),3) for k in (1,2) for u in (0.15,0.25) for s1 in (0.47,0.55)}
# --- un-split alone (diagnostic arm)
out['unsplit_only']={str(u):round(gain([max(r['D'],r['R']+r['C'])+(r['B']+u)+r['unresolved_control_gaps_ms'] for r in rows]),3) for u in (0.1,0.2,0.25)}
# --- head-row rebalance toward rank0 within the split (p127 direction, small)
def rebalance(krows,r1=0.00556,r0=0.00583):
    return [max(r['D'],r['R']+r['C'])+max(r['B']-krows*r1, r['A']+r['spec_start_offset_ms']+SIGMA+krows*r0)+r['unresolved_control_gaps_ms'] for r in rows]
out['head_rows_to_rank0']={str(k):round(gain(rebalance(k)),3) for k in (5,10,11,15,35.84)}
# --- static snapshot (p153 measured +0.35%) and symmetric threshold
def sym(h): return [max(r['D'],r['R']+max(0,r['C']-h))+max(r['B']-h,r['A']-h+r['spec_start_offset_ms'])+r['unresolved_control_gaps_ms'] for r in rows]
lo,hi=0,2
for _ in range(60):
    m=(lo+hi)/2
    if gain(sym(m))<2: lo=m
    else: hi=m
out['symmetric_half_cut_for_2pct']=hi
def donly(x): return [max(r['D']-(x if r['hit'] else 0),r['R']+r['C'])+max(r['B'],r['A']+r['spec_start_offset_ms'])+r['unresolved_control_gaps_ms'] for r in rows]
lo,hi=0,2
for _ in range(60):
    m=(lo+hi)/2
    if gain(donly(m))<2: lo=m
    else: hi=m
out['D_only_cut_for_2pct']=hi
print(json.dumps(out,indent=1))
json.dump(out,open(Path(__file__).with_name('price-output.json'),'w'),indent=1)
