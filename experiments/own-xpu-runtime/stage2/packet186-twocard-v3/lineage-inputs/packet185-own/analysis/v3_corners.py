import importlib.util,sys,io,contextlib,json
from pathlib import Path
spec=importlib.util.spec_from_file_location('p',str(Path(__file__).with_name('price_levers.py')))
m=importlib.util.module_from_spec(spec)
with contextlib.redirect_stdout(io.StringIO()): spec.loader.exec_module(m)
def v3x(k,u,s1,c0,exp=0.025,cap=0.08,extra_rt=0.0,accept_ser=0.0):
    T=[]
    for r in m.rows:
        own=r['B']+u-k*s1; L=k*c0
        tail=max(0.0,r['A']+r['spec_start_offset_ms']-own)
        if r['hit']:
            ready=max(r['D'],tail+L+exp+cap+extra_rt+accept_ser)
            t=max(ready+own+r['unresolved_control_gaps_ms'], L+r['A']+cap+exp+extra_rt+accept_ser)
        else:
            t=max(tail+r['R']+r['C']+L+exp+extra_rt+own+r['unresolved_control_gaps_ms'], r['D']+own+r['unresolved_control_gaps_ms'])
        T.append(t)
    return m.gain(T)
cases={
 'central k2 u.20 s1.48 c0.55':v3x(2,.20,.48,.55),
 'u lower bound (p106b) .05, s1.48 c0.55':v3x(2,.05,.48,.55),
 'pessimistic u.26 s1.45 c0.62':v3x(2,.26,.45,.62),
 'pessimistic + extra RT .05':v3x(2,.26,.45,.62,extra_rt=.05),
 'central + extra RT .05 + accept 0.335 serialized (p150 removable part)':v3x(2,.20,.48,.55,extra_rt=.05,accept_ser=.335),
 'central + full accept 0.743 serialized':v3x(2,.20,.48,.55,accept_ser=.743),
 'k1 central':v3x(1,.20,.48,.55),
 'k3 central':v3x(3,.20,.48,.55),
}
print(json.dumps({k:round(v,3) for k,v in cases.items()},indent=1))
def solve(f,lo,hi,target=2.0,decreasing=True):
    for _ in range(50):
        mid=(lo+hi)/2; g=f(mid)
        if (g>target)==decreasing: lo=mid
        else: hi=mid
    return (lo+hi)/2
print('u at which k2 central falls to +2%:',round(solve(lambda u:v3x(2,u,.48,.55),0,1),3))
print('c0 at which k2 central falls to +2%:',round(solve(lambda c:v3x(2,.20,.48,c),0.4,1.2),3))
print('s1 at which k2 central falls to +2%:',round(solve(lambda s:v3x(2,.20,s,.55),0.2,0.6,decreasing=False),3))
print('extra rank0 RT at which k2 central falls to +2%:',round(solve(lambda x:v3x(2,.20,.48,.55,extra_rt=x),0,1),3))
print('accept serialized at which k2 central falls to +2%:',round(solve(lambda x:v3x(2,.20,.48,.55,accept_ser=x),0,1),3))
SIG=0.478
def drafthead_rank0(unsplit=False,u=0.20,h=0.4717,xfer=0.048):
    T=[]
    for r in m.rows:
        if r['hit']:
            if unsplit:
                own=r['B']+u; t=(r['D']-h)+own+r['unresolved_control_gaps_ms']
                t=max(t, r['D']+xfer+r['A']+0.08)   # rank0 floor: head + A
            else:
                b_end=(r['D']-h)+r['B']; a_end=r['D']+xfer+r['A']+r['spec_start_offset_ms']+SIG
                t=max(b_end,a_end)+r['unresolved_control_gaps_ms']
        else:
            t=r['elapsed_ms'] if not unsplit else max(r['D'],r['R']+r['C'])+r['B']+u+r['unresolved_control_gaps_ms']
        T.append(t)
    return m.gain(T)
print('draft head -> rank0, split head kept:',round(drafthead_rank0(),3))
print('draft head -> rank0, un-split head:',round(drafthead_rank0(True),3))
print('V1 un-split + 25/23 speculative, u.20 s1.48 c0.59(p120):',round(m.gain(m.v1(1,.20,.48,.59)),3))
print('V3 k2 central with p153 static (accept serialized 0.41):',round(v3x(2,.20,.48,.55,accept_ser=.41),3))
