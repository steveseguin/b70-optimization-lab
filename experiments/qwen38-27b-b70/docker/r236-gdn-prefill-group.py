# R236: on top of R228, launch GDN *prefill* sequences in groups of at most VLLM_XPU_GDN_PREFILL_GROUP sequences
# (default 1 = one launch per prompt). R233 showed an MTP0 c64 miss that R232 did not have with an identical decode
# configuration: the ladder's arrival timing changes how prompt prefills share GDN launches, and the SYCL GDN kernel's
# per-sequence arithmetic depends on how many sequences share a launch (R229 vs R233). Pure-decode launches are untouched.
import hashlib
p = "/opt/venv/lib/python3.12/site-packages/vllm/_xpu_ops.py"
s = open(p).read()
old_cond = '''    if _group_spec or (os.environ.get("VLLM_XPU_GDN_SPLIT_MIXED", "0") == "1" and (
        (num_prefills > 0 and num_decodes > 0)
        or (num_spec_decodes > 0 and (num_prefills > 0 or num_decodes > 0))
    )):
'''
new_cond = '''    _prefill_group = int(os.environ.get("VLLM_XPU_GDN_PREFILL_GROUP", "1"))
    _group_prefill = _prefill_group > 0 and num_prefills > _prefill_group
    if _group_spec or _group_prefill or (os.environ.get("VLLM_XPU_GDN_SPLIT_MIXED", "0") == "1" and (
        (num_prefills > 0 and num_decodes > 0)
        or (num_spec_decodes > 0 and (num_prefills > 0 or num_decodes > 0))
    )):
'''
assert s.count(old_cond) == 1, "cond anchor"
s = s.replace(old_cond, new_cond)
# (a) decode-first contiguous layout branch (no spec rows): prefill part is one launch -> group it
old_a = '''            _kernel(core_attn_out[d:n], z[d:n],
                    projected_states_qkvz[d:n], projected_states_ba[d:n],
                    num_prefills, 0, 0, has_initial_state[d:],
                    (non_spec_query_start_loc[d:] - d).to(torch.int32).contiguous(),
                    None, non_spec_state_indices_tensor[d:].contiguous(),
                    None, None, None, None, n - d)
            return
'''
new_a = '''            pq = non_spec_query_start_loc[d:]  # prefill query starts, absolute token offsets
            pq_cpu = pq.to("cpu").tolist()
            pg = _prefill_group if _prefill_group > 0 else num_prefills
            for p0 in range(0, num_prefills, pg):
                p1 = min(p0 + pg, num_prefills)
                t0, t1 = int(pq_cpu[p0]), int(pq_cpu[p1])
                _kernel(core_attn_out[t0:t1], z[t0:t1],
                        projected_states_qkvz[t0:t1], projected_states_ba[t0:t1],
                        p1 - p0, 0, 0, has_initial_state[d + p0:d + p1].contiguous(),
                        (pq[p0:p1 + 1] - t0).to(torch.int32).contiguous(),
                        None, non_spec_state_indices_tensor[d + p0:d + p1].contiguous(),
                        None, None, None, None, t1 - t0)
            return
'''
assert s.count(old_a) == 1, "branch a anchor"
s = s.replace(old_a, new_a)
# (b) spec-present branch: non-spec sequences are gathered by class (decode / prefill); group the prefill class
old_b = '''            for is_dec in (True, False):
                sel = seq_ids[dec_mask] if is_dec else seq_ids[~dec_mask]
                if sel.numel() == 0:
                    continue
'''
new_b = '''            _pg = _prefill_group if _prefill_group > 0 else 10**9
            _classes = [(True, seq_ids[dec_mask])]
            _pre = seq_ids[~dec_mask]
            for _g0 in range(0, int(_pre.numel()), _pg):
                _classes.append((False, _pre[_g0:_g0 + _pg]))
            for is_dec, sel in _classes:
                if sel.numel() == 0:
                    continue
'''
assert s.count(old_b) == 1, "branch b anchor"
s = s.replace(old_b, new_b)
open(p, "w").write(s)
print("R236 GDN prefill grouping inserted; _xpu_ops.py sha256", hashlib.sha256(s.encode()).hexdigest())
