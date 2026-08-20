import json, torch
from vllm.model_executor.layers.fla.ops import chunk_gated_delta_rule
DEV="xpu:0"
torch.manual_seed(20260823)
H, K, V = 24, 128, 128
out=[]
for T in (49, 71, 187, 341, 512, 837):
    q = torch.randn(1, T, H, K, dtype=torch.float16, device=DEV)
    k = torch.randn(1, T, H, K, dtype=torch.float16, device=DEV)
    v = torch.randn(1, T, H, V, dtype=torch.float16, device=DEV)
    g = torch.randn(1, T, H, dtype=torch.float32, device=DEV).clamp(-8, -0.01)
    b = torch.rand(1, T, H, dtype=torch.float32, device=DEV)
    s0 = torch.randn(1, H, V, K, dtype=torch.float32, device=DEV)
    cu = torch.tensor([0, T], dtype=torch.int32, device=DEV)
    def fn():
        return chunk_gated_delta_rule(q, k, v, g, b, initial_state=s0,
                                      output_final_state=True, cu_seqlens=cu,
                                      use_qk_l2norm_in_kernel=True)
    o, st = fn(); torch.xpu.synchronize()
    oref, sref = o.clone(), st.clone()
    bad = 0
    for i in range(200):
        o2, st2 = fn()
        if not (torch.equal(o2, oref) and torch.equal(st2, sref)):
            bad += 1
            if bad == 1:
                do = float((o2.float()-oref.float()).abs().max())
                ds = float((st2.float()-sref.float()).abs().max())
                print(f"  T={T} first mismatch iter={i} d_out={do} d_state={ds}", flush=True)
    torch.xpu.synchronize()
    out.append({"op": f"gdn_chunk_prefill_T{T}", "bad": bad})
    print(json.dumps(out[-1]), flush=True)
    del q,k,v,g,b,s0,oref,sref; torch.xpu.empty_cache()
json.dump(out, open("/tmp/gdn_prefill_det.json","w"))
