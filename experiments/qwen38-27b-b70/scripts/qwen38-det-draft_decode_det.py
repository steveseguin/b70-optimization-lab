import json, torch
from vllm.model_executor.layers.fla.ops import fused_recurrent_gated_delta_rule_packed_decode as frd
DEV="xpu:0"
torch.manual_seed(20260828)
B, H, HV, K, V, NS = 1, 8, 24, 128, 128, 64
qkv = torch.randn(B, 5120, dtype=torch.float16, device=DEV)
a = torch.randn(B, HV, dtype=torch.float32, device=DEV)
b = torch.randn(B, HV, dtype=torch.float32, device=DEV)
A_log = torch.randn(HV, dtype=torch.float32, device=DEV)
dt_bias = torch.randn(HV, dtype=torch.float32, device=DEV)
state = torch.randn(NS, HV, V, K, dtype=torch.float32, device=DEV)
idx = torch.tensor([7], dtype=torch.int64, device=DEV)
out = torch.zeros(B, 1, HV, V, dtype=torch.float16, device=DEV)
snap = state.clone()
def fn():
    frd(qkv, a, b, A_log, dt_bias, K**-0.5, state, out, idx, use_qk_l2norm_in_kernel=True)
fn(); torch.xpu.synchronize()
ref_o = out.clone(); ref_s = state.clone()
bad = 0
for rep in range(500):
    out.zero_(); state.copy_(snap)
    fn(); torch.xpu.synchronize()
    if not (torch.equal(out, ref_o) and torch.equal(state, ref_s)): bad += 1
print(json.dumps({"op": "fused_recurrent_packed_decode_b1", "bad": bad}))
json.dump({"bad": bad}, open("/tmp/draft_decode_det.json","w"))
