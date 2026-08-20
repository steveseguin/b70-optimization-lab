import json, torch
import vllm_xpu_kernels._xpu_C  # noqa
DEV="xpu:0"
torch.manual_seed(20260826)
NS, CACHE, SPEC, CONVD = 64, 32, 6, 512   # slots, spec cache len, max spec, conv dim
out=[]

# ---- commit_pending ----
conv_state = torch.randn(NS, CONVD, 3, dtype=torch.float16, device=DEV)
conv_pending = torch.randn(NS, SPEC, CONVD, dtype=torch.float16, device=DEV)
write_pos0 = torch.randint(0, CACHE, (NS,), dtype=torch.int32, device=DEV)
cache_base0 = torch.zeros(NS, dtype=torch.int32, device=DEV)
is_flush0 = torch.ones(NS, dtype=torch.int8, device=DEV)
pending0 = torch.ones(NS, dtype=torch.int8, device=DEV)
pending_len0 = torch.randint(0, SPEC+1, (NS,), dtype=torch.int32, device=DEV)
accepted = torch.randint(0, SPEC+1, (8,), dtype=torch.int32, device=DEV)
indices = torch.randperm(NS-1, device=DEV)[:8].to(torch.int64) + 1

BOOK = (write_pos0, cache_base0, is_flush0, pending0, pending_len0)
snaps = (conv_state.clone(), conv_pending.clone()) + tuple(t.clone() for t in BOOK)
def run_commit():
    torch.ops._xpu_C.gdn_replayssm_commit_pending(
        conv_state, write_pos0, cache_base0, is_flush0, pending0, pending_len0,
        conv_pending, accepted, indices, CACHE, SPEC, 3, 0)
ALL7 = (conv_state, conv_pending) + BOOK
bad = 0
for rep in range(4000):
    for t, s2 in zip(ALL7, snaps): t.copy_(s2)
    run_commit(); torch.xpu.synchronize()
    r = tuple(t.clone() for t in ALL7)
    for t, s2 in zip(ALL7, snaps): t.copy_(s2)
    run_commit(); torch.xpu.synchronize()
    if not all(torch.equal(a, b) for a, b in zip(r, ALL7)):
        bad += 1
        which = [i for i, (a, b) in enumerate(zip(r, ALL7)) if not torch.equal(a, b)]
        det = {"tensor_idx": which}
        if 0 in which:
            mask = (r[0] != conv_state)          # [NS, CONVD, 3]
            per_slot = mask.any(dim=2).any(dim=1) # [NS]
            slots_hit = per_slot.nonzero().flatten().tolist()
            det["slots"] = slots_hit
            det["accepted"] = accepted.tolist()
            det["indices"] = indices.tolist()
            det["elems_per_hit_slot"] = [int(mask[sl].sum()) for sl in slots_hit]
            det["write_pos"] = write_pos0.tolist()
            det["pending_len"] = pending_len0.tolist()
            det["max_abs"] = float((r[0].float()-conv_state.float()).abs().max())
        print(json.dumps({"mismatch_detail": det}), flush=True)
out.append({"op": "replayssm_commit_pending", "bad": bad}); print(json.dumps(out[-1]), flush=True)

# ---- reset_slots ----
wp = torch.randint(0, CACHE, (NS,), dtype=torch.int32, device=DEV)
cb = torch.randint(0, CACHE, (NS,), dtype=torch.int32, device=DEV)
fl = torch.ones(NS, dtype=torch.int8, device=DEV)
pd = torch.ones(NS, dtype=torch.int8, device=DEV)
pl = torch.randint(0, SPEC+1, (NS,), dtype=torch.int32, device=DEV)
slots = torch.randint(1, NS, (16,), dtype=torch.long, device=DEV)
sn = (wp.clone(), cb.clone(), fl.clone(), pd.clone(), pl.clone())
def run_reset():
    torch.ops._xpu_C.gdn_replayssm_reset_slots(wp, cb, fl, pd, pl, slots, 1, 0)
bad = 0
for rep in range(200):
    for t, s in zip((wp, cb, fl, pd, pl), sn): t.copy_(s)
    run_reset(); torch.xpu.synchronize()
    r = tuple(t.clone() for t in (wp, cb, fl, pd, pl))
    for t, s in zip((wp, cb, fl, pd, pl), sn): t.copy_(s)
    run_reset(); torch.xpu.synchronize()
    if not all(torch.equal(a, b) for a, b in zip(r, (wp, cb, fl, pd, pl))): bad += 1
out.append({"op": "replayssm_reset_slots", "bad": bad}); print(json.dumps(out[-1]), flush=True)

# ---- copy_slots (single pair, production-valid) ----
HV, H, K, V = 24, 8, 128, 128
d_c = torch.randn(NS, HV, CACHE, V, dtype=torch.float32, device=DEV)
k_c = torch.randn(NS, H, CACHE, K, dtype=torch.float32, device=DEV)
g_c = torch.randn(NS, HV, CACHE, dtype=torch.float32, device=DEV)
cp = torch.randn(NS, SPEC, CONVD, dtype=torch.float32, device=DEV)
wp2 = torch.randint(0, CACHE, (NS,), dtype=torch.int32, device=DEV)
cb2 = torch.zeros(NS, dtype=torch.int32, device=DEV)
fl2 = torch.ones(NS, dtype=torch.int8, device=DEV)
pd2 = torch.ones(NS, dtype=torch.int8, device=DEV)
pl2 = torch.randint(0, SPEC+1, (NS,), dtype=torch.int32, device=DEV)
src = torch.tensor([5], dtype=torch.long, device=DEV)
dst = torch.tensor([9], dtype=torch.long, device=DEV)
ALL = (d_c, k_c, g_c, wp2, cb2, fl2, pd2, pl2, cp)
sn = tuple(t.clone() for t in ALL)
def run_copy():
    torch.ops._xpu_C.gdn_replayssm_copy_slots(d_c, k_c, g_c, wp2, cb2, fl2, pd2, pl2, cp, src, dst, 0)
bad = 0
for rep in range(200):
    for t, s2 in zip(ALL, sn): t.copy_(s2)
    run_copy(); torch.xpu.synchronize()
    r = tuple(t.clone() for t in ALL)
    for t, s2 in zip(ALL, sn): t.copy_(s2)
    run_copy(); torch.xpu.synchronize()
    if not all(torch.equal(a, b) for a, b in zip(r, ALL)): bad += 1
out.append({"op": "replayssm_copy_slots", "bad": bad}); print(json.dumps(out[-1]), flush=True)
json.dump(out, open("/tmp/replayssm_det.json","w"))
