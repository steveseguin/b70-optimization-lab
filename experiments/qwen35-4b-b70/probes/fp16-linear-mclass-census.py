# Run inside the R276 image on one card:  docker run --rm --entrypoint python3 --device /dev/dri:/dev/dri --group-add render --ipc=host -e ZE_AFFINITY_MASK=1 -v $PWD/<this>.py:/c.py:ro neural-download/vllm-openai-xpu:qwen38-int4-gdn-spec-group-sync-free-r276 /c.py
# Row-invariance census of eager F.linear (oneDNN fp16) at the Qwen3.5-4B vocabulary-projection shape.
# For each M: is row i of linear(X[:M]) bit-identical to linear(X[i:i+1])?  Is the call run-to-run deterministic?
import torch, sys, time
dev = "xpu"; torch.manual_seed(0)
N, K = 248320, 2560
W = (torch.randn(N, K, device=dev) * 0.02).half()
MAXM = 320
X = torch.randn(MAXM, K, device=dev).half()
lin = torch.nn.functional.linear
for _ in range(5): lin(X[:32], W)
torch.xpu.synchronize()
single = torch.cat([lin(X[i:i+1], W) for i in range(MAXM)], 0)   # M=1 reference, row by row
torch.xpu.synchronize()
Ms = [1,2,3,4,5,6,8,12,16,20,24,32,33,36,40,44,48,56,64,65,72,80,96,112,128,129,160,192,256,320]
print(f"shape N={N} K={K} fp16 eager oneDNN; torch {torch.__version__}")
print("   M  rows!=single  first_bad_row  maxabs      det  ms/call")
for M in Ms:
    a = lin(X[:M], W); torch.xpu.synchronize()
    b = lin(X[:M], W); torch.xpu.synchronize()
    det = torch.equal(a, b)
    bad = (a != single[:M]).any(dim=1)
    nb = int(bad.sum()); first = int(bad.nonzero()[0]) if nb else -1
    maxabs = float((a.float() - single[:M].float()).abs().max())
    t0 = time.perf_counter()
    for _ in range(10): lin(X[:M], W)
    torch.xpu.synchronize(); ms = (time.perf_counter() - t0) * 100
    print(f"{M:4d}  {nb:11d}  {first:13d}  {maxabs:.3e}  {str(det):>5}  {ms:7.2f}")
