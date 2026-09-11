# Run inside the R276 image on one card (ZE_AFFINITY_MASK=1): every unquantized-linear shape the 4B server logged, class map, invariance per class, and the per-call pad overhead at M=1.
# Invariance census for every unquantized-linear shape R290 met on the server (from the census log lines),
# plus the per-call overhead of the R290 pad at M=1 versus a plain call and versus R224's chunked op.
import torch, time, os
dev="xpu"; torch.manual_seed(0)
lin=torch.nn.functional.linear
def census(N,K,label):
    W=(torch.randn(N,K,device=dev)*0.02).half(); X=torch.randn(512,K,device=dev).half()
    for _ in range(3): lin(X[:32],W)
    single=torch.cat([lin(X[i:i+1],W) for i in range(256)],0); torch.xpu.synchronize()
    # class of row 0 for M=1..512
    refs=[];cls=[]
    for M in range(1,513):
        r=lin(X[:M],W)[:1]; c=None
        for i,q in enumerate(refs):
            if torch.equal(r,q): c=i;break
        if c is None: refs.append(r.clone()); c=len(refs)-1
        cls.append(c)
    runs=[];s=1
    for M in range(2,514):
        if M>512 or cls[M-1]!=cls[M-2]: runs.append(f"{s}-{M-1}:c{cls[M-2]}"); s=M
    print(f"\n=== {label} N={N} K={K}: classes={len(refs)} map={' '.join(runs)}")
    # for each class representative M: row-invariance (all rows == single-row? only for c0), position and pad invariance, determinism
    seen=set()
    for M in range(1,513):
        c=cls[M-1]
        if c in seen: continue
        seen.add(c)
        for m in sorted({M, min(512, M+7), min(512,2*M)}):
            if cls[m-1]!=c: continue
            o=lin(X[:m],W); perm=torch.roll(torch.arange(m,device=dev),3); op=lin(X[perm],W)
            pos=torch.equal(op[torch.argsort(perm)],o)
            h=max(m//2,1); xp=torch.cat([X[:h],torch.zeros(m-h,K,device=dev,dtype=torch.float16)],0)
            pad=torch.equal(lin(xp,W)[:h],o[:h])
            det=all(torch.equal(lin(X[:m],W),o) for _ in range(3))
            n=min(m,256); eqs=torch.equal(o[:n],single[:n])
            print(f"   class c{c} at M={m:3d}: pos_inv={pos} pad_inv={pad} det={det} ==single={eqs}")
    # overhead at M=1: plain vs zero-pad-to-33 (R290 style) vs persistent buffer copy
    x1=X[:1]
    def r290(x):
        pad=torch.zeros(32,K,device=dev,dtype=torch.float16); return lin(torch.cat([x,pad],0),W)[:1]
    buf=torch.zeros(33,K,device=dev,dtype=torch.float16)
    def r291(x):
        buf[:1].copy_(x); return lin(buf,W)[:1]
    for name,fn in (("plain M=1",lambda: lin(x1,W)),("R290 pad->33",lambda: r290(x1)),("persistent buf->33",lambda: r291(x1)),("plain M=33",lambda: lin(X[:33],W))):
        for _ in range(20): fn()
        torch.xpu.synchronize(); t0=time.perf_counter()
        for _ in range(200): fn()
        torch.xpu.synchronize(); print(f"   {name:20s} {(time.perf_counter()-t0)*5:.3f} ms/call")
for N,K,l in [(10240,2560,"per-layer A (TP1)"),(12288,2560,"per-layer B (TP1)"),(5120,2560,"per-layer A (TP2 shard)"),(6144,2560,"per-layer B (TP2 shard)"),(2560,5120,"fc-like"),(1280,5120,"fc shard (TP2)")]:
    census(N,K,l)
