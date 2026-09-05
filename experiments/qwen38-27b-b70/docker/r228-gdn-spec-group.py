# R228: batch-invariant GDN speculative step on XPU. On R224 + VLLM_BATCH_INVARIANT=1 every INT4 GEMM, FP16 linear and
# the attention decode are batch-invariant and the c1-c64 identity ladder is exact for MTP0 at every level, but with
# speculative rows it is exact only through 16 concurrent sequences (R226/R227): the remaining batch-dependent launch is
# the SYCL GDN kernel processing all speculative sequences of a step at once. Run the spec rows in groups of at most
# VLLM_XPU_GDN_SPEC_GROUP sequences (default 16; 0 disables) through the existing gather/scatter split path.
import hashlib
p = "/opt/venv/lib/python3.12/site-packages/vllm/_xpu_ops.py"
s = open(p).read()
old_cond = '''    if os.environ.get("VLLM_XPU_GDN_SPLIT_MIXED", "0") == "1" and (
        (num_prefills > 0 and num_decodes > 0)
        or (num_spec_decodes > 0 and (num_prefills > 0 or num_decodes > 0))
    ):
'''
new_cond = '''    _spec_group = int(os.environ.get("VLLM_XPU_GDN_SPEC_GROUP", "16"))
    _group_spec = (
        _spec_group > 0 and num_spec_decodes > _spec_group
        and spec_sequence_masks is not None and spec_token_indx is not None
    )
    if _group_spec or (os.environ.get("VLLM_XPU_GDN_SPLIT_MIXED", "0") == "1" and (
        (num_prefills > 0 and num_decodes > 0)
        or (num_spec_decodes > 0 and (num_prefills > 0 or num_decodes > 0))
    )):
'''
assert s.count(old_cond) == 1, "cond anchor"
s = s.replace(old_cond, new_cond)
old_spec = '''        if spec_token_indx is not None and spec_token_indx.numel() > 0:
            st = spec_token_indx.long()
            n_sp = st.numel()
            out_s = torch.zeros((n_sp,) + tuple(core_attn_out.shape[1:]), dtype=core_attn_out.dtype, device=dev)
            z_s = torch.empty_like(out_s)
            _kernel(out_s, z_s, projected_states_qkvz[st].contiguous(),
                    projected_states_ba[st].contiguous(), 0, 0, num_spec_decodes, None,
                    None, torch.empty(0, dtype=torch.int32, device=dev), None,
                    spec_query_start_loc, torch.arange(n_sp, dtype=torch.int32, device=dev),
                    spec_state_indices_tensor, num_accepted_tokens, n_sp)
            core_attn_out[st] = out_s
            z[st] = z_s
'''
new_spec = '''        if spec_token_indx is not None and spec_token_indx.numel() > 0:
            st = spec_token_indx.long()
            n_sp = st.numel()
            sp_qs_cpu = spec_query_start_loc[: num_spec_decodes + 1].to("cpu", non_blocking=False).tolist()
            group = _spec_group if _spec_group > 0 else num_spec_decodes
            if group != _spec_group:
                logger.warning_once("R228 GDN spec grouping inactive (group %d)", group)
            else:
                logger.warning_once("R228 GDN spec rows grouped by %d sequences", group)
            for s0 in range(0, num_spec_decodes, group):
                s1 = min(s0 + group, num_spec_decodes)
                t0, t1 = int(sp_qs_cpu[s0]), int(sp_qs_cpu[s1])
                rows = st[t0:t1]
                n_g = t1 - t0
                out_s = torch.zeros((n_g,) + tuple(core_attn_out.shape[1:]), dtype=core_attn_out.dtype, device=dev)
                z_s = torch.empty_like(out_s)
                qs_g = (spec_query_start_loc[s0:s1 + 1] - t0).to(torch.int32).contiguous()
                acc_g = num_accepted_tokens[s0:s1].contiguous() if num_accepted_tokens is not None else None
                _kernel(out_s, z_s, projected_states_qkvz[rows].contiguous(),
                        projected_states_ba[rows].contiguous(), 0, 0, s1 - s0, None,
                        None, torch.empty(0, dtype=torch.int32, device=dev), None,
                        qs_g, torch.arange(n_g, dtype=torch.int32, device=dev),
                        spec_state_indices_tensor[s0:s1].contiguous(), acc_g, n_g)
                core_attn_out[rows] = out_s
                z[rows] = z_s
'''
assert s.count(old_spec) == 1, "spec anchor"
s = s.replace(old_spec, new_spec)
open(p, "w").write(s)
print("R228 GDN spec grouping inserted; _xpu_ops.py sha256", hashlib.sha256(s.encode()).hexdigest())
