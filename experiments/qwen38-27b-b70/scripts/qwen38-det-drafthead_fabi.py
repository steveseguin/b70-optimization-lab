import json, torch
import vllm_xpu_kernels._xpu_C  # noqa
DEV="xpu:0"
def nt_pack(q): return q.t().contiguous().t()
torch.manual_seed(20260824)
zp8 = torch.tensor([8], dtype=torch.int8, device=DEV)
out=[]
# A: draft LM head int4 [M,5120]x[5120,37984] (TP-local vocab half)
K, N = 5120, 37984
w_nt = nt_pack(torch.randint(-2**31, 2**31-1, (K//8, N), dtype=torch.int32)).to(DEV)
ws = torch.randn(K//128, N, dtype=torch.float16, device=DEV).abs()
for m in (1,2,3,4,5,6):
    x = torch.randn(m, K, dtype=torch.float16, device=DEV)
    fn = lambda: torch.ops._xpu_C.int4_gemm_w4a16(x, w_nt, None, ws, zp8, 128, None, False)
    ref = fn(); torch.xpu.synchronize(); ref=ref.clone()
    bad = sum(0 if torch.equal(fn(), ref) else 1 for _ in range(100))
    torch.xpu.synchronize()
    out.append({"op": f"int4_draft_head_m{m}", "bad": bad}); print(json.dumps(out[-1]), flush=True)
del w_nt, ws; torch.xpu.empty_cache()
json.dump(out, open("/tmp/drafthead.json","w"))
