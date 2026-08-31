import json, torch
import vllm_xpu_kernels._xpu_C  # noqa
DEV="xpu:0"
def nt_pack(q): return q.t().contiguous().t()
torch.manual_seed(20260820)
zp8 = torch.tensor([8], dtype=torch.int8, device=DEV)
w_nt = nt_pack(torch.randint(-2**31, 2**31-1, (5120//8, 1408), dtype=torch.int32)).to(DEV)
ws = torch.randn(5120//128, 1408, dtype=torch.float16, device=DEV).abs()
out_rows=[]
for m in (6, 8, 16, 32, 64, 128, 256, 341, 512, 1024):
    x = torch.randn(m, 5120, dtype=torch.float16, device=DEV)
    fn = lambda: torch.ops._xpu_C.int4_gemm_w4a16(
        x, w_nt, None, ws, zp8, 128, None
    )
    ref = fn(); torch.xpu.synchronize(); ref = ref.clone()
    bad = 0
    for i in range(200):
        if not torch.equal(fn(), ref): bad += 1
    torch.xpu.synchronize()
    out_rows.append({"m": m, "mismatches": bad, "iters": 200})
    print(json.dumps(out_rows[-1]), flush=True)
json.dump(out_rows, open("/tmp/msweep.json","w"))
