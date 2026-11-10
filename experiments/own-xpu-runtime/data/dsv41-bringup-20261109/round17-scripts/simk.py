import sys, itertools
# rows: c0..c4 kk kept   (kept = guesses accepted when kk=5 were checked)
R=[]
for f in sys.argv[1:]:
    for l in open(f):
        v=l.split()
        if len(v)<7: continue
        R.append(([float(x) for x in v[:5]], int(v[5]), int(v[6])))
print("rounds", len(R))
# calibration: P(guess i right | previous right) by conf bin
bins=[0,.3,.5,.7,.85,.95,.99,1.01]
for i in range(5):
    out=[]
    for lo,hi in zip(bins,bins[1:]):
        s=[r for r in R if r[2]>=i and lo<=r[0][i]<hi]
        if s: out.append(f"[{lo:.2f},{hi:.2f}) n={len(s):3d} p={sum(r[2]>i for r in s)/len(s):.2f}")
    print("guess",i,"; ".join(out))
T={0:17.1,1:22.1,2:24.3,3:28.0,4:32.5,5:33.3}
def run(pol):
    tok=0; t=0
    for c,kk,a in R:
        k=pol(c); tok+=min(a,k)+1; t+=T[k]
    return tok/t*1000
for k in range(6): print("fixed k",k, f"{run(lambda c,k=k:k):.1f}")
best=[]
for kmin in (0,1,2):
  for tau in (0.05,0.1,0.15,0.2,0.3,0.4,0.5,0.6,0.7,0.8):
    def pol(c,kmin=kmin,tau=tau):
        p=1;k=0
        for x in c:
            p*=x
            if p<tau: break
            k+=1
        return max(kmin,k)
    best.append((run(pol),f"prod kmin={kmin} tau={tau}"))
for lam in (0.06,0.07,0.08,0.09,0.10,0.11):
  for allowed in ((3,5),(2,3,5),(1,2,3,4,5),(0,1,2,3,4,5),(3,4,5)):
    def pol(c,lam=lam,allowed=allowed):
        bestv=None
        for k in allowed:
            e=1;p=1
            for x in c[:k]: p*=x; e+=p
            v=e-lam*T[k]
            if bestv is None or v>bestv[0]: bestv=(v,k)
        return bestv[1]
    best.append((run(pol),f"expect lam={lam} allowed={allowed}"))
best.sort(reverse=True)
for v,n in best[:12]: print(f"{v:.1f}",n)
