# Run inside the R276 image on one card:  docker run --rm --entrypoint python3 --device /dev/dri:/dev/dri --group-add render --ipc=host -e ZE_AFFINITY_MASK=1 -v $PWD/<this>.py:/c.py:ro neural-download/vllm-openai-xpu:qwen38-int4-gdn-spec-group-sync-free-r276 /c.py
import torch
dev="xpu"; torch.manual_seed(0)
N,K=248320,2560; MAXM=512
W=(torch.randn(N,K,device=dev)*0.02).half(); X=torch.randn(MAXM,K,device=dev).half()
f=lambda x: torch.nn.functional.linear(x,W)
for _ in range(3): f(X[:32])
refs=[]; cls=[]
for M in range(1,MAXM+1):
    o=f(X[:M])[:1].clone()   # row 0 only: class = which rounding row 0 got
    c=None
    for i,r in enumerate(refs):
        if torch.equal(o,r): c=i; break
    if c is None: refs.append(o); c=len(refs)-1
    cls.append(c)
# print runs
runs=[]; start=1
for M in range(2,MAXM+1):
    if cls[M-1]!=cls[M-2]: runs.append((start,M-1,cls[M-2])); start=M
runs.append((start,MAXM,cls[-1]))
print("classes:",len(refs))
for a,b,c in runs: print(f"  M {a:3d}..{b:3d} -> class {c}")
