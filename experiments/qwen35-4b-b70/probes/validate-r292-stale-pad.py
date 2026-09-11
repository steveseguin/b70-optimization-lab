# Run inside the R292 image with VLLM_XPU_FP16_LINEAR_CLASSPAD=1 VLLM_TARGET_DEVICE=xpu on one card.
# Stale pad rows: fill the persistent pad buffer with garbage via a large call, then check that smaller
# calls still return rows bit-identical to fresh single-row calls, for every server shape, many times.
import torch, time
import vllm.model_executor.layers.utils as U
dev="xpu"; torch.manual_seed(7)
class L: pass
for N,K,label in [(248320,2560,"lm_head TP1"),(124160,2560,"lm_head TP2 shard"),(12288,2560,"per-layer B"),(10240,2560,"per-layer A"),(2560,4096,"out-proj"),(6144,2560,"TP2 B"),(2560,2048,"TP2 out-proj")]:
    W=(torch.randn(N,K,device=dev)*0.02).half()
    f=lambda x: U.default_unquantized_gemm(L(), x, W, None)
    f(torch.randn(1,K,device=dev).half()); torch.xpu.synchronize()
    bad=0; trials=0
    for trial in range(6):
        X=(torch.randn(600,K,device=dev)*(10.0 if trial%2 else 0.3)).half()   # garbage of wildly different scale
        f(X[:400]); f(X[:33]); f(X[:129]); f(X[:512])                          # dirty the buffers
        single=torch.cat([f(X[i:i+1]) for i in range(40)],0); torch.xpu.synchronize()
        for M in [1,2,3,4,8,12,16,20,24,32,33,40]:
            o=f(X[:M]); n=min(M,40); trials+=1
            if not torch.equal(o[:n],single[:n]): bad+=1
        f(X[:600])  # dirty again with different rows
        for M in [1,4,24]:
            o=f(X[:M]); trials+=1
            if not torch.equal(o[:M],single[:M]): bad+=1
    x1=X[:1]
    for _ in range(20): f(x1)
    torch.xpu.synchronize(); t0=time.perf_counter()
    for _ in range(200): f(x1)
    torch.xpu.synchronize(); ms=(time.perf_counter()-t0)*5
    t0=time.perf_counter()
    for _ in range(200): torch.nn.functional.linear(x1,W)
    torch.xpu.synchronize(); ms0=(time.perf_counter()-t0)*5
    print(f"{label:18s} N={N:6d} K={K}: stale-pad mismatches {bad}/{trials}   M=1 op {ms:.3f} ms  plain {ms0:.3f} ms")
