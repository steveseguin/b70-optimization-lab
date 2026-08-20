import json, time, torch
import vllm_xpu_kernels._xpu_C  # noqa
DEV="xpu:0"
def nt_pack(q): return q.t().contiguous().t()
torch.manual_seed(20260831)
zp8 = torch.tensor([8], dtype=torch.int8, device=DEV)
K, N = 5120, 124160   # hidden, TP-local vocab (248320/2)
w4 = nt_pack(torch.randint(-2**31, 2**31-1, (K//8, N), dtype=torch.int32)).to(DEV)
ws4 = torch.randn(K//128, N, dtype=torch.float16, device=DEV).abs()
w8 = torch.randint(-127, 127, (K, N), dtype=torch.int8, device=DEV).t().contiguous().t()
ws8 = torch.randn(N, dtype=torch.float32, device=DEV).abs()
out=[]
for m in (1, 6):
    x = torch.randn(m, K, dtype=torch.float16, device=DEV)
    xq, xs = torch.ops._xpu_C.per_token_quant_int8_xpu(x)
    for name, fn in (("int4", lambda: torch.ops._xpu_C.int4_gemm_w4a16(x, w4, None, ws4, zp8, 128, None, False)),
                     ("int8_pair", lambda: torch.ops._xpu_C.int8_gemm_w8a8(xq, xs, w8, ws8, torch.float16, None))):
        for _ in range(10): fn()
        torch.xpu.synchronize()
        t0 = time.perf_counter()
        for _ in range(60): fn()
        torch.xpu.synchronize()
        us = (time.perf_counter()-t0)/60*1e6
        bw = (N*K*(0.5 if name=="int4" else 1.0))/ (us*1e-6) / 1e9
        out.append({"op": f"{name}_head_m{m}_n124160", "us_per_call": round(us,1), "weight_GB_s": round(bw,1)})
        print(json.dumps(out[-1]), flush=True)
json.dump(out, open("/tmp/head_real.json","w"))
