import json, torch
import vllm_xpu_kernels._xpu_C  # noqa
DEV="xpu:0"
def nt_pack(q): return q.t().contiguous().t()
torch.manual_seed(20260825)
zp8 = torch.tensor([8], dtype=torch.int8, device=DEV)
shapes = {"qkv_5120x1408": (5120,1408), "o_5120x5120": (5120,5120),
          "gateup_5120x8704": (5120,8704), "down_8704x5120": (8704,5120),
          "draft_head_5120x37984": (5120,37984)}
out=[]
for name,(K,N) in shapes.items():
    w_nt = nt_pack(torch.randint(-2**31, 2**31-1, (K//8, N), dtype=torch.int32)).to(DEV)
    ws = torch.randn(K//128, N, dtype=torch.float16, device=DEV).abs()
    for m in (48, 49, 64, 71, 90, 128):
        x = torch.randn(m, K, dtype=torch.float16, device=DEV)
        fn = lambda: torch.ops._xpu_C.int4_gemm_w4a16(x, w_nt, None, ws, zp8, 128, None, False)
        ref = fn(); torch.xpu.synchronize(); ref=ref.clone()
        bad = sum(0 if torch.equal(fn(), ref) else 1 for _ in range(80))
        torch.xpu.synchronize()
        if bad: out.append({"op": f"{name}_m{m}", "bad": bad})
    del w_nt, ws; torch.xpu.empty_cache()
print(json.dumps({"dirty": out if out else "NONE - all clean at M=48..128"}))
json.dump(out, open("/tmp/m49.json","w"))
