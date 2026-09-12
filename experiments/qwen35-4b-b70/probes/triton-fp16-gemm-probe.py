# Run inside the R276 image on one card (ZE_AFFINITY_MASK=1). Result 2026-09-11: invariant and deterministic at every M, bit-identical to oneDNN at M=64, but 10% slower at M=1 on the lm_head shape and 2-5x slower from 32 rows; not a replacement for the class pad.
# Time-boxed prototype: a Triton fp16 GEMM (out = x @ W^T, fp32 accumulate, fixed BLOCK_K, no split-K) whose per-element
# reduction order is independent of M by construction. Question: is it row-invariant/deterministic at every M AND fast
# enough at M=1 (bandwidth-bound on the 1.2 GB weight) to replace padding? Compared with eager oneDNN F.linear.
import torch, time, triton, triton.language as tl
dev="xpu"; torch.manual_seed(0)

@triton.jit
def gemm_kernel(x_ptr, w_ptr, o_ptr, M, N, K, sxm, sxk, swn, swk, som, son,
                BM: tl.constexpr, BN: tl.constexpr, BK: tl.constexpr):
    pid_m = tl.program_id(0); pid_n = tl.program_id(1)
    rm = pid_m * BM + tl.arange(0, BM); rn = pid_n * BN + tl.arange(0, BN); rk = tl.arange(0, BK)
    acc = tl.zeros((BM, BN), dtype=tl.float32)
    for k0 in range(0, K, BK):
        xa = tl.load(x_ptr + rm[:, None] * sxm + (k0 + rk)[None, :] * sxk, mask=(rm[:, None] < M) & ((k0 + rk)[None, :] < K), other=0.0)
        wb = tl.load(w_ptr + rn[None, :] * swn + (k0 + rk)[:, None] * swk, mask=(rn[None, :] < N) & ((k0 + rk)[:, None] < K), other=0.0)
        acc += tl.dot(xa, wb)
    tl.store(o_ptr + rm[:, None] * som + rn[None, :] * son, acc.to(tl.float16), mask=(rm[:, None] < M) & (rn[None, :] < N))

def tgemm(x, w, BM=16, BN=128, BK=64):
    M, K = x.shape; N = w.shape[0]
    o = torch.empty((M, N), dtype=torch.float16, device=dev)
    grid = (triton.cdiv(M, BM), triton.cdiv(N, BN))
    gemm_kernel[grid](x, w, o, M, N, K, x.stride(0), x.stride(1), w.stride(0), w.stride(1), o.stride(0), o.stride(1), BM=BM, BN=BN, BK=BK)
    return o

lin = torch.nn.functional.linear
for N, K, label in [(248320, 2560, "lm_head 4B"), (12288, 2560, "per-layer B"), (2560, 4096, "out-proj")]:
    W = (torch.randn(N, K, device=dev) * 0.02).half(); X = torch.randn(320, K, device=dev).half()
    for cfg in [(16, 128, 64), (32, 64, 64), (16, 64, 32), (64, 128, 32)]:
        BM, BN, BK = cfg
        try:
            single = torch.cat([tgemm(X[i:i+1], W, BM, BN, BK) for i in range(64)], 0); torch.xpu.synchronize()
            inv = all(torch.equal(tgemm(X[:m], W, BM, BN, BK)[:min(m,64)], single[:min(m,64)]) for m in (1, 4, 32, 33, 64, 128, 256, 320))
            det = torch.equal(tgemm(X[:256], W, BM, BN, BK), tgemm(X[:256], W, BM, BN, BK))
            row = []
            for m in (1, 4, 32, 64, 256):
                f = lambda: tgemm(X[:m], W, BM, BN, BK)
                for _ in range(5): f()
                torch.xpu.synchronize(); t0 = time.perf_counter()
                for _ in range(20): f()
                torch.xpu.synchronize(); ms = (time.perf_counter() - t0) * 50
                for _ in range(5): lin(X[:m], W)
                torch.xpu.synchronize(); t0 = time.perf_counter()
                for _ in range(20): lin(X[:m], W)
                torch.xpu.synchronize(); ms0 = (time.perf_counter() - t0) * 50
                row.append(f"M{m}: {ms:.2f}/{ms0:.2f}")
            err = float((tgemm(X[:64], W, BM, BN, BK).float() - lin(X[:64], W).float()).abs().max())
            print(f"{label:12s} BM{BM} BN{BN} BK{BK}: invariant={inv} det={det} maxdiff_vs_onednn={err:.3e} | triton/onednn ms " + "  ".join(row), flush=True)
        except Exception as e:
            print(f"{label:12s} BM{BM} BN{BN} BK{BK}: FAILED {type(e).__name__}: {str(e)[:120]}", flush=True)
