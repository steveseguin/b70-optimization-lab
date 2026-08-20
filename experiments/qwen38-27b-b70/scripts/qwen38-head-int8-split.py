import json, time, torch
import vllm_xpu_kernels._xpu_C  # noqa
DEV="xpu:0"
torch.manual_seed(20260830)
K, N = 5120, 37984
w8 = torch.randint(-127, 127, (K, N), dtype=torch.int8, device=DEV).t().contiguous().t()
ws8 = torch.randn(N, dtype=torch.float32, device=DEV).abs()
out=[]
for m in (1, 6):
    x = torch.randn(m, K, dtype=torch.float16, device=DEV)
    xq, xs = torch.ops._xpu_C.per_token_quant_int8_xpu(x)
    for name, fn in (("quant", lambda: torch.ops._xpu_C.per_token_quant_int8_xpu(x)),
                     ("w8a8_gemm", lambda: torch.ops._xpu_C.int8_gemm_w8a8(xq, xs, w8, ws8, torch.float16, None))):
        for _ in range(20): fn()
        torch.xpu.synchronize()
        t0 = time.perf_counter()
        for _ in range(200): fn()
        torch.xpu.synchronize()
        us = (time.perf_counter()-t0)/200*1e6
        out.append({"op": f"{name}_m{m}", "us_per_call": round(us, 2)})
        print(json.dumps(out[-1]), flush=True)
json.dump(out, open("/tmp/head_split.json","w"))
