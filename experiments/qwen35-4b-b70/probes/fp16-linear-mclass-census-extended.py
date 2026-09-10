# Run inside the R276 image on one card:  docker run --rm --entrypoint python3 --device /dev/dri:/dev/dri --group-add render --ipc=host -e ZE_AFFINITY_MASK=1 -v $PWD/<this>.py:/c.py:ro neural-download/vllm-openai-xpu:qwen38-int4-gdn-spec-group-sync-free-r276 /c.py
# Extended row-invariance census at the Qwen3.5-4B vocabulary-projection shape (N=248320, K=2560, fp16).
# Questions: (1) how many M-classes; (2) within a class, is row i's value independent of its position and
# of the other rows (so a zero-padded call gives the same rows); (3) repeat determinism; (4) does a
# transposed weight layout (x @ W^T stored K x N) change the class structure; (5) cost per call.
import torch, time
dev="xpu"; torch.manual_seed(0)
N,K=248320,2560; MAXM=512
W=(torch.randn(N,K,device=dev)*0.02).half(); Wt=W.t().contiguous()
X=torch.randn(MAXM,K,device=dev).half()
variants={"linear(x,W)":lambda x:torch.nn.functional.linear(x,W), "x@Wt":lambda x:x@Wt}
Ms=[1,4,16,32,33,48,64,96,97,104,112,128,192,256,320,384,512]
for name,f in variants.items():
    for _ in range(5): f(X[:32])
    torch.xpu.synchronize()
    single=torch.cat([f(X[i:i+1]) for i in range(MAXM)],0); torch.xpu.synchronize()
    outs={}
    print(f"\n=== {name}")
    print("   M  ==single  class  pos_inv  pad_inv  det5  ms/call")
    refs=[]  # class representatives: (M, out rows 0..3)
    for M in Ms:
        o=f(X[:M]); torch.xpu.synchronize(); outs[M]=o
        eq_single=bool(torch.equal(o,single[:M]))
        cls=None
        for ci,(rm,ro) in enumerate(refs):
            if torch.equal(o[:4],ro): cls=ci; break
        if cls is None: refs.append((M,o[:4].clone())); cls=len(refs)-1
        # position invariance: roll the rows by 7 and compare row-wise after un-rolling
        perm=torch.roll(torch.arange(M,device=dev),7); op=f(X[perm]); torch.xpu.synchronize()
        pos_inv=bool(torch.equal(op[torch.argsort(perm)],o))
        # pad invariance: rows of a zero-padded call at this M equal the rows of the un-padded call at M//2
        h=max(M//2,1); xp=torch.cat([X[:h],torch.zeros(M-h,K,device=dev,dtype=torch.float16)],0)
        pad_inv=bool(torch.equal(f(xp)[:h],o[:h]))
        det=all(torch.equal(f(X[:M]),o) for _ in range(5))
        t0=time.perf_counter()
        for _ in range(10): f(X[:M])
        torch.xpu.synchronize(); ms=(time.perf_counter()-t0)*100
        print(f"{M:4d}  {str(eq_single):>8}  {cls:5d}  {str(pos_inv):>7}  {str(pad_inv):>7}  {str(det):>4}  {ms:7.2f}")
    print("class representatives (first M seen):",[m for m,_ in refs])
