# Run inside the R290 image with VLLM_XPU_FP16_LINEAR_CLASSPAD=1 VLLM_TARGET_DEVICE=xpu on one card (see classpad chain header).
import os, time, torch, logging
logging.basicConfig(level=logging.INFO)
import vllm.model_executor.layers.utils as U
dev="xpu"; torch.manual_seed(1)
lin=torch.nn.functional.linear
for (N,K,label) in [(248320,2560,"lm_head TP1"),(124160,2560,"lm_head TP2 shard"),(2560,5120,"mtp.fc-like")]:
    W=(torch.randn(N,K,device=dev)*0.02).half(); X=torch.randn(600,K,device=dev).half()
    class L: pass
    f=lambda x: U.default_unquantized_gemm(L(), x, W, None)
    f(X[:1]); torch.xpu.synchronize()
    ref=f(X[:128]); torch.xpu.synchronize()            # canonical-class reference rows
    print(f"\n=== {label} N={N} K={K}")
    bad=[]
    for M in [1,2,8,16,32,33,64,100,128,129,200,256,320,321,400,512,513,600]:
        o=f(X[:M]); torch.xpu.synchronize()
        n=min(M,128)
        ok=torch.equal(o[:n],ref[:n]) and torch.equal(o, f(X[:M]))
        if not ok: bad.append(M)
    print("row-invariant across M and deterministic:", "ALL OK" if not bad else f"FAIL at {bad}")
    # also: all rows of a big call equal the corresponding rows of single calls under classpad
    single=torch.cat([f(X[i:i+1]) for i in range(64)],0); big=f(X[:64]); torch.xpu.synchronize()
    print("64-row call == 64 single-row calls:", torch.equal(single,big))
    for M in [1,32,64,128,256,512]:
        t0=time.perf_counter()
        for _ in range(10): f(X[:M])
        torch.xpu.synchronize(); ms=(time.perf_counter()-t0)*100
        t0=time.perf_counter()
        for _ in range(10): lin(X[:M],W)
        torch.xpu.synchronize(); ms_plain=(time.perf_counter()-t0)*100
        pieces=-(-M//32)
        print(f"  M={M:3d}: classpad {ms:5.2f} ms  plain {ms_plain:5.2f} ms  (R224 chunk32 would be ~{pieces} pieces)")
