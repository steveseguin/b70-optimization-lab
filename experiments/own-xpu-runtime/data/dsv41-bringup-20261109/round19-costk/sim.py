# offline guess-length policy simulator over all-guesses-checked logs (runs/tau0/*_t0-spec.txt)
# rate = sum(tokens) / sum(draft + check(k)); check(k) from unprofiled per-cycle times (tg105v + tau0 logs)
import sys, math, glob, collections, statistics as st
W='/home/steve/dsv41-work'
CK=[10.02,12.70,14.96,16.55,19.04,20.64]; DR=1.78
def load(n):
    rows=[]
    for i,l in enumerate(open(f'{W}/runs/tau0/{n}_t0-spec.txt')):
        x=l.split()
        if len(x)<10: continue
        c=[float(v) for v in x[:5]]; acc=int(x[6])
        rows.append((c,acc))
    return rows
P=['code','analysis','prose','docs','ops']
D={n:load(n) for n in P}
def cum(c):
    out=[];r=1.0
    for v in c: r*=v; out.append(r)
    return out
def rate(rows,pol):
    tok=0;t=0
    for c,acc in rows:
        k=pol(c); tok+=min(acc,k)+1; t+=DR+CK[k]
    return 1000*tok/t
def tau(t):
    def f(c):
        k=0
        for p in cum(c):
            if p>=t: k+=1
            else: break
        return k
    return f
# calibration: P(guess j right | all before right) by raw conf bins, and P(acc>=j) vs cumprod bins
def calib(rows_all):
    bins=collections.defaultdict(lambda:[0,0])
    for c,acc in rows_all:
        for j,p in enumerate(cum(c)):
            b=min(9,int(p*10)); bins[(j,b)][0]+=1; bins[(j,b)][1]+=(acc>=j+1)
    return bins
allrows=sum(D.values(),[])
b=calib(allrows)
print('calibration: cumprod bin -> observed P(first j guesses right), by position j (n)')
for bb in range(10):
    print(f'{bb/10:.1f}-{(bb+1)/10:.1f}', ' '.join(f'{(b[(j,bb)][1]/b[(j,bb)][0]) if b[(j,bb)][0] else float("nan"):.2f}({b[(j,bb)][0]:3d})' for j in range(5)))
print()
print('TAU sweep (sim tok/s):')
for t in [0.0,0.2,0.3,0.4,0.45,0.5,0.55,0.6,0.7,0.8,1.01]:
    print(f'  tau {t:.2f}', ' '.join(f'{n} {rate(D[n],tau(t)):6.1f}' for n in P), f' mean {st.mean(rate(D[n],tau(t)) for n in P):6.1f}')

# --- cost-aware: choose k maximizing sum_{j<=k} Pj - lam*(DR+CK[k]) (renewal-reward / Dinkelbach), Pj calibrated
def fitcal(rows):
    # per position j, isotonic-ish binned map of cumprod -> P(first j right); 10 bins, pooled-adjacent monotone
    m=[]
    for j in range(5):
        cnt=[[0,0] for _ in range(10)]
        for c,acc in rows:
            p=cum(c)[j]; b=min(9,int(p*10)); cnt[b][0]+=1; cnt[b][1]+=(acc>=j+1)
        # pool adjacent violators
        blocks=[[cnt[b][1],cnt[b][0],[b]] for b in range(10) if cnt[b][0]>0]
        i=0
        while i<len(blocks)-1:
            if blocks[i][0]/blocks[i][1] > blocks[i+1][0]/blocks[i+1][1]:
                blocks[i]=[blocks[i][0]+blocks[i+1][0],blocks[i][1]+blocks[i+1][1],blocks[i][2]+blocks[i+1][2]]; del blocks[i+1]; i=max(0,i-1)
            else: i+=1
        mp=[None]*10
        for s,nn,bs in blocks:
            for bb in bs: mp[bb]=s/nn
        last=0.0
        for bb in range(10):
            if mp[bb] is None: mp[bb]=last
            last=mp[bb]
        m.append(mp)
    return m
def costk(lam,cal=None):
    def f(c):
        cp=cum(c); best=0; bv=-lam*(DR+CK[0]); s=0
        for k in range(1,6):
            p=cp[k-1]
            if cal: p=cal[k-1][min(9,int(p*10))]
            s+=p; v=s-lam*(DR+CK[k])
            if v>bv: bv=v; best=k
        return best
    return f
print()
print('cost-aware, raw cumprod as P:')
for lam in [0.12,0.14,0.16,0.18,0.20,0.22]:
    print(f'  lam {lam:.2f}', ' '.join(f'{n} {rate(D[n],costk(lam)):6.1f}' for n in P), f' mean {st.mean(rate(D[n],costk(lam)) for n in P):6.1f}')
print('cost-aware, calibrated on all five (in-sample):')
cal=fitcal(allrows)
for lam in [0.12,0.14,0.16,0.18,0.20]:
    print(f'  lam {lam:.2f}', ' '.join(f'{n} {rate(D[n],costk(lam,cal)):6.1f}' for n in P), f' mean {st.mean(rate(D[n],costk(lam,cal)) for n in P):6.1f}')
print('cost-aware, calibrated leave-one-prompt-out (held-out prompt scored):')
for lam in [0.12,0.14,0.16,0.18,0.20]:
    r=[rate(D[n],costk(lam,fitcal(sum((D[o] for o in P if o!=n),[])))) for n in P]
    print(f'  lam {lam:.2f}', ' '.join(f'{n} {v:6.1f}' for n,v in zip(P,r)), f' mean {st.mean(r):6.1f}')
print()
orc=lambda rows: 1000*sum(a+1 for c,a in rows)/sum(DR+CK[a] for c,a in rows)
print('oracle (check exactly the guesses that will be kept):', ' '.join(f'{n} {orc(D[n]):6.1f}' for n in P), f' mean {st.mean(orc(D[n]) for n in P):6.1f}')
# per-position thresholds on cumprod, coordinate search, in-sample (upper bound for threshold rules)
def thr(ts):
    def f(c):
        k=0
        for j,p in enumerate(cum(c)):
            if p>=ts[j]: k+=1
            else: break
        return k
    return f
ts=[0.5]*5; best=st.mean(rate(D[n],thr(ts)) for n in P)
for it in range(3):
    for j in range(5):
        for v in [x/100 for x in range(10,96,5)]:
            t2=ts[:]; t2[j]=v; r=st.mean(rate(D[n],thr(t2)) for n in P)
            if r>best: best=r; ts=t2
print('best per-position cutoffs in-sample', ts, f'mean {best:.1f}', ' '.join(f'{n} {rate(D[n],thr(ts)):6.1f}' for n in P))
