import json, torch
import vllm_xpu_kernels._xpu_C  # noqa
DEV="xpu:0"
def nt_pack(q): return q.t().contiguous().t()
torch.manual_seed(20260820)
zp8 = torch.tensor([8], dtype=torch.int8, device=DEV)
K, N = 5120, 1408
w_nt = nt_pack(torch.randint(-2**31, 2**31-1, (K//8, N), dtype=torch.int32)).to(DEV)
ws = torch.randn(K//128, N, dtype=torch.float16, device=DEV).abs()
M_REAL, M_PAD = 341, 512
real = torch.randn(M_REAL, K, dtype=torch.float16, device=DEV)
junk_a = torch.randn(M_PAD-M_REAL, K, dtype=torch.float16, device=DEV)
junk_b = torch.randn(M_PAD-M_REAL, K, dtype=torch.float16, device=DEV) * 100
def gemm(x):
    return torch.ops._xpu_C.int4_gemm_w4a16(
        x, w_nt, None, ws, zp8, 128, None
    )
xa = torch.cat([real, junk_a]); xb = torch.cat([real, junk_b])
oa = gemm(xa)[:M_REAL]; ob = gemm(xb)[:M_REAL]
torch.xpu.synchronize()
row_independence = torch.equal(oa, ob)
# stability of padded execution across 500 runs
ref = gemm(xa).clone(); torch.xpu.synchronize()
bad = sum(0 if torch.equal(gemm(xa), ref) else 1 for _ in range(500))
torch.xpu.synchronize()
print(json.dumps({"row_independence": row_independence, "padded_m512_stability_bad_iters": bad, "iters": 500}))
