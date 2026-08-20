import json, torch
from vllm_xpu_kernels.flash_attn_interface import flash_attn_varlen_func
DEV="xpu:0"
QH, KVH, HD = 12, 2, 256
out=[]
for m in (49, 71, 187, 341, 837):
    qq = torch.randn(m, QH, HD, dtype=torch.float16, device=DEV)
    kk = torch.randn(m, KVH, HD, dtype=torch.float16, device=DEV)
    vv = torch.randn(m, KVH, HD, dtype=torch.float16, device=DEV)
    cuq = torch.tensor([0, m], dtype=torch.int32, device=DEV)
    sk = torch.tensor([m], dtype=torch.int32, device=DEV)
    cuk = torch.tensor([0, m], dtype=torch.int32, device=DEV)
    ob = torch.empty_like(qq)
    fn = lambda: flash_attn_varlen_func(qq, kk, vv, m, cuq, m, cu_seqlens_k=cuk, softmax_scale=HD**-0.5, causal=True, out=ob)
    fn(); torch.xpu.synchronize()
    ref = ob.clone()
    bad=0
    for i in range(200):
        ob.fill_(float('nan'))
        fn()
        if not torch.equal(ob, ref): bad+=1
    torch.xpu.synchronize()
    out.append({"op": f"fa_prefill_m{m}", "bad": bad})
    print(json.dumps(out[-1]), flush=True)
json.dump(out, open("/tmp/fa_prefill_det.json","w"))
