import json, torch
import vllm_xpu_kernels._xpu_C  # noqa
DEV="xpu:0"
torch.manual_seed(20260827)
NS, CACHE, SPEC, CONVD, BASE = 64, 32, 6, 512, 3

def torch_ref(conv_state, conv_pending, write_pos, cache_base, is_flush,
              pending, pending_len, accepted_all, indices, max_cache_len,
              max_spec_len, conv_base_len):
    slots = indices.to(torch.long)
    valid = (slots > 0) & (slots < NS)
    slots = slots[valid]
    active = pending.index_select(0, slots) != 0
    slots = slots[active]
    if slots.numel() == 0:
        return
    accepted = accepted_all.to(torch.long)[valid][active]
    prev_len = pending_len.index_select(0, slots).to(torch.long)
    accepted = torch.clamp(accepted, min=0)
    accepted = torch.minimum(accepted, prev_len)
    if conv_base_len > 0 and slots.numel():
        old_conv = conv_state.index_select(0, slots)[:, :, :conv_base_len]
        raw = conv_pending.index_select(0, slots)
        history = torch.cat((old_conv.transpose(1, 2).contiguous(), raw), dim=1)
        offsets = torch.arange(conv_base_len, device=slots.device)
        window = accepted.unsqueeze(1) + offsets.unsqueeze(0)
        new_conv = history.gather(1, window.unsqueeze(-1).expand(-1, -1, history.size(-1)))
        conv_state.index_copy_(0, slots, torch.cat(
            (new_conv.transpose(1, 2).to(conv_state.dtype),
             conv_state.index_select(0, slots)[:, :, conv_base_len:]), dim=2))
    old_wp = write_pos.index_select(0, slots).to(torch.long)
    old_base = cache_base.index_select(0, slots).to(torch.long)
    old_flush = is_flush.index_select(0, slots) != 0
    flush_now = (accepted > 0) & old_flush
    new_base = torch.where(flush_now, (old_base + old_wp) % max_cache_len, old_base)
    new_wp = torch.where(old_flush, accepted, old_wp + accepted)
    next_flush = (new_wp + 2 * max_spec_len) > max_cache_len
    write_pos.index_copy_(0, slots, new_wp.to(write_pos.dtype))
    cache_base.index_copy_(0, slots, new_base.to(cache_base.dtype))
    is_flush.index_copy_(0, slots, next_flush.to(is_flush.dtype))
    pending.index_fill_(0, slots, 0)

mism = 0
for trial in range(60):
    conv_state = torch.randn(NS, CONVD, BASE, dtype=torch.float16, device=DEV)
    conv_pending = torch.randn(NS, SPEC, CONVD, dtype=torch.float16, device=DEV)
    write_pos = torch.randint(0, CACHE, (NS,), dtype=torch.int32, device=DEV)
    cache_base = torch.randint(0, CACHE, (NS,), dtype=torch.int32, device=DEV)
    is_flush = torch.randint(0, 2, (NS,), dtype=torch.int8, device=DEV)
    pending = torch.randint(0, 2, (NS,), dtype=torch.int8, device=DEV)
    pending_len = torch.randint(0, SPEC+1, (NS,), dtype=torch.int32, device=DEV)
    accepted = torch.randint(-1, SPEC+2, (8,), dtype=torch.int32, device=DEV)
    indices = torch.randperm(NS-1, device=DEV)[:8].to(torch.int64) + 1
    names = ["conv_state","conv_pending","write_pos","cache_base","is_flush","pending","pending_len"]
    snap = [t.clone() for t in (conv_state, conv_pending, write_pos, cache_base, is_flush, pending, pending_len)]
    torch.ops._xpu_C.gdn_replayssm_commit_pending(
        conv_state, write_pos, cache_base, is_flush, pending, pending_len,
        conv_pending, accepted, indices, CACHE, SPEC, BASE, 0)
    torch.xpu.synchronize()
    op_out = [t.clone() for t in (conv_state, conv_pending, write_pos, cache_base, is_flush, pending, pending_len)]
    # reference on identical inputs
    conv_state.copy_(snap[0]); conv_pending.copy_(snap[1]); write_pos.copy_(snap[2])
    cache_base.copy_(snap[3]); is_flush.copy_(snap[4]); pending.copy_(snap[5]); pending_len.copy_(snap[6])
    torch_ref(conv_state, conv_pending, write_pos, cache_base, is_flush, pending, pending_len,
              accepted, indices, CACHE, SPEC, BASE)
    torch.xpu.synchronize()
    ref_out = (conv_state, conv_pending, write_pos, cache_base, is_flush, pending, pending_len)
    bad = [names[i] for i, (a, b) in enumerate(zip(op_out, ref_out)) if not torch.equal(a, b)]
    if bad:
        mism += 1
        print(json.dumps({"trial": trial, "mismatch": bad}), flush=True)
print(json.dumps({"trials": 60, "mismatched": mism}))
json.dump({"trials": 60, "mismatched": mism}, open("/tmp/commit_equiv.json","w"))
