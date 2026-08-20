import json, torch
from vllm_xpu_kernels.flash_attn_interface import flash_attn_varlen_func
DEV="xpu:0"
QH, KVH, HD, BS = 12, 2, 256, 64
def blocks(kv):
    lb = (kv + BS - 1)//BS
    nb = lb + 3
    g = torch.Generator(device="cpu").manual_seed(777)
    order = torch.randperm(nb, generator=g)
    k = torch.randn(nb, BS, KVH, HD, dtype=torch.float16, device=DEV)
    v = torch.randn(nb, BS, KVH, HD, dtype=torch.float16, device=DEV)
    bt = torch.zeros(1, lb, dtype=torch.int32, device=DEV)
    bt[0].copy_(order[:lb].to(torch.int32).to(DEV))
    sk = torch.full((1,), kv, dtype=torch.int32, device=DEV)
    return k, v, bt, sk
out=[]
# decode: 6-row packed causal verifier, kv at observed flip neighborhoods + spread
for kv in (84, 296, 465, 514, 1024, 1306, 2047):
    k, v, bt, sk = blocks(kv)
    q = torch.randn(6, QH, HD, dtype=torch.float16, device=DEV)
    cu = torch.tensor([0, 6], dtype=torch.int32, device=DEV)
    obuf = torch.empty_like(q)
    fn = lambda: flash_attn_varlen_func(q, k, v, 6, cu, kv, seqused_k=sk, softmax_scale=HD**-0.5, causal=True, block_table=bt, out=obuf, is_mix_batch=False)
    fn(); torch.xpu.synchronize()
    ref = obuf.clone()
    bad=0
    for i in range(300):
        obuf.fill_(float('nan'))
        fn()
        if not torch.equal(obuf, ref): bad+=1
    torch.xpu.synchronize()
    out.append({"op": f"fa_decode_6row_causal_kv{kv}", "bad": bad})
    print(json.dumps(out[-1]), flush=True)
# prefill: causal self-attention at the divergent prompt lengths
for m in (49, 71, 187, 837, 100):
    qq = torch.randn(m, QH, HD, dtype=torch.float16, device=DEV)
    kk = torch.randn(m, KVH, HD, dtype=torch.float16, device=DEV)
    vv = torch.randn(m, KVH, HD, dtype=torch.float16, device=DEV)
    cuq = torch.tensor([0, m], dtype=torch.int32, device=DEV)
    ob = torch.empty_like(qq)
    fn = lambda: flash_attn_varlen_func(qq, kk, vv, m, cuq, m, softmax_scale=HD**-0.5, causal=True, out=ob)
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
json.dump(out, open("/tmp/fa_det.json","w"))
