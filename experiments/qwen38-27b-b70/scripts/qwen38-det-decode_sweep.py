import json, os, torch
import vllm_xpu_kernels._xpu_C  # noqa
DEV="xpu:0"
def nt_pack(q): return q.t().contiguous().t()
torch.manual_seed(20260821)
zp8 = torch.tensor([8], dtype=torch.int8, device=DEV)
out=[]
# int4 GEMM at MTP5 intermediate verifier widths
w_nt = nt_pack(torch.randint(-2**31, 2**31-1, (5120//8, 1408), dtype=torch.int32)).to(DEV)
ws = torch.randn(5120//128, 1408, dtype=torch.float16, device=DEV).abs()
for m in (2,3,4,5):
    x = torch.randn(m, 5120, dtype=torch.float16, device=DEV)
    fn = lambda: torch.ops._xpu_C.int4_gemm_w4a16(x, w_nt, None, ws, zp8, 128, None, False)
    ref = fn(); torch.xpu.synchronize(); ref=ref.clone()
    bad = sum(0 if torch.equal(fn(), ref) else 1 for _ in range(300))
    torch.xpu.synchronize()
    out.append({"op": f"int4_m{m}", "bad": bad}); print(json.dumps(out[-1]), flush=True)
# batch-invariance probe: SAME row computed at M=1 vs M=6 - bitwise or not?
x6 = torch.randn(6, 5120, dtype=torch.float16, device=DEV)
row0 = x6[0:1].clone()
o6 = torch.ops._xpu_C.int4_gemm_w4a16(x6, w_nt, None, ws, zp8, 128, None, False)
o1 = torch.ops._xpu_C.int4_gemm_w4a16(row0, w_nt, None, ws, zp8, 128, None, False)
torch.xpu.synchronize()
eq = torch.equal(o6[0:1], o1)
md = float((o6[0:1].float()-o1.float()).abs().max())
out.append({"op": "batch_invariance_row0_m6_vs_m1", "bitwise_equal": eq, "max_abs_diff": md})
print(json.dumps(out[-1]), flush=True)
json.dump(out, open("/tmp/decode_sweep.json","w"))
